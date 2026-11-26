from __future__ import annotations

from tests.helpers import (
    confirm_fields,
    error_code,
    make_docx,
    make_pdf,
    make_xlsx,
    upload,
)

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

FIELDS = {
    "body_material": "wool blend 70 percent",
    "lining_material": "brown canvas",
    "dimensions": "28 × 24 × 12 cm",
    "color": "warm beige",
}


def _extract(client, mock_llm, product_id: str, lines: list[str], items: list[dict],
             name: str = "规格.pdf", category: str = "BAG"):
    source = upload(client, product_id, name, make_pdf(lines))
    mock_llm["state"]["result"] = {"items": items}
    response = client.post(f"/api/v1/products/{product_id}/imports/extract",
                           json={"category_id": category, "source_ids": [source["id"]]})
    assert response.status_code == 201, response.text
    return source, response.json()


def test_pdf_extract_confirm_and_provenance(client, mock_llm):
    client.post("/api/v1/products", json={"id": "GOV01", "name": "治理测试"})
    _, detail = _extract(client, mock_llm, "GOV01", LINES, ITEMS)
    assert detail["candidates"]["dimensions"][0]["value"] == "28 × 24 × 12 cm"
    assert detail["candidates"]["dimensions"][0]["locator"]["page"] == 1
    assert detail["issues"] == []

    result = confirm_fields(client, detail["id"], FIELDS)
    assert result["version"] == 1
    version = result["import"]["version_id"]
    assert version

    product = client.get("/api/v1/products/GOV01").json()
    assert product["product"]["status"] == "confirmed"
    assert product["latest_version"]["fields"]["dimensions"] == "28 × 24 × 12 cm"
    provenance = product["latest_version"]["provenance"]
    assert provenance["dimensions"]["locator"]["page"] == 1
    assert provenance["dimensions"]["source_name"] == "规格.pdf"
    assert provenance["dimensions"]["status"] == "verified"


def test_missing_fields_and_manual_basis(client, mock_llm):
    client.post("/api/v1/products", json={"id": "GOV02", "name": "缺失字段测试"})
    lines = ["Only body material", "Body Material: wool blend 70 percent"]
    items = [{"field": "body_material", "block_id": 0,
              "quote": "Body Material: wool blend 70 percent", "value": "wool blend 70 percent"}]
    _, detail = _extract(client, mock_llm, "GOV02", lines, items, name="缺字段.pdf")
    issue_types = {(issue["field"], issue["type"]) for issue in detail["issues"]}
    assert ("lining_material", "missing") in issue_types
    assert ("dimensions", "missing") in issue_types
    assert ("color", "missing") in issue_types

    no_basis = client.post(f"/api/v1/imports/{detail['id']}/confirm", json={
        "fields": {"body_material": "wool blend 70 percent", "lining_material": "brown canvas",
                   "dimensions": "28 x 24 x 12 cm", "color": "warm beige"},
        "manual_basis": {}, "resolutions": [],
    })
    assert no_basis.status_code == 422
    assert error_code(no_basis) == "manual_basis_required"

    missing_required = client.post(f"/api/v1/imports/{detail['id']}/confirm", json={
        "fields": {"body_material": "wool blend 70 percent"},
        "manual_basis": {}, "resolutions": [],
    })
    assert missing_required.status_code == 422

    ok = confirm_fields(client, detail["id"], {
        "body_material": "wool blend 70 percent", "lining_material": "brown canvas",
        "dimensions": "28 x 24 x 12 cm", "color": "warm beige",
    }, manual_basis={"lining_material": "人工核对供应商邮件", "dimensions": "实物测量",
                     "color": "实物核对"})
    assert ok["version"] == 1
    provenance = ok["import"]["version_id"] and client.get("/api/v1/products/GOV02").json()["latest_version"]["provenance"]
    assert provenance["lining_material"]["method"] == "manual"
    assert provenance["lining_material"]["basis"] == "人工核对供应商邮件"


