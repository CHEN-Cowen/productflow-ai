"""内置品类模板。模板字段可配置，新增品类只需新增模板，不改商品表结构。"""
from __future__ import annotations

from typing import Any

BAG: dict[str, Any] = {
    "category_id": "BAG",
    "category_name": "箱包",
    "attributes": [
        {"key": "body_material", "label": "包身材质", "type": "text", "unit": "",
         "required": True, "critical": True, "allowed_values": []},
        {"key": "lining_material", "label": "里料", "type": "text", "unit": "",
         "required": True, "critical": True, "allowed_values": []},
        {"key": "dimensions", "label": "尺寸", "type": "dimension", "unit": "cm",
         "required": True, "critical": True, "allowed_values": []},
        {"key": "weight", "label": "重量", "type": "weight", "unit": "g",
         "required": False, "critical": False, "allowed_values": []},
        {"key": "leather_trim", "label": "皮件", "type": "text", "unit": "",
         "required": False, "critical": True, "allowed_values": []},
        {"key": "hardware_color", "label": "五金颜色", "type": "text", "unit": "",
         "required": False, "critical": True, "allowed_values": []},
        {"key": "color", "label": "颜色", "type": "text", "unit": "",
         "required": True, "critical": True, "allowed_values": []},
        {"key": "selling_point", "label": "核心卖点", "type": "text", "unit": "",
         "required": False, "critical": False, "allowed_values": []},
    ],
}

APPAREL: dict[str, Any] = {
    "category_id": "APPAREL",
    "category_name": "服饰",
    "attributes": [
        {"key": "fabric", "label": "面料", "type": "text", "unit": "",
         "required": True, "critical": True, "allowed_values": []},
        {"key": "lining_material", "label": "里料", "type": "text", "unit": "",
         "required": False, "critical": False, "allowed_values": []},
        {"key": "size", "label": "尺码", "type": "enum", "unit": "",
         "required": True, "critical": True,
         "allowed_values": ["XS", "S", "M", "L", "XL", "均码"]},
        {"key": "color", "label": "颜色", "type": "text", "unit": "",
         "required": True, "critical": True, "allowed_values": []},
        {"key": "fit", "label": "版型", "type": "text", "unit": "",
         "required": False, "critical": False, "allowed_values": []},
        {"key": "care", "label": "洗涤方式", "type": "text", "unit": "",
         "required": False, "critical": False, "allowed_values": []},
        {"key": "selling_point", "label": "核心卖点", "type": "text", "unit": "",
         "required": False, "critical": False, "allowed_values": []},
    ],
}

BUILTIN = {"BAG": BAG, "APPAREL": APPAREL}


def attributes(schema: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list((schema or {}).get("attributes") or [])


def attribute_map(schema: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {item["key"]: item for item in attributes(schema)}


def find_attribute(schema: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    return attribute_map(schema).get(key)


def field_labels(schema: dict[str, Any] | None) -> dict[str, str]:
    return {item["key"]: item["label"] for item in attributes(schema)}


def normalize_schema(payload: dict[str, Any], category_id: str) -> dict[str, Any]:
    """校验并清洗自定义模板，保证字段结构一致。"""
    from .errors import reject

    raw = payload.get("attributes")
    if not isinstance(raw, list) or not raw:
        raise reject("品类模板至少需要一个字段")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise reject("模板字段格式不正确")
        key = str(item.get("key") or "").strip()
        label = str(item.get("label") or "").strip()
        if not key or not label or not key.replace("_", "").isalnum():
            raise reject("字段键需为字母数字下划线，标签不能为空")
        if key in seen:
            raise reject(f"字段键 {key} 重复", code="duplicate_field")
        seen.add(key)
        field_type = str(item.get("type") or "text")
        if field_type not in {"text", "number", "dimension", "weight", "enum"}:
            raise reject(f"字段 {key} 的类型不支持")
        allowed = item.get("allowed_values") or []
        if not isinstance(allowed, list):
            raise reject(f"字段 {key} 的允许值必须是数组")
        normalized.append({
            "key": key,
            "label": label,
            "type": field_type,
            "unit": str(item.get("unit") or ""),
            "required": bool(item.get("required")),
            "critical": bool(item.get("critical")),
            "allowed_values": [str(value) for value in allowed],
        })
    return {
        "category_id": category_id,
        "category_name": str(payload.get("category_name") or category_id).strip(),
        "attributes": normalized,
    }
