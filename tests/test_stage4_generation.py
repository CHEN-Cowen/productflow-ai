from __future__ import annotations

import pytest

from backend import config
from tests.helpers import make_png, confirm_fields, error_code, make_pdf, upload

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
    "visual": "暖色背景，突出绒毛呢纹理。",
    "image_prompt": "暖米白羊毛混纺双肩包，棕色牛皮底托，暖金色五金，春节暖光，竖版商品主图。",
    "shots": [
        {"caption": "新春好礼，暖米白双肩包", "angle": "front", "duration": 4},
        {"caption": "绒毛呢质感，触手可及", "angle": "side", "duration": 4},
        {"caption": "棕色牛皮底托，稳稳承托", "angle": "bottom", "duration": 4},
    ],
    "hashtags": ["春节年货节"],
}


def _confirmed_plan(client, mock_llm, product_id: str = "GEN01") -> dict:
    client.post("/api/v1/products", json={"id": product_id, "name": "生产测试双肩包"})
    doc = upload(client, product_id, "规格.pdf", make_pdf(LINES))
    mock_llm["state"]["result"] = {"items": ITEMS}
    detail = client.post(f"/api/v1/products/{product_id}/imports/extract", json={
        "category_id": "BAG", "source_ids": [doc["id"]],
    }).json()
    confirm_fields(client, detail["id"], FIELDS)
    front = upload(client, product_id, "01-正面.png", make_png((248, 245, 240)), view_angle="front", review_status="confirmed")
    side = upload(client, product_id, "03-侧面.png", make_png((240, 236, 228)), view_angle="side", review_status="confirmed")
    mock_llm["state"]["result"] = PLAN
    plan = client.post(f"/api/v1/products/{product_id}/plans", json={
        "scene": "抖音春节年货节", "source_ids": [front["id"], side["id"]],
    }).json()
    assert client.post(f"/api/v1/plans/{plan['id']}/confirm").status_code == 200
    return {"plan": plan, "front": front, "side": side, "import": detail}


