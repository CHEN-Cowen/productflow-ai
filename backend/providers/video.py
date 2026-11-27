"""Seedance 视频生成适配器：快跑（Kuaipao）统一视频接口 POST /v2/videos。

- 图生视频-首帧：以参考图作为 input_reference，输出 9:16、720p、无声
- 流程：创建任务 → 轮询 GET /v2/videos/{id} → 下载 video_url
- video_url 在 expires_at 前有效，需及时下载到本地
"""
from __future__ import annotations

import base64
import json
import logging
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .. import config
from ..errors import CATEGORY_HINTS, provider_error
from .errors import classify_http_error

log = logging.getLogger("productflow.video")

# 项目视频输出标准：9:16 竖屏、720p、无声，与 FFmpeg 合成链路保持一致
DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_RESOLUTION = "720p"


def _config_missing(cfg: dict[str, str]) -> list[str]:
    return [name for name, key in (("VIDEO_URL", "url"), ("VIDEO_MODEL", "model"), ("VIDEO_API_KEY", "key"))
            if not cfg[key]]


def connectivity() -> dict:
    cfg = config.video_config()
    missing = _config_missing(cfg)
    return {
        "configured": not missing,
        "missing": missing,
        "model": cfg["model"],
        "url": cfg["url"],
        "note": "仅检查配置是否存在，不发送真实请求" if missing else "配置已就绪，可在生成任务中验证真实返回",
    }


