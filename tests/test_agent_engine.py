from backend.agent_engine import AgentEngine
from backend.memory import MemoryStore


def test_agent_runs_complete_graph_and_writes_memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")
    engine = AgentEngine(store)

    result = engine.run(
        "طور تقرير تحليل السوق",
        user_id="u1",
        session_id="s1",
    )

    assert result["answer"]
    assert result["steps_completed"] == len(result["plan"])
    assert result["review_attempts"] >= 1
    assert len(store.records) == 2
    assert all(record.kind == "episodic" for record in store.records)


def test_explicit_preference_is_promoted_to_semantic_memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")
    engine = AgentEngine(store)

    engine.run(
        "تذكر أنني أفضل التقارير باللغة العربية",
        user_id="u2",
        session_id="s2",
    )

    semantic = [record for record in store.records if record.kind == "semantic"]
    assert len(semantic) == 1
    assert semantic[0].importance == 0.9


def test_blank_prompt_is_rejected(tmp_path):
    engine = AgentEngine(MemoryStore(tmp_path / "memory.json"))

    try:
        engine.run("   ")
    except ValueError as exc:
        assert "Prompt cannot be empty" in str(exc)
    else:
        raise AssertionError("Blank prompt should be rejected")
