"""统一错误码与标准错误信封。

把现有的领域错误 code（如 duplicate_product、unsupported_file）映射到任务书约定的
标准化 ErrorCode，并标注是否可重试、是否需要人工介入。旧 code 保留在错误信封的
detail.hint 与兼容字段中，不破坏既有前端与测试。
"""
from __future__ import annotations

from typing import Any

# 旧 code -> (标准 code, 可重试, 需人工介入)
ERROR_CODES: dict[str, tuple[str, bool, bool]] = {
    # 文件
    "unsupported_file": ("FILE_FORMAT_UNSUPPORTED", False, False),
    "file_too_large": ("FILE_FORMAT_UNSUPPORTED", False, False),
    "file_mismatch": ("FILE_PARSE_FAILED", False, True),
    "pdf_encrypted": ("FILE_PARSE_FAILED", False, True),
    "pdf_invalid": ("FILE_PARSE_FAILED", False, True),
    "xlsx_invalid": ("FILE_PARSE_FAILED", False, True),
    "docx_invalid": ("FILE_PARSE_FAILED", False, True),
    "docx_unavailable": ("FILE_PARSE_FAILED", False, True),
    "ocr_unavailable": ("OCR_FAILED", False, True),
    # 通用
    "invalid_input": ("INVALID_INPUT", False, False),
    "not_found": ("NOT_FOUND", False, False),
    "conflict": ("DATA_CONFLICT", False, True),
    "duplicate_product": ("DUPLICATE_PRODUCT", False, False),
    "duplicate_source": ("DUPLICATE_FILE", False, False),
    "duplicate_field": ("SCHEMA_VALIDATION_FAILED", False, False),
    "category_conflict": ("DATA_CONFLICT", False, True),
    "cross_product_reference": ("ASSET_NOT_FOUND", False, False),
    "invalid_sku": ("INVALID_INPUT", False, False),
    # 数据治理
    "manual_basis_required": ("DATA_MISSING", False, True),
    "version_required": ("PRODUCT_NOT_VERIFIED", False, True),
    "stale_version": ("PRODUCT_VERSION_STALE", False, True),
    "claim_blocked": ("CLAIM_BLOCKED", False, True),
    "publish_blocked": ("DATA_MISSING", False, True),
    "already_published": ("DATA_CONFLICT", False, False),
    # 内容策划
    "plan_not_confirmed": ("PLANNING_NOT_APPROVED", False, True),
    # 模型服务
    "provider_not_configured": ("AI_PROVIDER_UNAVAILABLE", False, True),
    "provider_auth": ("AI_PROVIDER_UNAVAILABLE", False, True),
    "provider_permission": ("AI_PROVIDER_UNAVAILABLE", False, True),
    "provider_quota": ("BUDGET_EXCEEDED", False, True),
    "provider_timeout": ("AI_PROVIDER_TIMEOUT", True, False),
    "provider_connection": ("AI_PROVIDER_UNAVAILABLE", True, False),
    "provider_http": ("AI_PROVIDER_UNAVAILABLE", True, False),
    "provider_invalid_json": ("AI_OUTPUT_INVALID", True, False),
    "provider_format": ("AI_OUTPUT_INVALID", True, False),
    "provider_download": ("ASSET_NOT_FOUND", True, False),
    # 生成
    "stale_output": ("STALE_OUTPUT", False, True),
    "ffmpeg_error": ("VIDEO_GENERATION_FAILED", False, True),
    "ffmpeg_missing": ("VIDEO_GENERATION_FAILED", False, True),
    "storage_error": ("STORAGE_ERROR", True, False),
    # 租户
    "tenant_access_denied": ("TENANT_ACCESS_DENIED", False, False),
    # 工作流
    "workflow_retry_exceeded": ("WORKFLOW_RETRY_EXCEEDED", False, True),
}


def resolve(code: str) -> tuple[str, bool, bool]:
    """返回 (标准 code, 可重试, 需人工介入)。未知 code 保留原值并视为不可重试。"""
    standard, retryable, human = ERROR_CODES.get(code, (code.upper(), False, False))
    return standard, retryable, human


def envelope(
    *,
    success: bool,
    code: str = "",
    message: str = "",
    details: dict[str, Any] | None = None,
    hint: str = "",
    legacy_code: str = "",
) -> dict[str, Any]:
    """构造标准错误信封。同时保留 detail 形状用于兼容旧前端/测试。"""
    legacy = legacy_code or code
    standard, retryable, human = resolve(code)
    return {
        "success": success,
        "error": {
            "code": standard,
            "message": message,
            "details": details or {},
            "retryable": retryable,
            "requires_human_action": human,
        },
        "detail": {"code": legacy, "message": message, "hint": hint},
    }
