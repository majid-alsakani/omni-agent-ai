"""Multi-agent planning and orchestration for complex Omni-Agent tasks.

The implementation is provider-independent and deterministic by default. Each
specialist can later be replaced by an LLM-backed worker without changing the
LangGraph topology or the API contract.
"""

from __future__ import annotations

import operator
from typing import Any, Annotated, Protocol

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .memory import MemoryStore
from .tools import ToolRegistry


class MultiAgentState(TypedDict, total=False):
    input: str
    user_id: str
    session_id: str
    context: str
    objective: str
    tasks: list[dict[str, Any]]
    agent_outputs: Annotated[list[dict[str, Any]], operator.add]
    review: dict[str, Any]
    final_answer: str


class Specialist(Protocol):
    name: str

    def run(self, objective: str, context: str, task: dict[str, Any]) -> dict[str, Any]: ...


class LocalSpecialist:
    """Local deterministic specialist used for reliable integration tests."""

    def __init__(self, name: str, focus: str) -> None:
        self.name = name
        self.focus = focus

    def run(self, objective: str, context: str, task: dict[str, Any]) -> dict[str, Any]:
        role = task["role"]
        if role == "researcher":
            finding = "تم جمع محاور البحث: الهدف، أصحاب المصلحة، البيانات المطلوبة، ومصادر التحقق."
            evidence = ["تعريف المشكلة", "المصادر الموثوقة", "الافتراضات التي تحتاج تحققاً"]
        elif role == "analyst":
            finding = "تم تحويل المهمة إلى مؤشرات قياس ومسار تنفيذ قابل للمقارنة بين البدائل."
            evidence = ["مؤشر النجاح", "خطوات التنفيذ", "معيار قرار قابل للقياس"]
        elif role == "risk_manager":
            finding = "تم فحص مخاطر الهلوسة، فقدان البيانات، الصلاحيات، وتعارض نتائج الوكلاء."
            evidence = ["تأكيد بشري قبل إجراء خارجي", "سجل تدقيق", "خطة تراجع عند الفشل"]
        else:
            finding = "تم فحص المهمة من زاوية جودة التسليم وقابلية الاختبار."
            evidence = ["اكتمال النتيجة", "وضوح الحدود", "الخطوة التالية"]
        return {
            "agent": self.name,
            "role": role,
            "focus": self.focus,
            "status": "completed",
            "finding": finding,
            "evidence": evidence,
            "context_used": bool(context.strip()),
        }


