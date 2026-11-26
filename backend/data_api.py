"""Data Hub 命名空间路由（/api/v1/data）。

与既有 /products、/imports 接口并存；这里提供任务书 §5 的规范化数据治理接口。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from .services import audit, catalog, data_hub, issues as issue_service

router = APIRouter(prefix="/api/v1/data", tags=["data-hub"])


class ResolveIn(BaseModel):
    resolution: str


@router.get("/products")
def list_products(search: str = "", category_id: str = "") -> dict[str, Any]:
    items = data_hub.list_products(search.strip(), category_id.strip().upper())
    return {"items": items, "total": len(items)}


@router.get("/products/{product_id}")
def product_detail(product_id: str) -> dict[str, Any]:
    return data_hub.get_product(product_id)


@router.post("/products/{product_id}/publish")
def publish(product_id: str) -> dict[str, Any]:
    return data_hub.publish(product_id)


@router.get("/products/{product_id}/versions")
def versions(product_id: str) -> list[dict[str, Any]]:
    return catalog.list_versions(product_id)


@router.get("/products/{product_id}/impact")
def impact(product_id: str) -> dict[str, Any]:
    return catalog.impact(product_id)


@router.get("/products/{product_id}/issues")
def issues(product_id: str, resolution_status: str = "") -> list[dict[str, Any]]:
    return issue_service.list_for_product(product_id, resolution_status)


@router.post("/issues/{issue_id}/resolve")
def resolve_issue(issue_id: str, body: ResolveIn) -> dict[str, Any]:
    return issue_service.resolve(issue_id, body.resolution)


@router.get("/products/{product_id}/audit")
def product_audit(product_id: str) -> list[dict[str, Any]]:
    return audit.list_for_entity("product", product_id)
