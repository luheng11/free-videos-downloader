"""yt-dlp 封装服务：解析视频信息、代理下载、获取直链。

直接调用 yt-dlp 的 Python API，不二次封装源码，最小改动。
"""

import logging
import uuid
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

from .douyin import (
    download_douyin,
    get_douyin_play_url,
    is_douyin_url,
    parse_douyin,
)

logger = logging.getLogger("uvicorn.error")

DOWNLOADS_DIR = Path(__file__).resolve().parent.parent / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _default_parse_opts() -> dict[str, Any]:
    return {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "noplaylist": True,
    }


def _build_resolution(f: dict[str, Any]) -> str:
    w, h = f.get("width"), f.get("height")
    if w and h:
        return f"{w}x{h}"
    if h:
        return f"{h}p"
    return f.get("format_note") or "audio"


def parse_video(url: str) -> dict[str, Any]:
    """解析视频元数据（不下载），返回前端需要的精简字段。"""
    # 抖音专用模块（无需 cookie）
    if is_douyin_url(url):
        return parse_douyin(url)
    with YoutubeDL(_default_parse_opts()) as ydl:
        info = ydl.extract_info(url, download=False)
        info = ydl.sanitize_info(info)

    formats = []
    for f in info.get("formats", []):
        vcodec = f.get("vcodec")
        acodec = f.get("acodec")
        # 跳过既无视频也无音频的条目
        if vcodec in (None, "none") and acodec in (None, "none"):
            continue
        formats.append(
            {
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "resolution": f.get("resolution") or _build_resolution(f),
                "fps": f.get("fps"),
                "vcodec": vcodec,
                "acodec": acodec,
                "filesize": f.get("filesize") or f.get("filesize_approx"),
                "url": f.get("url"),
                "tbr": f.get("tbr"),
            }
        )

    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "uploader": info.get("uploader") or info.get("channel"),
        "uploader_url": info.get("uploader_url"),
        "webpage_url": info.get("webpage_url"),
        "extractor": info.get("extractor"),
        "extractor_key": info.get("extractor_key"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "description": (info.get("description") or "")[:500],
        "formats": formats,
        "best_format_id": info.get("format_id"),
        "subtitles": list((info.get("subtitles") or {}).keys()),
        "automatic_captions": list((info.get("automatic_captions") or {}).keys()),
    }


def get_direct_url(url: str, format_id: str | None = None) -> str | None:
    """获取视频直链（不下载），供智能下载策略判断使用。"""
    # 抖音直接返回无水印播放链
    if is_douyin_url(url):
        return get_douyin_play_url(url)
    opts = _default_parse_opts()
    if format_id:
        opts["format"] = format_id
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            info = ydl.sanitize_info(info)
    except Exception as exc:
        logger.warning("获取直链失败: %s", exc)
        return None

    requested = info.get("requested_formats") or []
    if requested:
        return requested[0].get("url")
    return info.get("url")


def download_video(url: str, format_id: str | None, task_id: str) -> str:
    """服务器代理下载到本地临时目录，返回文件路径。"""
    # 抖音专用模块（服务端代理下载）
    if is_douyin_url(url):
        return download_douyin(url, task_id)
    out_path = DOWNLOADS_DIR / f"{task_id}.%(ext)s"
    opts: dict[str, Any] = {
        "format": format_id or "best",
        "outtmpl": str(out_path),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with YoutubeDL(opts) as ydl:
        ydl.download([url])

    # 找到实际生成的文件
    for p in DOWNLOADS_DIR.glob(f"{task_id}.*"):
        if p.is_file():
            return str(p)
    raise FileNotFoundError(f"下载完成但未找到文件: task_id={task_id}")


def new_task_id() -> str:
    return uuid.uuid4().hex[:16]
