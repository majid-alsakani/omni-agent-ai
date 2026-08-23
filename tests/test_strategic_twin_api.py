from pathlib import Path

import backend.main as main
from backend.data_analysis import DataAnalysisEngine
from backend.memory import MemoryStore
from backend.strategic_twin import StrategicTwinEngine
from fastapi.testclient import TestClient


FIXTURE = Path(__file__).parent / "fixtures" / "uci_online_retail_excerpt.csv"


def test_strategic_twin_api_creates_reviewable_draft_then_learns_after_approval(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory.json")
    analyzer = DataAnalysisEngine(store)
    twin = StrategicTwinEngine(store, analyzer, draft_path=tmp_path / "drafts.json")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "data_engine", analyzer)
    monkeypatch.setattr(main, "twin_engine", twin)
    client = TestClient(main.app)

    with FIXTURE.open("rb") as upload:
        response = client.post(
            "/strategic-twin/analyze-data",
            data={
                "objective": "تقييم توسع محدود في التجزئة مع فحص الإلغاءات",
                "user_id": "api-twin-user",
                "session_id": "api-twin-session",
            },
            files={"file": ("uci_online_retail_excerpt.csv", upload, "text/csv")},
        )
    assert response.status_code == 200
    draft = response.json()["data"]
    assert draft["status"] == "pending_human_review"
    assert draft["assessment"]["review_required"] is True
    assert draft["evidence"]["sales"]["detected"] is True

    approval = client.post(
        "/strategic-twin/approve",
        json={
            "draft_id": draft["id"],
            "user_id": "api-twin-user",
            "approval_note": "اعتماد اختبار API لمسار تعلم محكوم.",
            "outcome": "اختبار ناجح",
        },
    )
    assert approval.status_code == 200
    assert approval.json()["data"]["status"] == "approved_and_learned"

    precedents = client.get(
        "/strategic-twin/precedents",
        params={"objective": "توسع التجزئة والإلغاءات", "user_id": "api-twin-user"},
    )
    assert precedents.status_code == 200
    assert precedents.json()["count"] >= 1
