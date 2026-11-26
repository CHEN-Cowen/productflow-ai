"""AI 字段提取记录（ExtractionRecord）独立化。

与 `imports.candidates`（内联 JSON）并存：后者继续供旧接口与前端读取，本表用于
独立查询、追溯与统计（confidence/model_name/prompt_version/extraction_status）。
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..db import dumps, one, now, rows, session
from . import tenants


def bulk_create(
    db,
    *,
    import_job_id: str,
    product_id: str,
    records: list[dict[str, Any]],
    model_name: str = "",
    prompt_version: str = "",
) -> None:
    """在同一 session 内写入提取记录。records 为候选条目列表。"""
    stamp = now()
    for item in records:
        db.execute(
            "INSERT INTO extraction_records(id,tenant_id,import_job_id,source_file_id,product_id,raw_field,"
            "raw_value,mapped_field,extracted_value,confidence,source_location,model_name,prompt_version,"
            "extraction_status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uuid4().hex, tenants.current(), import_job_id, item.get("source_id") or "",
             product_id, item.get("raw_field") or item.get("field") or "",
             item.get("raw_value") or "", item.get("mapped_field") or item.get("field") or "",
             item.get("extracted_value") or item.get("value") or "",
             float(item.get("confidence") or 0), dumps(item.get("source_location") or item.get("locator") or {}),
             model_name, prompt_version, item.get("extraction_status") or "pending", stamp),
        )


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "import_job_id": row["import_job_id"], "source_file_id": row["source_file_id"],
        "product_id": row["product_id"], "raw_field": row["raw_field"], "raw_value": row["raw_value"],
        "mapped_field": row["mapped_field"], "extracted_value": row["extracted_value"],
        "confidence": row["confidence"], "source_location": row["source_location"],
        "model_name": row["model_name"], "prompt_version": row["prompt_version"],
        "extraction_status": row["extraction_status"], "created_at": row["created_at"],
    }


def list_for_import(import_job_id: str) -> list[dict[str, Any]]:
    with session() as db:
        return [_row_to_dict(row) for row in rows(
            db, "SELECT * FROM extraction_records WHERE tenant_id=? AND import_job_id=? ORDER BY rowid",
            (tenants.current(), import_job_id))]


def list_for_product(product_id: str) -> list[dict[str, Any]]:
    with session() as db:
        return [_row_to_dict(row) for row in rows(
            db, "SELECT * FROM extraction_records WHERE tenant_id=? AND product_id=? ORDER BY rowid",
            (tenants.current(), product_id))]
