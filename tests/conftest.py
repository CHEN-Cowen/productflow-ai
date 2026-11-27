from __future__ import annotations

import os
import tempfile

import pytest

# 导入 backend.main 时会创建默认数据目录；测试前先指向临时目录，避免污染工作区
os.environ.setdefault("PRODUCTFLOW_DATA", tempfile.mkdtemp(prefix="productflow-test-"))


@pytest.fixture()
def app(tmp_path):
    from backend.main import create_app

    return create_app(tmp_path / "data")


@pytest.fixture()
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def mock_llm(monkeypatch):
    calls: list[tuple[str, dict]] = []
    state = {"result": {}}

    def fake(instruction: str, data: dict) -> dict:
        calls.append((instruction, data))
        result = state["result"]
        if callable(result):
            return result(instruction, data)
        return result

    monkeypatch.setattr("backend.providers.llm.generate_structured", fake)
    return {"calls": calls, "state": state}


@pytest.fixture()
def mock_image(monkeypatch):
    from tests.helpers import PNG_1X1

    calls: list[dict] = []
    state = {"results": None, "error": None}

    def fake(prompt: str, references=None, ratio: str = "", size: str = "", count: int = 1) -> list[dict]:
        calls.append({"prompt": prompt, "references": references, "ratio": ratio, "count": count})
        if state["error"] is not None:
            raise state["error"]
        if state["results"] is not None:
            return state["results"]
        return [{
            "content": PNG_1X1,
            "mime": "image/png",
            "width": 1,
            "height": 1,
            "request_id": "req-test",
            "provider": "volcengine-ark",
            "model": "seedream-test",
            "params": {"size": "1024x1365", "ratio": ratio, "reference_count": len(references or []), "count": count},
        }]

    monkeypatch.setattr("backend.providers.image.generate", fake)
    return {"calls": calls, "state": state}


@pytest.fixture()
def mock_video(monkeypatch):
    calls: list[dict] = []
    state = {"results": None, "error": None}

    def fake(prompt: str, references=None, ratio: str = "", duration: int = 12) -> list[dict]:
        calls.append({"prompt": prompt, "references": references, "ratio": ratio, "duration": duration})
        if state["error"] is not None:
            raise state["error"]
        if state["results"] is not None:
            return state["results"]
        return [{
            "content": b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 2048,
            "mime": "video/mp4",
            "width": 0,
            "height": 0,
            "request_id": "req-video-test",
            "provider": "kuaipao",
            "model": "seedance-test",
            "params": {"prompt": prompt, "resolution": "720p", "ratio": "adaptive", "duration": duration,
                       "seed": 1, "generate_audio": False, "reference_count": len(references or []),
                       "task_id": "cgt-test"},
        }]

    monkeypatch.setattr("backend.providers.video.generate", fake)
    return {"calls": calls, "state": state}
