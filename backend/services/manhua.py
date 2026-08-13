# -*- coding: utf-8 -*-
"""AI 漫剧解析/创作服务：素材提取（字幕/转写 + 关键帧视觉）-> LLM 生成漫剧脚本。

v1 纯文本产出：剧情梗概 + 角色设定 + 分镜表；分镜 visual 字段为后续文生图预留。
素材包缓存 7 天（按 url+分镜数），脚本缓存 24h（按 url+画风+分镜数）。
"""

from __future__ import annotations

import glob
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .ai_service import (
    AIServiceError,
    _load_stt_cache,
    _normalize_cache_url,
    _save_stt_cache,
)
from .downloader import DOWNLOADS_DIR, download_video
from .douyin import DouyinError, download_douyin, is_douyin_url, parse_douyin
from .llm import chat
from .speech import SpeechError, get_ffmpeg_exe, transcribe_video_file
from .subtitles import SubtitleError, SubtitleResult, fetch_subtitles
from .vision import VisionError, describe_image

logger = logging.getLogger("uvicorn.error")

MANHUA_CACHE_DIR = DOWNLOADS_DIR / "manhua_cache"
MATERIAL_TTL = 7 * 24 * 3600
SCRIPT_TTL = 24 * 3600
MAX_FRAME_CALLS = 12
VISION_WORKERS = 3
MAX_TEXT_CHARS = 30000

STYLES = {
    "guoman": "国漫",
    "riman": "日漫",
    "qban": "Q版",
    "hanman": "韩漫",
}

FRAME_DESCRIBE_PROMPT = (
    "你是漫剧分镜师。请用中文简洁描述这张视频画面，按要点："
    "1)主要人物：外貌、服装、表情、动作；2)场景与环境：地点、布局、光线；"
    "3)画面中可见的文字（如标题/字幕，若有）；4)情绪氛围。"
    "控制在60-120字，直接输出描述，不要额外格式。"
)


def generate_manhua(url: str, style: str = "guoman", panels: int = 8) -> dict[str, Any]:
    """生成漫剧脚本：素材包（缓存 7 天）-> LLM 脚本（缓存 24h）。"""
    style_name = STYLES.get((style or "").strip().lower())
    if not style_name:
        raise AIServiceError(f"不支持的画风: {style}（可选: {', '.join(STYLES)}）")
    try:
        panels = max(4, min(int(panels or 8), MAX_FRAME_CALLS))
    except (TypeError, ValueError):
        panels = 8

    cached_script = _load_script_cache(url, style, panels)
    if cached_script:
        logger.info("命中漫剧脚本缓存")
        return cached_script

    material = _build_material(url, panels)
    script = _generate_script(material, style_name, panels)
    script["reference_frames"] = material.get("reference_frames") or []
    _save_script_cache(url, style, panels, script)
    return script


# ---------- 素材包构建 ----------


def _build_material(url: str, panels: int) -> dict[str, Any]:
    """一次下载：字幕/转写拿台词 + 抽关键帧 + 视觉描述，结果落素材缓存。"""
    cached = _load_material_cache(url, panels)
    if cached:
        logger.info("命中漫剧素材缓存")
        return cached

    task_id = uuid.uuid4().hex[:16]
    video_path = None
    subtitle_err: Exception | None = None
    try:
        # 1) 字幕优先（B站 API / yt-dlp），不触发下载
        subs = None
        try:
            subs = fetch_subtitles(url)
        except SubtitleError as exc:
            subtitle_err = exc

        title = subs.title if subs else None
        text = subs.text if subs else ""
        segments = subs.segments if subs else []

        # 2) 下载视频一次（抽帧；无字幕时同一文件转写）
        video_path = _download_video(url, task_id)
        frames = _extract_keyframes(video_path, panels)
        reference_frames = _save_frames(url, frames)

        # 3) 无字幕 -> 从同一文件语音转写（复用 STT 缓存）
        if not text:
            stt_cache = _load_stt_cache(url)
            if stt_cache:
                text = stt_cache.text
                segments = stt_cache.segments
                if not title:
                    title = stt_cache.title
            else:
                try:
                    stt = transcribe_video_file(video_path)
                    segments = stt.get("segments") or []
                    text = stt.get("text") or "\n".join(
                        s.get("text", "") for s in segments
                    )
                    if text or segments:
                        _save_stt_cache(
                            url,
                            SubtitleResult(lang="语音转写", segments=segments, title=title),
                        )
                except SpeechError as exc:
                    logger.info("语音转写失败: %s", exc)
                    text = ""

        # 4) 标题兜底（抖音）
        if not title and is_douyin_url(url):
            try:
                title = parse_douyin(url).get("title")
            except Exception as exc:
                logger.info("获取抖音标题失败: %s", exc)

        # 5) 关键帧视觉描述
        frames_desc = _describe_frames(frames)

        if not text and not frames_desc:
            reason = f"（{subtitle_err}）" if subtitle_err else ""
            raise AIServiceError(
                f"该视频暂无可用字幕{reason}，且语音转写与画面提取均未获得有效内容"
            )

        material = {
            "cached_at": time.time(),
            "title": title,
            "text": text,
            "segments": segments,
            "frames": frames_desc,
            "reference_frames": reference_frames,
        }
        _save_material_cache(url, panels, material)
        return material
    except AIServiceError:
        raise
    except DouyinError as exc:
        raise AIServiceError(f"抖音视频处理失败：{exc}")
    finally:
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
            except OSError:
                pass