def test_equivalent_units_duplicate_and_conflict(client, mock_llm):
    client.post("/api/v1/products", json={"id": "GOV03", "name": "单位测试"})
    doc_a = upload(client, "GOV03", "A.pdf", make_pdf(LINES))
    doc_b = upload(client, "GOV03", "B.pdf", make_pdf([
        "Second source", "Dimensions: 28 cm x 24 cm x 12 cm",
    ]))
    mock_llm["state"]["result"] = {"items": [
        {"field": "dimensions", "block_id": 0,
         "quote": "Dimensions: 280 mm x 240 mm x 120 mm", "value": "280 mm x 240 mm x 120 mm"},
        {"field": "dimensions", "block_id": 1,
         "quote": "Dimensions: 28 cm x 24 cm x 12 cm", "value": "28 cm x 24 cm x 12 cm"},
    ]}
    response = client.post("/api/v1/products/GOV03/imports/extract", json={
        "category_id": "BAG", "source_ids": [doc_a["id"], doc_b["id"]],
    })
    assert response.status_code == 201, response.text
    detail = response.json()
    values = {item["value"] for item in detail["candidates"]["dimensions"]}
    assert values == {"28 × 24 × 12 cm"}
    assert any(issue["type"] == "duplicate" for issue in detail["issues"])

    doc_c = upload(client, "GOV03", "C.pdf", make_pdf(["Third source", "Dimensions: 30 cm x 24 cm x 12 cm"]))
    mock_llm["state"]["result"] = {"items": [
        {"field": "dimensions", "block_id": 0,
         "quote": "Dimensions: 280 mm x 240 mm x 120 mm", "value": "280 mm x 240 mm x 120 mm"},
        {"field": "dimensions", "block_id": 1,
         "quote": "Dimensions: 28 cm x 24 cm x 12 cm", "value": "28 cm x 24 cm x 12 cm"},
        {"field": "dimensions", "block_id": 2,
         "quote": "Dimensions: 30 cm x 24 cm x 12 cm", "value": "30 cm x 24 cm x 12 cm"},
    ]}
    conflict = client.post("/api/v1/products/GOV03/imports/extract", json={
        "category_id": "BAG", "source_ids": [doc_a["id"], doc_b["id"], doc_c["id"]],
    }).json()
    conflict_issue = next(issue for issue in conflict["issues"] if issue["field"] == "dimensions")
    assert conflict_issue["type"] == "conflict"
    assert len({item["value"] for item in conflict_issue["candidates"]}) == 2
    assert len(conflict_issue["candidates"]) == 3


def test_unlocatable_model_value_is_rejected(client, mock_llm):
    client.post("/api/v1/products", json={"id": "GOV04", "name": "来源校验"})
    _, detail = _extract(client, mock_llm, "GOV04", LINES, ITEMS + [{
        "field": "weight", "block_id": 0,
        "quote": "Weight: 650 g", "value": "650 g",
    }], name="无来源.pdf")
    assert detail["candidates"]["weight"] == []
    unverified = [issue for issue in detail["issues"] if issue["type"] == "unverified"]
    assert unverified and unverified[0]["field"] == "weight"


def test_excel_import(client, mock_llm):
    client.post("/api/v1/products", json={"id": "GOV05", "name": "Excel 测试"})
    content = make_xlsx([
        ["字段", "值"],
        ["Body Material", "wool blend 70 percent"],
        ["Lining Material", "brown canvas"],
        ["Dimensions", "28 cm x 24 cm x 12 cm"],
        ["Color", "warm beige"],
    ])
    source = upload(client, "GOV05", "参数表.xlsx", content)
    assert source["mime"].endswith("spreadsheetml.sheet")
    mock_llm["state"]["result"] = {"items": [
        {"field": "body_material", "block_id": 0,
         "quote": "字段: Body Material | 值: wool blend 70 percent", "value": "wool blend 70 percent"},
        {"field": "lining_material", "block_id": 1,
         "quote": "字段: Lining Material | 值: brown canvas", "value": "brown canvas"},
        {"field": "dimensions", "block_id": 2,
         "quote": "字段: Dimensions | 值: 28 cm x 24 cm x 12 cm", "value": "28 cm x 24 cm x 12 cm"},
        {"field": "color", "block_id": 3, "quote": "字段: Color | 值: warm beige", "value": "warm beige"},
    ]}
    detail = client.post("/api/v1/products/GOV05/imports/extract", json={
        "category_id": "BAG", "source_ids": [source["id"]],
    }).json()
    locator = detail["candidates"]["dimensions"][0]["locator"]
    assert locator["sheet"] == "商品参数"
    assert locator["row"] == 4 and "B" in locator["cells"]
    result = confirm_fields(client, detail["id"], FIELDS)
    assert result["version"] == 1


def test_word_parse_locator(client):
    from backend.services import parsing

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "spec.docx"
        path.write_bytes(make_docx(["BP01 商品说明", "包身材质：羊毛混纺"]))
        parsed = parsing.parse_docx(path, "spec.docx")
    assert parsed.blocks[0]["locator"]["kind"] == "docx"
    assert parsed.blocks[0]["locator"]["paragraph"] == 1
    assert "羊毛混纺" in parsed.blocks[1]["text"]


def test_image_degradation_without_ocr(client, mock_llm, monkeypatch):
    from backend.services import parsing
    from tests.helpers import PNG_1X1

    monkeypatch.setattr(parsing, "tesseract_path", lambda: "")
    client.post("/api/v1/products", json={"id": "GOV06", "name": "图片降级"})
    source = upload(client, "GOV06", "正面.png", PNG_1X1)
    detail = client.post("/api/v1/products/GOV06/imports/extract", json={
        "category_id": "BAG", "source_ids": [source["id"]],
    })
    assert detail.status_code == 201
    body = detail.json()
    assert body["candidates"]["body_material"] == []
    assert any("OCR" in warning for warning in body["warnings"])
    assert any(issue["type"] == "missing" for issue in body["issues"])


