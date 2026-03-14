from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class SignalScores(BaseModel):
    clarity: float = Field(..., description="How understandable the message feels.")
    trust: float = Field(..., description="How trustworthy the message feels.")
    hype: float = Field(..., description="How overhyped/exciting the message feels.")
    confusion: float = Field(..., description="How confusing the message feels.")
    credibility: float = Field(..., description="How credible and grounded the message feels.")

    @field_validator("clarity", "trust", "hype", "confusion", "credibility", mode="before")
    @classmethod
    def _coerce_and_clamp(cls, value: Any) -> float:
        if value is None:
            raise ValueError("Signal value cannot be null")
        number = float(value)
        return max(0.0, min(100.0, number))


class Persona(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    worldview: str = Field(..., min_length=1, max_length=600)
    likely_priorities: list[str] = Field(default_factory=list)
    share: float = Field(..., ge=0.0, le=1.0)

    @field_validator("likely_priorities", mode="before")
    @classmethod
    def _coerce_priorities(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return [str(value).strip()] if str(value).strip() else []


class MeaningMapRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Message to analyze")
    message_type: str = Field(default="general", description="e.g. startup_pitch, social_post")
    context: str | None = Field(default=None)
    objective: str | None = Field(default=None)
    num_personas: int = Field(default=5, ge=2, le=8)
    personas: list[Persona] | None = Field(default=None)
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_persona_count(self) -> "MeaningMapRequest":
        if self.personas:
            self.num_personas = len(self.personas)
        return self


class Interpretation(BaseModel):
    persona: Persona
    interpretation: str = Field(..., min_length=1)
    quote: str = Field(default="", description="1-2 sentence first-person quote from this persona")
    key_points: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    signals: SignalScores
    outlier: bool = Field(default=False, description="True if this persona's trust < 30")


class PairwiseDistance(BaseModel):
    persona_a: str
    persona_b: str
    distance: float = Field(..., ge=0.0, le=100.0)


class MapPoint(BaseModel):
    persona_name: str
    audience_share: float
    x: float = Field(..., ge=-1.0, le=1.0)
    y: float = Field(..., ge=-1.0, le=1.0)
    signals: SignalScores
    interpretation_excerpt: str
    outlier: bool = Field(default=False)


class MeaningMapSummary(BaseModel):
    alignment_score: float = Field(..., ge=0.0, le=100.0)
    divergence_score: float = Field(..., ge=0.0, le=100.0)
    risk_index: float = Field(..., ge=0.0, le=100.0)
    top_confusion_personas: list[str]
    low_trust_personas: list[str]
    key_misunderstanding_risks: list[dict[str, Any]]


class MeaningMapResult(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model: str
    input_echo: MeaningMapRequest
    personas: list[Persona]
    interpretations: list[Interpretation]
    pairwise_distances: list[PairwiseDistance]
    map_points: list[MapPoint]
    summary: MeaningMapSummary
