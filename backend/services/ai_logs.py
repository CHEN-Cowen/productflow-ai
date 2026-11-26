"""AI 模型调用统一审计日志。

记录 provider/model/model_version/prompt_version/输入输出摘要/token/cost/duration/
status/error/retry/idempotency_key。业务层任何模型调用都应经过这里，便于回答：
“用了哪个模型、是否产生费用、能否重试、是否需要人工介入”。
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..db import dumps, loads, one, now, rows, session
from . import tenants


def record(
    *,
    provider: str,
    model: str = "",
    model_version: str = "",
    prompt_version: str = "",
    input_summary: str = "",
    output_summary: str = "",
    token_usage: dict[str, Any] | None = None,
    cost: float = 0.0,
    duration_ms: int = 0,
    status: str,
    error_code: str = "",
    error: str = "",
    retry_count: int = 0,
    idempotency_key: str = "",
    request_id: str = "",
    task_id: str = "",
    step_name: str = "",
) -> str:
    log_id = uuid4().hex
    with session() as db:
        db.execute(
            "INSERT INTO ai_execution_logs(id,tenant_id,task_id,step_name,provider,model,model_version,"
            "prompt_version,input_summary,output_summary,token_usage_json,cost,duration_ms,status,"
            "error_code,error,retry_count,idempotency_key,request_id,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (log_id, tenants.current(), task_id, step_name, provider, model, model_version,
             prompt_version, _clip(input_summary), _clip(output_summary),
             dumps(token_usage or {}), float(cost or 0), int(duration_ms or 0), status,
             error_code[:80], _clip(error), int(retry_count or 0), idempotency_key, request_id, now()),
        )
    return log_id


def _clip(text: str) -> str:
    return (text or "")[:500]


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "tenant_id": row["tenant_id"], "task_id": row["task_id"],
        "step_name": row["step_name"], "provider": row["provider"], "model": row["model"],
        "model_version": row["model_version"], "prompt_version": row["prompt_version"],
        "input_summary": row["input_summary"], "output_summary": row["output_summary"],
        "token_usage": loads(row["token_usage_json"], {}), "cost": row["cost"],
        "duration_ms": row["duration_ms"], "status": row["status"], "error_code": row["error_code"],
        "error": row["error"], "retry_count": row["retry_count"],
        "idempotency_key": row["idempotency_key"], "request_id": row["request_id"],
        "created_at": row["created_at"],
    }


def list_for_task(task_id: str) -> list[dict[str, Any]]:
    with session() as db:
        return [_row_to_dict(row) for row in rows(
            db, "SELECT * FROM ai_execution_logs WHERE tenant_id=? AND task_id=? ORDER BY created_at DESC",
            (tenants.current(), task_id))]


def get(log_id: str) -> dict[str, Any]:
    with session() as db:
        row = one(db, "SELECT * FROM ai_execution_logs WHERE id=? AND tenant_id=?",
                  (log_id, tenants.current()))
        if row is None:
            from ..errors import not_found

            raise not_found("AI 调用记录不存在")
        return _row_to_dict(row)
