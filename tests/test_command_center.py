import backend.main as main
from backend.agent_engine import AgentEngine
from backend.memory import MemoryStore
from backend.multi_agent import MultiAgentEngine
from fastapi.testclient import TestClient


def test_command_center_and_api_info_are_served(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory.json")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "engine", AgentEngine(store))
    monkeypatch.setattr(main, "multi_engine", MultiAgentEngine(store))
    client = TestClient(main.app)

    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "Omni-Agent Command Center" in dashboard.text
    assert "/static/app.js" in dashboard.text

    stylesheet = client.get("/static/styles.css")
    assert stylesheet.status_code == 200
    assert "--purple" in stylesheet.text

    info = client.get("/api")
    assert info.status_code == 200
    assert info.json()["version"] == "3.1.0"
