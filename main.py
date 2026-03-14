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
    return result.model_dump(mode="json")
