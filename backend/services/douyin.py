"""抖音专用解析/下载模块（不依赖 yt-dlp，无需 cookie / 登录态）。

原理（参考 MIT 开源实现 rathodpratham-dev/douyin_video_downloader）：
  1. 分享短链 -> 302 重定向 -> 提取 video_id
  2. 抓取 https://www.iesdouyin.com/share/video/{video_id}/ 分享页（移动端 UA）
  3. 解析页面内嵌的 window._ROUTER_DATA，拿到视频元数据（该页面无需登录态）
  4. 取 play_addr 直链，把 playwm 替换为 play 得到无水印播放地址

注意：iesdouyin.com/web/api/v2/aweme/iteminfo/ 旧“公开 API”已失效
（返回 status_code=11110 encrypt_data_miss），因此本模块只走分享页解析。
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

logger = logging.getLogger("uvicorn.error")

DOWNLOADS_DIR = Path(__file__).resolve().parent.parent / "downloads"

# ---------- 常量 ----------

UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
    "Mobile/15E148 Safari/604.1"
)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Referer": "https://www.douyin.com/",
}
MOBILE_SHARE_HEADERS = {
    **DEFAULT_HEADERS,
    "User-Agent": UA_MOBILE,
}

_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_QUERY_ID_KEYS = ("modal_id", "item_ids", "group_id", "aweme_id")
_PATH_ID_RE = re.compile(r"/(?:video|note)/(\d{8,24})")
_GENERIC_PATH_ID_RE = re.compile(r"/(\d{8,24})(?:/|$)")
_FALLBACK_ID_RE = re.compile(r"(?<!\d)(\d{8,24})(?!\d)")
_DOUYIN_HOST_RE = re.compile(
    r"v\.douyin\.com|(?:www\.)?douyin\.com/(?:video|note)/|iesdouyin\.com/share/video/",
    re.IGNORECASE,
)

TIMEOUT = 20.0


class DouyinError(Exception):
    """抖音模块预期内错误。"""


# ---------- URL 识别 ----------


def is_douyin_url(url: str) -> bool:
    """判断链接是否为抖音链接（短链 / 视频页 / 分享页）。"""
    return bool(_DOUYIN_HOST_RE.search(url or ""))


def extract_first_url(text: str) -> str:
    """从分享文案中提取第一个 URL。"""
    match = _URL_RE.search(text or "")
    if not match:
        raise DouyinError("未找到有效 URL")
    candidate = match.group(0).strip().strip('"').strip("'")
    return candidate.rstrip(").,;!?")


def resolve_share_url(client: httpx.Client, share_url: str) -> str:
    """跟随分享短链重定向，返回最终页面 URL。"""
    resp = client.get(share_url, timeout=TIMEOUT)
    resp.raise_for_status()
    final = str(resp.url)
    if not final:
        raise DouyinError("分享链接重定向结果为空")
    return final


def extract_video_id(url: str) -> str:
    """从 URL 路径或查询参数中提取视频 ID。"""
    parsed = urlparse(url)
    for key in _QUERY_ID_KEYS:
        values = parse_qs(parsed.query).get(key)
        if values:
            m = re.search(r"(\d{8,24})", values[0])
            if m:
                return m.group(1)
    for pattern in (_PATH_ID_RE, _GENERIC_PATH_ID_RE):
        m = pattern.search(parsed.path)
        if m:
            return m.group(1)
    m = _FALLBACK_ID_RE.search(url)
    if m:
        return m.group(1)
    raise DouyinError("无法从链接中提取视频 ID")


# ---------- 分享页抓取 ----------


def _build_share_page_url(video_id: str, resolved_url: str) -> str:
    parsed = urlparse(resolved_url)
    if parsed.netloc and "iesdouyin.com" in parsed.netloc:
        return resolved_url
    return f"https://www.iesdouyin.com/share/video/{video_id}/"


def _get_share_page_html(client: httpx.Client, share_url: str) -> str:
    resp = client.get(share_url, headers=MOBILE_SHARE_HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    html = resp.text or ""
    # 抖音偶尔先返回 JS WAF 挑战页，解一次再重试
    if _is_waf_challenge_page(html):
        if _solve_and_set_waf_cookie(client, html, share_url):
            resp = client.get(share_url, headers=MOBILE_SHARE_HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            html = resp.text or ""
    return html


def _is_waf_challenge_page(html: str) -> bool:
    return "Please wait..." in html and "wci=" in html and "cs=" in html


def _decode_urlsafe_b64(value: str) -> bytes:
    normalized = value.replace("-", "+").replace("_", "/")
    normalized += "=" * (-len(normalized) % 4)
    return base64.b64decode(normalized)


def _solve_and_set_waf_cookie(client: httpx.Client, html: str, page_url: str) -> bool:
    """求解 WAF 的 SHA-256 工作量证明并写入 cookie。"""
    match = re.search(r'wci="([^"]+)"\s*,\s*cs="([^"]+)"', html)
    if not match:
        return False
    cookie_name, challenge_blob = match.groups()
    try:
        challenge_data = json.loads(_decode_urlsafe_b64(challenge_blob).decode("utf-8"))
        prefix = _decode_urlsafe_b64(challenge_data["v"]["a"])
        expected_digest = _decode_urlsafe_b64(challenge_data["v"]["c"]).hex()
    except (KeyError, ValueError, TypeError):
        return False

    solved_value: int | None = None
    for candidate in range(1_000_001):
        digest = hashlib.sha256(prefix + str(candidate).encode("utf-8")).hexdigest()
        if digest == expected_digest:
            solved_value = candidate
            break
    if solved_value is None:
        return False

    challenge_data["d"] = base64.b64encode(str(solved_value).encode("utf-8")).decode("utf-8")
    cookie_value = base64.b64encode(
        json.dumps(challenge_data, separators=(",", ":")).encode("utf-8")
    ).decode("utf-8")

    domain = urlparse(page_url).hostname or "www.iesdouyin.com"
    client.cookies.set(cookie_name, cookie_value, domain=domain, path="/")
    logger.info("已解出抖音 WAF 挑战，写入 cookie %s", cookie_name)
    return True


# ---------- _ROUTER_DATA 解析 ----------


def _extract_router_data_json(html: str) -> dict:
    marker = "window._ROUTER_DATA = "
    start = html.find(marker)
    if start < 0:
        return {}
    index = start + len(marker)
    while index < len(html) and html[index].isspace():
        index += 1
    if index >= len(html) or html[index] != "{":
        return {}

    depth = 0
    in_string = False
    escaped = False
    for cursor in range(index, len(html)):
        char = html[cursor]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                payload = html[index : cursor + 1]
                try:
                    return json.loads(payload)
                except ValueError:
                    return {}
    return {}


def _extract_item_info(router_data: dict) -> dict:
    loader_data = router_data.get("loaderData", {})
    if not isinstance(loader_data, dict):
        return {}
    for node in loader_data.values():
        if not isinstance(node, dict):
            continue
        video_info_res = node.get("videoInfoRes", {})
        if not isinstance(video_info_res, dict):
            continue
        item_list = video_info_res.get("item_list", [])
        if item_list and isinstance(item_list[0], dict):
            return item_list[0]
    return {}


# ---------- 业务入口 ----------


def _clean_play_url(item_info: dict) -> str:
    play_urls = item_info.get("video", {}).get("play_addr", {}).get("url_list", [])
    if not play_urls:
        raise DouyinError("未找到视频播放地址")
    return play_urls[0].replace("playwm", "play")


def parse_douyin(url: str) -> dict[str, Any]:
    """解析抖音视频元数据，返回与 parse_video 相同结构的字典。"""
    share_url = extract_first_url(url)
    with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=TIMEOUT) as client:
        resolved_url = resolve_share_url(client, share_url)
        video_id = extract_video_id(resolved_url)
        share_page_url = _build_share_page_url(video_id, resolved_url)
        html = _get_share_page_html(client, share_page_url)
        router_data = _extract_router_data_json(html)
        item = _extract_item_info(router_data)

    if not item:
        raise DouyinError("未能解析抖音视频（可能被风控拦截，请稍后重试）")

    play_url = _clean_play_url(item)
    video_meta = item.get("video", {}) or {}
    author = item.get("author") or {}
    stats = item.get("statistics") or {}

    cover = ""
    for key in ("cover", "origin_cover", "dynamic_cover"):
        url_list = video_meta.get(key, {}).get("url_list", [])
        if url_list:
            cover = url_list[0]
            break

    width, height = video_meta.get("width"), video_meta.get("height")
    if width and height:
        resolution = f"{width}x{height}"
    elif height:
        resolution = f"{height}p"
    else:
        resolution = "video"

    duration = video_meta.get("duration")
    if isinstance(duration, (int, float)) and duration > 1000:
        duration = round(duration / 1000.0, 1)  # 毫秒 -> 秒

    sec_uid = author.get("sec_uid")
    desc = item.get("desc") or ""
    video_id = str(item.get("aweme_id") or video_id)

    fmt = {
        "format_id": "best",
        "ext": "mp4",
        "resolution": resolution,
        "fps": None,
        "vcodec": "h264",
        "acodec": "aac",
        "filesize": None,
        "url": play_url,
        "tbr": None,
    }

    return {
        "id": video_id,
        "title": desc or f"douyin_{video_id}",
        "thumbnail": cover,
        "duration": duration,
        "uploader": author.get("nickname"),
        "uploader_url": f"https://www.douyin.com/user/{sec_uid}" if sec_uid else None,
        "webpage_url": resolved_url,
        "extractor": "Douyin",
        "extractor_key": "Douyin",
        "view_count": stats.get("play_count") or stats.get("digg_count"),
        "like_count": stats.get("digg_count"),
        "description": desc[:500],
        "formats": [fmt],
        "best_format_id": "best",
        "subtitles": [],
        "automatic_captions": [],
    }


def get_douyin_play_url(url: str) -> str | None:
    """获取无水印播放直链（供智能下载策略探测 / 302 重定向使用）。"""
    try:
        info = parse_douyin(url)
        return info["formats"][0]["url"]
    except Exception as exc:
        logger.warning("获取抖音直链失败: %s", exc)
        return None


def download_douyin(url: str, task_id: str) -> str:
    """服务端代理下载抖音视频到本地临时目录，返回文件路径。"""
    info = parse_douyin(url)
    play_url = info["formats"][0]["url"]
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    target = DOWNLOADS_DIR / f"{task_id}.mp4"
    with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=60) as client:
        with client.stream("GET", play_url) as resp:
            resp.raise_for_status()
            with target.open("wb") as f:
                for chunk in resp.iter_bytes(256 * 1024):
                    f.write(chunk)
    return str(target)
