"""定时清理临时下载文件，避免磁盘占满。"""

import asyncio
import logging
import os
import time

from .downloader import DOWNLOADS_DIR

logger = logging.getLogger("uvicorn.error")

FILE_MAX_AGE_SECONDS = 600  # 10 分钟
CLEANUP_INTERVAL_SECONDS = 120  # 每 2 分钟扫描一次


async def cleanup_loop() -> None:
    """后台协程，周期性删除过期临时文件。"""
    while True:
        try:
            now = time.time()
            removed = 0
            for p in DOWNLOADS_DIR.iterdir():
                if not p.is_file():
                    continue
                if now - p.stat().st_mtime > FILE_MAX_AGE_SECONDS:
                    try:
                        p.unlink()
                        removed += 1
                    except OSError:
                        pass
            if removed:
                logger.info("清理临时文件: 删除 %d 个", removed)
        except Exception:
            logger.exception("清理临时文件异常")
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