def test_image_generation_review_download_and_revise(client, mock_llm, mock_image):
    setup = _confirmed_plan(client, mock_llm)
    plan_id = setup["plan"]["id"]

    created = client.post(f"/api/v1/plans/{plan_id}/outputs/image", json={"ratio": "3:4", "count": 1})
    assert created.status_code == 201, created.text
    output = created.json()["outputs"][0]
    assert output["status"] == "pending"
    assert output["needs_review"] is False
    assert output["params"]["width"] == 1
    assert mock_image["calls"][0]["references"]

    preview = client.get(output["url"])
    assert preview.status_code == 200 and preview.content.startswith(b"\x89PNG")
    assert client.get(output["download_url"]).status_code == 409

    rejected = client.put(f"/api/v1/outputs/{output['id']}/review",
                          json={"approved": False, "note": "包型与参考图不一致"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert client.get(output["download_url"]).status_code == 409

    approved_output = client.post(f"/api/v1/plans/{plan_id}/outputs/image", json={}).json()["outputs"][0]
    approved = client.put(f"/api/v1/outputs/{approved_output['id']}/review",
                          json={"approved": True, "note": "与参考图一致"})
    assert approved.status_code == 200
    download = client.get(approved_output["download_url"])
    assert download.status_code == 200
    assert download.content.startswith(b"\x89PNG")
    assert download.headers["content-type"] == "image/png"

    duplicate_approve = client.put(f"/api/v1/outputs/{approved_output['id']}/review",
                                   json={"approved": True, "note": "再次通过"})
    assert duplicate_approve.status_code == 200

    revised = client.post(f"/api/v1/outputs/{output['id']}/revise", json={
        "prompt": "仅调整包型比例，保持暖米白与棕色皮件",
    })
    assert revised.status_code == 201, revised.text
    new_output = revised.json()
    assert new_output["attempt"] == 2
    assert new_output["source_output_id"] == output["id"]

    stats = client.get("/api/v1/stats").json()
    assert stats["outputs"]["image"] >= 3
    assert stats["review"]["approved"] >= 1
    assert stats["first_pass_approval"]["sample_size"] >= 2


@pytest.mark.skipif(not config.ffmpeg_path() or not config.ffmpeg_font(),
                    reason="需要 FFmpeg 与中文字体")
def test_video_composition_verify_and_delivery(client, mock_llm, mock_image):
    setup = _confirmed_plan(client, mock_llm, "GEN02")
    plan_id = setup["plan"]["id"]
    created = client.post(f"/api/v1/plans/{plan_id}/outputs/video", json={})
    assert created.status_code == 201, created.text
    output = created.json()["outputs"][0]
    assert output["kind"] == "video"
    assert output["status"] == "pending"
    params = output["params"]
    assert 10 <= params["duration"] <= 15
    assert (params["width"], params["height"]) == (720, 1280)
    assert params["codec"] == "h264"
    assert params["pix_fmt"] == "yuv420p"

    from backend.video import probe

    file_path = config.generated_dir() / output["filename"]
    assert file_path.is_file() and file_path.stat().st_size > 1000
    info = probe(file_path)
    assert (info["width"], info["height"]) == (720, 1280)

    assert client.get(output["download_url"]).status_code == 409
    approved = client.put(f"/api/v1/outputs/{output['id']}/review",
                          json={"approved": True, "note": "画幅、时长与字幕通过"})
    assert approved.status_code == 200
    download = client.get(output["download_url"])
    assert download.status_code == 200
    assert download.headers["content-type"] == "video/mp4"


def test_seedance_video_generation(client, mock_llm, mock_video):
    setup = _confirmed_plan(client, mock_llm, "GEN05")
    plan_id = setup["plan"]["id"]
    created = client.post(f"/api/v1/plans/{plan_id}/outputs/video", json={
        "provider": "seedance", "materials": [f"source:{setup['front']['id']}"],
    })
    assert created.status_code == 201, created.text
    output = created.json()["outputs"][0]
    assert output["kind"] == "video"
    assert output["status"] == "pending"
    assert output["provider"] == "volcengine-ark"
    assert output["params"]["resolution"] == "720p"
    assert output["params"]["duration"] == 12
    assert mock_video["calls"][0]["duration"] == 12
    assert mock_video["calls"][0]["references"]
    assert (config.generated_dir() / output["filename"]).is_file()


def test_seedance_invalid_provider_rejected(client, mock_llm):
    setup = _confirmed_plan(client, mock_llm, "GEN06")
    response = client.post(f"/api/v1/plans/{setup['plan']['id']}/outputs/video",
                           json={"provider": "unknown"})
    assert response.status_code == 422
    assert error_code(response) == "invalid_input"


def test_precise_impact_only_affected_fields(client, mock_llm, mock_image):
    setup = _confirmed_plan(client, mock_llm, "GEN07")
    plan_id = setup["plan"]["id"]
    output = client.post(f"/api/v1/plans/{plan_id}/outputs/image", json={}).json()["outputs"][0]
    client.put(f"/api/v1/outputs/{output['id']}/review", json={"approved": True, "note": "通过"})

    # 变更未被策划引用的字段 weight：不应影响该成品
    doc = upload(client, "GEN07", "v2.pdf", make_pdf([
        "BP01 Ladies Backpack Specification",
        "Body Material: wool blend 70 percent",
        "Lining Material: brown canvas",
        "Dimensions: 280 mm x 240 mm x 120 mm",
        "Color: warm beige",
        "Weight: 700 g",
    ]))
    mock_llm["state"]["result"] = {"items": ITEMS + [
        {"field": "weight", "block_id": 0, "quote": "Weight: 700 g", "value": "700 g"},
    ]}
    detail = client.post("/api/v1/products/GEN07/imports/extract", json={
        "category_id": "BAG", "source_ids": [doc["id"]],
    }).json()
    confirm_fields(client, detail["id"], {**FIELDS, "weight": "700 g"},
                   manual_basis={"weight": "实物称重"})

    unaffected = client.get("/api/v1/products/GEN07/outputs").json()[0]
    assert unaffected["needs_review"] is False

    # 再变更被引用的 body_material：应标记待复审
    doc2 = upload(client, "GEN07", "v3.pdf", make_pdf([
        "BP01 Ladies Backpack Specification",
        "Body Material: full grain leather",
        "Lining Material: brown canvas",
        "Dimensions: 280 mm x 240 mm x 120 mm",
        "Color: warm beige",
        "Weight: 700 g",
    ]))
    mock_llm["state"]["result"] = {"items": [
        dict(ITEMS[0], quote="Body Material: full grain leather", value="full grain leather"),
    ]}
    detail2 = client.post("/api/v1/products/GEN07/imports/extract", json={
        "category_id": "BAG", "source_ids": [doc2["id"]],
    }).json()
    confirm_fields(client, detail2["id"],
                   {**FIELDS, "body_material": "full grain leather", "weight": "700 g"},
                   manual_basis={"lining_material": "沿用", "dimensions": "沿用", "color": "沿用", "weight": "实物称重"})

    stale = client.get("/api/v1/products/GEN07/outputs").json()[0]
    assert stale["needs_review"] is True

    regen = client.post("/api/v1/products/GEN07/regenerate-affected").json()
    assert regen["affected_outputs"] >= 1
    assert any(item["field"] == "body_material" for item in regen["changed_fields"])


def test_new_product_version_pauses_old_outputs(client, mock_llm, mock_image):
    setup = _confirmed_plan(client, mock_llm, "GEN03")
    plan_id = setup["plan"]["id"]
    output = client.post(f"/api/v1/plans/{plan_id}/outputs/image", json={}).json()["outputs"][0]
    client.put(f"/api/v1/outputs/{output['id']}/review", json={"approved": True, "note": "通过"})

    changed_lines = list(LINES)
    changed_lines[1] = "Body Material: full grain leather"
    changed_items = [dict(ITEMS[0], quote="Body Material: full grain leather", value="full grain leather")]
    doc = upload(client, "GEN03", "v2.pdf", make_pdf(changed_lines))
    mock_llm["state"]["result"] = {"items": changed_items}
    detail = client.post("/api/v1/products/GEN03/imports/extract", json={
        "category_id": "BAG", "source_ids": [doc["id"]],
    }).json()
    confirm_fields(client, detail["id"], {**FIELDS, "body_material": "full grain leather"},
                   manual_basis={"lining_material": "沿用已确认资料", "dimensions": "沿用已确认尺寸",
                                 "color": "沿用已确认颜色"})

    stale = client.get(f"/api/v1/products/GEN03/outputs").json()[0]
    assert stale["needs_review"] is True
    assert client.get(stale["download_url"]).status_code == 409
    blocked_review = client.put(f"/api/v1/outputs/{stale['id']}/review",
                                json={"approved": True, "note": "强行通过"})
    assert blocked_review.status_code == 409
    assert error_code(blocked_review) == "stale_output"

    impact = client.get("/api/v1/products/GEN03/impact").json()
    assert any(item["field"] == "body_material" for item in impact["changed_fields"])
    assert impact["affected_outputs"] >= 1
    assert impact["affected_plans"][0]["id"] == plan_id

    library = client.get("/api/v1/library/outputs", params={"product_id": "GEN03"}).json()
    assert library["total"] >= 1
    assert library["items"][0]["needs_review"] is True


def test_image_provider_failure_is_recorded(client, mock_llm, mock_image):
    from backend.errors import provider_error

    setup = _confirmed_plan(client, mock_llm, "GEN04")
    mock_image["state"]["error"] = provider_error("quota", "生图额度不足", status=429,
                                                 hint="恢复额度后重试")
    response = client.post(f"/api/v1/plans/{setup['plan']['id']}/outputs/image", json={})
    assert response.status_code == 429
    assert error_code(response) == "provider_quota"
    runs = client.get(f"/api/v1/products/GEN04/runs").json()
    failed = [run for run in runs if run["status"] == "failed"]
    assert failed and failed[0]["error_code"] == "provider_quota"
