"""渠道策略模板 + 复杂内容影响分析。"""
from __future__ import annotations

from tests.helpers import confirm_fields, make_pdf, upload


def test_channel_strategy_resolve_and_fallback():
    from backend.services import channel_strategy

    assert channel_strategy.resolve("douyin")["channel"] == "抖音"
    assert channel_strategy.resolve("抖音")["channel"] == "抖音"
    assert channel_strategy.resolve("xiaohongshu")["channel"] == "小红书"
    assert channel_strategy.resolve("unknown")["channel"] == "通用"
    assert "video_constraints" in channel_strategy.resolve("taobao")


LINES = [
    "Body Material: wool blend 70 percent",
    "Lining Material: brown canvas",
    "Dimensions: 280 mm x 240 mm x 120 mm",
    "Color: warm beige",
]
ITEMS = [
    {"field": "body_material", "block_id": 0,
     "quote": "Body Material: wool blend 70 percent", "value": "wool blend 70 percent"},
    {"field": "lining_material", "block_id": 0,
     "quote": "Lining Material: brown canvas", "value": "brown canvas"},
    {"field": "dimensions", "block_id": 0,
     "quote": "Dimensions: 280 mm x 240 mm x 120 mm", "value": "280 mm x 240 mm x 120 mm"},
    {"field": "color", "block_id": 0, "quote": "Color: warm beige", "value": "warm beige"},
]
FIELDS = {"body_material": "wool blend 70 percent", "lining_material": "brown canvas",
          "dimensions": "28 × 24 × 12 cm", "color": "warm beige"}
PLAN = {
    "theme": "新春质感好礼",
    "selling_points": [
        {"text": "羊毛混纺绒毛呢", "field": "body_material", "evidence": "wool blend 70 percent"},
        {"text": "暖米白配色", "field": "color", "evidence": "warm beige"},
    ],
    "copy": "春节走亲访友，暖米白双肩包刚刚好。",
    "visual": "暖色背景，突出绒毛呢纹理。",
    "image_prompt": "暖米白羊毛混纺双肩包，竖版商品主图。",
    "shots": [{"caption": "新春好礼", "angle": "front", "duration": 4}],
    "hashtags": ["春节年货节"],
}


def _confirmed(client, mock_llm, product_id: str):
    client.post("/api/v1/products", json={"id": product_id, "name": "测试双肩包"})
    source = upload(client, product_id, "规格.pdf", make_pdf(LINES))
    mock_llm["state"]["result"] = {"items": ITEMS}
    detail = client.post(f"/api/v1/products/{product_id}/imports/extract", json={
        "category_id": "BAG", "source_ids": [source["id"]],
    }).json()
    confirm_fields(client, detail["id"], FIELDS)


def test_planning_version_stores_channel_strategy(client, mock_llm):
    from tests.helpers import PNG_1X1

    _confirmed(client, mock_llm, "CHAN01")
    image = upload(client, "CHAN01", "正面.png", PNG_1X1, view_angle="front")
    mock_llm["state"]["result"] = PLAN
    task = client.post("/api/v1/planning/tasks", json={
        "product_id": "CHAN01", "scene": "抖音春节年货节", "channel": "抖音",
        "source_ids": [image["id"]],
    }).json()
    client.post(f"/api/v1/planning/tasks/{task['id']}/approve")
    versions = client.get(f"/api/v1/planning/tasks/{task['id']}/versions").json()
    strategy = versions[0]["strategy"]
    assert strategy["channel_strategy"]["channel"] == "抖音"
    assert "cta" in strategy["channel_strategy"]


def test_impact_analysis_reports_field_level_reasons(client, mock_llm):
    from tests.helpers import PNG_1X1

    _confirmed(client, mock_llm, "IMPACT01")
    image = upload(client, "IMPACT01", "正面.png", PNG_1X1, view_angle="front")
    mock_llm["state"]["result"] = PLAN
    task = client.post("/api/v1/planning/tasks", json={
        "product_id": "IMPACT01", "scene": "春节", "channel": "抖音", "source_ids": [image["id"]],
    }).json()
    client.post(f"/api/v1/planning/tasks/{task['id']}/approve")

    # 变更商品字段（颜色），通过批量接口产生新版本
    client.post("/api/v1/imports/batch", json={"rows": [{
        "product_id": "IMPACT01", "category_id": "BAG", "name": "测试双肩包",
        "fields": {**FIELDS, "color": "棕色"},
    }]})

    impact = client.get("/api/v1/data/products/IMPACT01/impact").json()
    assert impact["changed_fields"]
    assert any(ch["field"] == "color" for ch in impact["changed_fields"])
    affected = impact["affected_plans"]
    assert affected, "旧版本策划应被标记为受影响"
    # 卖点2绑定 color 字段，应出现在影响原因中
    reasons = " ".join(item for plan in affected for item in plan["impact_reasons"])
    assert "颜色" in reasons
