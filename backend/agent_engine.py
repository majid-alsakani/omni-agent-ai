"""LangGraph orchestration for the Omni-Agent core."""

from __future__ import annotations

from typing import Any, Protocol

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .memory import MemoryStore


class AgentState(TypedDict, total=False):
    input: str
    user_id: str
    session_id: str
    context: str
    plan: list[str]
    current_step: int
    results: list[str]
    feedback: str
    review_attempts: int
    need_revision: bool
    final_answer: str


class ReasoningProvider(Protocol):
    def plan(self, prompt: str, context: str, feedback: str = "") -> list[str]: ...

    def execute(self, step: str, prompt: str, context: str, results: list[str]) -> str: ...

    def review(self, prompt: str, answer: str, results: list[str]) -> tuple[bool, str]: ...

    def finalize(self, prompt: str, results: list[str], context: str) -> str: ...


class LocalReasoningProvider:
    """Deterministic local provider used for development and repeatable tests.

    It is intentionally separated from the graph. A hosted LLM provider can later
    implement the same protocol without changing the memory or workflow layer.
    """

    def plan(self, prompt: str, context: str, feedback: str = "") -> list[str]:
        lower = prompt.casefold()
        steps = ["فهم الهدف والسياق", "استرجاع الذاكرة ذات الصلة"]
        if any(word in lower for word in ("حلل", "تحليل", "analy", "تقرير", "report")):
            steps.append("تحويل الطلب إلى نقاط عملية قابلة للتحقق")
        elif any(word in lower for word in ("نفذ", "ابن", "طور", "implement", "build")):
            steps.append("تحويل الهدف إلى خطة تنفيذ قابلة للقياس")
        else:
            steps.append("تحديد الإجابة أو الإجراء الأنسب")
        steps.append("صياغة نتيجة واضحة مع حدود الثقة والخطوة التالية")
        if feedback:
            steps.insert(0, "تطبيق ملاحظات المراجعة السابقة")
        return steps

    def execute(self, step: str, prompt: str, context: str, results: list[str]) -> str:
        if step == "فهم الهدف والسياق":
            return f"تم تحديد الهدف: {prompt.strip()}"
        if step == "استرجاع الذاكرة ذات الصلة":
            return f"تم فحص الذاكرة قبل التنفيذ.\n{context}"
        if step == "تحويل الطلب إلى نقاط عملية قابلة للتحقق":
            return "تم تقسيم العمل إلى: المتطلبات، التنفيذ، التحقق، ثم التوثيق."
        if step == "تحويل الهدف إلى خطة تنفيذ قابلة للقياس":
            return "تم تحويل الهدف إلى مخرجات قابلة للقياس مع اختبار قبل التسليم."
        if step == "تحديد الإجابة أو الإجراء الأنسب":
            return "تم اختيار مسار إجابة مباشر مع الاستفادة من السياق المحفوظ."
        if step == "تطبيق ملاحظات المراجعة السابقة":
            return "تم إدخال ملاحظات المراجعة في خطة المحاولة الجديدة."
        return "تم تجهيز نتيجة قابلة للمراجعة والتسليم."

    def review(self, prompt: str, answer: str, results: list[str]) -> tuple[bool, str]:
        if not answer.strip():
            return True, "الإجابة فارغة وتحتاج إلى إعادة صياغة."
        if len(results) < 3:
            return True, "لم تكتمل خطوات التنفيذ الأساسية."
        return False, "اجتازت النتيجة المراجعة المحلية: مكتملة وغير فارغة."

    def finalize(self, prompt: str, results: list[str], context: str) -> str:
        body = "\n".join(f"{index}. {item}" for index, item in enumerate(results, start=1))
        return (
            f"النتيجة التنفيذية لطلبك: {prompt.strip()}\n\n"
            f"{body}\n\n"
            "تمت مراجعة النتيجة قبل التسليم. هذا التشغيل محلي وقابل للتوسعة إلى مزود LLM، "
            "لكن لا يتم ادعاء تنفيذ إجراء خارجي لم يُنفذ فعلياً."
        )


