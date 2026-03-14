from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, Field

from backend.core.pipeline import MeaningMapPipeline
from backend.core.schemas import MeaningMapRequest

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_PUBLIC_DIR = PROJECT_ROOT / "frontend" / "public"

app = FastAPI(title="MeaningMap Web App", version="1.0.0")
app.mount("/assets", StaticFiles(directory=str(FRONTEND_PUBLIC_DIR / "assets")), name="assets")

_pipeline: MeaningMapPipeline | None = None


def _get_pipeline() -> MeaningMapPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = MeaningMapPipeline.from_env()
    return _pipeline


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(FRONTEND_PUBLIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/sample-result")
async def sample_result() -> FileResponse:
    return FileResponse(FRONTEND_PUBLIC_DIR / "sample-result.json")


@app.post("/api/analyze")
async def analyze(request: MeaningMapRequest) -> dict:
    try:
        pipeline = _get_pipeline()
        result = await pipeline.run(request)
        return result.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "MeaningMap analysis failed",
                "details": str(exc),
                "hint": "Set GRADIENT_MODEL_ACCESS_KEY and verify GRADIENT_MODEL_ID/GRADIENT_BASE_URL.",
            },
        ) from exc


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
