from pathlib import Path

from backend.data_analysis import DataAnalysisEngine
from backend.memory import MemoryStore
from backend.strategic_twin import StrategicTwinEngine


RETAIL_FIXTURE = Path(__file__).parent / "fixtures" / "uci_online_retail_excerpt.csv"


def test_sales_intelligence_agent_uses_real_retail_transaction_fields(tmp_path):
    memory = MemoryStore(tmp_path / "memory.json")
    result = DataAnalysisEngine(memory).run(
        RETAIL_FIXTURE.read_bytes(),
        source_name="uci_online_retail_excerpt.csv",
        user_id="retail-user",
        session_id="retail-session",
    )

    assert result["overview"]["rows"] == 300
    assert result["sales"]["detected"] is True
    assert result["sales"]["net_revenue"] > 0
    assert result["sales"]["completed_orders"] > 0
    assert result["sales"]["top_markets"]
    assert any(agent["agent"] == "Sales Intelligence Agent" for agent in result["agents"])


def test_strategic_twin_retrieves_precedents_creates_draft_and_learns_after_human_approval(tmp_path):
    memory = MemoryStore(tmp_path / "memory.json")
    memory.add(
        "قرار استراتيجي معتمد: توسع محدود في سوق التجزئة مع مراقبة الإلغاءات أسبوعياً.",
        kind="semantic",
        user_id="retail-user",
        importance=0.95,
        metadata={"mode": "strategic_twin", "outcome": "نجاح أولي"},
    )
    analyzer = DataAnalysisEngine(memory)
    twin = StrategicTwinEngine(memory, analyzer, draft_path=tmp_path / "drafts.json")

    draft = twin.analyze(
        RETAIL_FIXTURE.read_bytes(),
        source_name="uci_online_retail_excerpt.csv",
        objective="تقييم توسع محدود في سوق التجزئة مع مراقبة الإلغاءات",
        user_id="retail-user",
        session_id="twin-session",
    )

    assert draft["status"] == "pending_human_review"
    assert draft["precedents"]
    assert draft["evidence"]["sales"]["detected"] is True
    assert draft["assessment"]["review_required"] is True
    assert any(step["agent"] == "Sales Intelligence Agent" for step in draft["plan"])

    approved = twin.approve(
        draft["id"],
        user_id="retail-user",
        approval_note="اعتمد التجربة لمدة أسبوعين مع سقف إنفاق محدد ومراجعة الإلغاءات.",
        outcome="قيد القياس",
    )
    assert approved["status"] == "approved_and_learned"
    learned = memory.search("توسع سوق التجزئة", user_id="retail-user", kinds=("semantic",), limit=5)
    assert any("قرار استراتيجي معتمد" in record.content for record in learned)
