"""Verify the governed learning loop using an explicit test-only approval."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests


BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8040"
DATASET = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/tmp/uci-online-retail/online_retail.csv")
ARTIFACTS = Path("artifacts")
USER_ID = "uci-retail-live"
OBJECTIVE = "تقييم تجربة توسع تجاري محدودة مع مراقبة الإلغاءات وقيمة الطلبات في أسواق التجزئة."


def main() -> None:
    first = json.loads((ARTIFACTS / "online_retail_live_result.json").read_text(encoding="utf-8"))
    approved = requests.post(
        f"{BASE_URL}/strategic-twin/approve",
        json={
            "draft_id": first["strategic_twin"]["draft_id"],
            "user_id": USER_ID,
            "approval_note": "موافقة اختبارية صريحة للتحقق من حلقة التعلم المحلية؛ ليست قراراً تشغيلياً حقيقياً.",
            "outcome": "اختبار واجهة التعلم المكتملة",
        },
        timeout=30,
    )
    approved.raise_for_status()

    with DATASET.open("rb") as handle:
        rerun = requests.post(
            f"{BASE_URL}/strategic-twin/analyze-data",
            data={"objective": OBJECTIVE, "user_id": USER_ID, "session_id": "uci-retail-learning-rerun"},
            files={"file": (DATASET.name, handle, "text/csv")},
            timeout=180,
        )
    rerun.raise_for_status()
    draft = rerun.json()["data"]
    result = {
        "approval_status": approved.json()["data"]["status"],
        "semantic_memory_id": approved.json()["data"]["approval"]["memory_id"],
        "precedents_on_second_run": len(draft["precedents"]),
        "second_draft_status": draft["status"],
        "confidence_score": draft["assessment"]["confidence_score"],
    }
    (ARTIFACTS / "twin_learning_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
