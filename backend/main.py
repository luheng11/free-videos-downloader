"""FastAPI 应用入口，提供视频解析、智能下载、任务查询等 API。"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from services.cleanup import cleanup_loop
from services.download_service import smart_download
from services.downloader import DOWNLOADS_DIR, parse_video
from services.task_queue import task_queue

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：开启后台清理协程
    task = asyncio.create_task(cleanup_loop())
    yield
    # 关闭：取消清理协程
    task.cancel()


app = FastAPI(title="万能视频下载 API", version="1.0.0", lifespan=lifespan)

# CORS：允许前端开发服务器访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件：提供已下载文件的访问
app.mount("/files", StaticFiles(directory=str(DOWNLOADS_DIR)), name="files")


# ---------- 请求模型 ----------


class ParseRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format_id: str | None = None


class TaskSubmitRequest(BaseModel):
    url: str
    format_id: str | None = None


# ---------- 核心接口 ----------


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/parse")
async def api_parse(req: ParseRequest):
    """解析视频元数据（不下载）。"""
    try:
        info = await asyncio.to_thread(parse_video, req.url)
        return {"success": True, "data": info}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"解析失败: {exc}")


@app.post("/api/download")
async def api_download(req: DownloadRequest):
    """智能下载：自动选择直链重定向 / 代理下载 / 流式传输。"""
    try:
        return await smart_download(req.url, req.format_id, f"dl-{id(req)}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"下载失败: {exc}")


@app.post("/api/task")
async def api_submit_task(req: TaskSubmitRequest):
    """提交后台下载任务（用于需要进度跟踪的场景）。"""
    task = await task_queue.submit(req.url, req.format_id)
    return {"success": True, "data": task_queue.to_dict(task)}


@app.get("/api/task/{task_id}")
async def api_get_task(task_id: str):
    """查询任务状态。"""
    task = task_queue.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True, "data": task_queue.to_dict(task)}


@app.get("/api/tasks")
async def api_list_tasks():
    """列出最近的任务。"""
    tasks = task_queue.list_tasks()
    return {"success": True, "data": [task_queue.to_dict(t) for t in tasks]}


@app.get("/api/file/{task_id}")
async def api_get_file(task_id: str):
    """获取已下载文件的下载链接。"""
    task = task_queue.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status.value != "completed":
        raise HTTPException(status_code=400, detail=f"任务未完成，当前状态: {task.status.value}")
    if not task.filename:
        raise HTTPException(status_code=404, detail="文件信息缺失")
    return {"success": True, "data": {"url": f"/files/{task.filename}", "filename": task.filename}}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
