"""Run a reproducible live test against the local Omni-Agent API using UCI Online Retail."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests


BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8040"
DATASET = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/tmp/uci-online-retail/online_retail.csv")
ARTIFACTS = Path("artifacts")
USER_ID = "uci-retail-live"


def post_file(path: str, objective: str | None = None) -> dict:
    payload = {"user_id": USER_ID, "session_id": "uci-online-retail-live"}
    if objective:
        payload["objective"] = objective
    with DATASET.open("rb") as handle:
        response = requests.post(
            f"{BASE_URL}{path}",
            data=payload,
            files={"file": (DATASET.name, handle, "text/csv")},
            timeout=180,
        )
    response.raise_for_status()
    return response.json()


def main() -> None:
    if not DATASET.exists():
        raise SystemExit(f"Dataset not found: {DATASET}")
    ARTIFACTS.mkdir(exist_ok=True)
    meta = {"file": DATASET.name, "bytes": DATASET.stat().st_size}

    start = time.perf_counter()
    analysis_response = post_file("/analyze-data")
    analysis_seconds = round(time.perf_counter() - start, 2)

    start = time.perf_counter()
    twin_response = post_file(
        "/strategic-twin/analyze-data",
        "تقييم تجربة توسع تجاري محدودة مع مراقبة الإلغاءات وقيمة الطلبات في أسواق التجزئة.",
    )
    twin_seconds = round(time.perf_counter() - start, 2)

    analysis = analysis_response["data"]
    twin = twin_response["data"]
    report = {
        "dataset": meta,
        "analysis_runtime_seconds": analysis_seconds,
        "twin_runtime_seconds": twin_seconds,
        "analysis": {
            "overview": analysis["overview"],
            "quality": analysis["quality"],
            "headline": analysis["insights"]["headline"],
            "sales": analysis["sales"],
            "agents": analysis["agents"],
            "summary": analysis["summary"],
        },
        "strategic_twin": {
            "draft_id": twin["id"],
            "status": twin["status"],
            "precedent_count": len(twin["precedents"]),
            "plan": twin["plan"],
            "assessment": twin["assessment"],
        },
    }
    (ARTIFACTS / "online_retail_live_result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    sales = report["analysis"]["sales"]
    assessment = report["strategic_twin"]["assessment"]
    lines = [
        "# Live UCI Online Retail Test",
        "",
        "## Input",
        f"The test used `{meta['file']}` ({meta['bytes'] / (1024 * 1024):.2f} MB) converted from the official UCI Online Retail download.",
        "",
        "## Data Analysis Lab Result",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Rows analyzed | {analysis['overview']['rows']:,} |",
        f"| Columns | {analysis['overview']['columns']} |",
        f"| Runtime | {analysis_seconds:.2f} seconds |",
        f"| Data quality | {analysis['quality']['score']}/100 — {analysis['quality']['status']} |",
        f"| Net sales (Quantity × UnitPrice) | {sales.get('net_revenue', 'n/a')} |",
        f"| Completed sales | {sales.get('completed_revenue', 'n/a')} |",
        f"| Completed orders | {sales.get('completed_orders', 'n/a')} |",
        f"| Cancellation rows | {sales.get('cancellation_rows', 'n/a')} |",
        f"| Cancellation value | {sales.get('cancellation_value', 'n/a')} |",
        "",
        "## Strategic Twin Result",
        "",
        f"The twin created draft `{twin['id']}` in `{twin['status']}` after {twin_seconds:.2f} seconds. It retrieved {len(twin['precedents'])} semantic/procedural precedents for the test user.",
        "",
        f"> Recommendation: {assessment['recommendation']}",
        "",
        f"Confidence score: **{assessment['confidence_score']}/100**. This remains a reviewable draft and has not been auto-approved or written as a semantic decision.",
        "",
        "## Source",
        "",
        "UCI Online Retail: https://archive.ics.uci.edu/dataset/352/online+retail",
    ]
    (ARTIFACTS / "online_retail_live_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"analysis_seconds": analysis_seconds, "twin_seconds": twin_seconds, "rows": analysis['overview']['rows'], "quality": analysis['quality']['score'], "draft_status": twin['status']}, ensure_ascii=False))


if __name__ == "__main__":
    main()
