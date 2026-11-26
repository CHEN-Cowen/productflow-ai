"""确定性规则：单位归一、必填/类型校验、重复与冲突识别、宣传用词事实校验。"""
from __future__ import annotations

import re
from typing import Any

NUMBER_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(mm|毫米|cm|厘米|m|米|kg|千克|公斤|g|克|mg|英寸|inch)?", re.I)
PERCENT_MATERIAL = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*([\u4e00-\u9fa5A-Za-z]{1,8})")

CM_UNITS = {"mm": 0.1, "毫米": 0.1, "cm": 1, "厘米": 1, "m": 100, "米": 100, "英寸": 2.54, "inch": 2.54}
G_UNITS = {"mg": 0.001, "g": 1, "克": 1, "kg": 1000, "千克": 1000, "公斤": 1000}

# 无事实依据时必须阻止进入确认策划的宣传词
CLAIM_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("纯羊毛", ("纯羊毛", "100%羊毛", "全羊毛")),
    ("100%羊毛", ("100%羊毛", "纯羊毛", "全羊毛")),
    ("全羊毛", ("全羊毛", "100%羊毛", "纯羊毛")),
    ("防水", ("防水", "防泼水", "防水处理")),
    ("防泼水", ("防泼水", "防水")),
    ("抗污", ("抗污", "防污")),
    ("防污", ("防污", "抗污")),
    ("真皮", ("真皮", "头层牛皮")),
    ("头层牛皮", ("头层牛皮",)),
    ("可水洗", ("可水洗", "水洗")),
]

ABSOLUTE_TERMS = ("最好", "最佳", "最高级", "第一品牌", "顶级", "绝对", "国家级", "唯一")


def _fmt(number: float) -> str:
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def canonicalize(attr: dict[str, Any], raw: str) -> dict[str, Any]:
    """把原始值转成标准值与可比较数值。

    返回 {value, unit, numbers, valid, error}。dimension 统一到 cm，weight 统一到 g。
    """
    text = _clean(raw)
    field_type = attr.get("type", "text")
    if not text:
        return {"value": "", "unit": attr.get("unit", ""), "numbers": [], "valid": False,
                "error": "值为空"}
    if field_type in {"dimension", "weight"}:
        unit_map = CM_UNITS if field_type == "dimension" else G_UNITS
        default_unit = attr.get("unit") or ("cm" if field_type == "dimension" else "g")
        numbers: list[float] = []
        last_unit = ""
        for match in NUMBER_UNIT.finditer(text):
            number = float(match.group(1))
            unit = (match.group(2) or "").lower()
            if unit:
                last_unit = unit
            elif last_unit:
                unit = last_unit
            else:
                unit = default_unit.lower()
            factor = unit_map.get(unit)
            if factor is None:
                return {"value": text, "unit": "", "numbers": [], "valid": False,
                        "error": f"不支持的单位 {unit}"}
            numbers.append(number * factor)
        if not numbers:
            return {"value": text, "unit": "", "numbers": [], "valid": False,
                    "error": "缺少数字与单位"}
        if field_type == "dimension":
            value = " × ".join(_fmt(number) for number in numbers) + " cm"
            return {"value": value, "unit": "cm", "numbers": [round(n, 2) for n in numbers],
                    "valid": True, "error": ""}
        grams = round(numbers[0], 2)
        return {"value": f"{_fmt(grams)} g", "unit": "g", "numbers": [grams],
                "valid": True, "error": ""}
    if field_type == "number":
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return {"value": text, "unit": attr.get("unit", ""), "numbers": [], "valid": False,
                    "error": "不是有效数字"}
        number = float(match.group(0))
        return {"value": _fmt(number), "unit": attr.get("unit", ""), "numbers": [number],
                "valid": True, "error": ""}
    if field_type == "enum":
        allowed = attr.get("allowed_values") or []
        if allowed and text not in allowed:
            return {"value": text, "unit": "", "numbers": [], "valid": False,
                    "error": "不在允许值范围：" + "、".join(allowed)}
        return {"value": text, "unit": "", "numbers": [], "valid": True, "error": ""}
    return {"value": text, "unit": attr.get("unit", ""), "numbers": [], "valid": True, "error": ""}


def canonical_key(attr: dict[str, Any], canonical: dict[str, Any]) -> tuple:
    if attr.get("type") in {"dimension", "weight", "number"}:
        return tuple(round(number, 2) for number in canonical.get("numbers") or [])
    return (canonical.get("value", ""),)


def values_equal(attr: dict[str, Any], left: dict[str, Any], right: dict[str, Any]) -> bool:
    return canonical_key(attr, left) == canonical_key(attr, right)


