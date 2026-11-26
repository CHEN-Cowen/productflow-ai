import os
import shutil
import subprocess
from tempfile import TemporaryDirectory
from pathlib import Path

from fastapi import HTTPException


def compose_video(output, images, shots):
    ffmpeg = os.getenv("FFMPEG_PATH") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise HTTPException(503, "请安装 FFmpeg 或配置 FFMPEG_PATH")

    def run(*args, directory):
        subprocess.run([ffmpeg, "-nostdin", "-loglevel", "error", "-y", *args],
                       cwd=directory, capture_output=True, check=True, timeout=90)

    try:
        with TemporaryDirectory() as directory:
            frames = 360 // len(shots)
            font = os.getenv("FFMPEG_FONT")
            if not font and os.name == "nt":
                default_font = Path(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simhei.ttf")
                if default_font.is_file():
                    font = str(default_font)
            if font:
                shutil.copyfile(font, Path(directory, "caption-font.ttf"))
            for index, shot in enumerate(shots):
                Path(directory, "caption.txt").write_text(shot[:70], encoding="utf-8")
                caption = "drawtext=textfile=caption.txt:expansion=none:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.65:x=(w-tw)/2:y=h-130"
                if font:
                    caption += ":fontfile=caption-font.ttf"
                image = images[index % len(images)]
                with image.open("rb") as source:
                    suffix = ".png" if source.read(8).startswith(b"\x89PNG") else ".jpg"
                frame = "frame" + suffix
                shutil.copyfile(image, Path(directory, frame))
                filters = ("scale=720:1280:force_original_aspect_ratio=decrease,"
                           "pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1," + caption)
                run("-loop", "1", "-framerate", "30", "-i", frame,
                    "-vf", filters, "-frames:v", str(frames), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    f"shot-{index}.mp4", directory=directory)
            Path(directory, "shots.txt").write_text(
                "".join(f"file shot-{index}.mp4\n" for index in range(len(shots))), encoding="ascii")
            run("-f", "concat", "-i", "shots.txt", "-c", "copy", "-movflags", "+faststart",
                str(output.resolve()), directory=directory)
    except (OSError, subprocess.SubprocessError) as error:
        output.unlink(missing_ok=True)
        raise HTTPException(502, "FFmpeg 合成失败，请检查图片、libx264 和 drawtext 字体配置") from error
