"""工作流执行记录：节点状态、错误与耗时。"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..db import dumps, loads, one, now, rows, session


def start(task_id: str, workflow_type: str, product_id: str, steps: list[str]) -> str:
    run_id = uuid4().hex
    with session() as db:
        db.execute(
            "INSERT INTO workflow_runs(id,task_id,product_id,workflow_type,status,steps_json,error,error_code,"
            "created_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (run_id, task_id, product_id, workflow_type, "running",
             dumps([{"name": name, "status": "pending", "detail": "", "at": ""} for name in steps]),
             "", "", now(), ""),
        )
    return run_id


def step(run_id: str, name: str, status: str, detail: str = "") -> None:
    with session() as db:
        row = one(db, "SELECT steps_json FROM workflow_runs WHERE id=?", (run_id,))
        if row is None:
            return
        steps = loads(row["steps_json"], [])
        for item in steps:
            if item.get("name") == name:
                item.update(status=status, detail=detail[:300], at=now())
                break
        db.execute("UPDATE workflow_runs SET steps_json=? WHERE id=?", (dumps(steps), run_id))


def finish(run_id: str, status: str, error: str = "", error_code: str = "") -> None:
    with session() as db:
        db.execute(
            "UPDATE workflow_runs SET status=?, error=?, error_code=?, finished_at=? WHERE id=?",
            (status, error[:500], error_code[:80], now(), run_id),
        )


def _run(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "task_id": row["task_id"], "product_id": row.get("product_id") or "",
        "workflow_type": row["workflow_type"], "status": row["status"],
        "steps": loads(row["steps_json"], []), "error": row["error"], "error_code": row["error_code"],
        "created_at": row["created_at"], "finished_at": row["finished_at"],
    }


def get(run_id: str) -> dict[str, Any]:
    with session() as db:
        row = one(db, "SELECT * FROM workflow_runs WHERE id=?", (run_id,))
        if row is None:
            from ..errors import not_found

            raise not_found("执行记录不存在")
        return _run(row)


def list_for_product(product_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with session() as db:
        return [_run(row) for row in rows(
            db, "SELECT * FROM workflow_runs WHERE product_id=? ORDER BY created_at DESC LIMIT ?",
            (product_id, limit))]


def list_for_task(task_id: str) -> list[dict[str, Any]]:
    with session() as db:
        return [_run(row) for row in rows(
            db, "SELECT * FROM workflow_runs WHERE task_id=? ORDER BY created_at DESC", (task_id,))]
