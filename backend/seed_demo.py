"""演示数据：BP01 六视角参考图、样例规格、已确认版本、春节策划与真实 12 秒视频。

用法：
    python -m backend.seed_demo            # 创建/补齐演示数据并合成视频
    python -m backend.seed_demo --no-video # 不合成视频
    python -m backend.seed_demo --image    # 若已配置生图模型，额外生成一张真实商品图

说明：BP01 样例字段依据复试题资料整理，页面与版本备注会明确标记为样例，不冒充供应商原件核验事实。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
from uuid import uuid4

from . import config, db
from .db import dumps, loads, now, one, rows, session
from .errors import ApiError
from .services import catalog, generation, imports, planning

SAMPLE_FACTS = {
    "body_material": "羊毛 70%、聚酯纤维 30% 混纺",
    "lining_material": "同色系棕色帆布",
    "dimensions": "28 × 24 × 12 cm",
    "weight": "650 g",
    "leather_trim": "棕色牛皮",
    "hardware_color": "暖金色金属",
    "color": "暖米白",
}
SAMPLE_NOTE = "演示样例：依据复试题资料整理，正式使用前须以供应商原件核验"
ANGLE_KEYWORDS = [
    ("front", ("正面", "front")), ("back", ("背面", "back")),
    ("side", ("侧面", "side")), ("top", ("顶部", "top")),
    ("bottom", ("底部", "bottom")), ("interior", ("内里", "interior")),
]


def _source_digest(product_id: str, digest: str) -> dict | None:
    with session() as db:
        return one(db, "SELECT * FROM sources WHERE product_id=? AND sha256=?", (product_id, digest))


def add_source(product_id: str, name: str, content: bytes, mime: str, kind: str,
               *, angle: str = "", purpose: str = "reference", review_status: str = "confirmed") -> dict:
    digest = hashlib.sha256(content).hexdigest()
    existing = _source_digest(product_id, digest)
    if existing:
        return existing
    suffix = {"image/png": ".png", "image/jpeg": ".jpg", "application/pdf": ".pdf"}.get(mime, "")
    source_id = uuid4().hex
    (config.uploads_dir() / (source_id + suffix)).write_bytes(content)
    with session() as db:
        db.execute(
            "INSERT INTO sources(id,product_id,sku_id,name,mime,size,sha256,kind,purpose,view_angle,"
            "review_status,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (source_id, product_id, None, name, mime, len(content), digest, kind, purpose,
             angle, review_status, "stored", now()),
        )
        return one(db, "SELECT * FROM sources WHERE id=?", (source_id,))


def _reference_images() -> list[tuple[str, bytes, str]]:
    archive = config.BASE_DIR / "BP01六张高清图.zip"
    found: list[tuple[str, bytes, str]] = []
    if archive.is_file():
        with zipfile.ZipFile(archive) as bundle:
            for entry in bundle.infolist():
                if entry.is_dir() or not entry.filename.lower().endswith((".png", ".jpg", ".jpeg")):
                    continue
                name = Path(entry.filename).name
                content = bundle.read(entry)
                found.append((name, content, "image/png" if name.lower().endswith(".png") else "image/jpeg"))
    if not found:
        for path in sorted(config.references_dir().glob("*")):
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                found.append((path.name, path.read_bytes(),
                              "image/png" if path.suffix.lower() == ".png" else "image/jpeg"))
    return found


def _angle_for(name: str) -> str:
    lower = name.lower()
    for angle, keywords in ANGLE_KEYWORDS:
        if any(keyword in lower for keyword in keywords):
            return angle
    return ""


def ensure_bp01() -> dict:
    with session() as db:
        product = one(db, "SELECT * FROM products WHERE id='BP01'")
    if product is None:
        catalog.create_product({
            "id": "BP01", "name": "BP01 女士双肩包", "category_id": "BAG",
            "origin": "越南",
            "description": "演示样例：商品事实来自复试题资料整理，待供应商原件核验。",
        })
    else:
        with session() as db:
            db.execute(
                "UPDATE products SET category_id='BAG', "
                "origin=CASE WHEN origin='' THEN '越南' ELSE origin END, "
                "description=CASE WHEN description='' THEN ? ELSE description END, "
                "updated_at=? WHERE id='BP01'",
                ("演示样例：商品事实来自复试题资料整理，待供应商原件核验。", now()),
            )

    sample_source = None
    for name, content, mime in _reference_images():
        angle = _angle_for(name)
        add_source("BP01", name, content, mime, "image",
                   angle=angle, purpose="reference", review_status="confirmed")
    images = [item for item in catalog.list_sources("BP01") if item["kind"] == "image" and item["view_angle"]]
    print(f"[seed] BP01 参考图：{len(images)} 张已标注视角")

    with session() as db:
        existing = one(db, "SELECT id FROM sources WHERE product_id='BP01' AND name LIKE 'BP01-样例规格%'")
    if existing is None:
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "BP01样例资料"
        sheet.append(["字段", "值", "说明"])
        for key, label in (
            ("body_material", "包身材质"), ("lining_material", "里料"), ("dimensions", "尺寸"),
            ("weight", "重量"), ("leather_trim", "皮件"), ("hardware_color", "五金颜色"), ("color", "颜色"),
        ):
            sheet.append([label, SAMPLE_FACTS[key], SAMPLE_NOTE])
        buffer = io.BytesIO()
        workbook.save(buffer)
        sample_source = add_source(
            "BP01", "BP01-样例规格.xlsx", buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "document",
            purpose="spec", review_status="confirmed",
        )
        config.samples_dir().joinpath("BP01-样例规格.xlsx").write_bytes(buffer.getvalue())
        print("[seed] 已生成样例规格 Excel（标注为非供应商原件）")
    else:
        with session() as db:
            sample_source = one(db, "SELECT * FROM sources WHERE id=?", (existing["id"],))

    with session() as db:
        version = one(db, "SELECT * FROM product_versions WHERE product_id='BP01' ORDER BY version DESC LIMIT 1")
    if version is None:
        with session() as db:
            version_id = imports._create_version(
                db, "BP01", "BAG", SAMPLE_FACTS,
                {
                    key: {
                        "source_id": sample_source["id"] if sample_source else "",
                        "source_name": sample_source["name"] if sample_source else "样例规格",
                        "locator": {"kind": "xlsx", "sheet": "BP01样例资料", "row": index + 2},
                        "quote": value,
                        "raw_value": value,
                        "standard_value": value,
                        "method": "sample_seed",
                        "status": "sample",
                        "basis": SAMPLE_NOTE,
                    }
                    for index, (key, value) in enumerate(SAMPLE_FACTS.items())
                },
                "BP01-BEIGE", SAMPLE_NOTE, "seed",
            )
            db.execute("UPDATE product_versions SET note=? WHERE id=?",
                       (SAMPLE_NOTE, version_id))
        print("[seed] 已创建 BP01 样例确认版本 v1")
    else:
        print(f"[seed] BP01 已有版本 v{version['version']}，保留不覆盖")
    return catalog.get_product("BP01")


def _plan_content(product: dict, daily: bool = False) -> dict:
    fields = product["latest_version"]["fields"]
    labels = {attr["key"]: attr["label"] for attr in product["category"]["schema"]["attributes"]}
    picks = [(key, fields.get(key, "")) for key in ("body_material", "color", "dimensions", "hardware_color")
             if fields.get(key)]
    if not picks:
        picks = [(key, value) for key, value in fields.items()][:2]
    points = []
    for index, (key, value) in enumerate(picks[:3]):
        text = {
            "body_material": "羊毛混纺绒毛呢，触感温润",
            "color": "暖米白配色，通勤百搭",
            "dimensions": "28×24×12 cm 容量，日常轻装",
            "hardware_color": "暖金色五金，细节提气",
        }.get(key, f"{labels.get(key, key)}：{value}")
        points.append({"text": text, "field": key, "evidence": value[:40]})
    if daily:
        return {
            "theme": "日常通勤轻装",
            "selling_points": points,
            "copy": "日常通勤，轻装出发。暖米白双肩包，装下一天所需。",
            "visual": "清晨自然光下的通勤场景，突出包型比例与暖米白质感。",
            "image_prompt": "暖米白羊毛混纺女士双肩包，棕色牛皮底托，暖金色五金，清晨自然光，简洁通勤场景，9:16 竖版。",
            "shots": [
                {"caption": "日常通勤，轻装出发", "angle": "front", "duration": 4},
                {"caption": "暖米白绒毛呢近看", "angle": "side", "duration": 4},
                {"caption": "棕色牛皮底托细节", "angle": "bottom", "duration": 4},
            ],
            "hashtags": ["日常通勤", "双肩包"],
        }
    return {
        "theme": "新春暖礼·暖米白双肩包",
        "selling_points": points,
        "copy": "春节走亲访友，暖米白双肩包刚刚好。",
        "visual": "暖色春节氛围，突出羊毛混纺纹理、棕色牛皮底托与暖金色五金。",
        "image_prompt": "暖米白羊毛混纺女士双肩包，棕色牛皮整块底托，暖金色五金，春节暖光氛围，竖版商品主图，9:16。",
        "shots": [
            {"caption": "新春好礼，暖米白双肩包", "angle": "front", "duration": 4},
            {"caption": "羊毛混纺绒毛呢质感", "angle": "side", "duration": 4},
            {"caption": "棕色牛皮底托与暖金五金", "angle": "bottom", "duration": 4},
        ],
        "hashtags": ["春节年货节", "通勤双肩包"],
    }


def ensure_plan(product: dict, daily: bool = False) -> dict | None:
    scene = "日常商品展示" if daily else "抖音春节年货节"
    with session() as db:
        existing = one(db, "SELECT id FROM plans WHERE product_id='BP01' AND scene=? ORDER BY created_at LIMIT 1", (scene,))
    if existing:
        print(f"[seed] 已存在策划「{scene}」，保留")
        return planning.get_plan(existing["id"])
    sources = [item for item in catalog.list_sources("BP01") if item["kind"] == "image" and item["view_angle"]]
    if not sources:
        print("[seed] 缺少已标注视角的参考图，跳过策划")
        return None
    content = _plan_content(product, daily)
    if daily:
        main_plan = ensure_plan(product, daily=False)
        if not main_plan:
            return None
        created = planning.reuse_plan(main_plan["id"], {
            "scene": scene, "channel": "抖音", "audience": "通勤女性",
            "content_type": "日常短视频", "manual": True, "content": content,
        })
    else:
        created = planning.create_plan("BP01", {
            "scene": scene, "channel": "抖音", "audience": "约30岁女性",
            "content_type": "商品主图+短视频",
            "source_ids": [item["id"] for item in sources],
            "manual": True, "content": content,
        })
    if created["status"] != "confirmed":
        created = planning.confirm_plan(created["id"])
        print(f"[seed] 策划「{scene}」已人工确认")
    return created


def ensure_video(plan: dict) -> None:
    with session() as db:
        existing = one(db, "SELECT id FROM outputs WHERE plan_id=? AND kind='video' LIMIT 1", (plan["id"],))
    if existing:
        print("[seed] 已存在视频成品，保留")
        return
    try:
        result = generation.generate_video(plan["id"], {})
        output = result["outputs"][0]
        print(f"[seed] 已合成真实视频：{output['filename']} · {output['params'].get('duration')} 秒 · "
              f"{output['params'].get('width')}x{output['params'].get('height')}")
    except ApiError as error:
        print(f"[seed] 视频合成失败（{error.code}）：{error.message}；{error.hint}")


def ensure_apparel() -> None:
    with session() as db:
        existing = one(db, "SELECT id FROM products WHERE id='AP01'")
    if existing is None:
        catalog.create_product({
            "id": "AP01", "name": "AP01 女士针织开衫", "category_id": "APPAREL",
            "description": SAMPLE_NOTE,
        })
    with session() as db:
        version = one(db, "SELECT id FROM product_versions WHERE product_id='AP01' LIMIT 1")
    if version is None:
        with session() as db:
            imports._create_version(
                db, "AP01", "APPAREL",
                {"fabric": "棉 80%、羊毛 20%", "lining_material": "无", "size": "M",
                 "color": "米白", "fit": "宽松", "care": "冷水手洗"},
                {key: {"method": "sample_seed", "status": "sample", "basis": SAMPLE_NOTE,
                       "standard_value": value, "source_id": "", "source_name": "样例资料",
                       "locator": {}, "quote": ""}
                 for key, value in {"fabric": "棉 80%、羊毛 20%", "size": "M", "color": "米白"}.items()},
                "AP01-M", SAMPLE_NOTE, "seed",
            )
        print("[seed] 已创建第二品类样例商品 AP01")
    try:
        catalog.create_sku("AP01", {"sku_code": "AP01-M", "attributes": {"size": "M", "color": "米白"}})
        print("[seed] 已创建 SKU AP01-M")
    except Exception:  # noqa: BLE001 - 已存在则跳过
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="ProductFlow AI 演示数据")
    parser.add_argument("--no-video", action="store_true", help="不合成视频")
    parser.add_argument("--image", action="store_true", help="配置生图模型时额外生成一张真实商品图")
    args = parser.parse_args()
    config.configure()
    db.init_db()
    product = ensure_bp01()
    plan = ensure_plan(product)
    ensure_plan(product, daily=True)
    ensure_apparel()
    if plan and not args.no_video:
        ensure_video(plan)
    if plan and args.image:
        try:
            result = generation.generate_image(plan["id"], {"ratio": "3:4", "count": 1})
            print(f"[seed] 已生成真实商品图候选 {len(result['outputs'])} 张，待审核")
        except ApiError as error:
            print(f"[seed] 生图未完成（{error.code}）：{error.message}；{error.hint}")
    print("[seed] 完成。启动后端与前端后，打开 #/products/BP01 查看演示链路。")


if __name__ == "__main__":
    main()