def supported_values(attr: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen: set[tuple] = set()
    for item in candidates:
        key = canonical_key(attr, item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _issue(field: str, label: str, issue_type: str, message: str,
           items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": f"{field}:{issue_type}",
        "field": field,
        "label": label,
        "type": issue_type,
        "message": message,
        "candidates": [
            {key: item.get(key) for key in ("source_id", "source_name", "value", "raw_value", "locator", "quote")}
            for item in (items or [])
        ],
        "resolution": "",
    }


def build_issues(schema: dict[str, Any], candidates: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """对候选字段做缺失、类型、冲突和重复检查。"""
    issues: list[dict[str, Any]] = []
    for attr in schema.get("attributes") or []:
        key, label = attr["key"], attr["label"]
        items = [item for item in candidates.get(key, []) if isinstance(item, dict)]
        valid = [item for item in items if item.get("valid")]
        invalid = [item for item in items if not item.get("valid")]
        if not items:
            if attr.get("required"):
                issues.append(_issue(key, label, "missing", "必填字段待补充"))
            continue
        if invalid:
            messages = "；".join(sorted({item.get("error") or "格式不正确" for item in invalid}))
            issues.append(_issue(key, label, "invalid", f"提取值格式不正确：{messages}", invalid))
        if not valid:
            continue
        groups = supported_values(attr, valid)
        if len(groups) > 1:
            issues.append(_issue(
                key, label, "conflict",
                "不同来源给出不一致的值：" + " / ".join(group["value"] for group in groups),
                valid,
            ))
        elif len(valid) > 1:
            issues.append(_issue(
                key, label, "duplicate", "多份资料给出相同值，可选择合并或保留",
                valid,
            ))
    return issues


def validate_fields(schema: dict[str, Any], fields: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    """确认入库前校验：必填、允许值、类型、未知字段。返回 (标准值, 错误列表)。"""
    errors: list[str] = []
    normalized: dict[str, str] = {}
    attrs = {attr["key"]: attr for attr in schema.get("attributes") or []}
    unknown = sorted(set(fields) - set(attrs))
    if unknown:
        errors.append("存在模板外字段：" + "、".join(unknown))
    for key, attr in attrs.items():
        raw = fields.get(key, "")
        text = _clean(raw) if isinstance(raw, str) else ""
        if not text:
            if attr.get("required"):
                errors.append(f"{attr['label']}不能为空")
            continue
        if len(text) > 300:
            errors.append(f"{attr['label']}不能超过 300 字")
            continue
        canonical = canonicalize(attr, text)
        if not canonical["valid"]:
            errors.append(f"{attr['label']}：{canonical['error']}")
            continue
        normalized[key] = canonical["value"]
    return normalized, errors


def completeness(schema: dict[str, Any], fields: dict[str, str]) -> dict[str, Any]:
    required = [attr for attr in schema.get("attributes") or [] if attr.get("required")]
    missing = [attr["key"] for attr in required if not _clean(fields.get(attr["key"], ""))]
    return {
        "required_total": len(required),
        "required_filled": len(required) - len(missing),
        "missing": missing,
        "complete": not missing,
    }


def content_texts(content: dict[str, Any]) -> list[tuple[str, str]]:
    texts: list[tuple[str, str]] = []
    for key in ("theme", "copy", "visual", "image_prompt"):
        value = content.get(key)
        if isinstance(value, str) and value:
            texts.append((key, value))
    for index, point in enumerate(content.get("selling_points") or []):
        if isinstance(point, dict) and point.get("text"):
            texts.append((f"selling_points[{index}]", str(point["text"])))
    for index, shot in enumerate(content.get("shots") or []):
        if isinstance(shot, dict) and shot.get("caption"):
            texts.append((f"shots[{index}]", str(shot["caption"])))
    for tag in content.get("hashtags") or []:
        if isinstance(tag, str):
            texts.append(("hashtags", tag))
    return texts


def check_claims(content: dict[str, Any], fields: dict[str, str], labels: dict[str, str]) -> list[dict[str, Any]]:
    """阻止无事实依据的宣传词和绝对化用语进入已确认策划。"""
    facts = " ".join(_clean(value) for value in fields.values() if isinstance(value, str))
    compact_facts = re.sub(r"\s+", "", facts).lower()
    blocked: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(term: str, kind: str, message: str, where: str) -> None:
        if (term, kind) in seen:
            return
        seen.add((term, kind))
        blocked.append({"term": term, "type": kind, "message": message, "where": where})

    for where, text in content_texts(content):
        for term, supports in CLAIM_RULES:
            if term not in text:
                continue
            if any(re.sub(r"\s+", "", support).lower() in compact_facts for support in supports):
                continue
            add(term, "unsupported_claim", f"“{term}”缺少已确认商品事实支持", where)
        for term in ABSOLUTE_TERMS:
            if term in text:
                add(term, "absolute_claim", f"“{term}”属于绝对化宣传用语，需人工删除", where)
        for number, material in PERCENT_MATERIAL.findall(text):
            material = material.strip()
            patterns = (
                f"{number}%{material}",
                f"{material}{number}%",
            )
            if not any(re.sub(r"\s+", "", pattern).lower() in compact_facts for pattern in patterns):
                add(f"{number}%{material}", "unsupported_claim",
                    f"“{number}%{material}”与已确认成分不一致", where)

    for index, point in enumerate(content.get("selling_points") or []):
        if not isinstance(point, dict):
            continue
        field = str(point.get("field") or "")
        evidence = _clean(point.get("evidence") or "")
        text = _clean(point.get("text") or "")
        if field not in fields:
            add(f"卖点{index + 1}", "ungrounded_point",
                f"卖点未关联已确认字段：{labels.get(field, field or '空')}", f"selling_points[{index}]")
            continue
        fact = _clean(fields.get(field, ""))
        if not evidence:
            add(f"卖点{index + 1}", "ungrounded_point",
                f"卖点缺少字段 {labels.get(field, field)} 的原文依据", f"selling_points[{index}]")
        elif evidence not in fact and fact not in evidence:
            add(f"卖点{index + 1}", "ungrounded_point",
                f"卖点依据与字段 {labels.get(field, field)} 的值不一致", f"selling_points[{index}]")
        if not text:
            add(f"卖点{index + 1}", "ungrounded_point", "卖点文案为空", f"selling_points[{index}]")
    return blocked
