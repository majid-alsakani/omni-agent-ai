"""FastAPI entrypoint for Omni-Agent."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .agent_engine import AgentEngine
from .memory import MemoryStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEMORY_PATH = PROJECT_ROOT / "data" / "memory.json"
store = MemoryStore(MEMORY_PATH)
engine = AgentEngine(store)

app = FastAPI(
    title="Omni-Agent AI",
    version="2.1.0",
    description="A testable LangGraph agent with persistent episodic and semantic memory.",
)


class Query(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)
    user_id: str = Field(default="default_user", min_length=1, max_length=128)
    session_id: str = Field(default="default_session", min_length=1, max_length=128)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "Omni-Agent AI", "status": "ready", "version": app.version}


@app.get("/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "memory_records": len(store.records), "engine": "langgraph"}


@app.post("/ask")
async def ask_agent(query: Query) -> dict[str, object]:
    try:
        result = engine.run(
            query.prompt,
            user_id=query.user_id,
            session_id=query.session_id,
        )
        return {"status": "success", "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Agent execution failed") from exc


@app.get("/memory")
async def get_memory(user_id: str = "default_user", session_id: str | None = None) -> dict[str, object]:
    records = store.recent(user_id=user_id, session_id=session_id, limit=50)
    return {
        "count": len(records),
        "items": [record.to_dict() for record in records],
    }
