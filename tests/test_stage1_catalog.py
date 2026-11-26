from __future__ import annotations

import sqlite3

from tests.helpers import error_code, make_pdf, upload


def test_create_read_duplicate_and_search(client):
    created = client.post("/api/v1/products", json={
        "id": "NP01", "name": "女士双肩包", "category_id": "BAG",
    })
    assert created.status_code == 201
    assert created.json()["product"]["status"] == "draft"

    read_back = client.get("/api/v1/products/NP01")
    assert read_back.status_code == 200
    assert read_back.json()["product"]["name"] == "女士双肩包"

    duplicate = client.post("/api/v1/products", json={"id": "NP01", "name": "重复商品"})
    assert duplicate.status_code == 409
    assert error_code(duplicate) == "duplicate_product"
    assert "已存在" in duplicate.json()["detail"]["message"]

    listing = client.get("/api/v1/products", params={"search": "双肩"}).json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == "NP01"


def test_data_survives_restart(tmp_path):
    from backend.main import create_app

    data = tmp_path / "data"
    first_app = create_app(data)
    from fastapi.testclient import TestClient

    with TestClient(first_app) as first:
        assert first.post("/api/v1/products", json={"id": "KEEP1", "name": "持久化草稿"}).status_code == 201
    second_app = create_app(data)
    with TestClient(second_app) as second:
        detail = second.get("/api/v1/products/KEEP1").json()
        assert detail["product"]["name"] == "持久化草稿"


def test_upload_preview_and_rejections(client):
    client.post("/api/v1/products", json={"id": "UP01", "name": "上传测试"})
    source = upload(client, "UP01", "规格书.pdf", make_pdf(["BP01 specification"]))
    assert source["mime"] == "application/pdf"
    preview = client.get(source["url"])
    assert preview.status_code == 200
    assert preview.content.startswith(b"%PDF-")

    duplicate = client.post("/api/v1/products/UP01/sources", files={"file": ("规格书.pdf", make_pdf(["BP01 specification"]))})
    assert duplicate.status_code == 409
    assert error_code(duplicate) == "duplicate_source"

    invalid = client.post("/api/v1/products/UP01/sources", files={"file": ("bad.txt", b"hello")})
    assert invalid.status_code == 422
    assert error_code(invalid) == "unsupported_file"

    client.post("/api/v1/products", json={"id": "UP02", "name": "另一个商品"})
    cross = client.get(f"/api/v1/products/UP02/sources/{source['id']}")
    assert cross.status_code == 404


def test_old_database_migrates_without_data_loss(tmp_path):
    data = tmp_path / "legacy"
    data.mkdir()
    database = sqlite3.connect(data / "productflow.sqlite3")
    database.executescript(
        """
        CREATE TABLE products (id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE sources (
            id TEXT PRIMARY KEY, product_id TEXT NOT NULL, name TEXT NOT NULL, mime TEXT NOT NULL
        );
        CREATE TABLE reference_tags (source_id TEXT PRIMARY KEY, angle TEXT NOT NULL);
        INSERT INTO products VALUES ('BP01', '女士双肩包');
        INSERT INTO sources VALUES ('legacy-source', 'BP01', '正面.png', 'image/png');
        INSERT INTO reference_tags VALUES ('legacy-source', 'front');
        """
    )
    database.commit()
    database.close()

    from backend.main import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app(data)) as client:
        detail = client.get("/api/v1/products/BP01").json()
        assert detail["product"]["name"] == "女士双肩包"
        assert detail["sources"][0]["view_angle"] == "front"
        assert detail["sources"][0]["kind"] == "image"
        assert client.get("/api/v1/products").json()["total"] == 1


def test_categories_and_sku(client):
    categories = client.get("/api/v1/categories").json()
    ids = {item["id"] for item in categories}
    assert {"BAG", "APPAREL"} <= ids
    bag = next(item for item in categories if item["id"] == "BAG")
    keys = {attr["key"] for attr in bag["schema"]["attributes"]}
    assert {"body_material", "lining_material", "dimensions", "weight", "leather_trim", "hardware_color"} <= keys

    original_version = bag["version"]
    updated = client.put("/api/v1/categories/BAG", json={
        "category_id": "BAG",
        "category_name": "箱包",
        "attributes": bag["schema"]["attributes"] + [{
            "key": "strap_type", "label": "肩带类型", "type": "text",
            "required": False, "critical": False,
        }],
    })
    assert updated.status_code == 200
    assert updated.json()["version"] == original_version + 1
    versions = client.get("/api/v1/categories/BAG/versions").json()
    assert len(versions) >= original_version + 1

    client.post("/api/v1/products", json={"id": "SKU01", "name": "SKU 测试", "category_id": "BAG"})
    sku = client.post("/api/v1/products/SKU01/skus", json={
        "sku_code": "sku01-beige", "attributes": {"color": "暖米白"},
    })
    assert sku.status_code == 201
    assert sku.json()["sku_code"] == "SKU01-BEIGE"
    duplicate = client.post("/api/v1/products/SKU01/skus", json={"sku_code": "SKU01-BEIGE"})
    assert duplicate.status_code == 409
