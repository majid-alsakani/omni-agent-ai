import backend.main as main
from backend.agent_engine import AgentEngine
from backend.memory import MemoryStore
from fastapi.testclient import TestClient


def test_health_and_ask_endpoints_are_operational(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory.json")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "engine", AgentEngine(store))
    client = TestClient(main.app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    response = client.post(
        "/ask",
        json={
            "prompt": "حلل أداء المبيعات",
            "user_id": "u-api",
            "session_id": "s-api",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["answer"]
    assert payload["data"]["steps_completed"] >= 3

    second = client.post(
        "/ask",
        json={
            "prompt": "تابع المهمة السابقة",
            "user_id": "u-api",
            "session_id": "s-api",
        },
    )
    assert second.status_code == 200
    assert "أحداث سابقة" in second.json()["data"]["memory_context"]


def test_invalid_prompt_returns_validation_error(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory.json")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "engine", AgentEngine(store))
    client = TestClient(main.app)

    response = client.post("/ask", json={"prompt": "   "})
    assert response.status_code == 422
