"""智能下载策略：根据直链可用性与文件大小自动选择最优路径。

策略：
  1. 直链可用且未过期 -> 302 重定向（不占服务器资源）
  2. 直链不可用/有防盗链 -> 服务端代理下载
  3. 大文件(>500MB) -> 服务端流式传输（避免内存溢出）
"""

import logging
import os
from typing import Iterator

import httpx
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse

from .downloader import download_video, get_direct_url

logger = logging.getLogger("uvicorn.error")

LARGE_FILE_THRESHOLD = 500 * 1024 * 1024  # 500MB
_DIRECT_URL_PROBE_TIMEOUT = 6.0
_STREAM_CHUNK_SIZE = 1024 * 1024  # 1MB


async def is_url_accessible(url: str) -> bool:
    """探测直链是否可访问（HEAD 请求，超时即视为不可用）。"""
    if not url:
        return False
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=_DIRECT_URL_PROBE_TIMEOUT
        ) as client:
            resp = await client.head(url)
            return resp.status_code < 400
    except Exception as exc:
        logger.info("直链探测失败，将回退代理下载: %s", exc)
        return False


async def smart_download(url: str, format_id: str | None, task_id: str):
    """根据策略返回最合适的 Response 对象。"""
    # 1. 尝试直链
    direct_url = get_direct_url(url, format_id)
    if direct_url and await is_url_accessible(direct_url):
        logger.info("任务 %s 使用直链重定向", task_id)
        return RedirectResponse(url=direct_url, status_code=302)

    # 2. 代理下载
    logger.info("任务 %s 直链不可用，回退代理下载", task_id)
    filepath = download_video(url, format_id, task_id)
    file_size = os.path.getsize(filepath)
    filename = os.path.basename(filepath)

    # 3. 大文件流式传输
    if file_size > LARGE_FILE_THRESHOLD:
        logger.info("任务 %s 大文件流式传输: %s bytes", task_id, file_size)
        return StreamingResponse(
            _stream_file(filepath),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # 4. 普通文件直接返回
    return FileResponse(
        filepath,
        media_type="application/octet-stream",
        filename=filename,
    )


def _stream_file(filepath: str) -> Iterator[bytes]:
    """同步文件分块读取生成器，供 StreamingResponse 使用。"""
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(_STREAM_CHUNK_SIZE)
            if not chunk:
                break
            yield chunk