class AgentEngine:
    """Stateful graph runner connecting planning, execution, review, and memory."""

    def __init__(self, memory: MemoryStore, provider: ReasoningProvider | None = None, max_review_attempts: int = 1) -> None:
        self.memory = memory
        self.provider = provider or LocalReasoningProvider()
        self.max_review_attempts = max(0, max_review_attempts)
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("load_context", self._load_context)
        workflow.add_node("planner", self._planner)
        workflow.add_node("executor", self._executor)
        workflow.add_node("reviewer", self._reviewer)
        workflow.add_node("finalizer", self._finalizer)

        workflow.add_edge(START, "load_context")
        workflow.add_edge("load_context", "planner")
        workflow.add_edge("planner", "executor")
        workflow.add_conditional_edges(
            "executor",
            self._route_after_execution,
            {"execute": "executor", "review": "reviewer"},
        )
        workflow.add_conditional_edges(
            "reviewer",
            self._route_after_review,
            {"revise": "planner", "finish": "finalizer"},
        )
        workflow.add_edge("finalizer", END)
        return workflow.compile()

    def _load_context(self, state: AgentState) -> dict[str, Any]:
        context = self.memory.build_context(
            state["input"],
            user_id=state["user_id"],
            session_id=state["session_id"],
        )
        return {"context": context, "results": [], "current_step": 0, "review_attempts": 0, "feedback": ""}

    def _planner(self, state: AgentState) -> dict[str, Any]:
        plan = self.provider.plan(state["input"], state["context"], state.get("feedback", ""))
        if not plan:
            raise ValueError("Provider returned an empty plan")
        return {"plan": plan, "current_step": 0}

    def _executor(self, state: AgentState) -> dict[str, Any]:
        index = state["current_step"]
        plan = state["plan"]
        if index >= len(plan):
            raise IndexError("Execution step is outside the plan")
        result = self.provider.execute(
            plan[index],
            state["input"],
            state["context"],
            state.get("results", []),
        )
        return {
            "results": [*state.get("results", []), result],
            "current_step": index + 1,
        }

    def _route_after_execution(self, state: AgentState) -> str:
        return "review" if state["current_step"] >= len(state["plan"]) else "execute"

    def _reviewer(self, state: AgentState) -> dict[str, Any]:
        draft = self.provider.finalize(state["input"], state.get("results", []), state["context"])
        need_revision, feedback = self.provider.review(state["input"], draft, state.get("results", []))
        attempts = state.get("review_attempts", 0) + 1
        allowed = need_revision and attempts <= self.max_review_attempts
        return {
            "need_revision": allowed,
            "feedback": feedback,
            "review_attempts": attempts,
            "final_answer": draft,
        }

    def _route_after_review(self, state: AgentState) -> str:
        return "revise" if state.get("need_revision", False) else "finish"

    def _finalizer(self, state: AgentState) -> dict[str, Any]:
        answer = self.provider.finalize(state["input"], state.get("results", []), state["context"])
        user_id = state["user_id"]
        session_id = state["session_id"]
        self.memory.add(
            f"طلب المستخدم: {state['input']}",
            kind="episodic",
            user_id=user_id,
            session_id=session_id,
            importance=0.55,
            metadata={"role": "user"},
        )
        self.memory.add(
            f"آخر نتيجة للطلب '{state['input']}': {answer[:800]}",
            kind="episodic",
            user_id=user_id,
            session_id=session_id,
            importance=0.45,
            metadata={"role": "agent"},
        )
        if self._looks_like_preference_or_fact(state["input"]):
            self.memory.add(
                state["input"],
                kind="semantic",
                user_id=user_id,
                session_id=session_id,
                importance=0.90,
                metadata={"source": "explicit_user_statement"},
            )
        return {"final_answer": answer}

    @staticmethod
    def _looks_like_preference_or_fact(prompt: str) -> bool:
        lower = prompt.casefold()
        markers = ("تذكر", "احفظ", "لا تنس", "أفضل", "يفضل", "مهم", "remember", "prefer", "always")
        return any(marker in lower for marker in markers)

    def run(self, prompt: str, *, user_id: str = "default_user", session_id: str = "default_session") -> dict[str, Any]:
        clean_prompt = " ".join(prompt.strip().split())
        if not clean_prompt:
            raise ValueError("Prompt cannot be empty")
        state: AgentState = {
            "input": clean_prompt,
            "user_id": user_id,
            "session_id": session_id,
            "plan": [],
            "current_step": 0,
            "results": [],
            "feedback": "",
            "review_attempts": 0,
            "need_revision": False,
            "final_answer": "",
        }
        result = self.graph.invoke(state)
        return {
            "answer": result["final_answer"],
            "plan": result["plan"],
            "steps_completed": len(result.get("results", [])),
            "review_attempts": result.get("review_attempts", 0),
            "memory_context": result.get("context", ""),
        }
