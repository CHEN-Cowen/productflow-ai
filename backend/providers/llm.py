"""OpenAI 兼容 Chat Completions 文本适配器。

支持 DeepSeek 等服务的 JSON 模式；对外错误统一映射为可行动的错误类别。
日志只记录状态码、服务商请求 ID 与耗时，不写密钥或完整响应。
"""
from __future__ import annotations

import json
import logging
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .. import config
from ..errors import CATEGORY_HINTS, ApiError, provider_error
from .errors import classify_http_error

log = logging.getLogger("productflow.llm")


def _missing_config() -> list[str]:
    cfg = config.llm_config()
    return [name for name, key in (("LLM_URL", "url"), ("LLM_MODEL", "model"), ("LLM_API_KEY", "key"))
            if not cfg[key]]


def _request(messages: list[dict], temperature: float = 0.1) -> tuple[dict, str]:
    cfg = config.llm_config()
    missing = _missing_config()
    if missing:
        raise provider_error(
            "not_configured",
            "文本模型尚未配置：" + "、".join(missing),
            status=503,
            hint=CATEGORY_HINTS["not_configured"],
        )
    body = json.dumps(
        {
            "model": cfg["model"],
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        cfg["url"],
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"},
        method="POST",
    )
    started = time.monotonic()
    request_id = ""
    try:
        with urlopen(request, timeout=float(cfg["timeout"])) as response:
            request_id = response.headers.get("x-request-id") or response.headers.get("x-tt-logid") or ""
            raw = response.read()
    except HTTPError as error:
        try:
            error_body = error.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - 读取错误体失败不影响分类
            error_body = ""
        log.warning("llm http error status=%s request_id=%s", error.code,
                    error.headers.get("x-request-id") if error.headers else "")
        raise classify_http_error(error.code, error_body) from None
    except (TimeoutError, socket.timeout):
        raise provider_error("timeout", "模型请求超时", status=504, hint=CATEGORY_HINTS["timeout"]) from None
    except URLError as error:
        reason = str(error.reason or "")
        log.warning("llm connection error reason=%s", reason[:120])
        raise provider_error(
            "connection", "模型连接失败或被重置", hint=CATEGORY_HINTS["connection"]
        ) from None
    except (ConnectionError, OSError) as error:
        log.warning("llm socket error type=%s", type(error).__name__)
        raise provider_error("connection", "模型连接失败或被重置", hint=CATEGORY_HINTS["connection"]) from None
    finally:
        log.info("llm request duration_ms=%s", int((time.monotonic() - started) * 1000))
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise provider_error("format", "模型响应不是 JSON", hint=CATEGORY_HINTS["format"]) from None
    return payload, request_id


def _extract_json(payload: dict) -> dict:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise provider_error("format", "模型响应缺少 choices.message.content", hint=CATEGORY_HINTS["format"]) from None
    if not isinstance(content, str):
        raise provider_error("format", "模型返回内容不是文本", hint=CATEGORY_HINTS["format"])
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        value = json.loads(text)
    except ValueError:
        raise provider_error("invalid_json", "模型未返回合法 JSON", hint=CATEGORY_HINTS["invalid_json"]) from None
    if not isinstance(value, dict):
        raise provider_error("format", "模型返回的 JSON 不是对象", hint=CATEGORY_HINTS["format"])
    return value


def generate_structured(instruction: str, data: dict) -> dict:
    """调用文本模型并返回 JSON 对象；非法 JSON 时做一次严格重试。"""
    messages = [
        {"role": "system", "content": instruction},
        {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
    ]
    payload, _ = _request(messages)
    try:
        return _extract_json(payload)
    except ApiError as error:
        if error.code != "provider_invalid_json":
            raise
        log.info("llm invalid json, retry once with stricter instruction")
    retry_messages = messages + [
        {"role": "assistant", "content": "（上一次输出不是合法 JSON）"},
        {"role": "user", "content": "请只返回一个合法 JSON 对象，不要代码块或解释文字。"},
    ]
    payload, _ = _request(retry_messages, temperature=0)
    return _extract_json(payload)


def connectivity() -> dict:
    cfg = config.llm_config()
    missing = _missing_config()
    return {
        "configured": not missing,
        "missing": missing,
        "model": cfg["model"],
        "url": cfg["url"],
        "note": "仅检查配置是否存在，不发送真实请求" if missing else "配置已就绪，可在数据导入时验证真实返回",
    }