def _json_request(url: str, *, method: str, payload: dict | None = None,
                  key: str = "", timeout: float = 60.0) -> tuple[dict, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = Request(url, data=data, headers=headers, method=method)
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            request_id = response.headers.get("x-request-id") or response.headers.get("x-tt-logid") or ""
            raw = response.read()
    except HTTPError as error:
        try:
            error_body = error.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            error_body = ""
        raise classify_http_error(error.code, error_body, provider="视频生成服务") from None
    except (TimeoutError, socket.timeout):
        raise provider_error("timeout", "视频生成请求超时", status=504, hint=CATEGORY_HINTS["timeout"]) from None
    except (URLError, ConnectionError, OSError):
        raise provider_error("connection", "视频生成连接失败或被重置", hint=CATEGORY_HINTS["connection"]) from None
    finally:
        log.info("video request method=%s duration_ms=%s", method, int((time.monotonic() - started) * 1000))
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise provider_error("format", "视频生成响应不是 JSON", hint=CATEGORY_HINTS["format"]) from None
    if isinstance(result.get("error"), dict):
        message = str(result["error"].get("message") or result["error"].get("code") or "视频生成失败")
        code = str(result["error"].get("code") or "")
        marker = f"{code} {message}".lower()
        if any(key in marker for key in ("setlimitexceed", "quota", "额度", "limit")):
            raise provider_error("quota", f"视频生成额度不足：{message}", status=429,
                                 hint=CATEGORY_HINTS["quota"])
        raise provider_error("http", f"视频生成服务返回错误：{message}", hint=CATEGORY_HINTS["http"])
    return result, request_id


def _create_task(payload: dict, cfg: dict[str, str]) -> tuple[str, str]:
    result, request_id = _json_request(cfg["url"], method="POST", payload=payload,
                                       key=cfg["key"], timeout=float(cfg["timeout"]))
    task_id = result.get("id") or result.get("task_id")
    if not task_id:
        raise provider_error("format", "视频生成任务响应缺少 id", hint=CATEGORY_HINTS["format"])
    return str(task_id), request_id


def _get_task(task_id: str, cfg: dict[str, str]) -> dict:
    url = cfg["url"].rstrip("/") + "/" + task_id
    result, _ = _json_request(url, method="GET", key=cfg["key"], timeout=float(cfg["timeout"]))
    return result


def _wait(task_id: str, cfg: dict[str, str]) -> dict:
    interval = max(1.0, float(cfg["poll_interval"]))
    deadline = time.monotonic() + float(cfg["poll_timeout"])
    while True:
        result = _get_task(task_id, cfg)
        status = str(result.get("status") or "")
        if status == "completed":
            return result
        if status == "failed":
            error = result.get("error") or {}
            code = str(error.get("code") or "generation_failed")
            message = str(error.get("message") or "视频生成失败")
            if code == "timeout":
                raise provider_error("timeout", f"视频生成任务超时：{message}", status=504,
                                     hint=CATEGORY_HINTS["timeout"])
            raise provider_error("http", f"视频生成任务失败：{message}", hint=CATEGORY_HINTS["http"])
        if time.monotonic() >= deadline:
            raise provider_error("timeout", "视频生成轮询超时，任务仍在处理中", status=504,
                                 hint=CATEGORY_HINTS["timeout"])
        time.sleep(interval)


def _download(url: str, cfg: dict[str, str]) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise provider_error("download", "视频下载地址协议不受支持", hint=CATEGORY_HINTS["download"])
    try:
        with urlopen(Request(url, headers={"User-Agent": "ProductFlowAI/1.0"}),
                     timeout=float(cfg["download_timeout"])) as response:
            return response.read(100 * 1024 * 1024 + 1)
    except HTTPError as error:
        raise provider_error("download", f"视频下载失败（HTTP {error.code}）", hint=CATEGORY_HINTS["download"]) from None
    except (TimeoutError, socket.timeout):
        raise provider_error("download", "视频下载超时", status=504, hint=CATEGORY_HINTS["download"]) from None
    except (URLError, OSError):
        raise provider_error("download", "视频下载连接失败", hint=CATEGORY_HINTS["download"]) from None


def _check_mp4(content: bytes) -> None:
    if len(content) < 1024:
        raise provider_error("format", "视频文件过小或不完整", hint=CATEGORY_HINTS["format"])
    if b"ftyp" not in content[:32]:
        raise provider_error("format", "视频返回的不是有效 MP4", hint=CATEGORY_HINTS["format"])


def generate(
    prompt: str,
    references: list[dict] | None = None,
    *,
    ratio: str = "",
    duration: int = 12,
) -> list[dict]:
    """生成 1 个视频（图生视频-首帧），返回 [{content, mime, width, height, request_id, params}]。"""
    cfg = config.video_config()
    missing = _config_missing(cfg)
    if missing:
        raise provider_error(
            "not_configured",
            "视频生成服务尚未配置：" + "、".join(missing),
            status=503,
            hint=CATEGORY_HINTS["not_configured"],
        )
    aspect_ratio = (ratio or "").strip() or DEFAULT_ASPECT_RATIO
    seconds = max(1, int(duration or 12))
    payload: dict = {
        "model": cfg["model"],
        "prompt": prompt,
        "seconds": str(seconds),
        "resolution": DEFAULT_RESOLUTION,
        "aspect_ratio": aspect_ratio,
        "generate_audio": False,
    }
    for item in (references or [])[:1]:
        encoded = base64.b64encode(item["content"]).decode("ascii")
        payload["input_reference"] = f"data:{item['mime']};base64,{encoded}"
    task_id, request_id = _create_task(payload, cfg)
    result = _wait(task_id, cfg)
    video_url = str(result.get("video_url") or "")
    if not video_url:
        raise provider_error("format", "视频生成任务完成但缺少 video_url", hint=CATEGORY_HINTS["format"])
    video = _download(video_url, cfg)
    if len(video) > 100 * 1024 * 1024:
        raise provider_error("format", "视频文件超过 100 MB 上限", hint=CATEGORY_HINTS["format"])
    _check_mp4(video)
    params = {
        "prompt": prompt,
        "ratio": str(result.get("aspect_ratio") or aspect_ratio),
        "resolution": str(result.get("resolution") or DEFAULT_RESOLUTION),
        "duration": int(result.get("seconds") or seconds),
        "size": str(result.get("size") or ""),
        "reference_count": len(references or []),
        "task_id": task_id,
    }
    return [{
        "content": video,
        "mime": "video/mp4",
        "width": 0,
        "height": 0,
        "request_id": request_id or task_id,
        "provider": "kuaipao",
        "model": cfg["model"],
        "params": params,
    }]
