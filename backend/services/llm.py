# -*- coding: utf-8 -*-
"""LLM 服务：OpenAI 兼容接口（默认阿里云百炼 DashScope Qwen）。"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger("uvicorn.error")

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-plus"
CHUNK_CHARS = 5000
LLM_TIMEOUT = 90.0

LANG_NAMES = {
    "zh": "简体中文",
    "en": "English（英文）",
    "ja": "日本語（日文）",
}


class LLMError(Exception):
    """LLM 调用预期内错误。"""


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def get_config() -> dict[str, str]:
    return {
        "base_url": _env("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "api_key": _env("LLM_API_KEY"),
        "model": _env("LLM_MODEL", DEFAULT_MODEL),
    }


def ensure_configured() -> None:
    cfg = get_config()
    if not cfg["api_key"]:
        raise LLMError("未配置 LLM_API_KEY，请在 backend/.env 中设置后重启后端")


def chat(
    messages: list[dict[str, str]],
    temperature: float = 0.4,
    max_tokens: int = 2000,
) -> str:
    """调用 chat/completions，返回纯文本内容。"""
    cfg = get_config()
    if not cfg["api_key"]:
        raise LLMError("未配置 LLM_API_KEY，请在 backend/.env 中设置后重启后端")

    url = f"{cfg['base_url']}/chat/completions"
    payload: dict[str, Any] = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=LLM_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise LLMError(f"AI 接口网络错误: {exc}")
    if resp.status_code != 200:
        raise LLMError(f"AI 接口调用失败 (HTTP {resp.status_code}): {resp.text[:300]}")
    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise LLMError(f"AI 接口返回格式异常: {exc}")
    return (content or "").strip()


def _chunk_text(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[。！？.!?；;])\s*", text)
    chunks: list[str] = []
    current = ""
    for s in sentences:
        if current and len(current) + len(s) + 1 > max_chars:
            chunks.append(current.strip())
            current = s
        else:
            current = (current + " " + s).strip() if current else s
    if current.strip():
        chunks.append(current.strip())
    return chunks


def summarize(text: str) -> str:
    """基于字幕生成中文总结（超长自动分块，先分块总结再合并）。"""
    ensure_configured()
    chunks = _chunk_text(text)
    if not chunks:
        raise LLMError("字幕内容为空")

    if len(chunks) == 1:
        return chat(
            [
                {
                    "role": "system",
                    "content": (
                        "你是一个专业的视频内容总结助手。请用中文输出视频总结，"
                        "结构为：第一行一句话概括，然后列出 3-8 个要点（编号列表）。"
                        "只输出总结内容本身，不要任何额外说明。"
                    ),
                },
                {"role": "user", "content": f"以下是视频字幕文本：\n\n{chunks[0]}"},
            ],
            temperature=0.4,
            max_tokens=2000,
        )

    partials = []
    for i, chunk in enumerate(chunks, 1):
        partial = chat(
            [
                {
                    "role": "system",
                    "content": "你是视频总结助手。用中文输出该字幕片段的要点（编号列表，简洁，不超过 6 条）。",
                },
                {"role": "user", "content": f"字幕片段 {i}/{len(chunks)}：\n\n{chunk}"},
            ],
            temperature=0.4,
            max_tokens=1200,
        )
        partials.append(partial)

    merged = "\n\n".join(f"片段{i}：\n{p}" for i, p in enumerate(partials, 1))
    return chat(
        [
            {
                "role": "system",
                "content": (
                    "你是视频总结助手。请基于各片段要点，用中文输出整个视频的总结："
                    "第一行一句话概括，然后列出 3-8 个要点（编号列表）。只输出总结。"
                ),
            },
            {"role": "user", "content": f"各片段要点：\n\n{merged}"},
        ],
        temperature=0.4,
        max_tokens=2000,
    )


def translate(text: str, target_lang: str) -> str:
    """按「编号. 文本」行协议逐块翻译字幕，返回同样格式的译文。"""
    ensure_configured()
    chunks = _chunk_text(text)
    if not chunks:
        raise LLMError("字幕内容为空")
    lang_name = LANG_NAMES.get(target_lang, target_lang)

    results = []
    for i, chunk in enumerate(chunks, 1):
        out = chat(
            [
                {
                    "role": "system",
                    "content": (
                        f"你是字幕翻译引擎。将用户提供的带编号字幕逐条翻译为{lang_name}。"
                        "必须保持每行开头的编号不变，每行一条译文，不要合并或拆分行，不要任何解释。"
                    ),
                },
                {"role": "user", "content": chunk},
            ],
            temperature=0.2,
            max_tokens=4000,
        )
        results.append(out)
    return "\n".join(results)