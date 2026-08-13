# -*- coding: utf-8 -*-
"""视觉理解服务：调用 Qwen-VL（阿里云百炼 DashScope，OpenAI 兼容接口）描述图片。

与 LLM 服务共用 LLM_API_KEY / LLM_BASE_URL；模型名由 VISION_MODEL 配置，
默认 qwen3.8-max（本机已验证可用），可改为 qwen-vl-max 等。
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

import httpx

from .llm import get_config

logger = logging.getLogger("uvicorn.error")

DEFAULT_VISION_MODEL = "qwen3.8-max"
VISION_TIMEOUT = 90.0


class VisionError(Exception):
    """视觉理解预期内错误。"""


def get_vision_model() -> str:
    return (os.getenv("VISION_MODEL") or DEFAULT_VISION_MODEL).strip()


def describe_image(image_bytes: bytes, prompt: str, fmt: str = "jpeg") -> str:
    """调用 Qwen-VL 描述单张图片，返回纯文本描述。"""
    cfg = get_config()
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        raise VisionError("未配置 LLM_API_KEY，请在 backend/.env 中设置后重启后端")
    if not image_bytes:
        raise VisionError("图片内容为空")

    data_uri = "data:image/{};base64,{}".format(
        fmt, base64.b64encode(image_bytes).decode("ascii")
    )
    url = "{}/chat/completions".format(cfg.get("base_url") or "").rstrip("/")
    payload: dict[str, Any] = {
        "model": get_vision_model(),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "stream": False,
        "max_tokens": 1024,
    }
    headers = {
        "Authorization": "Bearer {}".format(api_key),
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=VISION_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise VisionError(f"视觉接口网络错误: {exc}")
    if resp.status_code != 200:
        raise VisionError(f"视觉接口调用失败 (HTTP {resp.status_code}): {resp.text[:300]}")
    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise VisionError(f"视觉接口返回格式异常: {exc}")
    return (content or "").strip()
