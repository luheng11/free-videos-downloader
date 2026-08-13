# -*- coding: utf-8 -*-
"""字幕获取服务：B 站平台字幕 API 优先（WBI 签名），yt-dlp 提取兜底。"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx

from .douyin import is_douyin_url

logger = logging.getLogger("uvicorn.error")

BILI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}

# 首选语言顺序：中文优先，其次英文，最后任意
PREFERRED_LANGS = ("zh-cn", "zh-hans", "zh", "ai-zh", "zh-hant", "en")

_BILI_URL_RE = re.compile(
    r"(?:www\.|m\.)?bilibili\.com/(?:video|list|bangumi)|b23\.tv", re.IGNORECASE
)
_BVID_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
_TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})"
)
_TIME_RE_MMSS = re.compile(
    r"(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2})[.,](\d{1,3})"
)

# B 站 WBI 签名
_MIXIN_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]


class SubtitleError(Exception):
    """字幕获取失败（预期内错误）。"""


@dataclass
class SubtitleResult:
    lang: str
    segments: list[dict[str, Any]]
    title: str | None = None

    @property
    def text(self) -> str:
        return "\n".join(seg["text"] for seg in self.segments)


def is_bilibili_url(url: str) -> bool:
    return bool(_BILI_URL_RE.search(url or ""))


def fetch_subtitles(url: str) -> SubtitleResult:
    """获取视频字幕。B 站优先平台 API，失败/其他平台走 yt-dlp。

    抖音网页不暴露字幕（yt-dlp 亦需登录态），直接抛错，由上层 AI 服务
    降级为语音转写（DashScope ASR）。
    """
    if is_douyin_url(url):
        raise SubtitleError("该视频暂无可用字幕（抖音不提供字幕，将尝试语音转写）")
    if is_bilibili_url(url):
        try:
            result = _fetch_bilibili_subtitles(url)
            if result:
                return result
        except Exception as exc:
            logger.info("B 站字幕 API 不可用，降级 yt-dlp: %s", exc)
        result = _fetch_via_ytdlp(url)
        if result:
            return result
        raise SubtitleError("该视频暂无可用字幕")
    result = _fetch_via_ytdlp(url)
    if result:
        return result
    raise SubtitleError("该视频暂无可用字幕")


# ---------- B 站平台字幕 API（WBI 签名） ----------


def _get_wbi_keys(client: httpx.Client) -> tuple[str, str]:
    resp = client.get("https://api.bilibili.com/x/web-interface/nav")
    resp.raise_for_status()
    data = resp.json().get("data") or {}
    img_url = ((data.get("wbi_img") or {}).get("img_url")) or ""
    sub_url = ((data.get("wbi_img") or {}).get("sub_url")) or ""
    img_key = img_url.rsplit("/", 1)[-1].split(".")[0]
    sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0]
    if not img_key or not sub_key:
        raise SubtitleError("获取 B 站签名密钥失败")
    return img_key, sub_key


def _mixin_key(img_key: str, sub_key: str) -> str:
    raw = img_key + sub_key
    return "".join(raw[i] for i in _MIXIN_TAB)[:32]


def _sign_params(params: dict, mixin: str) -> dict:
    params = dict(params)
    params["wts"] = int(time.time())
    params = dict(sorted(params.items()))
    query = urllib.parse.urlencode(params)
    params["w_rid"] = hashlib.md5((query + mixin).encode()).hexdigest()
    return params


def _fetch_bilibili_subtitles(url: str) -> SubtitleResult | None:
    with httpx.Client(headers=BILI_HEADERS, follow_redirects=True, timeout=20) as client:
        bvid = _extract_bvid(url, client)
        view = _get_json_retry(
            client, "https://api.bilibili.com/x/web-interface/view", {"bvid": bvid}
        )
        data = view.get("data") or {}
        pages = data.get("pages") or []
        if not pages:
            return None
        cid = pages[0]["cid"]
        title = data.get("title")

        img_key, sub_key = _get_wbi_keys(client)
        mixin = _mixin_key(img_key, sub_key)
        player = _get_json_retry(
            client,
            "https://api.bilibili.com/x/player/wbi/v2",
            _sign_params({"bvid": bvid, "cid": cid}, mixin),
        )
        subs = ((player.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
        if not subs:
            return None

        chosen = _pick_subtitle(subs)
        sub_url = chosen.get("subtitle_url") or ""
        if not sub_url:
            return None
        if sub_url.startswith("//"):
            sub_url = "https:" + sub_url
        sj = client.get(sub_url)
        sj.raise_for_status()
        body = (sj.json() or {}).get("body") or []
        segments = _segments_from_bili_body(body)
        if not segments:
            return None
        return SubtitleResult(lang=chosen.get("lan") or "zh-CN", segments=segments, title=title)
    return None


def _get_json_retry(client: httpx.Client, url: str, params: dict, retries: int = 2) -> dict:
    """带重试的 JSON 请求；412/非 JSON 时短等重试。"""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = client.get(url, params=params)
            if resp.status_code == 412:
                raise SubtitleError("B 站接口风控 (412)")
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(2)
    raise SubtitleError(f"B 站接口请求失败: {last_exc}")


def _extract_bvid(url: str, client: httpx.Client) -> str:
    m = _BVID_RE.search(url)
    if m:
        return m.group(1)
    resp = client.get(url)  # 跟随 b23.tv 短链
    m = _BVID_RE.search(str(resp.url))
    if m:
        return m.group(1)
    raise SubtitleError("无法识别 B 站视频 ID")


def _pick_subtitle(subs: list[dict]) -> dict:
    def key(s: dict) -> int:
        lan = (s.get("lan") or "").lower()
        for i, pref in enumerate(PREFERRED_LANGS):
            if lan == pref or lan.startswith(pref):
                return i
        return len(PREFERRED_LANGS)
    return min(subs, key=key)


def _segments_from_bili_body(body: list) -> list[dict[str, Any]]:
    segments = []
    for item in body or []:
        text = (item.get("content") or "").strip()
        if text:
            segments.append(
                {
                    "start": float(item.get("from") or 0),
                    "end": float(item.get("to") or 0),
                    "text": text,
                }
            )
    return segments


# ---------- yt-dlp 兜底 ----------


def _fetch_via_ytdlp(url: str) -> SubtitleResult | None:
    try:
        from yt_dlp import YoutubeDL

        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        logger.info("yt-dlp 提取字幕失败: %s", exc)
        return None

    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    combined = {**auto, **manual}
    if not combined:
        return None

    lang = _pick_lang(list(combined.keys()))
    if not lang:
        return None
    entries = combined.get(lang) or []
    pick = None
    for ext in ("vtt", "srt", "json3", "srv3", "ttml"):
        pick = next((e for e in entries if e.get("ext") == ext), None)
        if pick:
            break
    if pick is None:
        pick = next((e for e in entries if e.get("url")), None)
    if not pick or not pick.get("url"):
        return None

    try:
        content = _download_text(pick["url"])
    except Exception as exc:
        logger.info("下载字幕文件失败: %s", exc)
        return None
    segments = _parse_subtitle_text(content, pick.get("ext"))
    if not segments:
        return None
    return SubtitleResult(lang=lang, segments=segments, title=info.get("title"))


def _pick_lang(langs: list[str]) -> str | None:
    if not langs:
        return None
    lowered = [ln.lower() for ln in langs]
    for pref in PREFERRED_LANGS:
        for i, lan in enumerate(lowered):
            if lan == pref or lan.startswith(pref):
                return langs[i]
    return langs[0]


def _download_text(url: str) -> str:
    with httpx.Client(
        follow_redirects=True,
        timeout=30,
        headers={"User-Agent": BILI_HEADERS["User-Agent"]},
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


# ---------- 字幕解析 ----------


def _parse_subtitle_text(content: str, ext: str | None) -> list[dict[str, Any]]:
    ext = (ext or "").lower()
    if ext == "json3":
        return _parse_json3(content)
    if ext in ("srv3", "json", "vtt", "srt", "ttml", ""):
        try:
            j = json.loads(content)
            if isinstance(j, dict) and isinstance(j.get("body"), list):
                return _segments_from_bili_body(j["body"])
        except Exception:
            pass
        return _parse_srt_vtt(content)
    return []


def _parse_json3(content: str) -> list[dict[str, Any]]:
    try:
        j = json.loads(content)
    except Exception:
        return []
    segments = []
    for ev in j.get("events") or []:
        start = (ev.get("tStartMs") or 0) / 1000.0
        end = ((ev.get("tStartMs") or 0) + (ev.get("dDurationMs") or 0)) / 1000.0
        text = "".join((seg.get("utf8") or "") for seg in (ev.get("segs") or []))
        text = re.sub(r"<[^>]+>", "", text).strip()
        if text:
            segments.append({"start": round(start, 3), "end": round(end, 3), "text": text})
    return segments


def _to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / (10 ** len(ms))


def _parse_srt_vtt(content: str) -> list[dict[str, Any]]:
    segments = []
    text = content.lstrip("\ufeff")
    for block in re.split(r"\n\s*\n", text):
        if "-->" not in block:
            continue
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        timing_line = next((ln for ln in lines if "-->" in ln), None)
        if not timing_line:
            continue
        m = _TIME_RE.search(timing_line) or _TIME_RE_MMSS.search(timing_line)
        if not m:
            continue
        groups = m.groups()
        if len(groups) == 8:
            start = _to_seconds(groups[0], groups[1], groups[2], groups[3])
            end = _to_seconds(groups[4], groups[5], groups[6], groups[7])
        else:
            start = _to_seconds("0", groups[0], groups[1], groups[2])
            end = _to_seconds("0", groups[3], groups[4], groups[5])
        tidx = lines.index(timing_line)
        body_lines = [ln for ln in lines[tidx + 1 :] if ln and not ln.startswith("<c.")]
        seg_text = re.sub(r"<[^>]+>", "", " ".join(body_lines)).strip()
        if seg_text:
            segments.append({"start": round(start, 3), "end": round(end, 3), "text": seg_text})
    return segments