def _download_video(url: str, task_id: str) -> str:
    """下载视频文件用于抽帧（非抖音用低清晰度格式以减小体积）。

    格式链：最差视频流优先，逐级兜底到默认 best，避免个别平台无对应格式。
    """
    if is_douyin_url(url):
        return download_douyin(url, task_id)
    return download_video(url, "worstvideo/worst/best", task_id)


# ---------- 关键帧提取 ----------


def _extract_keyframes(video_path: str, count: int) -> list[dict[str, Any]]:
    """提取 <=count 个关键帧，返回 [{time, bytes, fmt}]。场景检测优先，不足半数回退均匀采样。"""
    count = max(1, min(count, MAX_FRAME_CALLS))
    ffmpeg = get_ffmpeg_exe()
    frames = _scene_frames(ffmpeg, video_path, count)
    if len(frames) < max(2, count // 2):
        uniform = _uniform_frames(ffmpeg, video_path, count)
        if len(uniform) > len(frames):
            frames = uniform
    return frames


def _scene_frames(ffmpeg: str, video_path: str, count: int) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory() as tmp:
        out_pat = os.path.join(tmp, "f_%03d.jpg")
        proc = subprocess.run(
            [
                ffmpeg, "-y", "-i", video_path,
                "-vf", "select='gt(scene,0.3)',scale=960:-2,showinfo",
                "-vsync", "vfr", "-frames:v", str(count), "-q:v", "4",
                out_pat,
            ],
            capture_output=True,
            timeout=300,
        )
        files = sorted(glob.glob(os.path.join(tmp, "f_*.jpg")))
        if not files:
            return []
        stderr = proc.stderr.decode("utf-8", "ignore")
        times = [float(t) for t in re.findall(r"pts_time:([0-9.]+)", stderr)]
        frames = []
        for i, fp in enumerate(files):
            t = times[i] if i < len(times) else 0.0
            with open(fp, "rb") as f:
                frames.append({"time": round(float(t), 1), "bytes": f.read(), "fmt": "jpeg"})
        return frames


def _uniform_frames(ffmpeg: str, video_path: str, count: int) -> list[dict[str, Any]]:
    duration = _probe_duration(ffmpeg, video_path)
    with tempfile.TemporaryDirectory() as tmp:
        frames = []
        if not duration or duration <= 1.0:
            out = os.path.join(tmp, "u.jpg")
            subprocess.run(
                [ffmpeg, "-y", "-i", video_path, "-frames:v", "1",
                 "-vf", "scale=960:-2", "-q:v", "4", out],
                capture_output=True, timeout=120,
            )
            if os.path.exists(out):
                with open(out, "rb") as f:
                    frames.append({"time": 0.0, "bytes": f.read(), "fmt": "jpeg"})
            return frames
        step = duration / max(count, 1)
        for i in range(count):
            t = min(step * i + step * 0.3, max(0.0, duration - 0.1))
            out = os.path.join(tmp, f"u_{i}.jpg")
            subprocess.run(
                [ffmpeg, "-y", "-ss", str(t), "-i", video_path,
                 "-frames:v", "1", "-vf", "scale=960:-2", "-q:v", "4", out],
                capture_output=True, timeout=120,
            )
            if os.path.exists(out):
                with open(out, "rb") as f:
                    frames.append({"time": round(t, 1), "bytes": f.read(), "fmt": "jpeg"})
        return frames


def _probe_duration(ffmpeg: str, video_path: str) -> float | None:
    try:
        proc = subprocess.run([ffmpeg, "-i", video_path], capture_output=True, timeout=60)
        stderr = proc.stderr.decode("utf-8", "ignore")
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
        if m:
            h, mi, s = m.groups()
            return int(h) * 3600 + int(mi) * 60 + float(s)
    except Exception:
        pass
    return None


def _describe_frames(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """并行调用 Qwen-VL 描述关键帧，单帧失败降级为空描述。"""
    if not frames:
        return []

    def work(fr: dict[str, Any]) -> dict[str, Any]:
        try:
            desc = describe_image(
                fr["bytes"], FRAME_DESCRIBE_PROMPT, fr.get("fmt") or "jpeg"
            )
            return {"time": fr["time"], "description": desc}
        except VisionError as exc:
            logger.info("关键帧 %ss 视觉描述失败: %s", fr["time"], exc)
            return {"time": fr["time"], "description": ""}

    with ThreadPoolExecutor(max_workers=VISION_WORKERS) as ex:
        results = list(ex.map(work, frames))
    return [r for r in results if r.get("description")]


def _save_frames(url: str, frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把抽取的关键帧落盘，返回 [{time, url}]（/files 静态可访问）。"""
    if not frames:
        return []
    digest = hashlib.sha256(_normalize_cache_url(url).encode("utf-8")).hexdigest()[:32]
    fdir = MANHUA_CACHE_DIR / "frames" / digest
    try:
        fdir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.info("创建关键帧目录失败: %s", exc)
        return []
    refs = []
    for i, fr in enumerate(frames, 1):
        fn = "frame_{:02d}_{}.jpg".format(i, int(fr.get("time") or 0))
        try:
            (fdir / fn).write_bytes(fr.get("bytes") or b"")
            refs.append({
                "time": fr.get("time"),
                "url": "/files/manhua_cache/frames/{}/{}".format(digest, fn),
            })
        except Exception as exc:
            logger.info("保存关键帧失败: %s", exc)
    return refs


# ---------- 剧本生成 ----------


def _generate_script(material: dict[str, Any], style_name: str, panels: int) -> dict[str, Any]:
    title = (material.get("title") or "未命名视频").strip()
    text = (material.get("text") or "").strip()[:MAX_TEXT_CHARS]
    frame_lines = [
        f"- {fr.get('time')}s: {fr.get('description')}" for fr in (material.get("frames") or [])
    ]
    frames_txt = "\n".join(frame_lines) or "（无关键帧画面描述）"

    system = (
        "你是资深漫剧编剧，擅长把短视频改编成" + style_name + "风格的漫剧脚本。"
        "根据用户提供的视频素材（标题、台词、关键帧画面描述）创作完整漫剧脚本。\n"
        "角色设定与画面描述必须忠实于关键帧描述中实际出现的形象（外貌/服装/气质），不得凭空创造与画面不符的外貌。\n"
        "严格要求：只输出一个 JSON 对象，不要输出任何解释、markdown 代码块或其他内容。\n"
        "JSON 结构："
        '{"title":"漫剧标题（有网感）","synopsis":"50-150字剧情梗概",'
        '"characters":[{"name":"角色名","role":"角色定位（主角/反派/配角等）","desc":"30-60字外貌与性格描述"}],'
        '"panels":[{"index":1,"time":0,"scene":"画面场景","dialogue":"该格对白，没有则为空字符串",'
        '"narration":"旁白或内心独白，没有则为空字符串","emotion":"情绪氛围",'
        '"visual":"画面描述，可独立作为AI绘图提示词，含人物/场景/镜头/画风关键词"}]}\n'
        f"要求：panels 恰好 {panels} 格，按剧情顺序推进；dialogue/narration 用中文；time 为对应视频时间（秒，浮点数）。"
    )
    user = (
        f"视频标题：{title}\n\n"
        f"台词文本（字幕/语音转写）：\n{text}\n\n"
        f"关键帧画面描述：\n{frames_txt}\n\n"
        f"请创作 {panels} 格 {style_name} 风格漫剧脚本。"
    )

    last_err: Exception | None = None
    for attempt in range(2):
        try:
            content = chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.6,
                max_tokens=4000,
            )
            data = _parse_script_json(content)
            return _normalize_script(data, style_name, panels, title)
        except Exception as exc:
            last_err = exc
            logger.info("漫剧脚本生成解析失败（第 %s 次）: %s", attempt + 1, exc)
            if attempt == 0:
                user = user + "\n\n注意：上次输出不是合法 JSON，请只输出 JSON 对象本身，不要任何其他内容。"
    raise AIServiceError(f"AI 生成漫剧脚本失败: {last_err}")


def _parse_script_json(content: str) -> dict[str, Any]:
    content = (content or "").strip()
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        content = content[start:end + 1]
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("脚本 JSON 不是对象")
    return data


def _normalize_script(
    data: dict[str, Any], style_name: str, panels: int, fallback_title: str
) -> dict[str, Any]:
    characters = []
    for c in (data.get("characters") or []):
        if not isinstance(c, dict):
            continue
        characters.append(
            {
                "name": (c.get("name") or "").strip() or "未命名角色",
                "role": (c.get("role") or "").strip(),
                "desc": (c.get("desc") or "").strip(),
            }
        )
    panel_list = []
    for i, p in enumerate((data.get("panels") or [])):
        if not isinstance(p, dict):
            continue
        try:
            t = round(float(p.get("time") or 0), 1)
        except (TypeError, ValueError):
            t = 0.0
        panel_list.append(
            {
                "index": i + 1,
                "time": t,
                "scene": (p.get("scene") or "").strip(),
                "dialogue": (p.get("dialogue") or "").strip(),
                "narration": (p.get("narration") or "").strip(),
                "emotion": (p.get("emotion") or "").strip(),
                "visual": (p.get("visual") or "").strip(),
            }
        )
    if not panel_list:
        raise ValueError("AI 生成的漫剧分镜为空")
    return {
        "title": (data.get("title") or fallback_title or "未命名漫剧").strip(),
        "style": style_name,
        "panels_count": len(panel_list),
        "synopsis": (data.get("synopsis") or "").strip(),
        "characters": characters,
        "panels": panel_list,
        "generated_at": int(time.time()),
    }


# ---------- 缓存 ----------


def _cache_path(kind: str, key: str) -> Path:
    return MANHUA_CACHE_DIR / f"{kind}_{key}.json"


def _material_key(url: str, panels: int) -> str:
    raw = f"{_normalize_cache_url(url)}#frames={panels}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _script_key(url: str, style: str, panels: int) -> str:
    raw = f"{_normalize_cache_url(url)}#{style}#panels={panels}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _load_material_cache(url: str, panels: int) -> dict[str, Any] | None:
    try:
        path = _cache_path("material", _material_key(url, panels))
        if not path.exists():
            return None
        data = json.loads(path.read_text("utf-8"))
        if time.time() - float(data.get("cached_at") or 0) > MATERIAL_TTL:
            path.unlink(missing_ok=True)
            return None
        if not data.get("text") and not data.get("frames"):
            return None
        return data
    except Exception as exc:
        logger.info("读取漫剧素材缓存失败: %s", exc)
        return None


def _save_material_cache(url: str, panels: int, material: dict[str, Any]) -> None:
    try:
        MANHUA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path("material", _material_key(url, panels))
        path.write_text(json.dumps(material, ensure_ascii=False), "utf-8")
    except Exception as exc:
        logger.info("写入漫剧素材缓存失败: %s", exc)


def _load_script_cache(url: str, style: str, panels: int) -> dict[str, Any] | None:
    try:
        path = _cache_path("script", _script_key(url, style, panels))
        if not path.exists():
            return None
        data = json.loads(path.read_text("utf-8"))
        if time.time() - float(data.get("generated_at") or 0) > SCRIPT_TTL:
            path.unlink(missing_ok=True)
            return None
        if not data.get("panels"):
            return None
        return data
    except Exception as exc:
        logger.info("读取漫剧脚本缓存失败: %s", exc)
        return None


def _save_script_cache(url: str, style: str, panels: int, script: dict[str, Any]) -> None:
    try:
        MANHUA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path("script", _script_key(url, style, panels))
        path.write_text(json.dumps(script, ensure_ascii=False), "utf-8")
    except Exception as exc:
        logger.info("写入漫剧脚本缓存失败: %s", exc)
