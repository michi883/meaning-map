from __future__ import annotations

from dotenv import load_dotenv
from gradient_adk import entrypoint
from pydantic import ValidationError

from backend.core.pipeline import MeaningMapPipeline
from backend.core.schemas import MeaningMapRequest

load_dotenv()
_pipeline: MeaningMapPipeline | None = None


def _get_pipeline() -> MeaningMapPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = MeaningMapPipeline.from_env()
    return _pipeline


@entrypoint
async def run(payload: dict, context: dict) -> dict:
    """Gradient ADK entrypoint."""
    try:
        request = MeaningMapRequest.model_validate(payload)
    except ValidationError as exc:
        return {
            "error": "Invalid payload",
            "details": exc.errors(),
            "expected_keys": [
                "content",
                "message_type",
                "context",
                "objective",
                "num_personas",
                "personas",
                "temperature",
            ],
        }

    try:
        pipeline = _get_pipeline()
    except Exception as exc:
        return {
            "error": "Agent configuration error",
            "details": str(exc),
            "hint": "Set GRADIENT_MODEL_ACCESS_KEY (and optionally GRADIENT_MODEL_ID/GRADIENT_BASE_URL).",
        }

    result = await pipeline.run(request)
    result_dict = result.model_dump(mode="json")

    # Persist to DB if DATABASE_URL is configured
    try:
        import os
        if os.getenv("DATABASE_URL", "").strip():
            from backend.core.db import init_db, save_analysis
            from backend.core.embeddings import GradientEmbeddingsClient

            await init_db()
            embedding = None
            try:
                emb_client = GradientEmbeddingsClient.from_env()
                embedding = await emb_client.embed(request.content)
            except Exception:
                pass
            analysis_id = await save_analysis(
                content=request.content,
                message_type=request.message_type,
                model=result_dict.get("model", "unknown"),
                summary=result_dict.get("summary", {}),
                result=result_dict,
                embedding=embedding,
            )
            result_dict["analysis_id"] = analysis_id
    except Exception:
        pass

    return result_dict
