"""阶段 3：商品发布入库（事务 + 规则校验 + 审计日志）与 data 命名空间。"""
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
FIELDS = {
    "body_material": "wool blend 70 percent",
    "lining_material": "brown canvas",
    "dimensions": "28 × 24 × 12 cm",
    "color": "warm beige",
}


def _confirm(client, mock_llm, product_id: str):
    source = upload(client, product_id, "规格.pdf", make_pdf(LINES))
    mock_llm["state"]["result"] = {"items": ITEMS}
    detail = client.post(f"/api/v1/products/{product_id}/imports/extract",
                         json={"category_id": "BAG", "source_ids": [source["id"]]}).json()
    confirm_fields(client, detail["id"], FIELDS)


def test_publish_requires_version(client):
    client.post("/api/v1/products", json={"id": "PUB01", "name": "未确认商品"})
    response = client.post("/api/v1/data/products/PUB01/publish")
    assert response.status_code == 422
    assert error_code(response) == "version_required"


def test_publish_success_and_audit(client, mock_llm):
    client.post("/api/v1/products", json={"id": "PUB02", "name": "发布测试包"})
    _confirm(client, mock_llm, "PUB02")
    published = client.post("/api/v1/data/products/PUB02/publish")
    assert published.status_code == 200, published.text
    # data 命名空间读取
    detail = client.get("/api/v1/data/products/PUB02").json()
    assert detail["product"]["status"] == "verified"
    audit = client.get("/api/v1/data/products/PUB02/audit").json()
    assert any(item["action"] == "publish" for item in audit)
    # 重复发布被拒绝
    again = client.post("/api/v1/data/products/PUB02/publish")
    assert error_code(again) == "already_published"


def test_data_namespace_products_list(client):
    client.post("/api/v1/products", json={"id": "PUB03", "name": "列表商品"})
    body = client.get("/api/v1/data/products").json()
    assert body["total"] >= 1
    assert any(item["id"] == "PUB03" for item in body["items"])
