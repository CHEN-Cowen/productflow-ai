# 统一异常处理与错误码

## 错误信封

所有错误返回统一结构（`backend/error_codes.py::envelope`）：

```json
{
  "success": false,
  "error": {
    "code": "DATA_CONFLICT",
    "message": "商品高度存在不同来源的冲突",
    "details": {},
    "retryable": false,
    "requires_human_action": true
  },
  "detail": { "code": "conflict", "message": "...", "hint": "..." }
}
```

- `error`：标准信封（标准 ErrorCode + 可重试/需人工介入标记）。
- `detail`：向后兼容字段（旧前端/测试仍读取 `detail.code/message/hint`）。

## 标准 ErrorCode（任务书 §9）

| 标准 code | 可重试 | 需人工 |
| --- | --- | --- |
| FILE_FORMAT_UNSUPPORTED / FILE_PARSE_FAILED | 否 | 视情况 |
| OCR_FAILED | 否 | 是 |
| AI_PROVIDER_TIMEOUT | 是 | 否 |
| AI_PROVIDER_UNAVAILABLE | 是 | 是 |
| AI_OUTPUT_INVALID | 是 | 否 |
| SCHEMA_VALIDATION_FAILED | 否 | 否 |
| DATA_CONFLICT | 否 | 是 |
| DATA_MISSING | 否 | 是 |
| PRODUCT_NOT_VERIFIED | 否 | 是 |
| PRODUCT_VERSION_STALE | 否 | 是 |
| ASSET_NOT_FOUND | 否 | 否 |
| CLAIM_BLOCKED | 否 | 是 |
| PLANNING_NOT_APPROVED | 否 | 是 |
| WORKFLOW_RETRY_EXCEEDED | 否 | 是 |
| BUDGET_EXCEEDED | 否 | 是 |
| TENANT_ACCESS_DENIED | 否 | 否 |
| STORAGE_ERROR / VIDEO_GENERATION_FAILED | 是/否 | 视情况 |

旧领域 code → 标准 code 的映射见 `backend/error_codes.py::ERROR_CODES`。

## 异常分类（provider）

`providers/errors.py::classify_http_error` 把 HTTP/网络/额度错误映射为 `provider_auth / permission / quota / timeout / connection / http / invalid_json / format / download`，每个类别带可行动提示（`errors.py::CATEGORY_HINTS`）。

## 原则

1. 用户能读懂原因（中文 message + hint）。
2. 开发能定位（error.details + 后端日志 request_id/耗时，不写密钥与完整响应）。
3. 可恢复错误标记 retryable，允许有限重试。
4. 不可恢复错误进入人工处理（requires_human_action）。
5. 不因模型异常跳过关键检查；不把失败标成成功；不丢原始文件与任务记录。
