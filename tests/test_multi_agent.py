from backend.memory import MemoryStore
from backend.multi_agent import MultiAgentEngine
from backend.vector_memory import LocalVectorBackend


def test_multi_agent_orchestrates_three_specialists(tmp_path):
    store = MemoryStore(tmp_path / "memory.json", vector_backend=LocalVectorBackend())
    engine = MultiAgentEngine(store)

    result = engine.run(
        "نفذ خطة معقدة للبحث والتحليل ومقارنة البدائل مع فحص المخاطر",
        user_id="multi-user",
        session_id="multi-session",
    )

    assert result["review"]["status"] == "approved"
    assert set(result["agents"]) == {"Research Agent", "Analysis Agent", "Risk Agent"}
    assert len(result["agent_outputs"]) == 3
    assert "قرار المنسق" in result["answer"]
    assert any(record.metadata.get("mode") == "multi_agent" for record in store.records)


def test_semantic_memory_uses_vector_backend(tmp_path):
    backend = LocalVectorBackend()
    store = MemoryStore(tmp_path / "memory.json", vector_backend=backend)
    store.add(
        "أفضل تقارير الأعمال المختصرة باللغة العربية",
        kind="semantic",
        user_id="u-vector",
        importance=0.9,
    )

    matches = store.search(
        "تقارير عربية مختصرة",
        user_id="u-vector",
        kinds=("semantic",),
        limit=1,
    )
    assert len(matches) == 1
    assert matches[0].content.startswith("أفضل تقارير الأعمال")
