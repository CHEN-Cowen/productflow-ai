"""阶段 4/5：策划版本化、结构化输出与下发。"""
from __future__ import annotations

from tests.helpers import confirm_fields, error_code, make_pdf, upload

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
        {"text": "羊毛混纺绒毛呢，触感温暖", "field": "body_material", "evidence": "wool blend 70 percent"},
        {"text": "暖米白配色，百搭通勤", "field": "color", "evidence": "warm beige"},
    ],
    "copy": "春节走亲访友，一只暖米白双肩包刚刚好。",
    "visual": "暖色背景，突出绒毛呢纹理与牛皮细节。",
    "image_prompt": "暖米白羊毛混纺双肩包，棕色牛皮底托，暖金色五金，春节暖光氛围，竖版商品主图。",
    "shots": [
        {"caption": "新春好礼，暖米白双肩包", "angle": "front", "duration": 4},
        {"caption": "绒毛呢质感，触手可及", "angle": "side", "duration": 4},
        {"caption": "棕色牛皮底托，稳稳承托", "angle": "bottom", "duration": 4},
    ],
    "hashtags": ["春节年货节", "通勤双肩包"],
}


def _confirmed(client, mock_llm, product_id: str = "CP01") -> str:
    client.post("/api/v1/products", json={"id": product_id, "name": "策划测试双肩包"})
    source = upload(client, product_id, "规格.pdf", make_pdf(LINES))
    mock_llm["state"]["result"] = {"items": ITEMS}
    detail = client.post(f"/api/v1/products/{product_id}/imports/extract", json={
        "category_id": "BAG", "source_ids": [source["id"]],
    }).json()
    confirm_fields(client, detail["id"], FIELDS)
    return product_id


def _create_task(client, mock_llm, product_id: str, scene: str = "抖音春节年货节") -> dict:
    from tests.helpers import PNG_1X1

    image = upload(client, product_id, "01-正面.png", PNG_1X1, view_angle="front", review_status="confirmed")
    mock_llm["state"]["result"] = PLAN
    created = client.post("/api/v1/planning/tasks", json={
        "product_id": product_id, "scene": scene, "channel": "抖音",
        "audience": "约30岁女性", "source_ids": [image["id"]],
    })
    assert created.status_code == 201, created.text
    return created.json()


def test_planning_approve_version_output_dispatch(client, mock_llm):
    _confirmed(client, mock_llm)
    task = _create_task(client, mock_llm, "CP01")
    assert task["status"] == "draft"

    # 未确认时不能输出/下发
    assert error_code(client.get(f"/api/v1/planning/tasks/{task['id']}/output")) == "plan_not_confirmed"
    assert error_code(client.post(f"/api/v1/planning/tasks/{task['id']}/dispatch")) == "plan_not_confirmed"

    # 确认 → 生成不可变策划版本
    approved = client.post(f"/api/v1/planning/tasks/{task['id']}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "confirmed"

    versions = client.get(f"/api/v1/planning/tasks/{task['id']}/versions").json()
    assert len(versions) == 1
    assert versions[0]["approval_status"] == "approved"
    assert versions[0]["creative"]["theme"] == "新春质感好礼"

    # 结构化输出
    output = client.get(f"/api/v1/planning/tasks/{task['id']}/output").json()
    assert output["planning_task_id"] == task["id"]
    assert output["approval_status"] == "approved"
    assert output["selling_points"]
    assert output["video_plan"]["shots"]

    # 下发
    dispatched = client.post(f"/api/v1/planning/tasks/{task['id']}/dispatch").json()
    assert dispatched["dispatched"] is True
    assert dispatched["output"]["product_id"] == "CP01"


def test_cancel_task(client, mock_llm):
    _confirmed(client, mock_llm, "CP02")
    task = _create_task(client, mock_llm, "CP02", "日常商品展示")
    cancelled = client.post(f"/api/v1/planning/tasks/{task['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
