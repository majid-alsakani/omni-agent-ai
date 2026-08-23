from pathlib import Path

import backend.main as main
from backend.data_analysis import DataAnalysisEngine
from backend.memory import MemoryStore
from fastapi.testclient import TestClient


FIXTURE = Path(__file__).parent / "fixtures" / "uci_iris.csv"


def test_data_analysis_engine_profiles_real_uci_iris_data(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")
    engine = DataAnalysisEngine(store)

    result = engine.run(
        FIXTURE.read_bytes(),
        source_name="uci_iris.csv",
        user_id="data-user",
        session_id="data-session",
    )

    assert result["mode"] == "data-analysis-multi-agent"
    assert result["overview"]["rows"] == 150
    assert result["overview"]["columns"] == 5
    assert set(result["overview"]["numeric_columns"]) == {
        "sepal_length", "sepal_width", "petal_length", "petal_width"
    }
    assert result["overview"]["categorical_columns"] == ["species"]
    assert len(result["agents"]) == 3
    assert 0 <= result["quality"]["score"] <= 100
    assert result["source"]["stored"] is False
    assert store.records[-1].metadata["mode"] == "data_analysis"


def test_analyze_data_api_accepts_csv_and_rejects_non_csv(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory.json")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "data_engine", DataAnalysisEngine(store))
    client = TestClient(main.app)

    with FIXTURE.open("rb") as upload:
        response = client.post(
            "/analyze-data",
            data={"user_id": "api-data-user", "session_id": "api-data-session"},
            files={"file": ("uci_iris.csv", upload, "text/csv")},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["overview"]["rows"] == 150
    assert payload["data"]["quality"]["status"]

    bad = client.post(
        "/analyze-data",
        data={"user_id": "api-data-user", "session_id": "api-data-session"},
        files={"file": ("not_csv.txt", b"a,b\n1,2\n", "text/plain")},
    )
    assert bad.status_code == 422
    assert "CSV" in bad.json()["detail"]
