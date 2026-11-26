"""FFmpeg 视频合成：9:16 竖屏、约 12 秒、字幕、转场，并用 ffprobe 校验成品。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from . import config
from .errors import CATEGORY_HINTS, ApiError

WIDTH, HEIGHT, FPS = 720, 1280, 30
TARGET_SECONDS = 12.0
MIN_SECONDS, MAX_SECONDS = 10.0, 15.0
TRANSITION = 0.3


def _ffmpeg() -> str:
    binary = config.ffmpeg_path()
    if not binary:
        raise ApiError(503, "未安装 FFmpeg 或未配置 FFMPEG_PATH", "ffmpeg_missing",
                       "安装 FFmpeg 并确保 ffmpeg 在 PATH 中，或设置 FFMPEG_PATH")
    return binary


def _ffprobe() -> str:
    binary = config.ffprobe_path()
    if not binary:
        raise ApiError(503, "未找到 ffprobe，可设置 FFPROBE_PATH", "ffprobe_missing",
                       "ffprobe 通常与 FFmpeg 一起安装")
    return binary


def _run(args: list[str], cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def _tail(text: str, limit: int = 400) -> str:
    lines = [line for line in (text or "").strip().splitlines() if line.strip()]
    return " | ".join(lines[-3:])[:limit]


def _wrap(text: str) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= 14:
        return cleaned or "商品展示"
    lines = [cleaned[index:index + 14] for index in range(0, min(len(cleaned), 28), 14)]
    if len(cleaned) > 28:
        lines[-1] = lines[-1][:13] + "…"
    return "\n".join(lines)


def _durations(shots: list[dict[str, Any]]) -> list[float]:
    count = max(1, len(shots))
    explicit = [float(shot.get("duration") or 0) for shot in shots]
    if shots and 10 <= sum(explicit) <= 15:
        return explicit
    total = TARGET_SECONDS + TRANSITION * (count - 1 if count > 1 else 0)
    each = round(total / count, 2)
    values = [each] * count
    values[-1] = round(total - each * (count - 1), 2)
    return values


def probe(path: Path) -> dict[str, Any]:
    result = _run([_ffprobe(), "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                  Path(path).parent, timeout=60)
    if result.returncode != 0:
        raise ApiError(502, "FFprobe 无法读取成品：" + _tail(result.stderr), "ffmpeg_error",
                       "请检查视频文件是否完整")
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams") or []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    duration = float((data.get("format") or {}).get("duration") or 0)
    return {
        "duration": round(duration, 2),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "codec": video.get("codec_name") or "",
        "pix_fmt": video.get("pix_fmt") or "",
        "has_audio": any(stream.get("codec_type") == "audio" for stream in streams),
    }


def verify(path: Path) -> dict[str, Any]:
    info = probe(path)
    problems = []
    if not (MIN_SECONDS <= info["duration"] <= MAX_SECONDS):
        problems.append(f"时长 {info['duration']} 秒不在 10-15 秒")
    if (info["width"], info["height"]) != (WIDTH, HEIGHT):
        problems.append(f"画幅 {info['width']}x{info['height']} 不是 {WIDTH}x{HEIGHT}")
    if info["codec"] != "h264":
        problems.append(f"编码不是 H.264（{info['codec']}）")
    if info["pix_fmt"] != "yuv420p":
        problems.append(f"像素格式不是 yuv420p（{info['pix_fmt']}）")
    if problems:
        raise ApiError(502, "视频校验未通过：" + "；".join(problems), "ffmpeg_error",
                       "请检查参考图与字幕字体后重新合成")
    return info


def compose_video(output: Path, images: list[Path], shots: list[dict[str, Any]]) -> dict[str, Any]:
    """按镜头合成竖屏视频，返回 ffprobe 校验后的元信息。失败时删除半成品。"""
    if not images:
        raise ApiError(422, "至少需要一张镜头素材", "invalid_input", "请选择参考图或已审核商品图")
    ffmpeg = _ffmpeg()
    font = config.ffmpeg_font()
    if not font:
        raise ApiError(503, "未找到可用的中文字体，无法绘制字幕", "ffmpeg_font_missing",
                       "设置 FFMPEG_FONT 指向包含中文字形的 TTF/TTC 字体文件")
    duration_values = _durations(shots)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=str(output.parent)) as directory:
            work = Path(directory)
            shutil.copyfile(font, work / "caption-font.ttf")
            clips: list[Path] = []
            for index, duration in enumerate(duration_values):
                source = Path(images[index % len(images)])
                suffix = ".png" if source.suffix.lower() == ".png" else ".jpg"
                frame = work / f"frame-{index}{suffix}"
                shutil.copyfile(source, frame)
                caption = _wrap((shots[index] if index < len(shots) else {}).get("caption", ""))
                (work / f"caption-{index}.txt").write_text(caption, encoding="utf-8")
                fade_out = max(0.1, duration - 0.25)
                filters = (
                    f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                    f"crop={WIDTH}:{HEIGHT},setsar=1,fps={FPS},"
                    "drawtext=expansion=none:"
                    f"textfile=caption-{index}.txt:fontsize=34:fontcolor=white:"
                    "box=1:boxcolor=0x2A2420@0.72:boxborderw=18:"
                    f"fontfile=caption-font.ttf:x=(w-tw)/2:y=h-190,"
                    f"fade=t=in:st=0:d=0.25,fade=t=out:st={fade_out}:d=0.25,format=yuv420p"
                )
                clip = work / f"clip-{index}.mp4"
                result = _run([
                    ffmpeg, "-nostdin", "-loglevel", "error", "-y",
                    "-loop", "1", "-framerate", str(FPS), "-t", f"{duration:.2f}", "-i", frame.name,
                    "-vf", filters, "-t", f"{duration:.2f}", "-r", str(FPS),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-an", clip.name,
                ], work)
                if result.returncode != 0:
                    raise ApiError(502, "生成镜头失败：" + _tail(result.stderr), "ffmpeg_error",
                                   "请检查字幕字体和输入图片")
                clips.append(clip)
            if len(clips) == 1:
                shutil.copyfile(clips[0], output)
            else:
                args = [ffmpeg, "-nostdin", "-loglevel", "error", "-y"]
                for clip in clips:
                    args += ["-i", clip.name]
                filters = []
                offset = 0.0
                previous = "[0:v]"
                for index in range(1, len(clips)):
                    offset += duration_values[index - 1] - TRANSITION
                    label = f"[vx{index}]"
                    filters.append(
                        f"{previous}[{index}:v]xfade=transition=fade:duration={TRANSITION}:"
                        f"offset={offset:.2f}{label}"
                    )
                    previous = label
                total = duration_values[0] + sum(duration_values[1:]) - TRANSITION * (len(clips) - 1)
                args += ["-filter_complex", ";".join(filters), "-map", previous,
                         "-t", f"{total:.2f}", "-r", str(FPS), "-c:v", "libx264",
                         "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                         "-movflags", "+faststart", "-an", str(output.resolve())]
                result = _run(args, work)
                if result.returncode != 0:
                    raise ApiError(502, "合成转场失败：" + _tail(result.stderr), "ffmpeg_error",
                                   "请检查 FFmpeg 是否包含 xfade 滤镜")
        info = verify(output)
        return {**info, "shots": [{"caption": (shot or {}).get("caption", ""),
                                   "duration": duration_values[index]}
                                  for index, shot in enumerate(shots)],
                "font": Path(font).name}
    except ApiError:
        Path(output).unlink(missing_ok=True)
        raise
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        Path(output).unlink(missing_ok=True)
        raise ApiError(502, "视频合成失败，请检查 FFmpeg 配置", "ffmpeg_error",
                       CATEGORY_HINTS["http"]) from error
