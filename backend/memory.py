"""Persistent memory for Omni-Agent.

The first implementation deliberately uses a small, dependency-free JSON store so it
can be run and tested locally.  The public interface is storage-agnostic: a vector or
hybrid database can replace this class later without changing the agent graph.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


_TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)
_STOP_WORDS = {
    "و", "في", "من", "على", "الى", "إلى", "عن", "هذا", "هذه", "ذلك", "التي",
    "الذي", "ما", "هل", "هو", "هي", "انا", "أنا", "مع", "أن", "إن", "the", "and",
    "for", "from", "with", "that", "this", "what", "how", "are", "is", "to", "of",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_RE.findall(value)
        if len(token) > 1 and token.lower() not in _STOP_WORDS
    }


@dataclass
class MemoryRecord:
    id: str
    content: str
    kind: str
    user_id: str
    session_id: Optional[str] = None
    importance: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    accessed_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryRecord":
        return cls(
            id=str(payload["id"]),
            content=str(payload["content"]),
            kind=str(payload.get("kind", "episodic")),
            user_id=str(payload.get("user_id", "default_user")),
            session_id=payload.get("session_id"),
            importance=float(payload.get("importance", 0.5)),
            metadata=dict(payload.get("metadata", {})),
            created_at=str(payload.get("created_at", _now())),
            accessed_at=str(payload.get("accessed_at", payload.get("created_at", _now()))),
        )


class MemoryStore:
    """Thread-safe persistent memory with deterministic hybrid lexical retrieval."""

    def __init__(self, path: str | Path | None = None, max_episodic_per_session: int = 100) -> None:
        self.path = Path(path) if path else None
        self.max_episodic_per_session = max_episodic_per_session
        self._lock = threading.RLock()
        self._records: list[MemoryRecord] = []
        self._load()

    @property
    def records(self) -> list[MemoryRecord]:
        with self._lock:
            return list(self._records)

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                self._records = [MemoryRecord.from_dict(item) for item in payload]
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            # A corrupt optional cache must not prevent the API from starting.
            self._records = []

    def _persist(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps([record.to_dict() for record in self._records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def add(
        self,
        content: str,
        *,
        kind: str,
        user_id: str,
        session_id: str | None = None,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        """Add or update a memory. Exact duplicates are updated instead of multiplied."""
        clean = " ".join(content.strip().split())
        if not clean:
            raise ValueError("Memory content cannot be empty")
        if kind not in {"episodic", "semantic", "procedural"}:
            raise ValueError("kind must be episodic, semantic, or procedural")
        importance = max(0.0, min(1.0, float(importance)))
        with self._lock:
            duplicate = next(
                (
                    item
                    for item in self._records
                    if item.user_id == user_id and item.kind == kind and item.content == clean
                ),
                None,
            )
            if duplicate:
                duplicate.importance = max(duplicate.importance, importance)
                duplicate.accessed_at = _now()
                duplicate.metadata.update(metadata or {})
                self._persist()
                return duplicate

            record = MemoryRecord(
                id=f"mem_{uuid.uuid4().hex[:12]}",
                content=clean,
                kind=kind,
                user_id=user_id,
                session_id=session_id,
                importance=importance,
                metadata=metadata or {},
            )
            self._records.append(record)
            self._trim_episodic(user_id=user_id, session_id=session_id)
            self._persist()
            return record

    def _trim_episodic(self, *, user_id: str, session_id: str | None) -> None:
        matching = [
            item for item in self._records
            if item.user_id == user_id and item.session_id == session_id and item.kind == "episodic"
        ]
        excess = len(matching) - self.max_episodic_per_session
        if excess <= 0:
            return
        remove_ids = {item.id for item in sorted(matching, key=lambda item: item.created_at)[:excess]}
        self._records = [item for item in self._records if item.id not in remove_ids]

    def search(
        self,
        query: str,
        *,
        user_id: str,
        session_id: str | None = None,
        kinds: Iterable[str] | None = None,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        """Retrieve relevant memories using lexical overlap, importance, and recency."""
        if limit <= 0:
            return []
        query_tokens = _tokens(query)
        allowed = set(kinds) if kinds else None
        with self._lock:
            candidates = [
                item for item in self._records
                if item.user_id == user_id and (allowed is None or item.kind in allowed)
            ]
            scored: list[tuple[float, MemoryRecord]] = []
            for item in candidates:
                item_tokens = _tokens(item.content)
                overlap = len(query_tokens & item_tokens) / max(1, len(query_tokens))
                same_session = 0.12 if session_id and item.session_id == session_id else 0.0
                kind_boost = 0.08 if item.kind == "semantic" else 0.0
                score = overlap * 0.68 + item.importance * 0.20 + same_session + kind_boost
                if not query_tokens:
                    score = item.importance * 0.45 + same_session + kind_boost
                if score > 0 or not query_tokens:
                    scored.append((score, item))
            scored.sort(key=lambda pair: (pair[0], pair[1].created_at), reverse=True)
            selected = [item for _, item in scored[:limit]]
            for item in selected:
                item.accessed_at = _now()
            if selected:
                self._persist()
            return selected

    def recent(
        self,
        *,
        user_id: str,
        session_id: str | None = None,
        limit: int = 8,
    ) -> list[MemoryRecord]:
        with self._lock:
            items = [
                item for item in self._records
                if item.user_id == user_id and item.kind == "episodic"
                and (session_id is None or item.session_id == session_id)
            ]
            return sorted(items, key=lambda item: item.created_at, reverse=True)[:limit]

    def build_context(
        self,
        query: str,
        *,
        user_id: str,
        session_id: str | None = None,
        limit: int = 5,
    ) -> str:
        recent = self.recent(user_id=user_id, session_id=session_id, limit=6)
        relevant = self.search(
            query,
            user_id=user_id,
            session_id=session_id,
            kinds=("semantic", "procedural"),
            limit=limit,
        )
        recent_text = "\n".join(f"- {item.content}" for item in recent) or "لا توجد أحداث سابقة."
        relevant_text = "\n".join(f"- [{item.kind}] {item.content}" for item in relevant) or "لا توجد معرفة محفوظة ذات صلة."
        return (
            "[الأحداث الأخيرة]\n"
            f"{recent_text}\n\n"
            "[المعرفة والمهارات ذات الصلة]\n"
            f"{relevant_text}"
        )

    def clear(self) -> None:
        with self._lock:
            self._records = []
            self._persist()
