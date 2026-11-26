"""统一工作流编排：独立步骤、事件与幂等键。

在 `workflow_runs`（任务级聚合）之上增加 `workflow_steps`（节点级：输入/输出快照、
错误、重试次数、起止时间）与 `workflow_events`（事件流）。对会产生外部费用的 AI
调用，用 `acquire(run_id, step_name, key)` 做幂等控制，避免重复执行、重复扣费。
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..db import dumps, loads, one, now, rows, session
from . import tenants


def begin(task_id: str, workflow_type: str, product_id: str, step_names: list[str]) -> str:
    run_id = uuid4().hex
    stamp = now()
    with session() as db:
        db.execute(
            "INSERT INTO workflow_runs(id,tenant_id,task_id,product_id,workflow_type,status,steps_json,"
            "error,error_code,created_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, tenants.current(), task_id, product_id, workflow_type, "running",
             dumps([{"name": name, "status": "pending", "detail": "", "at": ""} for name in step_names]),
             "", "", stamp, ""),
        )
        for name in step_names:
            db.execute(
                "INSERT INTO workflow_steps(id,tenant_id,run_id,name,status,input_snapshot,output_snapshot,"
                "error_code,error_message,retry_count,started_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (uuid4().hex, tenants.current(), run_id, name, "pending", "", "", "", "", 0, "", ""),
            )
    return run_id


def step(
    run_id: str,
    name: str,
    status: str,
    *,
    detail: str = "",
    input_snapshot: str = "",
    output_snapshot: str = "",
    error_code: str = "",
    error_message: str = "",
    retry_count: int = 0,
) -> None:
    stamp = now()
    with session() as db:
        db.execute(
            "UPDATE workflow_steps SET status=?, input_snapshot=?, output_snapshot=?, error_code=?, "
            "error_message=?, retry_count=?, completed_at=? WHERE run_id=? AND name=?",
            (status, input_snapshot[:2000], output_snapshot[:2000], error_code[:80],
             error_message[:500], int(retry_count), stamp if status in {"success", "failed"} else "",
             run_id, name),
        )
        # 兼容：同步更新 workflow_runs.steps_json（供旧读取路径）
        row = one(db, "SELECT steps_json FROM workflow_runs WHERE id=?", (run_id,))
        if row is not None:
            steps = loads(row["steps_json"], [])
            for item in steps:
                if item.get("name") == name:
                    item.update(status=status, detail=detail[:300], at=stamp)
                    break
            db.execute("UPDATE workflow_runs SET steps_json=? WHERE id=?", (dumps(steps), run_id))


def finish(run_id: str, status: str, error: str = "", error_code: str = "") -> None:
    with session() as db:
        db.execute(
            "UPDATE workflow_runs SET status=?, error=?, error_code=?, finished_at=? WHERE id=?",
            (status, error[:500], error_code[:80], now(), run_id),
        )


def event(run_id: str, event_type: str, *, step_name: str = "", payload: dict[str, Any] | None = None) -> None:
    with session() as db:
        db.execute(
            "INSERT INTO workflow_events(tenant_id,run_id,step_name,event_type,payload_json,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (tenants.current(), run_id, step_name, event_type, dumps(payload or {}), now()),
        )


def acquire(run_id: str, step_name: str, idempotency_key: str) -> bool:
    """幂等闸：同一 run + step + key 只放行一次，返回 True 表示可执行，False 表示已执行过。"""
    with session() as db:
        exists = one(
            db,
            "SELECT 1 FROM workflow_events WHERE run_id=? AND step_name=? AND event_type='executed' "
            "AND payload_json LIKE ?",
            (run_id, step_name, f"%{idempotency_key}%"),
        )
        if exists:
            return False
        db.execute(
            "INSERT INTO workflow_events(tenant_id,run_id,step_name,event_type,payload_json,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (tenants.current(), run_id, step_name, "executed",
             dumps({"idempotency_key": idempotency_key}), now()),
        )
        return True


def steps(run_id: str) -> list[dict[str, Any]]:
    with session() as db:
        return [dict(row) for row in rows(
            db, "SELECT * FROM workflow_steps WHERE run_id=? ORDER BY rowid", (run_id,))]


def events(run_id: str) -> list[dict[str, Any]]:
    with session() as db:
        return [
            {"id": row["id"], "step_name": row["step_name"], "event_type": row["event_type"],
             "payload": loads(row["payload_json"], {}), "created_at": row["created_at"]}
            for row in rows(db, "SELECT * FROM workflow_events WHERE run_id=? ORDER BY id", (run_id,))
        ]
