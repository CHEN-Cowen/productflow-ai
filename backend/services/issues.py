"""数据异常（DataIssue）独立化。

与 `imports.issues_json`（内联 JSON）并存，用于独立查询、解决与追溯。
支持 missing / conflict / duplicate / invalid / low_confidence / untraceable / unverified。
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..db import dumps, one, now, rows, session
from ..errors import conflict, not_found, reject
from . import tenants

SEVERITIES = {"low", "warning", "high", "critical"}


def bulk_create(db, *, product_id: str, issues: list[dict[str, Any]]) -> None:
    """同一 session 内写入数据异常。issues 为 build_issues 输出的条目。"""
    stamp = now()
    for item in issues:
        issue_type = item.get("type") or "invalid"
        severity = "high" if issue_type in {"conflict", "missing"} else "warning"
        db.execute(
            "INSERT INTO data_issues(id,tenant_id,product_id,attribute_key,issue_type,severity,"
            "source_records,issue_description,resolution_status,resolution_value,resolved_by,resolved_at,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uuid4().hex, tenants.current(), product_id, item.get("field") or "",
             issue_type, severity, dumps(item.get("candidates") or []),
             item.get("message") or "", "open", "", "", "", stamp),
        )


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "product_id": row["product_id"], "attribute_key": row["attribute_key"],
        "issue_type": row["issue_type"], "severity": row["severity"],
        "source_records": row["source_records"], "issue_description": row["issue_description"],
        "resolution_status": row["resolution_status"], "resolution_value": row["resolution_value"],
        "resolved_by": row["resolved_by"], "resolved_at": row["resolved_at"], "created_at": row["created_at"],
    }


def list_for_product(product_id: str, resolution_status: str = "") -> list[dict[str, Any]]:
    query = "SELECT * FROM data_issues WHERE tenant_id=? AND product_id=?"
    params: list[Any] = [tenants.current(), product_id]
    if resolution_status:
        query += " AND resolution_status=?"
        params.append(resolution_status)
    query += " ORDER BY rowid"
    with session() as db:
        return [_row_to_dict(row) for row in rows(db, query, params)]


def resolve(issue_id: str, resolution: str, resolved_by: str = "user") -> dict[str, Any]:
    if resolution not in {"merge", "keep", "resolved", "ignored"}:
        raise reject("异常处理方式无效")
    stamp = now()
    with session() as db:
        row = one(db, "SELECT * FROM data_issues WHERE id=? AND tenant_id=?",
                  (issue_id, tenants.current()))
        if row is None:
            raise not_found("数据异常不存在")
        if row["resolution_status"] != "open":
            raise conflict("该异常已处理")
        db.execute(
            "UPDATE data_issues SET resolution_status='resolved', resolution_value=?, resolved_by=?, resolved_at=? "
            "WHERE id=? AND tenant_id=?",
            (resolution, resolved_by, stamp, issue_id, tenants.current()),
        )
        return _row_to_dict(one(db, "SELECT * FROM data_issues WHERE id=?", (issue_id,)))
