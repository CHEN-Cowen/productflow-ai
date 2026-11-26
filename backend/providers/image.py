"""图片生成适配器：支持火山方舟 /api/v3/images/generations 与 OpenAI 兼容接口。

- 参考图以 data URL 或服务商接受的格式传入
- 支持比例/尺寸与候选数量
- 返回 Base64 或 URL，服务端下载后校验文件完整性、图像格式和尺寸
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
from ..errors import CATEGORY_HINTS, ApiError, provider_error
from .errors import classify_http_error

log = logging.getLogger("productflow.image")

RATIO_SIZES = {
    "1:1": "1024x1024",
    "3:4": "1024x1365",
    "4:3": "1365x1024",
    "9:16": "1024x1820",
    "16:9": "1820x1024",
}


def size_for_ratio(ratio: str) -> str:
    ratio = (ratio or "").strip()
    if ratio in RATIO_SIZES:
        return RATIO_SIZES[ratio]
    if "x" in ratio.lower() and all(part.strip().isdigit() for part in ratio.lower().split("x", 1)):
        return ratio.lower()
    return ""


def _config_missing(cfg: dict[str, str]) -> list[str]:
    return [name for name, key in (("IMAGE_URL", "url"), ("IMAGE_MODEL", "model"), ("IMAGE_API_KEY", "key"))
            if not cfg[key]]


def _post(payload: dict, cfg: dict[str, str]) -> tuple[dict, str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        cfg["url"],
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=float(cfg["timeout"])) as response:
            request_id = response.headers.get("x-request-id") or response.headers.get("x-tt-logid") or ""
            raw = response.read()
    except HTTPError as error:
        try:
            error_body = error.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            error_body = ""
        log.warning("image http error status=%s request_id=%s", error.code,
                    error.headers.get("x-request-id") if error.headers else "")
        raise classify_http_error(error.code, error_body, provider="生图服务") from None
    except (TimeoutError, socket.timeout):
        raise provider_error("timeout", "生图请求超时", status=504, hint=CATEGORY_HINTS["timeout"]) from None
    except URLError:
        raise provider_error("connection", "生图连接失败或被重置", hint=CATEGORY_HINTS["connection"]) from None
    except (ConnectionError, OSError):
        raise provider_error("connection", "生图连接失败或被重置", hint=CATEGORY_HINTS["connection"]) from None
    finally:
        log.info("image request duration_ms=%s", int((time.monotonic() - started) * 1000))
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise provider_error("format", "生图响应不是 JSON", hint=CATEGORY_HINTS["format"]) from None
    if isinstance(result.get("error"), dict):
        message = str(result["error"].get("message") or result["error"].get("code") or "生图失败")
        code = str(result["error"].get("code") or "")
        marker = f"{code} {message}".lower()
        if any(key in marker for key in ("setlimitexceed", "quota", "额度", "limit")):
            raise provider_error("quota", f"生图额度不足：{message}", status=429,
                                 hint=CATEGORY_HINTS["quota"])
        raise provider_error("http", f"生图服务返回错误：{message}", hint=CATEGORY_HINTS["http"])
    return result, request_id


def inspect_image(content: bytes) -> tuple[str, int, int]:
    """校验 PNG/JPEG 文件结构并返回 MIME 与宽高。"""
    if len(content) < 50:
        raise provider_error("format", "图片文件过小或不完整", hint=CATEGORY_HINTS["format"])
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(content) < 33 or content[12:16] != b"IHDR":
            raise provider_error("format", "PNG 文件头不完整", hint=CATEGORY_HINTS["format"])
        width = int.from_bytes(content[16:20], "big")
        height = int.from_bytes(content[20:24], "big")
        if b"IEND" not in content[-64:]:
            raise provider_error("format", "PNG 文件缺少结束块，可能下载不完整", hint=CATEGORY_HINTS["format"])
        if not width or not height:
            raise provider_error("format", "PNG 尺寸无效", hint=CATEGORY_HINTS["format"])
        return "image/png", width, height
    if content.startswith(b"\xff\xd8\xff"):
        index = 2
        while index + 9 < len(content):
            if content[index] != 0xFF:
                index += 1
                continue
            marker = content[index + 1]
            if marker in (0xD8, 0xD9):
                index += 2
                continue
            length = int.from_bytes(content[index + 2:index + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2, 0xC3) and index + 9 <= len(content):
                height = int.from_bytes(content[index + 5:index + 7], "big")
                width = int.from_bytes(content[index + 7:index + 9], "big")
                if width and height:
                    return "image/jpeg", width, height
            if length <= 0:
                break
            index += 2 + length
        raise provider_error("format", "JPEG 文件结构不完整或缺少尺寸信息", hint=CATEGORY_HINTS["format"])
    raise provider_error("format", "生图返回的文件不是 PNG 或 JPEG", hint=CATEGORY_HINTS["format"])


def _download(url: str, cfg: dict[str, str]) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise provider_error("download", "生图返回的下载地址协议不受支持", hint=CATEGORY_HINTS["download"])
    try:
        with urlopen(Request(url, headers={"User-Agent": "ProductFlowAI/1.0"}), timeout=float(cfg["download_timeout"])) as response:
            return response.read(20 * 1024 * 1024 + 1)
    except HTTPError as error:
        raise provider_error("download", f"图片下载失败（HTTP {error.code}）", hint=CATEGORY_HINTS["download"]) from None
    except (TimeoutError, socket.timeout):
        raise provider_error("download", "图片下载超时", status=504, hint=CATEGORY_HINTS["download"]) from None
    except (URLError, OSError):
        raise provider_error("download", "图片下载连接失败", hint=CATEGORY_HINTS["download"]) from None


def generate(
    prompt: str,
    references: list[dict] | None = None,
    *,
    ratio: str = "",
    size: str = "",
    count: int = 1,
) -> list[dict]:
    """生成 1-4 张候选图，返回 [{content, mime, width, height, request_id, params}]。"""
    cfg = config.image_config()
    missing = _config_missing(cfg)
    if missing:
        raise provider_error(
            "not_configured",
            "生图服务尚未配置：" + "、".join(missing),
            status=503,
            hint=CATEGORY_HINTS["not_configured"],
        )
    count = max(1, min(int(count or 1), 4))
    resolved_size = size_for_ratio(ratio) or size or cfg["size"]
    images: list[str] = []
    for item in references or []:
        encoded = base64.b64encode(item["content"]).decode("ascii")
        images.append(f"data:{item['mime']};base64,{encoded}")
    results: list[dict] = []
    for _ in range(count):
        payload: dict = {
            "model": cfg["model"],
            "prompt": prompt,
            "size": resolved_size,
            "response_format": "b64_json",
            "watermark": False,
        }
        if images:
            payload["image"] = images if len(images) > 1 else images[0]
        response, request_id = _post(payload, cfg)
        data = response.get("data")
        if not isinstance(data, list) or not data:
            raise provider_error("format", "生图响应缺少 data 列表", hint=CATEGORY_HINTS["format"])
        item = data[0] if isinstance(data[0], dict) else {}
        content: bytes
        if item.get("b64_json"):
            try:
                content = base64.b64decode(str(item["b64_json"]), validate=True)
            except (ValueError, TypeError):
                raise provider_error("format", "生图返回的 Base64 无法解码", hint=CATEGORY_HINTS["format"]) from None
        elif item.get("url") or item.get("image_url"):
            content = _download(str(item.get("url") or item.get("image_url")), cfg)
        else:
            raise provider_error("format", "生图响应既没有图片数据也没有下载地址", hint=CATEGORY_HINTS["format"])
        if len(content) > 20 * 1024 * 1024:
            raise provider_error("format", "生图文件超过 20 MB 上限", hint=CATEGORY_HINTS["format"])
        mime, width, height = inspect_image(content)
        results.append({
            "content": content,
            "mime": mime,
            "width": width,
            "height": height,
            "request_id": request_id,
            "provider": "volcengine-ark",
            "model": cfg["model"],
            "params": {"prompt": prompt, "size": resolved_size, "ratio": ratio,
                       "reference_count": len(images), "count": count},
        })
    return results


def connectivity() -> dict:
    cfg = config.image_config()
    missing = _config_missing(cfg)
    return {
        "configured": not missing,
        "missing": missing,
        "model": cfg["model"],
        "url": cfg["url"],
        "default_size": cfg["size"],
        "note": "仅检查配置是否存在，不发送真实请求" if missing else "配置已就绪，可在生成任务中验证真实返回",
    }
