"""租户上下文与隔离辅助。

当前项目无登录系统，租户以 `X-Tenant-Id` 请求头注入，缺省为 `default`。
所有私有数据写入时记录 tenant_id，读取时按当前租户过滤；跨租户访问直接拒绝。
接入真实登录后，只需替换 `current()` 的来源，不改业务 SQL。
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from ..db import one, now, rows, session
from ..errors import not_found, tenant_denied

DEFAULT_TENANT = "default"
DEFAULT_OPERATOR = "user"

_tenant: ContextVar[str] = ContextVar("tenant_id", default=DEFAULT_TENANT)
_operator: ContextVar[str] = ContextVar("operator_id", default=DEFAULT_OPERATOR)


def current() -> str:
    return _tenant.get()


def set_current(tenant_id: str) -> str:
    tenant_id = (tenant_id or "").strip() or DEFAULT_TENANT
    _tenant.set(tenant_id)
    return tenant_id


def current_operator() -> str:
    return (_operator.get() or "").strip() or DEFAULT_OPERATOR


def set_operator(operator_id: str) -> str:
    operator_id = (operator_id or "").strip() or DEFAULT_OPERATOR
    _operator.set(operator_id)
    return operator_id


def resolve(tenant_id: str = "") -> str:
    """解析并校验租户，返回规范化 tenant id。"""
    tid = (tenant_id or "").strip() or DEFAULT_TENANT
    with session() as db:
        if one(db, "SELECT 1 FROM tenants WHERE id=?", (tid,)) is None:
            raise not_found(f"租户 {tid} 不存在")
    return tid


def create_tenant(name: str, tenant_id: str = "") -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        from ..errors import reject

        raise reject("租户名称不能为空")
    tid = (tenant_id or "").strip()
    stamp = now()
    if not tid:
        from uuid import uuid4

        tid = "t" + uuid4().hex[:10]
    with session() as db:
        if one(db, "SELECT 1 FROM tenants WHERE id=?", (tid,)):
            from ..errors import conflict

            raise conflict("租户编号已存在")
        db.execute(
            "INSERT INTO tenants(id,name,status,created_at,updated_at) VALUES(?,?,?,?,?)",
            (tid, name, "active", stamp, stamp),
        )
        return _tenant_row(one(db, "SELECT * FROM tenants WHERE id=?", (tid,)))


def _tenant_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "name": row["name"], "status": row["status"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def list_tenants() -> list[dict[str, Any]]:
    with session() as db:
        return [_tenant_row(row) for row in rows(db, "SELECT * FROM tenants ORDER BY id")]


def product_tenant(db, product_id: str) -> str:
    """返回商品所属租户；商品不存在时抛 404。"""
    row = one(db, "SELECT tenant_id FROM products WHERE id=?", (product_id,))
    if row is None:
        raise not_found("找不到该商品")
    return row["tenant_id"] or DEFAULT_TENANT


def require_product_access(db, product_id: str) -> str:
    """校验当前租户可访问商品，返回该商品 tenant_id；跨租户抛 403。"""
    owner = product_tenant(db, product_id)
    if owner != current():
        raise tenant_denied(f"商品 {product_id} 不属于当前租户")
    return owner