class MultiAgentEngine:
    """Self-planning multi-agent graph for complex and long-horizon tasks."""

    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory
        self.tools = ToolRegistry(memory)
        self.specialists: dict[str, Specialist] = {
            "researcher": LocalSpecialist("Research Agent", "جمع الحقائق والأسئلة المفتوحة"),
            "analyst": LocalSpecialist("Analysis Agent", "تحويل الهدف إلى خطة ومؤشرات"),
            "risk_manager": LocalSpecialist("Risk Agent", "السلامة والجودة والحدود"),
        }
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(MultiAgentState)
        workflow.add_node("load_context", self._load_context)
        workflow.add_node("orchestrator", self._orchestrator)
        workflow.add_node("researcher", self._worker("researcher"))
        workflow.add_node("analyst", self._worker("analyst"))
        workflow.add_node("risk_manager", self._worker("risk_manager"))
        workflow.add_node("reviewer", self._reviewer)
        workflow.add_node("synthesizer", self._synthesizer)

        workflow.add_edge(START, "load_context")
        workflow.add_edge("load_context", "orchestrator")
        # Fan-out: the three specialist nodes run independently and their outputs
        # are merged by the Annotated reducer in MultiAgentState.
        workflow.add_edge("orchestrator", "researcher")
        workflow.add_edge("orchestrator", "analyst")
        workflow.add_edge("orchestrator", "risk_manager")
        workflow.add_edge("researcher", "reviewer")
        workflow.add_edge("analyst", "reviewer")
        workflow.add_edge("risk_manager", "reviewer")
        workflow.add_edge("reviewer", "synthesizer")
        workflow.add_edge("synthesizer", END)
        return workflow.compile()

    def _load_context(self, state: MultiAgentState) -> dict[str, Any]:
        return {
            "context": self.memory.build_context(
                state["input"],
                user_id=state["user_id"],
                session_id=state["session_id"],
                limit=8,
            )
        }

    def _orchestrator(self, state: MultiAgentState) -> dict[str, Any]:
        objective = " ".join(state["input"].split())
        tasks = [
            {"id": "research", "role": "researcher", "instruction": "اجمع المعطيات والأسئلة المفتوحة."},
            {"id": "analysis", "role": "analyst", "instruction": "حدد الخطة ومؤشرات النجاح."},
            {"id": "risk", "role": "risk_manager", "instruction": "افحص المخاطر والضوابط."},
        ]
        validation = self.tools.call("plan_validator", objective=objective, tasks=tasks)
        return {
            "objective": objective,
            "tasks": tasks,
            "agent_outputs": [],
            "review": {"plan_validation": validation.data, "plan_status": validation.status},
        }

    def _worker(self, role: str):
        def run(state: MultiAgentState) -> dict[str, Any]:
            task = next(item for item in state["tasks"] if item["role"] == role)
            output = self.specialists[role].run(state["objective"], state["context"], task)
            memory_trace = self.tools.call(
                "memory_lookup",
                query=state["objective"],
                user_id=state["user_id"],
                session_id=state["session_id"],
            )
            output["tool_trace"] = {
                "memory_lookup": {"status": memory_trace.status, "matches": len(memory_trace.data["matches"])}
            }
            return {"agent_outputs": [output]}

        return run

    def _reviewer(self, state: MultiAgentState) -> dict[str, Any]:
        outputs = state.get("agent_outputs", [])
        names = {item.get("agent") for item in outputs}
        complete = len(outputs) == 3 and all(item.get("status") == "completed" for item in outputs)
        return {
            "review": {
                "status": "approved" if complete else "needs_attention",
                "agents_received": len(outputs),
                "expected_agents": 3,
                "missing_agents": sorted({"Research Agent", "Analysis Agent", "Risk Agent"} - names),
                "message": "اجتازت المخرجات مراجعة الاتساق المحلية." if complete else "توجد مخرجات ناقصة.",
            }
        }

    def _synthesizer(self, state: MultiAgentState) -> dict[str, Any]:
        outputs = state.get("agent_outputs", [])
        gate = self.tools.call("risk_gate", action="synthesize_multi_agent_answer", external_side_effect=False)
        sections = []
        for output in outputs:
            sections.append(
                f"### {output['agent']}\n{output['finding']}\n"
                f"الأدلة/النقاط: {', '.join(output['evidence'])}\n"
                f"سجل الأدوات: {output.get('tool_trace', {})}"
            )
        answer = (
            f"النتيجة الموحدة للمهمة متعددة الوكلاء: {state['objective']}\n\n"
            + "\n\n".join(sections)
            + "\n\n### قرار المنسق\nتم دمج نتائج الوكلاء الثلاثة بعد المراجعة. "
            f"بوابة المخاطر: {gate.status}. "
            "لا تُنفذ أي عملية خارجية قبل إضافة أداة موثوقة وصلاحية وتأكيد بشري."
        )
        self.memory.add(
            f"مهمة متعددة الوكلاء: {state['objective']}",
            kind="episodic",
            user_id=state["user_id"],
            session_id=state["session_id"],
            importance=0.70,
            metadata={"mode": "multi_agent", "agents": [item["agent"] for item in outputs]},
        )
        self.memory.add(
            f"خلاصة متعددة الوكلاء: {answer[:900]}",
            kind="episodic",
            user_id=state["user_id"],
            session_id=state["session_id"],
            importance=0.60,
            metadata={"mode": "multi_agent", "review": state["review"]},
        )
        return {"final_answer": answer}

    def run(self, prompt: str, *, user_id: str = "default_user", session_id: str = "default_session") -> dict[str, Any]:
        clean_prompt = " ".join(prompt.strip().split())
        if not clean_prompt:
            raise ValueError("Prompt cannot be empty")
        result = self.graph.invoke({
            "input": clean_prompt,
            "user_id": user_id,
            "session_id": session_id,
            "agent_outputs": [],
        })
        return {
            "answer": result["final_answer"],
            "objective": result["objective"],
            "agents": [item["agent"] for item in result.get("agent_outputs", [])],
            "agent_outputs": result.get("agent_outputs", []),
            "review": result["review"],
            "memory_context": result.get("context", ""),
        }
