"""阶段 1：统一错误信封、租户隔离、AI 执行日志、工作流幂等。"""
from __future__ import annotations

from tests.helpers import create_product, error_code


def test_error_envelope_has_standard_shape(client):
    create_product(client, "ENV01")
    response = client.post("/api/v1/products", json={"id": "ENV01", "name": "重复商品"})
    assert response.status_code == 409
    body = response.json()
    # 标准信封
    assert body["success"] is False
    assert body["error"]["code"] == "DUPLICATE_PRODUCT"
    assert "retryable" in body["error"]
    assert "requires_human_action" in body["error"]
    assert "details" in body["error"]
    # 兼容旧形状
    assert body["detail"]["code"] == "duplicate_product"


def test_tenant_crud_and_list(client):
    created = client.post("/api/v1/tenants", json={"name": "品牌 B", "id": "tb"}).json()
    assert created["id"] == "tb"
    ids = {item["id"] for item in client.get("/api/v1/tenants").json()}
    assert "default" in ids and "tb" in ids


def test_cross_tenant_access_is_denied(client):
    # 默认租户下建商品
    create_product(client, "ISO01", name="隔离测试包")
    # 建第二个租户
    client.post("/api/v1/tenants", json={"name": "品牌 B", "id": "tb"})
    # 默认租户可见
    assert client.get("/api/v1/products/ISO01").status_code == 200
    # 租户 B 访问默认租户商品 → 拒绝
    denied = client.get("/api/v1/products/ISO01", headers={"X-Tenant-Id": "tb"})
    assert denied.status_code == 403
    assert error_code(denied) == "tenant_access_denied"
    assert denied.json()["error"]["code"] == "TENANT_ACCESS_DENIED"
    # 租户 B 列表里看不到默认租户商品
    items = client.get("/api/v1/products", headers={"X-Tenant-Id": "tb"}).json()["items"]
    assert all(item["id"] != "ISO01" for item in items)


def test_cross_tenant_source_access_is_denied(client):
    product = create_product(client, "ISOS1")
    source = client.post(
        f"/api/v1/products/{product['product']['id']}/sources",
        files={"file": ("spec.pdf", b"%PDF-1.4\n%%EOF")},
    ).json()
    client.post("/api/v1/tenants", json={"name": "品牌 B", "id": "tb"})
    denied = client.get(
        f"/api/v1/products/{product['product']['id']}/sources/{source['id']}",
        headers={"X-Tenant-Id": "tb"},
    )
    assert denied.status_code == 404 or denied.status_code == 403


def test_ai_execution_log_roundtrip(app):
    from backend.services import ai_logs

    log_id = ai_logs.record(
        provider="llm", model="deepseek-chat", input_summary="抽取字段",
        output_summary="{\"items\": []}", token_usage={"prompt_tokens": 10, "completion_tokens": 3},
        cost=0.0002, duration_ms=120, status="success", request_id="req-1",
        task_id="task-1", step_name="extract",
    )
    record = ai_logs.get(log_id)
    assert record["provider"] == "llm"
    assert record["model"] == "deepseek-chat"
    assert record["status"] == "success"
    assert record["token_usage"]["prompt_tokens"] == 10
    listed = ai_logs.list_for_task("task-1")
    assert any(item["id"] == log_id for item in listed)


def test_workflow_steps_and_idempotency(app):
    from backend.services import workflow

    run_id = workflow.begin("task-wf", "content_planning", "ISO01", ["load_facts", "plan"])
    workflow.step(run_id, "load_facts", "success", detail="ok", output_snapshot="{}")
    workflow.event(run_id, "started", step_name="plan")
    steps = workflow.steps(run_id)
    assert {item["name"] for item in steps} == {"load_facts", "plan"}
    assert any(item["name"] == "load_facts" and item["status"] == "success" for item in steps)

    # 幂等：同一 key 只放行一次
    assert workflow.acquire(run_id, "plan", "idem-1") is True
    assert workflow.acquire(run_id, "plan", "idem-1") is False
    assert workflow.acquire(run_id, "plan", "idem-2") is True

    workflow.finish(run_id, "success")
