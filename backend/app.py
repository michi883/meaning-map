from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, Field

from backend.core.pipeline import MeaningMapPipeline
from backend.core.schemas import MeaningMapRequest

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_PUBLIC_DIR = PROJECT_ROOT / "frontend" / "public"

_pipeline: MeaningMapPipeline | None = None

# Database is optional — works without it for local dev / demo mode
_db_available = False


def _get_pipeline() -> MeaningMapPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = MeaningMapPipeline.from_env()
    return _pipeline


def _has_database() -> bool:
    return bool(os.getenv("DATABASE_URL", "").strip())


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _db_available
    if _has_database():
        try:
            from backend.core.db import init_db
            await init_db()
            _db_available = True
            logger.info("PostgreSQL + pgvector connected")
        except Exception as exc:
            logger.warning("Database unavailable, running without persistence: %s", exc)
    else:
        logger.info("No DATABASE_URL set, running without persistence")
    yield
    if _db_available:
        from backend.core.db import close_db
        await close_db()


app = FastAPI(title="MeaningMap Web App", version="1.0.0", lifespan=lifespan)
app.mount("/assets", StaticFiles(directory=str(FRONTEND_PUBLIC_DIR / "assets")), name="assets")


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(FRONTEND_PUBLIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "database": _db_available}


@app.get("/sample-result")
async def sample_result() -> FileResponse:
    return FileResponse(FRONTEND_PUBLIC_DIR / "sample-result.json")


@app.post("/api/analyze")
async def analyze(request: MeaningMapRequest) -> dict:
    try:
        pipeline = _get_pipeline()
        result = await pipeline.run(request)
        result_dict = result.model_dump(mode="json")

        # Persist to DB with embedding if database is available
        analysis_id = None
        if _db_available:
            try:
                analysis_id = await _persist_analysis(request, result_dict)
            except Exception as exc:
                logger.error("Failed to persist analysis: %s", exc, exc_info=True)

        if analysis_id:
            result_dict["analysis_id"] = analysis_id

        return result_dict
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "MeaningMap analysis failed",
                "details": str(exc),
                "hint": "Set GRADIENT_MODEL_ACCESS_KEY and verify GRADIENT_MODEL_ID/GRADIENT_BASE_URL.",
            },
        ) from exc


async def _persist_analysis(request: MeaningMapRequest, result_dict: dict) -> str:
    from backend.core.db import save_analysis

    # Generate embedding for semantic search
    embedding = None
    try:
        from backend.core.embeddings import GradientEmbeddingsClient
        embeddings_client = GradientEmbeddingsClient.from_env()
        embedding = await embeddings_client.embed(request.content)
    except Exception as exc:
        logger.warning("Embedding generation failed, saving without vector: %s", exc)

    return await save_analysis(
        content=request.content,
        message_type=request.message_type,
        model=result_dict.get("model", "unknown"),
        summary=result_dict.get("summary", {}),
        result=result_dict,
        embedding=embedding,
    )


class FixItRequest(BaseModel):
    content: str = Field(..., min_length=1)
    risk: str = Field(..., min_length=1)
    persona: str = Field(..., min_length=1)


@app.post("/api/fix")
async def fix_message(request: FixItRequest) -> dict:
    try:
        pipeline = _get_pipeline()
        system_prompt = (
            "You are a messaging expert. Rewrite the user's message to address the "
            "specific risk for the specified persona, keeping the same core meaning. "
            "Return strict JSON only: {\"rewrite\": \"string\"}"
        )
        user_prompt = (
            f"Original message:\n{request.content}\n\n"
            f"Risk to address: {request.risk}\n"
            f"Persona affected: {request.persona}\n\n"
            "Rewrite the message to fix this risk for this persona."
        )
        response = await pipeline._llm_client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_completion_tokens=800,
        )
        return {"rewrite": str(response.get("rewrite", "")).strip() or "Could not generate rewrite."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)}) from exc


# ── History & Search endpoints (PostgreSQL + pgvector) ──


@app.get("/api/history")
async def history(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    if not _db_available:
        return {"items": [], "db_available": False}
    from backend.core.db import list_analyses
    items = await list_analyses(limit=limit, offset=offset)
    return {"items": items, "db_available": True}


@app.get("/api/history/{analysis_id}")
async def get_history_item(analysis_id: str) -> dict:
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available")
    from backend.core.db import get_analysis
    item = await get_analysis(analysis_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return item


@app.get("/api/search")
async def search(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=50)) -> dict:
    if not _db_available:
        return {"results": [], "db_available": False}
    try:
        from backend.core.embeddings import GradientEmbeddingsClient
        embeddings_client = GradientEmbeddingsClient.from_env()
        query_embedding = await embeddings_client.embed(q)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": f"Embedding failed: {exc}"}) from exc

    from backend.core.db import search_analyses
    results = await search_analyses(embedding=query_embedding, limit=limit)
    return {"results": results, "db_available": True}
