"""服务商错误分类：把 HTTP/网络/额度问题转成可行动的错误类别。"""
from __future__ import annotations

import json

from ..errors import CATEGORY_HINTS, ApiError, provider_error

_QUOTA_MARKERS = (
    "setlimitexceed", "quota", "额度", "limit exceeded", "insufficient quota",
    "insufficient balance", "余额不足", "rate limit",
)
_AUTH_MARKERS = ("authentication", "invalid api key", "unauthorized", "invalid_api_key", "api key")
_PERMISSION_MARKERS = ("permission", "accessdenied", "not authorized", "forbidden", "model not open")


def classify_http_error(status: int, body: str, *, provider: str = "模型") -> ApiError:
    code = ""
    message = ""
    try:
        payload = json.loads(body)
        error = payload.get("error") if isinstance(payload.get("error"), dict) else payload
        code = str(error.get("code") or error.get("type") or "")
        message = str(error.get("message") or payload.get("message") or "")
    except (ValueError, AttributeError):
        message = body[:400]
    marker = f"{code} {message}".lower()
    detail = f"（HTTP {status}{' ' + code if code else ''}）"
    if status == 401 or any(item in marker for item in _AUTH_MARKERS):
        return provider_error("auth", f"{provider}认证失败{detail}", hint=CATEGORY_HINTS["auth"])
    if status == 429 or any(item in marker for item in _QUOTA_MARKERS):
        return provider_error(
            "quota", f"{provider}额度不足或被限流{detail}", status=429, hint=CATEGORY_HINTS["quota"]
        )
    if status == 403 or any(item in marker for item in _PERMISSION_MARKERS):
        return provider_error("permission", f"{provider}权限不足{detail}", hint=CATEGORY_HINTS["permission"])
    if status >= 500:
        return provider_error("http", f"{provider}服务暂时不可用{detail}", hint=CATEGORY_HINTS["http"])
    return provider_error("http", f"{provider}调用失败{detail}", hint=CATEGORY_HINTS["http"])
