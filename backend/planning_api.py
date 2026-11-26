"""Content Planning 命名空间路由（/api/v1/planning）。

提供任务书 §7 的策划任务、审核、版本与下发接口；商品事实约束沿用 planning 服务。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .services import planning

router = APIRouter(prefix="/api/v1/planning", tags=["content-planning"])


class TaskIn(BaseModel):
    product_id: str
    scene: str
    channel: str = "抖音"
    audience: str = ""
    content_type: str = "商品主图+短视频"
    source_ids: list[str] = Field(default_factory=list)
    version_id: int | None = None
    manual: bool = False
    content: dict[str, Any] | None = None


class ModifyIn(BaseModel):
    content: dict[str, Any]
    note: str = ""


@router.get("/tasks")
def list_tasks(product_id: str = "") -> list[dict[str, Any]]:
    if product_id:
        return planning.list_plans(product_id)
    return planning.list_all_plans()


@router.post("/tasks", status_code=201)
def create_task(body: TaskIn) -> dict[str, Any]:
    payload = body.model_dump(exclude={"product_id"})
    return planning.create_plan(body.product_id, payload)


@router.get("/tasks/{task_id}")
def task_detail(task_id: str) -> dict[str, Any]:
    return planning.get_plan(task_id)


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str) -> dict[str, Any]:
    return planning.cancel_plan(task_id)


@router.get("/tasks/{task_id}/review")
def task_review(task_id: str) -> dict[str, Any]:
    return planning.get_plan(task_id)


@router.post("/tasks/{task_id}/approve")
def approve_task(task_id: str) -> dict[str, Any]:
    return planning.confirm_plan(task_id)


@router.post("/tasks/{task_id}/modify")
def modify_task(task_id: str, body: ModifyIn) -> dict[str, Any]:
    return planning.update_plan(task_id, body.model_dump())


@router.get("/tasks/{task_id}/versions")
def task_versions(task_id: str) -> list[dict[str, Any]]:
    return planning.list_plan_versions(task_id)


@router.get("/tasks/{task_id}/versions/{version_id}")
def task_version(task_id: str, version_id: int) -> dict[str, Any]:
    return planning.get_plan_version(task_id, version_id)


@router.get("/tasks/{task_id}/output")
def task_output(task_id: str) -> dict[str, Any]:
    return planning.planning_output(task_id)


@router.post("/tasks/{task_id}/dispatch")
def dispatch_task(task_id: str) -> dict[str, Any]:
    return planning.dispatch(task_id)
