"""FastAPI entrypoint for Omni-Agent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent_engine import AgentEngine
from .data_analysis import DataAnalysisEngine
from .memory import MemoryStore
from .multi_agent import MultiAgentEngine
from .vector_memory import LocalVectorBackend, PostgresVectorBackend, VectorMemoryBackend


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEMORY_PATH = PROJECT_ROOT / "data" / "memory.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def _build_vector_backend() -> tuple[VectorMemoryBackend, str]:
    """Choose pgvector when configured, otherwise keep local development frictionless."""
    dsn = os.getenv("OMNI_VECTOR_DSN") or os.getenv("DATABASE_URL")
    if not dsn:
        return LocalVectorBackend(), "local-hashed-vector"
    try:
        backend = PostgresVectorBackend(dsn)
        backend.ensure_schema()
        return backend, backend.name
    except Exception:
        if os.getenv("ALLOW_LOCAL_VECTOR_FALLBACK", "1") != "1":
            raise
        return LocalVectorBackend(), "local-hashed-vector-fallback"


vector_backend, vector_backend_name = _build_vector_backend()
store = MemoryStore(MEMORY_PATH, vector_backend=vector_backend)
engine = AgentEngine(store)
multi_engine = MultiAgentEngine(store)
data_engine = DataAnalysisEngine(store)

app = FastAPI(
    title="Omni-Agent AI",
    version="3.2.0",
    description="A testable LangGraph single-agent and self-planning multi-agent system with persistent memory.",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class Query(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)
    user_id: str = Field(default="default_user", min_length=1, max_length=128)
    session_id: str = Field(default="default_session", min_length=1, max_length=128)
    mode: Literal["single", "multi", "auto"] = "auto"


def _is_complex(prompt: str) -> bool:
    lower = prompt.casefold()
    signals = (
        "عدة وكلاء", "متعدد", "معقد", "قارن", "خطة شاملة", "بحث وتحليل", "مخاطر",
        "multi-agent", "complex", "compare", "research and analyze", "risk",
    )
    return len(prompt.split()) >= 12 or any(signal in lower for signal in signals)


@app.get("/", include_in_schema=False)
async def command_center() -> FileResponse:
    """Serve the interactive product dashboard."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api")
async def api_info() -> dict[str, str]:
    return {"name": "Omni-Agent AI", "status": "ready", "version": app.version}


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "memory_records": len(store.records),
        "engines": ["langgraph-single", "langgraph-multi-agent", "data-analysis-multi-agent"],
        "vector_store": vector_backend_name,
    }


@app.post("/ask")
async def ask_agent(query: Query) -> dict[str, object]:
    try:
        selected_mode = "multi" if query.mode == "auto" and _is_complex(query.prompt) else query.mode
        if selected_mode == "multi":
            result = multi_engine.run(query.prompt, user_id=query.user_id, session_id=query.session_id)
        else:
            result = engine.run(query.prompt, user_id=query.user_id, session_id=query.session_id)
        return {"status": "success", "mode": selected_mode, "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Agent execution failed") from exc


@app.post("/multi-ask")
async def multi_ask_agent(query: Query) -> dict[str, object]:
    """Explicit entry point for autonomous multi-agent planning."""
    try:
        result = multi_engine.run(query.prompt, user_id=query.user_id, session_id=query.session_id)
        return {"status": "success", "mode": "multi", "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Multi-agent execution failed") from exc


@app.post("/analyze-data")
async def analyze_data(
    file: UploadFile = File(..., description="CSV file to analyze"),
    user_id: str = Form("default_user"),
    session_id: str = Form("default_session"),
) -> dict[str, object]:
    """Analyze a CSV locally through profiling, insight, and quality specialists."""
    try:
        content = await file.read()
        result = data_engine.run(
            content,
            source_name=file.filename or "upload.csv",
            user_id=user_id,
            session_id=session_id,
        )
        return {"status": "success", "mode": "data-analysis-multi-agent", "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Data analysis failed") from exc
    finally:
        await file.close()


@app.get("/tools")
async def list_tools() -> dict[str, object]:
    return {
        "count": len(multi_engine.tools.names),
        "tools": multi_engine.tools.names,
        "policy": "Allowlisted tools only; external side effects require human approval.",
    }


@app.get("/memory")
async def get_memory(user_id: str = "default_user", session_id: str | None = None) -> dict[str, object]:
    records = store.recent(user_id=user_id, session_id=session_id, limit=50)
    return {
        "count": len(records),
        "items": [record.to_dict() for record in records],
    }