def test_batch_import_and_second_category(client):
    payload = {"rows": [
        {"product_id": "BATCH1", "name": "批量箱包", "category_id": "BAG",
         "fields": FIELDS, "sku": "BATCH1-01"},
        {"product_id": "BATCH1", "name": "重复行", "category_id": "BAG", "fields": FIELDS},
        {"product_id": "AP01", "name": "针织开衫", "category_id": "APPAREL",
         "fields": {"fabric": "棉 80% 羊毛 20%", "size": "M", "color": "米白"}},
        {"product_id": "AP02", "name": "错误尺码", "category_id": "APPAREL",
         "fields": {"fabric": "棉", "size": "XXXL", "color": "米白"}},
    ]}
    response = client.post("/api/v1/imports/batch", json=payload)
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["ok"] == 2 and job["failed"] == 2
    failed = [item for item in job["results"] if item["status"] == "failed"]
    assert any(item["code"] == "duplicate_product" for item in failed)
    assert any(item["code"] == "invalid_input" for item in failed)

    apparel = client.get("/api/v1/products/AP01").json()
    assert apparel["product"]["category_id"] == "APPAREL"
    keys = {attr["key"] for attr in apparel["category"]["schema"]["attributes"]}
    assert "fabric" in keys and "body_material" not in keys
    assert apparel["latest_version"]["fields"]["size"] == "M"

    sku = client.post("/api/v1/products/AP01/skus", json={"sku_code": "AP01-M", "attributes": {"size": "M"}})
    assert sku.status_code == 201


def test_version_history_and_diff(client, mock_llm):
    client.post("/api/v1/products", json={"id": "GOV07", "name": "版本测试"})
    _, first = _extract(client, mock_llm, "GOV07", LINES, ITEMS, name="v1.pdf")
    confirm_fields(client, first["id"], FIELDS)

    changed_lines = list(LINES)
    changed_lines[1] = "Body Material: full grain leather"
    changed_item = [dict(ITEMS[0], quote="Body Material: full grain leather", value="full grain leather")]
    _, second = _extract(client, mock_llm, "GOV07", changed_lines, changed_item, name="v2.pdf")
    confirm_fields(client, second["id"], {**FIELDS, "body_material": "full grain leather"},
                   manual_basis={"lining_material": "沿用 v1 已确认资料",
                                 "dimensions": "沿用 v1 实测尺寸", "color": "沿用 v1 实物核对"})

    versions = client.get("/api/v1/products/GOV07/versions").json()
    assert [item["version"] for item in versions] == [2, 1]
    assert versions[1]["fields"]["body_material"] == "wool blend 70 percent"

    diff = client.get("/api/v1/products/GOV07/versions/diff", params={"from_version": 1, "to_version": 2}).json()
    assert diff["changed"][0]["field"] == "body_material"
    assert diff["changed"][0]["from"] == "wool blend 70 percent"
    assert diff["changed"][0]["to"] == "full grain leather"


def test_restore_version(client, mock_llm):
    client.post("/api/v1/products", json={"id": "GOV08", "name": "版本恢复测试"})
    _, first = _extract(client, mock_llm, "GOV08", LINES, ITEMS, name="v1.pdf")
    confirm_fields(client, first["id"], FIELDS)

    changed_lines = list(LINES)
    changed_lines[1] = "Body Material: full grain leather"
    changed_item = [dict(ITEMS[0], quote="Body Material: full grain leather", value="full grain leather")]
    _, second = _extract(client, mock_llm, "GOV08", changed_lines, changed_item, name="v2.pdf")
    confirm_fields(client, second["id"], {**FIELDS, "body_material": "full grain leather"},
                   manual_basis={"lining_material": "沿用 v1 已确认资料",
                                 "dimensions": "沿用 v1 实测尺寸", "color": "沿用 v1 实物核对"})

    versions = client.get("/api/v1/products/GOV08/versions").json()
    v1 = next(v for v in versions if v["version"] == 1)

    restored = client.post(f"/api/v1/products/GOV08/versions/{v1['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["version"] == 3
    assert restored.json()["fields"]["body_material"] == "wool blend 70 percent"
    assert restored.json()["is_current"] is True

    versions_after = client.get("/api/v1/products/GOV08/versions").json()
    assert [v["version"] for v in versions_after] == [3, 2, 1]


def test_confirm_records_operator(client, mock_llm):
    client.post("/api/v1/products", json={"id": "GOV09", "name": "操作人测试"})
    _, detail = _extract(client, mock_llm, "GOV09", LINES, ITEMS, name="op.pdf")
    response = client.post(f"/api/v1/imports/{detail['id']}/confirm",
                           json={"fields": FIELDS, "manual_basis": {}, "resolutions": [], "note": "确认"},
                           headers={"X-Operator-Id": "reviewer-a"})
    assert response.status_code == 200
    provenance = client.get("/api/v1/products/GOV09").json()["latest_version"]["provenance"]
    assert provenance["body_material"]["confirmed_by"] == "reviewer-a"
    assert provenance["body_material"]["confirmed_at"]
