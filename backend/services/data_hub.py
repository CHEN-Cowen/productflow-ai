"""商品数据中心（Data Hub）聚合服务：发布入库与查询。

发布在数据库事务内执行，校验任务书 §5.7 的六条规则；任何一条不满足都不置 verified。
"""
from __future__ import annotations

from typing import Any

from ..db import dumps, loads, now, one, rows, session
from ..errors import conflict, not_found, reject
from ..templates import attributes
from . import audit, catalog, issues, rules, tenants


def _publish_rules(db, product: dict[str, Any], version: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    schema = catalog.category(db, version.get("category_id") or version["category"])["schema"]
    attrs = {attr["key"]: attr for attr in attributes(schema)}
    fields = loads(version["fields"], {})

    # 规则 1：合法商品身份
    if not (product["name"] or "").strip():
        errors.append("商品名称为空")

    # 规则 2：必填属性完整
    completeness = rules.completeness(schema, fields)
    if not completeness["complete"]:
        missing = [attrs.get(key, {}).get("label", key) for key in completeness["missing"]]
        errors.append("必填字段缺失：" + "、".join(missing))

    # 规则 3 & 5：已填写的关键属性必须确认且可追溯（可选的空字段不阻断）
    provenance = loads(version.get("provenance_json"), {})
    untraced: list[str] = []
    for key, attr in attrs.items():
        if not attr.get("critical"):
            continue
        if not (fields.get(key) or "").strip():
            continue
        prov = provenance.get(key)
        if not prov or prov.get("status") != "verified":
            untraced.append(attr.get("label", key))
    if untraced:
        errors.append("关键属性未确认或不可追溯：" + "、".join(untraced))

    # 规则 4：关键冲突必须解决
    open_high = issues.list_for_product(product["id"], resolution_status="open")
    blocking = [item for item in open_high if item["severity"] in {"high", "critical"}]
    if blocking:
        errors.append(f"仍有 {len(blocking)} 个未解决的关键数据异常")

    return fields, errors


def publish(product_id: str, operator_id: str = "user") -> dict[str, Any]:
    with session() as db:
        product = one(db, "SELECT * FROM products WHERE id=? AND tenant_id=?",
                      (product_id, tenants.current()))
        if product is None:
            raise not_found("找不到该商品")
        if (product.get("status") or "") == "verified":
            raise conflict("商品已是已发布状态", code="already_published")
        version = one(db, "SELECT * FROM product_versions WHERE tenant_id=? AND product_id=? "
                          "ORDER BY version DESC, id DESC LIMIT 1", (tenants.current(), product_id))
        if version is None:
            raise reject("请先确认商品版本，再发布", code="version_required")
        fields, errors = _publish_rules(db, product, version)
        if errors:
            raise reject("；".join(errors[:5]), code="publish_blocked")
        before = product.get("status") or "draft"
        db.execute("UPDATE products SET status='verified', updated_at=? WHERE id=? AND tenant_id=?",
                   (now(), product_id, tenants.current()))
        audit.record(db, entity_type="product", entity_id=product_id, action="publish",
                     before_value=before, after_value="verified",
                     reason=f"发布商品版本 {version['version']}", operator_id=operator_id)
    return get_product(product_id)


def get_product(product_id: str) -> dict[str, Any]:
    with session() as db:
        return catalog.product_detail(db, product_id)


def list_products(search: str = "", category_id: str = "") -> list[dict[str, Any]]:
    return catalog.list_products(search, category_id)


def list_versions(product_id: str) -> list[dict[str, Any]]:
    return catalog.list_versions(product_id)


def open_issues(product_id: str) -> list[dict[str, Any]]:
    return issues.list_for_product(product_id, resolution_status="open")
