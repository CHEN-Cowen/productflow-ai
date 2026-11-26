from __future__ import annotations

import pytest

from backend.errors import ApiError
from backend.providers import image as image_provider
from backend.providers.errors import classify_http_error
from tests.helpers import PNG_1X1


def test_health_and_model_status(client):
    health = client.get("/api/v1/health").json()
    assert health["status"] == "ok"
    assert "llm" in health["models"] and "image" in health["models"]
    status = client.get("/api/v1/models/status").json()
    assert status["llm"]["configured"] is False
    assert "密钥" in status["note"]


@pytest.mark.parametrize(
    "status,body,code",
    [
        (401, '{"error":{"message":"invalid api key"}}', "provider_auth"),
        (403, '{"error":{"message":"permission denied"}}', "provider_permission"),
        (429, '{"error":{"message":"rate limit"}}', "provider_quota"),
        (400, '{"error":{"code":"SetLimitExceed","message":"quota exceeded"}}', "provider_quota"),
        (500, "upstream error", "provider_http"),
        (400, '{"error":{"message":"bad parameter"}}', "provider_http"),
    ],
)
def test_provider_error_classification(status, body, code):
    error = classify_http_error(status, body)
    assert error.code == code
    assert error.hint


def test_missing_config_is_actionable(monkeypatch):
    for name in ("LLM_URL", "LLM_MODEL", "LLM_API_KEY", "IMAGE_URL", "IMAGE_MODEL", "IMAGE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ApiError) as llm_error:
        from backend.providers import llm

        llm.generate_structured("test", {})
    assert llm_error.value.code == "provider_not_configured"
    assert llm_error.value.status == 503

    with pytest.raises(ApiError) as image_error:
        image_provider.generate("test")
    assert image_error.value.code == "provider_not_configured"


def test_inspect_image_accepts_png_and_rejects_garbage():
    mime, width, height = image_provider.inspect_image(PNG_1X1)
    assert (mime, width, height) == ("image/png", 1, 1)
    with pytest.raises(ApiError) as error:
        image_provider.inspect_image(b"not an image" * 20)
    assert error.value.code == "provider_format"


def test_ratio_sizes():
    assert image_provider.size_for_ratio("3:4") == "1024x1365"
    assert image_provider.size_for_ratio("9:16") == "1024x1820"
    assert image_provider.size_for_ratio("1024x1536") == "1024x1536"
