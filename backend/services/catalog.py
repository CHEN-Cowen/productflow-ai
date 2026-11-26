"""商品主档、品类模板、SKU、原始资料与版本查询。"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from .. import config
from ..db import dumps, loads, one, now, rows, session
from ..errors import conflict, not_found, reject
from ..templates import field_labels, normalize_schema
from . import rules

ANGLES = {"front": "正面", "back": "背面", "side": "侧面", "top": "顶部", "bottom": "底部", "interior": "内里"}
PURPOSES = {"reference": "商品参考", "spec": "规格资料", "marketing": "营销素材"}
REVIEW_STATUS = {"pending": "待审核", "confirmed": "已确认", "rejected": "已废弃"}
PRODUCT_ID = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,31}$")
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _product(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "category_id": row.get("category_id") or "BAG",
        "brand": row.get("brand") or "",
        "origin": row.get("origin") or "",
        "description": row.get("description") or "",
        "status": row.get("status") or "draft",
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
    }


def category(db, category_id: str) -> dict[str, Any]:
    row = one(db, "SELECT * FROM categories WHERE id=?", (category_id,))
    if row is None:
        raise not_found("品类模板不存在")
    return {
        "id": row["id"],
        "name": row["name"],
        "version": row["version"],
        "schema": loads(row["schema_json"], {}),
        "is_builtin": bool(row["is_builtin"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_categories() -> list[dict[str, Any]]:
    with session() as db:
        return [category(db, row["id"]) for row in rows(db, "SELECT id FROM categories ORDER BY is_builtin DESC, id")]


def create_category(payload: dict[str, Any]) -> dict[str, Any]:
    category_id = str(payload.get("category_id") or "").strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,31}", category_id or ""):
        raise reject("品类编号需以字母开头，包含大写字母、数字或下划线")
    schema = normalize_schema(payload, category_id)
    stamp = now()
    with session() as db:
        if one(db, "SELECT 1 FROM categories WHERE id=?", (category_id,)):
            raise conflict("品类编号已存在")
        db.execute(
            "INSERT INTO categories(id,name,version,schema_json,is_builtin,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (category_id, schema["category_name"], 1, dumps(schema), 0, stamp, stamp),
        )
        db.execute(
            "INSERT INTO category_versions(category_id,version,schema_json,created_at) VALUES(?,?,?,?)",
            (category_id, 1, dumps(schema), stamp),
        )
        return category(db, category_id)


def update_category(category_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    schema = normalize_schema(payload, category_id)
    stamp = now()
    with session() as db:
        current = category(db, category_id)
        version = current["version"] + 1
        db.execute(
            "UPDATE categories SET name=?, version=?, schema_json=?, updated_at=? WHERE id=?",
            (schema["category_name"], version, dumps(schema), stamp, category_id),
        )
        db.execute(
            "INSERT INTO category_versions(category_id,version,schema_json,created_at) VALUES(?,?,?,?)",
            (category_id, version, dumps(schema), stamp),
        )
        return category(db, category_id)


def category_versions(category_id: str) -> list[dict[str, Any]]:
    with session() as db:
        category(db, category_id)
        return [
            {"version": row["version"], "schema": loads(row["schema_json"], {}), "created_at": row["created_at"]}
            for row in rows(db, "SELECT * FROM category_versions WHERE category_id=? ORDER BY version DESC", (category_id,))
        ]


def list_products(search: str = "", category_id: str = "") -> list[dict[str, Any]]:
    query = (
        "SELECT p.*, (SELECT COUNT(*) FROM sources s WHERE s.product_id=p.id) AS source_count, "
        "(SELECT COUNT(*) FROM product_versions v WHERE v.product_id=p.id) AS version_count, "
        "(SELECT COUNT(*) FROM plans pl WHERE pl.product_id=p.id) AS plan_count, "
        "(SELECT COUNT(*) FROM outputs o JOIN plans pl ON pl.id=o.plan_id WHERE pl.product_id=p.id) AS output_count "
        "FROM products p WHERE 1=1"
    )
    params: list[Any] = []
    if search:
        query += " AND (p.id LIKE ? OR p.name LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if category_id:
        query += " AND p.category_id=?"
        params.append(category_id)
    query += " ORDER BY p.updated_at DESC, p.id"
    with session() as db:
        return [
            {**_product(row), "source_count": row["source_count"], "version_count": row["version_count"],
             "plan_count": row["plan_count"], "output_count": row["output_count"]}
            for row in rows(db, query, params)
        ]


def create_product(payload: dict[str, Any]) -> dict[str, Any]:
    product_id = str(payload.get("id") or "").strip().upper()
    name = str(payload.get("name") or "").strip()
    if not PRODUCT_ID.fullmatch(product_id or ""):
        raise reject("商品编号需为 1-32 位大写字母、数字或短横线，且以字母或数字开头")
    if not name or len(name) > 120:
        raise reject("请输入 1-120 字的商品名称")
    category_id = str(payload.get("category_id") or "BAG").strip().upper()
    stamp = now()
    with session() as db:
        category(db, category_id)
        if one(db, "SELECT 1 FROM products WHERE id=?", (product_id,)):
            raise conflict("该商品编号已存在，请使用新编号或打开既有商品", code="duplicate_product")
        db.execute(
            "INSERT INTO products(id,name,category_id,brand,origin,description,status,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (product_id, name, category_id, str(payload.get("brand") or "").strip(),
             str(payload.get("origin") or "").strip(), str(payload.get("description") or "").strip(),
             "draft", stamp, stamp),
        )
        return product_detail(db, product_id)


def update_product(product_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with session() as db:
        current = one(db, "SELECT * FROM products WHERE id=?", (product_id,))
        if current is None:
            raise not_found("找不到该商品")
        name = str(payload.get("name", current["name"])).strip()
        if not name or len(name) > 120:
            raise reject("商品名称需为 1-120 字")
        category_id = str(payload.get("category_id", current["category_id"])).strip().upper()
        category(db, category_id)
        db.execute(
            "UPDATE products SET name=?, category_id=?, brand=?, origin=?, description=?, updated_at=? WHERE id=?",
            (name, category_id, str(payload.get("brand", current["brand"]) or "").strip(),
             str(payload.get("origin", current["origin"]) or "").strip(),
             str(payload.get("description", current["description"]) or "").strip(), now(), product_id),
        )
        return product_detail(db, product_id)


def _version(row: dict[str, Any], current_id: int | None) -> dict[str, Any]:
    return {
        "id": row["id"],
        "product_id": row["product_id"],
        "version": row["version"],
        "category": row["category"],
        "category_id": row.get("category_id") or row["category"],
        "sku": row.get("sku") or "",
        "fields": loads(row["fields"], {}),
        "provenance": loads(row.get("provenance_json"), {}),
        "note": row.get("note") or "",
        "created_by": row.get("created_by") or "user",
        "created_at": row.get("created_at") or "",
        "is_current": row["id"] == current_id,
    }


def latest_version(db, product_id: str) -> dict[str, Any] | None:
    row = one(db, "SELECT * FROM product_versions WHERE product_id=? ORDER BY version DESC, id DESC LIMIT 1", (product_id,))
    return _version(row, row["id"]) if row else None


def list_versions(product_id: str) -> list[dict[str, Any]]:
    with session() as db:
        if one(db, "SELECT 1 FROM products WHERE id=?", (product_id,)) is None:
            raise not_found("找不到该商品")
        latest = latest_version(db, product_id)
        return [_version(row, latest["id"] if latest else None) for row in rows(
            db, "SELECT * FROM product_versions WHERE product_id=? ORDER BY version DESC, id DESC", (product_id,))]


def get_version(version_id: int) -> dict[str, Any]:
    with session() as db:
        row = one(db, "SELECT * FROM product_versions WHERE id=?", (version_id,))
        if row is None:
            raise not_found("商品版本不存在")
        latest = latest_version(db, row["product_id"])
        return _version(row, latest["id"] if latest else None)


def version_diff(product_id: str, from_version: int | None = None, to_version: int | None = None) -> dict[str, Any]:
    with session() as db:
        versions = rows(db, "SELECT * FROM product_versions WHERE product_id=? ORDER BY version DESC, id DESC", (product_id,))
    if len(versions) < 2 and not (from_version and to_version):
        return {"from": None, "to": None, "changed": [], "message": "还没有两个版本可对比"}
    target = next((v for v in versions if v["version"] == to_version), versions[0])
    source = next((v for v in versions if v["version"] == from_version),
                  next((v for v in versions if v["version"] < target["version"]), None))
    if source is None:
        return {"from": None, "to": _version(target, None), "changed": []}
    labels = field_labels(category_schema(product_id))
    old = loads(source["fields"], {})
    new = loads(target["fields"], {})
    changed = [
        {"field": key, "label": labels.get(key, key), "from": old.get(key, ""), "to": new.get(key, "")}
        for key in sorted(set(old) | set(new)) if old.get(key, "") != new.get(key, "")
    ]
    return {
        "from": {"id": source["id"], "version": source["version"], "created_at": source.get("created_at") or ""},
        "to": {"id": target["id"], "version": target["version"], "created_at": target.get("created_at") or ""},
        "changed": changed,
    }


def category_schema(product_id: str) -> dict[str, Any]:
    with session() as db:
        row = one(db, "SELECT category_id FROM products WHERE id=?", (product_id,))
        if row is None:
            raise not_found("找不到该商品")
        return category(db, row["category_id"] or "BAG")["schema"]


def product_detail(db, product_id: str) -> dict[str, Any]:
    row = one(db, "SELECT * FROM products WHERE id=?", (product_id,))
    if row is None:
        raise not_found("找不到该商品")
    product = _product(row)
    schema = category(db, product["category_id"])["schema"]
    latest = latest_version(db, product_id)
    fields = latest["fields"] if latest else {}
    sources = [_source(item) for item in rows(
        db, "SELECT * FROM sources WHERE product_id=? ORDER BY created_at, rowid", (product_id,))]
    skus = [_sku(item) for item in rows(db, "SELECT * FROM skus WHERE product_id=? ORDER BY created_at", (product_id,))]
    plans_count = one(db, "SELECT COUNT(*) AS n FROM plans WHERE product_id=?", (product_id,))["n"]
    outputs_count = one(
        db, "SELECT COUNT(*) AS n FROM outputs o JOIN plans p ON p.id=o.plan_id WHERE p.product_id=?",
        (product_id,))["n"]
    pending = one(
        db, "SELECT COUNT(*) AS n FROM outputs o JOIN plans p ON p.id=o.plan_id "
            "WHERE p.product_id=? AND o.status='pending'", (product_id,))["n"]
    return {
        "product": product,
        "category": {"id": product["category_id"], "name": category(db, product["category_id"])["name"],
                     "version": category(db, product["category_id"])["version"], "schema": schema},
        "sources": sources,
        "skus": skus,
        "latest_version": latest,
        "versions": [_version(item, latest["id"] if latest else None) for item in rows(
            db, "SELECT * FROM product_versions WHERE product_id=? ORDER BY version DESC, id DESC", (product_id,))],
        "completeness": rules.completeness(schema, fields) if latest else {
            "required_total": len([a for a in schema["attributes"] if a.get("required")]),
            "required_filled": 0,
            "missing": [a["key"] for a in schema["attributes"] if a.get("required")],
            "complete": False},
        "counts": {"sources": len(sources), "plans": plans_count, "outputs": outputs_count, "pending_reviews": pending},
    }


def get_product(product_id: str) -> dict[str, Any]:
    with session() as db:
        return product_detail(db, product_id)


def create_sku(product_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    code = str(payload.get("sku_code") or "").strip().upper()
    if not code or len(code) > 40:
        raise reject("请填写 1-40 位 SKU 编码")
    attributes = payload.get("attributes") or {}
    if not isinstance(attributes, dict):
        raise reject("SKU 规格需为键值对象")
    stamp = now()
    with session() as db:
        if one(db, "SELECT 1 FROM products WHERE id=?", (product_id,)) is None:
            raise not_found("找不到该商品")
        if one(db, "SELECT 1 FROM skus WHERE product_id=? AND sku_code=?", (product_id, code)):
            raise conflict("该商品下 SKU 编码已存在")
        sku_id = uuid4().hex
        db.execute("INSERT INTO skus(id,product_id,sku_code,attributes_json,created_at) VALUES(?,?,?,?,?)",
                   (sku_id, product_id, code, dumps(attributes), stamp))
        return _sku(one(db, "SELECT * FROM skus WHERE id=?", (sku_id,)))


def list_skus(product_id: str) -> list[dict[str, Any]]:
    with session() as db:
        if one(db, "SELECT 1 FROM products WHERE id=?", (product_id,)) is None:
            raise not_found("找不到该商品")
        return [_sku(row) for row in rows(db, "SELECT * FROM skus WHERE product_id=? ORDER BY created_at", (product_id,))]


def _sku(row: dict[str, Any]) -> dict[str, Any]:
    return {"id": row["id"], "product_id": row["product_id"], "sku_code": row["sku_code"],
            "attributes": loads(row["attributes_json"], {}), "created_at": row["created_at"]}


def _source(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "product_id": row["product_id"], "sku_id": row.get("sku_id") or "",
        "name": row["name"], "mime": row["mime"], "size": row.get("size") or 0,
        "kind": row.get("kind") or ("image" if str(row["mime"]).startswith("image/") else "document"),
        "purpose": row.get("purpose") or "reference",
        "view_angle": row.get("view_angle") or "", "angle_label": ANGLES.get(row.get("view_angle") or "", ""),
        "review_status": row.get("review_status") or "pending",
        "status": row.get("status") or "stored", "created_at": row.get("created_at") or "",
        "url": f"/api/v1/products/{row['product_id']}/sources/{row['id']}",
    }


def detect_file(content: bytes, filename: str = "") -> tuple[str, str]:
    """根据文件内容识别类型，返回 (mime, kind)。不信任客户端扩展名。"""
    if content.startswith(b"%PDF-"):
        return "application/pdf", "document"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "image"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "image"
    if content.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile:
            raise reject("压缩包格式损坏或不是 Excel/Word 文件", code="unsupported_file") from None
        if "xl/workbook.xml" in names:
            return XLSX_MIME, "document"
        if "word/document.xml" in names:
            return DOCX_MIME, "document"
    raise reject("仅支持 PDF、XLSX、DOCX、PNG、JPEG 文件", hint="旧版 .doc/.xls 请另存为 .docx/.xlsx 后上传",
                 code="unsupported_file")


def upload_source(
    product_id: str,
    filename: str,
    content: bytes,
    *,
    sku_id: str = "",
    purpose: str = "reference",
    view_angle: str = "",
    review_status: str = "pending",
) -> dict[str, Any]:
    if not content:
        raise reject("文件为空")
    if len(content) > config.MAX_UPLOAD_BYTES:
        raise reject("文件大小不能超过 10 MB", code="file_too_large")
    mime, kind = detect_file(content, filename)
    if purpose not in PURPOSES:
        raise reject("请选择素材用途")
    if view_angle and view_angle not in ANGLES:
        raise reject("请选择有效的视角")
    if review_status not in REVIEW_STATUS:
        raise reject("审核状态无效")
    safe_name = Path(str(filename or "原始资料").replace("\\", "/")).name[:180] or "原始资料"
    digest = hashlib.sha256(content).hexdigest()
    source_id = uuid4().hex
    suffix = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg",
              XLSX_MIME: ".xlsx", DOCX_MIME: ".docx"}.get(mime, "")
    path = config.uploads_dir() / (source_id + suffix)
    stamp = now()
    with session() as db:
        if one(db, "SELECT 1 FROM products WHERE id=?", (product_id,)) is None:
            raise not_found("找不到该商品")
        if sku_id and one(db, "SELECT 1 FROM skus WHERE id=? AND product_id=?", (sku_id, product_id)) is None:
            raise reject("SKU 不属于该商品", code="invalid_sku")
        duplicate = one(db, "SELECT id FROM sources WHERE product_id=? AND sha256=?", (product_id, digest))
        if duplicate:
            raise conflict("该资料已上传过，请勿重复上传", hint=f"已有资料 ID：{duplicate['id']}",
                           code="duplicate_source")
        path.write_bytes(content)
        try:
            db.execute(
                "INSERT INTO sources(id,product_id,sku_id,name,mime,size,sha256,kind,purpose,view_angle,"
                "review_status,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (source_id, product_id, sku_id or None, safe_name, mime, len(content), digest, kind,
                 purpose, view_angle, review_status, "stored", stamp),
            )
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return _source(one(db, "SELECT * FROM sources WHERE id=?", (source_id,)))


def list_sources(product_id: str, *, angle: str = "", review_status: str = "", search: str = "") -> list[dict[str, Any]]:
    query = "SELECT * FROM sources WHERE product_id=?"
    params: list[Any] = [product_id]
    if angle:
        query += " AND view_angle=?"
        params.append(angle)
    if review_status:
        query += " AND review_status=?"
        params.append(review_status)
    if search:
        query += " AND name LIKE ?"
        params.append(f"%{search}%")
    query += " ORDER BY created_at, rowid"
    with session() as db:
        return [_source(row) for row in rows(db, query, params)]


def get_source(product_id: str, source_id: str) -> dict[str, Any]:
    with session() as db:
        row = one(db, "SELECT * FROM sources WHERE id=? AND product_id=?", (source_id, product_id))
        if row is None:
            raise not_found("找不到该资料，或资料不属于该商品")
        return _source(row)


def source_file(product_id: str, source_id: str) -> tuple[dict[str, Any], Path]:
    with session() as db:
        row = one(db, "SELECT * FROM sources WHERE id=? AND product_id=?", (source_id, product_id))
        if row is None:
            raise not_found("找不到该资料，或资料不属于该商品")
        source = _source(row)
    path = next(iter(config.uploads_dir().glob(source_id + ".*")), None)
    if path is None:
        # 兼容历史版本：旧资料可能按无扩展名保存
        legacy = config.uploads_dir() / source_id
        path = legacy if legacy.is_file() else None
    if path is None or not path.is_file():
        raise not_found("资料文件缺失，请重新上传")
    if path.stat().st_size != source["size"]:
        raise conflict("资料文件大小与记录不一致，请重新上传", code="file_mismatch")
    return source, path


def list_all_sources(*, product_id: str = "", angle: str = "", review_status: str = "",
                     search: str = "") -> list[dict[str, Any]]:
    query = ("SELECT s.*, p.name AS product_name FROM sources s JOIN products p ON p.id=s.product_id WHERE 1=1")
    params: list[Any] = []
    if product_id:
        query += " AND s.product_id=?"
        params.append(product_id)
    if angle:
        query += " AND s.view_angle=?"
        params.append(angle)
    if review_status:
        query += " AND s.review_status=?"
        params.append(review_status)
    if search:
        query += " AND (s.name LIKE ? OR p.name LIKE ? OR s.product_id LIKE ?)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    query += " ORDER BY s.created_at DESC, s.rowid DESC"
    with session() as db:
        return [dict(item) | {"url": f"/api/v1/products/{item['product_id']}/sources/{item['id']}"}
                for item in [dict(row) for row in db.execute(query, params).fetchall()]]


def update_source(product_id: str, source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with session() as db:
        current = one(db, "SELECT * FROM sources WHERE id=? AND product_id=?", (source_id, product_id))
        if current is None:
            raise not_found("找不到该资料，或资料不属于该商品")
        angle = payload.get("view_angle", current["view_angle"])
        purpose = payload.get("purpose", current["purpose"])
        status = payload.get("review_status", current["review_status"])
        sku_id = payload.get("sku_id", current.get("sku_id") or "")
        if angle and angle not in ANGLES:
            raise reject("请选择有效的视角")
        if purpose not in PURPOSES:
            raise reject("请选择素材用途")
        if status not in REVIEW_STATUS:
            raise reject("审核状态无效")
        if sku_id and one(db, "SELECT 1 FROM skus WHERE id=? AND product_id=?", (sku_id, product_id)) is None:
            raise reject("SKU 不属于该商品", code="invalid_sku")
        db.execute(
            "UPDATE sources SET view_angle=?, purpose=?, review_status=?, sku_id=? WHERE id=? AND product_id=?",
            (angle or "", purpose, status, sku_id or None, source_id, product_id),
        )
        return _source(one(db, "SELECT * FROM sources WHERE id=?", (source_id,)))


ANGLE_KEYWORDS = [
    ("front", ("正面", "前面", "front")),
    ("back", ("背面", "后面", "反面", "back")),
    ("side", ("侧面", "侧身", "side")),
    ("top", ("顶部", "上面", "俯视", "top")),
    ("bottom", ("底部", "底面", "鞋底", "bottom", "sole")),
    ("interior", ("内里", "内部", "内衬", "interior", "inner", "lining")),
]


def suggest_angle(filename: str) -> dict[str, Any]:
    """按文件名给出视角建议，必须由人工应用后才写入数据库。"""
    name = filename.lower()
    for angle, keywords in ANGLE_KEYWORDS:
        if any(keyword in name for keyword in keywords):
            return {"angle": angle, "label": ANGLES[angle], "method": "filename_rule",
                    "note": "根据文件名给出建议，请人工确认后保存"}
    return {"angle": "", "label": "", "method": "filename_rule", "note": "文件名未包含视角关键词，请人工选择"}


def impact(product_id: str) -> dict[str, Any]:
    with session() as db:
        if one(db, "SELECT 1 FROM products WHERE id=?", (product_id,)) is None:
            raise not_found("找不到该商品")
        versions = rows(db, "SELECT * FROM product_versions WHERE product_id=? ORDER BY version DESC, id DESC LIMIT 2", (product_id,))
        if not versions:
            return {"product_id": product_id, "changed_fields": [], "affected_plans": [], "affected_outputs": 0}
        current = versions[0]
        previous = versions[1] if len(versions) > 1 else None
        labels = field_labels(category(db, current.get("category_id") or current["category"])["schema"])
        old = loads(previous["fields"], {}) if previous else {}
        new = loads(current["fields"], {})
        changed = [
            {"field": key, "label": labels.get(key, key), "from": old.get(key, ""), "to": new.get(key, "")}
            for key in sorted(set(old) | set(new)) if old.get(key, "") != new.get(key, "")
        ]
        plans = rows(db, "SELECT * FROM plans WHERE product_id=? ORDER BY created_at DESC", (product_id,))
        affected = []
        for plan in plans:
            if plan["version_id"] == current["id"]:
                continue
            outputs = rows(db, "SELECT id, kind, status FROM outputs WHERE plan_id=?", (plan["id"],))
            affected.append({"id": plan["id"], "scene": plan["scene"], "version_id": plan["version_id"],
                             "outputs": outputs})
        return {
            "product_id": product_id,
            "current_version": {"id": current["id"], "version": current["version"]},
            "previous_version": {"id": previous["id"], "version": previous["version"]} if previous else None,
            "changed_fields": changed,
            "affected_plans": affected,
            "affected_outputs": sum(len(item["outputs"]) for item in affected),
            "note": "旧版本成品会暂停下载并标记待复审" if affected else "暂无受影响的旧版本成品",
        }
