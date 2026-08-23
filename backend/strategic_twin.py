"""Strategic Decision Twin: evidence-led planning with governed learning.

The twin does not execute external actions.  It retrieves relevant approved
precedents, analyzes new evidence locally, creates a reviewable decision draft,
and only writes an approved decision back to semantic memory after a human call.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .data_analysis import DataAnalysisEngine
from .memory import MemoryRecord, MemoryStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrategicTwinEngine:
    """Governed strategic planning loop over historical precedents and new data."""

    def __init__(self, memory: MemoryStore, data_engine: DataAnalysisEngine, draft_path: str | Path | None = None) -> None:
        self.memory = memory
        self.data_engine = data_engine
        self.draft_path = Path(draft_path) if draft_path else None
        self._drafts: dict[str, dict[str, Any]] = {}
        self._load_drafts()

    def _load_drafts(self) -> None:
        if not self.draft_path or not self.draft_path.exists():
            return
        try:
            payload = json.loads(self.draft_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                self._drafts = {str(item["id"]): dict(item) for item in payload if "id" in item}
        except (OSError, ValueError, TypeError, KeyError):
            self._drafts = {}

    def _persist_drafts(self) -> None:
        if not self.draft_path:
            return
        self.draft_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.draft_path.with_suffix(self.draft_path.suffix + ".tmp")
        temporary.write_text(json.dumps(list(self._drafts.values()), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.draft_path)

    def precedents(self, objective: str, *, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        matches = self.memory.search(
            objective,
            user_id=user_id,
            kinds=("semantic", "procedural"),
            limit=limit,
        )
        return [self._precedent_view(record) for record in matches]

    def analyze(
        self,
        content: bytes,
        *,
        source_name: str,
        objective: str,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        objective = " ".join(objective.strip().split())
        if not objective:
            raise ValueError("اكتب هدفاً استراتيجياً واضحاً قبل تشغيل التوأم")
        precedents = self.precedents(objective, user_id=user_id, limit=5)
        analysis = self.data_engine.run(
            content,
            source_name=source_name,
            user_id=user_id,
            session_id=session_id,
        )
        plan = self._plan(objective, precedents, analysis)
        assessment = self._assess(objective, precedents, analysis)
        draft_id = f"decision_{uuid.uuid4().hex[:12]}"
        draft = {
            "id": draft_id,
            "status": "pending_human_review",
            "created_at": _now(),
            "user_id": user_id,
            "session_id": session_id,
            "objective": objective,
            "plan": plan,
            "precedents": precedents,
            "evidence": self._evidence(analysis),
            "assessment": assessment,
            "analysis": analysis,
            "approval": None,
        }
        self._drafts[draft_id] = draft
        self._persist_drafts()
        self.memory.add(
            f"مسودة قرار استراتيجية: {objective}. الحالة: مراجعة بشرية مطلوبة. الثقة: {assessment['confidence_score']}/100.",
            kind="episodic",
            user_id=user_id,
            session_id=session_id,
            importance=0.8,
            metadata={"mode": "strategic_twin", "draft_id": draft_id, "status": draft["status"]},
        )
        return self._public_draft(draft)

    def approve(
        self,
        draft_id: str,
        *,
        user_id: str,
        approval_note: str,
        outcome: str | None = None,
    ) -> dict[str, Any]:
        draft = self._drafts.get(draft_id)
        if not draft:
            raise ValueError("لم يتم العثور على مسودة القرار")
        if draft["user_id"] != user_id:
            raise ValueError("لا تملك صلاحية اعتماد هذه المسودة")
        if draft["status"] != "pending_human_review":
            raise ValueError("تمت معالجة هذه المسودة مسبقاً")
        note = " ".join(approval_note.strip().split())
        if not note:
            raise ValueError("أضف ملاحظة اعتماد تشرح أساس القرار")
        decision = draft["assessment"]["recommendation"]
        semantic = self.memory.add(
            (
                f"قرار استراتيجي معتمد: الهدف {draft['objective']}. التوصية: {decision}. "
                f"أساس الاعتماد: {note}."
                + (f" النتيجة اللاحقة: {outcome}." if outcome else "")
            ),
            kind="semantic",
            user_id=user_id,
            session_id=draft["session_id"],
            importance=0.95,
            metadata={
                "mode": "strategic_twin",
                "draft_id": draft_id,
                "approval_note": note,
                "outcome": outcome,
                "confidence_score": draft["assessment"]["confidence_score"],
                "data_quality_score": draft["evidence"]["quality_score"],
            },
        )
        draft["status"] = "approved_and_learned"
        draft["approval"] = {"approved_at": _now(), "approval_note": note, "outcome": outcome, "memory_id": semantic.id}
        self._persist_drafts()
        return self._public_draft(draft)

    def _plan(self, objective: str, precedents: list[dict[str, Any]], analysis: dict[str, Any]) -> list[dict[str, str]]:
        steps = [
            {"agent": "Precedent Retrieval Agent", "action": "استدعاء سوابق معتمدة ذات معنى قريب من الهدف", "status": f"{len(precedents)} سوابق مسترجعة"},
            {"agent": "Data Evidence Agent", "action": "فحص الملف وتقييم جودة الدليل الجديد", "status": f"جودة {analysis['quality']['score']}/100"},
            {"agent": "Strategic Planner", "action": "تحديد أسئلة التحقق والفجوات قبل التوصية", "status": "مكتمل"},
            {"agent": "Risk & Governance Agent", "action": "منع التنفيذ الخارجي وإلزام الموافقة البشرية", "status": "مراجعة بشرية مطلوبة"},
        ]
        if analysis["sales"]["detected"]:
            steps.insert(2, {"agent": "Sales Intelligence Agent", "action": "قياس المبيعات والطلبات والإلغاءات والأسواق", "status": "مكتمل"})
        return steps

    def _assess(self, objective: str, precedents: list[dict[str, Any]], analysis: dict[str, Any]) -> dict[str, Any]:
        quality = int(analysis["quality"]["score"])
        sales = analysis["sales"]
        precedent_points = min(15, len(precedents) * 5)
        evidence_points = 15 if sales["detected"] else 7
        confidence = max(0, min(95, round((quality * 0.7) + precedent_points + evidence_points)))
        gaps = []
        if quality < 75:
            gaps.append("جودة البيانات أقل من عتبة القرار المقترحة؛ يجب معالجة القيم الناقصة أو التكرارات أولاً.")
        if not precedents:
            gaps.append("لا توجد سوابق معتمدة مسترجعة؛ تعامل مع التوصية باعتبارها تجربة محكومة لا سياسة ثابتة.")
        if not sales["detected"]:
            gaps.append("لم تكتشف حقول مبيعات موحدة؛ لا يمكن تأكيد مؤشرات تجارية مباشرة.")
        if sales["detected"] and sales["cancellation_rows"] > 0:
            gaps.append("توجد معاملات إلغاء؛ راجع أثرها قبل تفسير إجمالي المبيعات كطلب نهائي.")
        if not gaps:
            gaps.append("الدليل التحليلي مناسب لمسودة قرار، مع بقاء الموافقة البشرية إلزامية.")
        if quality < 60:
            recommendation = "أجّل القرار التشغيلي وابدأ دورة تنظيف/استكمال للبيانات."
        elif sales["detected"]:
            recommendation = "نفّذ تجربة محدودة قابلة للقياس، ثم راجع المؤشرات والنتائج قبل التوسع."
        else:
            recommendation = "اعتمد فرضية عمل محدودة واجمع مؤشرات تجارية إضافية قبل الالتزام الواسع."
        return {
            "recommendation": recommendation,
            "confidence_score": confidence,
            "review_required": True,
            "gaps_and_risks": gaps,
            "objective": objective,
        }

    def _evidence(self, analysis: dict[str, Any]) -> dict[str, Any]:
        return {
            "rows": analysis["overview"]["rows"],
            "columns": analysis["overview"]["columns"],
            "quality_score": analysis["quality"]["score"],
            "quality_status": analysis["quality"]["status"],
            "headline": analysis["insights"]["headline"],
            "sales": analysis["sales"],
        }

    def _precedent_view(self, record: MemoryRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "content": record.content,
            "kind": record.kind,
            "importance": record.importance,
            "metadata": record.metadata,
            "created_at": record.created_at,
        }

    def _public_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": draft["id"],
            "status": draft["status"],
            "created_at": draft["created_at"],
            "objective": draft["objective"],
            "plan": draft["plan"],
            "precedents": draft["precedents"],
            "evidence": draft["evidence"],
            "assessment": draft["assessment"],
            "approval": draft["approval"],
        }
