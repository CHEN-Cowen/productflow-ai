"""集中配置：数据目录、上传限制、模型与 FFmpeg 环境变量。

密钥只在后端读取，任何接口和日志都不返回或写入密钥。
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = BASE_DIR / "data"

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SOURCE_COUNT_PER_IMPORT = 8

_state = {"data_dir": Path(os.environ.get("PRODUCTFLOW_DATA", DEFAULT_DATA_DIR))}


def _load_dotenv(path: Path) -> None:
    """读取本地 .env（不覆盖已存在的环境变量），避免额外依赖。"""
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def configure(data_dir: str | Path | None = None) -> None:
    _load_dotenv(BASE_DIR / ".env")
    if data_dir:
        _state["data_dir"] = Path(data_dir)
    else:
        _state["data_dir"] = Path(os.environ.get("PRODUCTFLOW_DATA", DEFAULT_DATA_DIR))


def data_dir() -> Path:
    return _state["data_dir"].resolve()


def db_path() -> Path:
    return data_dir() / "productflow.sqlite3"


def _sub(name: str) -> Path:
    path = data_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def uploads_dir() -> Path:
    return _sub("uploads")


def generated_dir() -> Path:
    return _sub("generated")


def references_dir() -> Path:
    return _sub("references")


def samples_dir() -> Path:
    return _sub("samples")


def ensure_dirs() -> list[Path]:
    return [uploads_dir(), generated_dir(), references_dir(), samples_dir()]


def _env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def llm_config() -> dict[str, str]:
    return {
        "url": _env("LLM_URL"),
        "model": _env("LLM_MODEL"),
        "key": _env("LLM_API_KEY"),
        "timeout": _env("LLM_TIMEOUT") or "120",
    }


def image_config() -> dict[str, str]:
    return {
        "url": _env("IMAGE_URL"),
        "model": _env("IMAGE_MODEL"),
        "key": _env("IMAGE_API_KEY"),
        "size": _env("IMAGE_SIZE") or "1024x1365",
        "timeout": _env("IMAGE_TIMEOUT") or "180",
        "download_timeout": _env("IMAGE_DOWNLOAD_TIMEOUT") or "90",
    }


def video_config() -> dict[str, str]:
    return {
        "url": _env("VIDEO_URL"),
        "model": _env("VIDEO_MODEL"),
        "key": _env("VIDEO_API_KEY"),
        "timeout": _env("VIDEO_TIMEOUT") or "300",
        "download_timeout": _env("VIDEO_DOWNLOAD_TIMEOUT") or "120",
        "poll_interval": _env("VIDEO_POLL_INTERVAL") or "5",
        "poll_timeout": _env("VIDEO_POLL_TIMEOUT") or "600",
    }


def ffmpeg_path() -> str:
    import shutil

    return _env("FFMPEG_PATH") or (shutil.which("ffmpeg") or "")


def ffprobe_path() -> str:
    import shutil

    explicit = _env("FFPROBE_PATH")
    if explicit:
        return explicit
    ffmpeg = ffmpeg_path()
    if ffmpeg:
        candidate = Path(ffmpeg).with_name(Path(ffmpeg).stem.replace("ffmpeg", "ffprobe") + Path(ffmpeg).suffix)
        if candidate.is_file():
            return str(candidate)
    return shutil.which("ffprobe") or ""


def ffmpeg_font() -> str:
    explicit = _env("FFMPEG_FONT")
    if explicit:
        return explicit
    candidates: list[Path] = []
    if os.name == "nt":
        fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        candidates += [
            fonts / "msyh.ttc",
            fonts / "msyhbd.ttc",
            fonts / "simhei.ttf",
            fonts / "simsun.ttc",
            fonts / "Deng.ttf",
        ]
    else:
        candidates += [
            Path("/System/Library/Fonts/PingFang.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""


def model_status() -> dict[str, dict[str, object]]:
    llm = llm_config()
    image = image_config()
    video = video_config()
    return {
        "llm": {
            "configured": all((llm["url"], llm["model"], llm["key"])),
            "model": llm["model"],
            "url_configured": bool(llm["url"]),
        },
        "image": {
            "configured": all((image["url"], image["model"], image["key"])),
            "model": image["model"],
            "url_configured": bool(image["url"]),
        },
        "video": {
            "configured": all((video["url"], video["model"], video["key"])),
            "model": video["model"],
            "url_configured": bool(video["url"]),
        },
        "ffmpeg": {
            "configured": bool(ffmpeg_path()),
            "ffprobe": bool(ffprobe_path()),
            "font": bool(ffmpeg_font()),
        },
        "ocr": {"configured": bool(_env("TESSERACT_CMD") or __import__("shutil").which("tesseract"))},
    }
