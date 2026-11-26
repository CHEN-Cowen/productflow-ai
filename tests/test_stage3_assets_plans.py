from __future__ import annotations

from tests.helpers import confirm_fields, error_code, make_pdf, upload

LINES = [
    "BP01 Ladies Backpack Specification",
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


def _confirmed(client, mock_llm, product_id: str = "PLAN01") -> dict:
    client.post("/api/v1/products", json={"id": product_id, "name": "策划测试双肩包"})
    source = upload(client, product_id, "规格.pdf", make_pdf(LINES))
    mock_llm["state"]["result"] = {"items": ITEMS}
    detail = client.post(f"/api/v1/products/{product_id}/imports/extract", json={
        "category_id": "BAG", "source_ids": [source["id"]],
    }).json()
    confirm_fields(client, detail["id"], FIELDS)
    return client.get(f"/api/v1/products/{product_id}").json()


def test_asset_angle_persists_and_cross_product_guard(client):
    from tests.helpers import PNG_1X1

    client.post("/api/v1/products", json={"id": "ASSET01", "name": "素材测试"})
    image = upload(client, "ASSET01", "01-正面-1920.png", PNG_1X1)
    suggestion = client.post(f"/api/v1/products/ASSET01/sources/{image['id']}/suggest-angle").json()
    assert suggestion["angle"] == "front"

    updated = client.put(f"/api/v1/products/ASSET01/sources/{image['id']}", json={"view_angle": "back"})
    assert updated.status_code == 200
    assert client.get("/api/v1/products/ASSET01").json()["sources"][0]["view_angle"] == "back"

    invalid = client.put(f"/api/v1/products/ASSET01/sources/{image['id']}", json={"view_angle": "unknown"})
    assert invalid.status_code == 422

    client.post("/api/v1/products", json={"id": "ASSET02", "name": "另一个商品"})
    assert client.put(f"/api/v1/products/ASSET02/sources/{image['id']}", json={"view_angle": "front"}).status_code == 404


def test_six_angle_assets(client):
    from tests.helpers import make_png

    client.post("/api/v1/products", json={"id": "ASSET03", "name": "六视角"})
    angles = [("01-正面.png", "front"), ("02-背面.png", "back"), ("03-侧面.png", "side"),
              ("04-顶部.png", "top"), ("05-底部.png", "bottom"), ("06-内里.png", "interior")]
    for index, (name, angle) in enumerate(angles):
        image = upload(client, "ASSET03", name, make_png((250 - index, 248, 245)))
        response = client.put(f"/api/v1/products/ASSET03/sources/{image['id']}", json={"view_angle": angle})
        assert response.status_code == 200
    sources = client.get("/api/v1/products/ASSET03").json()["sources"]
    assert {item["view_angle"] for item in sources} == {angle for _, angle in angles}


def test_plan_create_edit_confirm_and_reuse(client, mock_llm):
    product = _confirmed(client, mock_llm)
    from tests.helpers import PNG_1X1

    image = upload(client, "PLAN01", "01-正面.png", PNG_1X1, view_angle="front")
    mock_llm["state"]["result"] = PLAN
    created = client.post("/api/v1/products/PLAN01/plans", json={
        "scene": "抖音春节年货节", "channel": "抖音", "audience": "约30岁女性",
        "content_type": "商品主图+短视频", "source_ids": [image["id"]],
    })
    assert created.status_code == 201, created.text
    plan = created.json()
    assert plan["status"] == "draft"
    assert plan["version_id"] == product["latest_version"]["id"]
    assert plan["blocked"] == []
    assert plan["content"]["theme"] == "新春质感好礼"
    assert plan["materials"][0]["angle_label"] == "正面"

    bad_content = {**PLAN, "copy": "100%纯羊毛，防水抗污，顶级品质。",
                   "selling_points": [{"text": "纯羊毛", "field": "body_material", "evidence": "100%羊毛"}]}
    edited = client.put(f"/api/v1/plans/{plan['id']}", json={"content": bad_content, "note": "加入宣传词"})
    assert edited.status_code == 200, edited.text
    blocked = edited.json()["blocked"]
    terms = {item["term"] for item in blocked}
    assert {"纯羊毛", "100%纯羊毛", "防水", "抗污", "顶级"} <= terms
    refused = client.post(f"/api/v1/plans/{plan['id']}/confirm")
    assert refused.status_code == 409
    assert error_code(refused) == "claim_blocked"

    good_content = {**PLAN, "copy": "春节走亲访友，暖米白双肩包刚刚好。"}
    assert client.put(f"/api/v1/plans/{plan['id']}", json={"content": good_content, "note": "删除无依据宣传"}).status_code == 200
    confirmed = client.post(f"/api/v1/plans/{plan['id']}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    read_back = client.get(f"/api/v1/plans/{plan['id']}").json()
    assert read_back["content"]["copy"] == good_content["copy"]

    mock_llm["state"]["result"] = {
        **PLAN, "theme": "日常通勤轻装",
        "copy": "日常通勤，轻装出发。",
        "shots": [
            {"caption": "日常通勤轻装出发", "angle": "front", "duration": 4},
            {"caption": "材质细节近看", "angle": "side", "duration": 4},
            {"caption": "整包收纳展示", "angle": "top", "duration": 4},
        ],
    }
    reused = client.post(f"/api/v1/plans/{plan['id']}/reuse", json={
        "scene": "日常商品展示", "content_type": "日常短视频",
    })
    assert reused.status_code == 201, reused.text
    new_plan = reused.json()
    assert new_plan["parent_plan_id"] == plan["id"]
    assert new_plan["source_ids"] == plan["source_ids"]
    assert new_plan["parent_plan"]["scene"] == "抖音春节年货节"

    stats = client.get("/api/v1/stats").json()
    assert stats["reuse"]["plans_with_parent"] >= 1
    assert stats["cost"]["status"] == "未采集"


def test_plan_requires_confirmed_version_and_angle(client, mock_llm):
    from tests.helpers import PNG_1X1

    client.post("/api/v1/products", json={"id": "PLAN02", "name": "未确认商品"})
    image = upload(client, "PLAN02", "正面.png", PNG_1X1, view_angle="front")
    rejected = client.post("/api/v1/products/PLAN02/plans", json={
        "scene": "测试场景", "source_ids": [image["id"]],
    })
    assert rejected.status_code == 422
    assert error_code(rejected) == "version_required"

    _confirmed(client, mock_llm, "PLAN03")
    untagged = upload(client, "PLAN03", "未标记.png", PNG_1X1)
    rejected = client.post("/api/v1/products/PLAN03/plans", json={
        "scene": "测试场景", "source_ids": [untagged["id"]],
    })
    assert rejected.status_code == 422
    assert "视角" in rejected.json()["detail"]["message"]
