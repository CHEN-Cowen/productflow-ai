"""场景 G：AI 超时 → 可重试状态，不重复建任务，不丢节点记录。"""
from __future__ import annotations

from backend.errors import ApiError
from tests.helpers import error_code, make_pdf, upload

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


def _timeout(instruction, data):
    raise ApiError(504, "模型请求超时", "provider_timeout")


def test_timeout_is_retryable_and_preserves_run(client, mock_llm):
    client.post("/api/v1/products", json={"id": "RETRY01", "name": "重试测试"})
    source = upload(client, "RETRY01", "规格.pdf", make_pdf(LINES))

    # 第一次：模型超时
    mock_llm["state"]["result"] = _timeout
    failed = client.post("/api/v1/products/RETRY01/imports/extract", json={
        "category_id": "BAG", "source_ids": [source["id"]],
    })
    assert failed.status_code == 504
    assert error_code(failed) == "provider_timeout"
    assert failed.json()["error"]["code"] == "AI_PROVIDER_TIMEOUT"
    assert failed.json()["error"]["retryable"] is True

    # 未创建导入任务（不重复建任务）
    assert client.get("/api/v1/products/RETRY01/imports").json() == []

    # 节点记录被保留：存在一条 failed 的 workflow run
    runs = client.get("/api/v1/products/RETRY01/runs").json()
    assert runs, "超时后应保留工作流执行记录"
    latest = runs[0]
    assert latest["status"] == "failed"
    assert latest["error_code"] == "provider_timeout"

    # 第二次：模型恢复，重新提取成功，且只产生一个导入任务
    mock_llm["state"]["result"] = {"items": ITEMS}
    ok = client.post("/api/v1/products/RETRY01/imports/extract", json={
        "category_id": "BAG", "source_ids": [source["id"]],
    })
    assert ok.status_code == 201, ok.text
    imports = client.get("/api/v1/products/RETRY01/imports").json()
    assert len(imports) == 1
    assert imports[0]["status"] == "reviewing"
