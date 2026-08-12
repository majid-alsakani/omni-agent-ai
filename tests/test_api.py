import backend.main as main
from backend.agent_engine import AgentEngine
from backend.memory import MemoryStore
from backend.multi_agent import MultiAgentEngine
from fastapi.testclient import TestClient


def test_health_and_ask_endpoints_are_operational(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory.json")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "engine", AgentEngine(store))
    monkeypatch.setattr(main, "multi_engine", MultiAgentEngine(store))
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


def test_complex_prompt_routes_to_multi_agent_engine(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory.json")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "engine", AgentEngine(store))
    monkeypatch.setattr(main, "multi_engine", MultiAgentEngine(store))
    client = TestClient(main.app)

    response = client.post(
        "/ask",
        json={
            "prompt": "نفذ مهمة معقدة للبحث والتحليل ومقارنة البدائل مع فحص المخاطر",
            "user_id": "u-multi-api",
            "session_id": "s-multi-api",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "multi"
    assert payload["data"]["review"]["status"] == "approved"
    assert len(payload["data"]["agents"]) == 3


def test_invalid_prompt_returns_validation_error(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory.json")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "engine", AgentEngine(store))
    monkeypatch.setattr(main, "multi_engine", MultiAgentEngine(store))
    client = TestClient(main.app)

    response = client.post("/ask", json={"prompt": "   "})
    assert response.status_code == 422
