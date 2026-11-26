"""统一业务错误：面向前端给出可采取行动的错误类别。

错误类别：
- invalid_input / not_found / conflict：用户可修正
- provider_not_configured / provider_auth / provider_permission / provider_quota
- provider_timeout / provider_connection / provider_invalid_json / provider_format
- storage_error / ffmpeg_error / ocr_unavailable
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException


@dataclass
class ApiError(Exception):
    status: int
    message: str
    code: str = "error"
    hint: str = ""

    def to_http(self) -> HTTPException:
        return HTTPException(
            status_code=self.status,
            detail={"message": self.message, "code": self.code, "hint": self.hint},
        )


def reject(message: str, hint: str = "", code: str = "invalid_input") -> ApiError:
    return ApiError(422, message, code, hint)


def conflict(message: str, hint: str = "", code: str = "conflict") -> ApiError:
    return ApiError(409, message, code, hint)


def not_found(message: str = "记录不存在") -> ApiError:
    return ApiError(404, message, "not_found")


def provider_error(
    category: str,
    message: str,
    *,
    status: int = 502,
    hint: str = "",
) -> ApiError:
    return ApiError(status, message, f"provider_{category}", hint)


CATEGORY_HINTS = {
    "not_configured": "在后端进程环境中配置对应的 URL、模型 ID 和 API Key 后重启服务。",
    "auth": "检查 API Key 是否正确或已过期，密钥只放在后端环境变量中。",
    "permission": "当前账号/模型未开通权限，请在服务商控制台开通模型或授权接入点。",
    "quota": "服务商额度不足或被限流，请充值/恢复额度后重试；历史任务与失败原因已保留。",
    "timeout": "服务商响应超时，可稍后重试；请确认网络与服务商状态。",
    "connection": "连接被重置或网络不可达，请检查网络/代理后重试。",
    "invalid_json": "模型返回的不是合法 JSON 对象，可重试或改用支持 JSON 模式的模型。",
    "format": "模型返回结构不符合约定格式，请检查模型能力或提示词。",
    "http": "服务商返回异常状态码，请稍后重试并查看服务商状态页。",
    "download": "图片下载失败或文件不完整，请重试。",
}
