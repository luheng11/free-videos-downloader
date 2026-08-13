# -*- coding: utf-8 -*-
"""语音转写服务：调用阿里云百炼 DashScope Fun-ASR-Flash 将音频转写为字幕。

用于抖音等无字幕视频的 AI 兜底：下载视频 -> ffmpeg 提取音频 -> ASR 转写。
Fun-ASR-Flash 单次上限：base64 音频 10MB / 时长 300 秒，超长音频自动分块。
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import tempfile
from typing import Any

import httpx

from .llm import get_config

logger = logging.getLogger("uvicorn.error")

ASR_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
ASR_MODEL = "fun-asr-flash-2026-06-15"
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # DashScope base64 音频数据上限 10MB
ASR_TIMEOUT = 180.0
FFMPEG_TIMEOUT = 300.0
# Fun-ASR-Flash 单次最长 300s，留余量按 280s 分块
CHUNK_SECONDS = 280
# 16kHz 单声道 16bit wav 每秒字节数
_WAV_BYTES_PER_SEC = 16000 * 2


class SpeechError(Exception):
    """语音转写预期内错误。"""


def get_ffmpeg_exe() -> str:
    """返回可用的 ffmpeg 可执行文件路径（优先 imageio-ffmpeg 内嵌二进制）。"""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise SpeechError(f"未找到 ffmpeg，请先执行 pip install imageio-ffmpeg: {exc}")


def _run_ffmpeg(ffmpeg: str, args: list[str]) -> None:
    proc = subprocess.run([ffmpeg, *args], capture_output=True, timeout=FFMPEG_TIMEOUT)
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", "ignore")[-500:]
        raise SpeechError(f"音频提取失败: {stderr}")


def transcribe_audio(audio_bytes: bytes, fmt: str = "wav") -> dict[str, Any]:
    """调用 Fun-ASR-Flash 转写一段音频（≤10MB / ≤300s），返回 {text, segments}（秒）。"""
    cfg = get_config()
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        raise SpeechError("未配置 LLM_API_KEY，请在 backend/.env 中设置后重启后端")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise SpeechError("音频文件超过 10MB 上限，无法转写")

    data_uri = "data:audio/{};base64,{}".format(fmt, base64.b64encode(audio_bytes).decode("ascii"))
    payload = {
        "model": ASR_MODEL,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": data_uri},
                        }
                    ],
                }
            ]
        },
        "parameters": {"format": fmt, "sample_rate": "16000"},
    }
    headers = {
        "Authorization": "Bearer {}".format(api_key),
        "Content-Type": "application/json",
        "X-DashScope-SSE": "disable",
    }
    try:
        with httpx.Client(timeout=ASR_TIMEOUT) as client:
            resp = client.post(ASR_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise SpeechError(f"语音转写网络错误: {exc}")
    if resp.status_code != 200:
        raise SpeechError(f"语音转写接口调用失败 (HTTP {resp.status_code}): {resp.text[:300]}")
    try:
        data = resp.json()
        output = data.get("output") or {}
        text = (output.get("text") or "").strip()
        sentences = output.get("sentence") or []
    except Exception as exc:
        raise SpeechError(f"语音转写返回格式异常: {exc}")
    if not text and not sentences:
        raise SpeechError("语音转写未识别到有效内容")

    segments = _sentences_to_segments(sentences)
    if not segments and text:
        segments = [{"start": 0.0, "end": 0.0, "text": text}]
    return {"text": text, "segments": segments}


def transcribe_video_file(video_path: str) -> dict[str, Any]:
    """从视频文件提取 16kHz 单声道音频并转写；超长音频自动按块转写并合并时间轴。"""
    ffmpeg = get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as tmp:
        full_wav = os.path.join(tmp, "full.wav")
        _run_ffmpeg(
            ffmpeg,
            ["-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", full_wav],
        )
        if not os.path.exists(full_wav):
            raise SpeechError("音频提取失败：未生成输出文件")
        size = os.path.getsize(full_wav)
        if size <= MAX_AUDIO_BYTES:
            with open(full_wav, "rb") as f:
                return transcribe_audio(f.read(), "wav")

        # 超过 10MB：按 CHUNK_SECONDS 分块转写，偏移合并时间轴
        duration = (size - 44) / float(_WAV_BYTES_PER_SEC)
        segments_all: list[dict[str, Any]] = []
        texts: list[str] = []
        start = 0.0
        while start < duration - 0.5:
            chunk_wav = os.path.join(tmp, "chunk_{}.wav".format(int(start)))
            _run_ffmpeg(
                ffmpeg,
                ["-y", "-ss", str(start), "-t", str(CHUNK_SECONDS), "-i", full_wav,
                 "-ac", "1", "-ar", "16000", chunk_wav],
            )
            with open(chunk_wav, "rb") as f:
                chunk_bytes = f.read()
            if len(chunk_bytes) > MAX_AUDIO_BYTES:
                raise SpeechError("分块音频仍超过 10MB，无法转写")
            try:
                res = transcribe_audio(chunk_bytes, "wav")
            except SpeechError as exc:
                # 无语音/纯音乐片段：跳过，继续下一块
                logger.info("分块 %ss 转写为空，跳过: %s", start, exc)
                start += CHUNK_SECONDS
                continue
            for seg in res.get("segments") or []:
                seg["start"] = round(seg["start"] + start, 3)
                seg["end"] = round(seg["end"] + start, 3)
                segments_all.append(seg)
            if res.get("text"):
                texts.append(res["text"])
            start += CHUNK_SECONDS
        if not segments_all:
            raise SpeechError("语音转写未识别到有效语音内容")
        if not texts and segments_all:
            texts = [seg["text"] for seg in segments_all]
        return {"text": "\n".join(texts), "segments": segments_all}


def _sentences_to_segments(sentences: Any) -> list[dict[str, Any]]:
    """把 ASR 返回的 sentence（begin_time/end_time 毫秒）合并为字幕片段（秒）。

    Fun-ASR-Flash 对短音频返回单个 dict，长音频返回 list[dict]，两种都兼容。
    """
    items: list[dict[str, Any]] = []
    if isinstance(sentences, dict):
        items = [sentences]
    elif isinstance(sentences, list):
        items = [s for s in sentences if isinstance(s, dict)]
    segments = []
    for item in items:
        seg_text = (item.get("text") or "").strip()
        if not seg_text:
            continue
        begin = item.get("begin_time") or 0
        end = item.get("end_time") or begin
        segments.append(
            {
                "start": round(begin / 1000.0, 3),
                "end": round(end / 1000.0, 3),
                "text": seg_text,
            }
        )
    return segments
