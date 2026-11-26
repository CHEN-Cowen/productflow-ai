"""阶段 2：ExtractionRecord 与 DataIssue 独立化。"""
from __future__ import annotations

from tests.helpers import make_pdf, upload


def _extract(client, mock_llm, product_id: str, items: list[dict], lines: list[str]):
    source = upload(client, product_id, "规格.pdf", make_pdf(lines))
    mock_llm["state"]["result"] = {"items": items}
    response = client.post(f"/api/v1/products/{product_id}/imports/extract",
                           json={"category_id": "BAG", "source_ids": [source["id"]]})
    assert response.status_code == 201, response.text
    return response.json()


def test_extraction_records_are_independent(client, mock_llm):
    client.post("/api/v1/products", json={"id": "DH01", "name": "数据中心测试"})
    items = [
        {"field": "dimensions", "block_id": 0,
         "quote": "Dimensions: 280 mm x 240 mm x 120 mm", "value": "280 mm x 240 mm x 120 mm"},
        {"field": "color", "block_id": 0, "quote": "Color: warm beige", "value": "warm beige"},
    ]
    detail = _extract(client, mock_llm, "DH01", items,
                      ["Dimensions: 280 mm x 240 mm x 120 mm", "Color: warm beige"])
    extractions = client.get(f"/api/v1/imports/{detail['id']}/extractions").json()
    assert extractions, "提取记录应独立落表"
    mapped = {item["mapped_field"] for item in extractions}
    assert "dimensions" in mapped and "color" in mapped
    dim = next(item for item in extractions if item["mapped_field"] == "dimensions")
    assert dim["extracted_value"] == "28 × 24 × 12 cm"
    assert dim["source_file_id"]


def test_data_issues_independent_and_resolvable(client, mock_llm):
    client.post("/api/v1/products", json={"id": "DH02", "name": "异常测试"})
    # 只给一个字段，其余必填缺失 → 生成 missing 问题
    items = [{"field": "body_material", "block_id": 0,
              "quote": "Body Material: wool", "value": "wool"}]
    _extract(client, mock_llm, "DH02", items, ["Body Material: wool"])
    issues = client.get("/api/v1/products/DH02/issues").json()
    types = {item["issue_type"] for item in issues}
    assert "missing" in types

    target = next(item for item in issues if item["issue_type"] == "missing")
    resolved = client.post(f"/api/v1/issues/{target['id']}/resolve",
                           json={"resolution": "resolved"}).json()
    assert resolved["resolution_status"] == "resolved"
    open_issues = client.get("/api/v1/products/DH02/issues",
                             params={"resolution_status": "open"}).json()
    assert all(item["id"] != target["id"] for item in open_issues)
