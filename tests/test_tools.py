from backend.memory import MemoryStore
from backend.tools import ToolRegistry


def test_allowlisted_tools_and_risk_gate(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")
    tools = ToolRegistry(store)

    assert tools.names == ["memory_lookup", "plan_validator", "risk_gate"]
    plan = tools.call(
        "plan_validator",
        objective="مهمة معقدة",
        tasks=[
            {"role": "researcher"},
            {"role": "analyst"},
            {"role": "risk_manager"},
        ],
    )
    assert plan.status == "completed"

    safe = tools.call("risk_gate", action="create_draft", external_side_effect=False)
    blocked = tools.call("risk_gate", action="send_email", external_side_effect=True)
    assert safe.status == "approved_for_simulation"
    assert blocked.status == "approval_required"
    assert blocked.requires_human_approval is True
