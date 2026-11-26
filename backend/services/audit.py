"""人工操作审计日志（AuditLog）。

所有关键事实的人工修改、确认、驳回、发布都必须记录：操作人、实体、动作、前后值与原因。
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..db import dumps, loads, one, now, rows, session
from . import tenants


def record(
    db,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    before_value: Any = "",
    after_value: Any = "",
    reason: str = "",
    operator_id: str = "user",
) -> str:
    log_id = uuid4().hex
    db.execute(
        "INSERT INTO audit_logs(id,tenant_id,operator_id,entity_type,entity_id,action,before_value,after_value,"
        "reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (log_id, tenants.current(), operator_id, entity_type, str(entity_id), action,
         dumps(before_value) if not isinstance(before_value, str) else before_value,
         dumps(after_value) if not isinstance(after_value, str) else after_value,
         reason[:500], now()),
    )
    return log_id


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "operator_id": row["operator_id"], "entity_type": row["entity_type"],
        "entity_id": row["entity_id"], "action": row["action"],
        "before_value": _unpack(row["before_value"]), "after_value": _unpack(row["after_value"]),
        "reason": row["reason"], "created_at": row["created_at"],
    }


def _unpack(value: str) -> Any:
    return loads(value, value)


def list_for_entity(entity_type: str, entity_id: str) -> list[dict[str, Any]]:
    with session() as db:
        return [_row_to_dict(row) for row in rows(
            db, "SELECT * FROM audit_logs WHERE tenant_id=? AND entity_type=? AND entity_id=? ORDER BY rowid DESC",
            (tenants.current(), entity_type, entity_id))]


def get(log_id: str) -> dict[str, Any]:
    with session() as db:
        row = one(db, "SELECT * FROM audit_logs WHERE id=? AND tenant_id=?", (log_id, tenants.current()))
        if row is None:
            from ..errors import not_found

            raise not_found("审计记录不存在")
        return _row_to_dict(row)
