"""Safe, auditable tools that can be called by Omni-Agent specialists."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .memory import MemoryStore


@dataclass
class ToolResult:
    name: str
    status: str
    data: dict[str, Any]
    requires_human_approval: bool = False


class ToolRegistry:
    """Allowlisted tool registry with structured results and audit-friendly traces."""

    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory
        self._tools: dict[str, Callable[..., ToolResult]] = {
            "memory_lookup": self._memory_lookup,
            "plan_validator": self._plan_validator,
            "risk_gate": self._risk_gate,
        }

    @property
    def names(self) -> list[str]:
        return sorted(self._tools)

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        if name not in self._tools:
            raise KeyError(f"Tool is not allowlisted: {name}")
        return self._tools[name](**kwargs)

    def _memory_lookup(self, *, query: str, user_id: str, session_id: str | None = None) -> ToolResult:
        records = self.memory.search(
            query,
            user_id=user_id,
            session_id=session_id,
            kinds=("semantic", "procedural"),
            limit=5,
        )
        return ToolResult(
            name="memory_lookup",
            status="completed",
            data={"matches": [record.to_dict() for record in records]},
        )

    def _plan_validator(self, *, objective: str, tasks: list[dict[str, Any]]) -> ToolResult:
        roles = {task.get("role") for task in tasks}
        required = {"researcher", "analyst", "risk_manager"}
        missing = sorted(required - roles)
        return ToolResult(
            name="plan_validator",
            status="completed" if not missing else "needs_revision",
            data={"task_count": len(tasks), "missing_roles": missing},
        )

    def _risk_gate(self, *, action: str, external_side_effect: bool = False) -> ToolResult:
        approval_required = bool(external_side_effect)
        return ToolResult(
            name="risk_gate",
            status="approval_required" if approval_required else "approved_for_simulation",
            data={
                "action": action,
                "external_side_effect": external_side_effect,
                "reason": "أي إرسال أو تعديل خارجي يحتاج موافقة بشرية صريحة.",
            },
            requires_human_approval=approval_required,
        )
