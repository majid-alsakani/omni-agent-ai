from backend.memory import MemoryStore


def test_memory_persists_and_retrieves_relevant_facts(tmp_path):
    path = tmp_path / "memory.json"
    first = MemoryStore(path)
    first.add(
        "أنا أفضل أن تكون التقارير باللغة العربية",
        kind="semantic",
        user_id="u1",
        importance=0.9,
    )
    first.add(
        "حدث تجريبي عن مشروع مختلف",
        kind="episodic",
        user_id="u1",
        session_id="s1",
    )

    second = MemoryStore(path)
    matches = second.search("التقارير العربية", user_id="u1", kinds=("semantic",), limit=1)

    assert len(matches) == 1
    assert "العربية" in matches[0].content


def test_episodic_memory_is_bounded(tmp_path):
    store = MemoryStore(tmp_path / "memory.json", max_episodic_per_session=3)
    for index in range(5):
        store.add(
            f"حدث رقم {index}",
            kind="episodic",
            user_id="u1",
            session_id="s1",
        )

    recent = store.recent(user_id="u1", session_id="s1", limit=10)
    assert len(recent) == 3
    assert {item.content for item in recent} == {"حدث رقم 2", "حدث رقم 3", "حدث رقم 4"}


def test_empty_memory_context_is_explicit(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")
    context = store.build_context("طلب جديد", user_id="u1", session_id="s1")
    assert "لا توجد أحداث سابقة" in context
    assert "لا توجد معرفة محفوظة ذات صلة" in context
