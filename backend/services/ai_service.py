# -*- coding: utf-8 -*-
"""AI 编排服务：取字幕 -> 调 LLM；无字幕时降级语音转写，提供视频总结与字幕翻译。

语音转写结果按视频链接缓存（TTL 7 天），避免重复下载/转写；失败自动重试一次。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from .douyin import download_douyin, is_douyin_url, parse_douyin
from .llm import LLMError, summarize as llm_summarize, translate as llm_translate
from .speech import SpeechError, transcribe_video_file
from .subtitles import SubtitleError, SubtitleResult, fetch_subtitles

logger = logging.getLogger("uvicorn.error")

DOWNLOADS_DIR = Path(__file__).resolve().parent.parent / "downloads"
STT_CACHE_DIR = DOWNLOADS_DIR / "stt_cache"
STT_CACHE_TTL = 7 * 24 * 3600  # 7 天
_TRANSCRIBE_ATTEMPTS = 2


class AIServiceError(Exception):
    """AI 服务预期内错误。"""


def summarize_video(url: str) -> dict[str, Any]:
    """视频总结：取字幕（无字幕则语音转写）-> LLM 生成中文总结。"""
    try:
        subs = _fetch_subtitles_with_fallback(url)
        summary = llm_summarize(subs.text)
    except SubtitleError as exc:
        raise AIServiceError(str(exc))
    except LLMError as exc:
        raise AIServiceError(str(exc))
    except Exception as exc:
        logger.exception("视频总结失败")
        raise AIServiceError(f"视频总结失败: {exc}")
    return {
        "title": subs.title,
        "summary": summary,
        "subtitle_lang": subs.lang,
    }


def translate_video(url: str, target_lang: str) -> dict[str, Any]:
    """字幕翻译：取字幕（无字幕则语音转写）-> LLM 逐条翻译，保留时间轴。"""
    try:
        subs = _fetch_subtitles_with_fallback(url)
    except SubtitleError as exc:
        raise AIServiceError(str(exc))
    except Exception as exc:
        logger.exception("字幕获取失败")
        raise AIServiceError(f"字幕获取失败: {exc}")

    numbered = "\n".join(f"{i}. {seg['text']}" for i, seg in enumerate(subs.segments, 1))
    try:
        translated = llm_translate(numbered, target_lang)
    except LLMError as exc:
        raise AIServiceError(str(exc))
    except Exception as exc:
        logger.exception("字幕翻译失败")
        raise AIServiceError(f"字幕翻译失败: {exc}")

    segments = _merge_translation(subs.segments, translated)
    return {
        "title": subs.title,
        "target_lang": target_lang,
        "segments": segments,
    }


def _fetch_subtitles_with_fallback(url: str) -> SubtitleResult:
    """字幕优先；失败时降级为语音转写（抖音等无字幕视频）。"""
    try:
        return fetch_subtitles(url)
    except SubtitleError as exc:
        try:
            return _transcribe_fallback(url)
        except SubtitleError as fb_exc:
            raise SubtitleError(f"{exc}；语音转写：{fb_exc}")


def _transcribe_fallback(url: str) -> SubtitleResult:
    """下载视频 -> 提取音频 -> DashScope ASR，返回转写字幕。

    带缓存（7 天）与一次自动重试；失败时抛出 SubtitleError 并附具体原因。
    """
    cached = _load_stt_cache(url)
    if cached:
        logger.info("命中语音转写缓存: %s", url[:60])
        return cached

    last_exc: Exception | None = None
    for attempt in range(_TRANSCRIBE_ATTEMPTS):
        task_id = uuid.uuid4().hex[:16]
        video_path = None
        title = None
        try:
            if is_douyin_url(url):
                info = parse_douyin(url)
                title = info.get("title")
                video_path = download_douyin(url, task_id)
            else:
                video_path, title = _download_audio_generic(url, task_id)
            result = transcribe_video_file(video_path)
            segments = result.get("segments") or []
            if not segments:
                raise SubtitleError("语音转写未识别到有效语音内容")
            stt = SubtitleResult(lang="语音转写", segments=segments, title=title)
            _save_stt_cache(url, stt)
            return stt
        except SubtitleError:
            raise
        except Exception as exc:
            last_exc = exc
            logger.info("语音转写兜底第 %s/%s 次失败: %s", attempt + 1, _TRANSCRIBE_ATTEMPTS, exc)
            if attempt + 1 < _TRANSCRIBE_ATTEMPTS:
                time.sleep(1.0)
        finally:
            if video_path and os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except OSError:
                    pass

    raise SubtitleError(f"语音转写失败：{last_exc}")


# ---------- 语音转写磁盘缓存 ----------


def _normalize_cache_url(url: str) -> str:
    """去掉分享文案，只保留第一个 URL，使同一链接的不同粘贴文本命中同一缓存。"""
    url = (url or "").strip()
    m = re.search(r"https?://[^\s]+", url, re.IGNORECASE)
    if m:
        url = m.group(0).strip()
        url = url.strip('"').strip("'").rstrip(").,;!?")
    return url


def _stt_cache_path(url: str) -> Path:
    digest = hashlib.sha256(_normalize_cache_url(url).encode("utf-8")).hexdigest()[:32]
    return STT_CACHE_DIR / f"{digest}.json"


def _load_stt_cache(url: str) -> SubtitleResult | None:
    try:
        path = _stt_cache_path(url)
        if not path.exists():
            return None
        data = json.loads(path.read_text("utf-8"))
        if time.time() - float(data.get("cached_at") or 0) > STT_CACHE_TTL:
            path.unlink(missing_ok=True)
            return None
        segments = data.get("segments") or []
        if not segments:
            return None
        return SubtitleResult(
            lang=data.get("lang") or "语音转写",
            segments=segments,
            title=data.get("title"),
        )
    except Exception as exc:
        logger.info("读取语音转写缓存失败: %s", exc)
        return None


def _save_stt_cache(url: str, result: SubtitleResult) -> None:
    try:
        STT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "cached_at": time.time(),
            "lang": result.lang,
            "title": result.title,
            "segments": result.segments,
        }
        _stt_cache_path(url).write_text(
            json.dumps(payload, ensure_ascii=False), "utf-8"
        )
    except Exception as exc:
        logger.info("写入语音转写缓存失败: %s", exc)


# ---------- 通用下载（非抖音） ----------


def _download_audio_generic(url: str, task_id: str) -> tuple[str, str | None]:
    """非抖音平台：用 yt-dlp 下载最佳音频到临时目录，返回 (文件路径, 视频标题)。"""
    from yt_dlp import YoutubeDL

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    outtmpl = str(DOWNLOADS_DIR / f"{task_id}.%(ext)s")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    title = None
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get("title")
        ydl.download([url])
    for p in DOWNLOADS_DIR.glob(f"{task_id}.*"):
        if p.is_file():
            return str(p), title
    raise SpeechError("下载音频失败：未找到输出文件")


def _merge_translation(
    segments: list[dict[str, Any]], translated_text: str
) -> list[dict[str, Any]]:
    """把 LLM 返回的「编号. 译文」行合并回原始时间轴。

    兼容两种输出格式：
      - 内联编号：`1. Hello`
      - 编号独立成行：`1` 换行 `Hello`
    """
    parsed: list[tuple[int | None, str]] = []
    pending_idx: int | None = None
    for line in translated_text.splitlines():
        line = line.strip()
        if not line:
            continue
        m_inline = re.match(r"^(\d+)\s*[.、:：]\s*(.*)$", line)
        m_num = re.match(r"^(\d+)\s*$", line)
        if m_inline:
            parsed.append((int(m_inline.group(1)), m_inline.group(2).strip()))
            pending_idx = None
        elif m_num:
            pending_idx = int(m_num.group(1))
        elif pending_idx is not None:
            parsed.append((pending_idx, line))
            pending_idx = None
        else:
            parsed.append((None, line))

    by_index: dict[int, str] = {}
    ordered: list[str] = []
    for idx, text in parsed:
        if idx is not None and 1 <= idx <= len(segments) and idx not in by_index:
            by_index[idx] = text
        else:
            ordered.append(text)

    result = []
    for i, seg in enumerate(segments, 1):
        new_seg = dict(seg)
        if i in by_index:
            new_seg["text"] = by_index[i]
        elif ordered:
            new_seg["text"] = ordered.pop(0)
        result.append(new_seg)
    return result
