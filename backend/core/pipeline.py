from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

from .analysis import build_map_points, build_summary, compute_pairwise_distances, normalize_personas
from .client import GradientLLMClient
from .prompts import INTERPRETATION_SYSTEM_PROMPT, PERSONA_DISTRIBUTION_SYSTEM_PROMPT
from .schemas import (
    Interpretation,
    MeaningMapRequest,
    MeaningMapResult,
    Persona,
    SignalScores,
)

_DEFAULT_PERSONA_LIBRARY: list[dict[str, Any]] = [
    {
        "name": "Enthusiastic Early Adopter",
        "worldview": "Looks for bold innovation and upside; tolerant of ambiguity.",
        "likely_priorities": ["novelty", "speed", "market potential"],
    },
    {
        "name": "Skeptical Pragmatist",
        "worldview": "Needs evidence, practical value, and clear tradeoffs before buying in.",
        "likely_priorities": ["proof", "clarity", "execution risk"],
    },
    {
        "name": "Budget-Conscious Buyer",
        "worldview": "Measures outcomes versus cost and worries about hidden complexity.",
        "likely_priorities": ["price", "ROI", "efficiency"],
    },
    {
        "name": "Industry Insider",
        "worldview": "Benchmarks claims against known patterns and competitive context.",
        "likely_priorities": ["differentiation", "feasibility", "positioning"],
    },
    {
        "name": "Casual Observer",
        "worldview": "Responds to first impressions and emotional tone over technical detail.",
        "likely_priorities": ["simplicity", "tone", "relatability"],
    },
    {
        "name": "Risk-Averse Decision Maker",
        "worldview": "Prioritizes downside protection, compliance, and predictable outcomes.",
        "likely_priorities": ["risk", "reliability", "credibility"],
    },
    {
        "name": "Trend-Driven Influencer",
        "worldview": "Evaluates social momentum and how shareable the message feels.",
        "likely_priorities": ["hype", "social proof", "memorability"],
    },
    {
        "name": "Technical Evaluator",
        "worldview": "Examines architecture-level details and consistency of technical claims.",
        "likely_priorities": ["technical validity", "constraints", "performance"],
    },
]


class MeaningMapPipeline:
    def __init__(self, llm_client: GradientLLMClient, max_concurrency: int = 4) -> None:
        self._llm_client = llm_client
        self._max_concurrency = max(1, max_concurrency)

    @classmethod
    def from_env(cls) -> "MeaningMapPipeline":
        return cls(GradientLLMClient.from_env())

    async def run(self, request: MeaningMapRequest) -> MeaningMapResult:
        personas = request.personas or await self._generate_personas(request)
        personas = normalize_personas(personas)

        if not personas:
            personas = normalize_personas(self._default_personas(request.num_personas))

        interpretations = await self._generate_interpretations(request, personas)
        distances = compute_pairwise_distances(interpretations)
        map_points = build_map_points(interpretations)
        summary = build_summary(interpretations, distances)

        return MeaningMapResult(
            model=self._llm_client.model_id,
            input_echo=request,
            personas=personas,
            interpretations=interpretations,
            pairwise_distances=distances,
            map_points=map_points,
            summary=summary,
        )

    async def _generate_personas(self, request: MeaningMapRequest) -> list[Persona]:
        user_prompt = (
            f"Message type: {request.message_type}\n"
            f"Objective: {request.objective or 'N/A'}\n"
            f"Context: {request.context or 'N/A'}\n"
            f"Requested persona count: {request.num_personas}\n"
            "Message to analyze:\n"
            f"{request.content}"
        )

        try:
            response = await self._llm_client.generate_json(
                system_prompt=PERSONA_DISTRIBUTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=request.temperature,
                max_completion_tokens=1200,
            )
            raw_personas = response.get("personas", [])
            personas = self._parse_personas(raw_personas, expected_count=request.num_personas)
            if len(personas) >= 2:
                return personas
        except Exception as exc:
            logger.error("Persona generation failed: %s", exc, exc_info=True)

        return self._default_personas(request.num_personas)

    async def _generate_interpretations(
        self,
        request: MeaningMapRequest,
        personas: list[Persona],
    ) -> list[Interpretation]:
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def _run_one(persona: Persona) -> Interpretation:
            async with semaphore:
                try:
                    return await self._interpret_for_persona(request, persona)
                except Exception as exc:
                    logger.error("Interpretation failed for persona %r: %s", persona.name, exc, exc_info=True)
                    return self._fallback_interpretation(persona)

        results = await asyncio.gather(*[_run_one(persona) for persona in personas])

        fallback_count = sum(
            1 for r in results if r.interpretation.startswith("Interpretation unavailable")
        )
        if fallback_count == len(results):
            logger.error("All %d persona interpretations failed — likely an API or auth issue", len(results))

        return results

    async def _interpret_for_persona(
        self,
        request: MeaningMapRequest,
        persona: Persona,
    ) -> Interpretation:
        priorities = ", ".join(persona.likely_priorities) if persona.likely_priorities else "N/A"
        user_prompt = (
            f"Persona name: {persona.name}\n"
            f"Persona worldview: {persona.worldview}\n"
            f"Persona priorities: {priorities}\n"
            f"Message type: {request.message_type}\n"
            f"Objective: {request.objective or 'N/A'}\n"
            f"Context: {request.context or 'N/A'}\n"
            "Message:\n"
            f"{request.content}"
        )

        response = await self._llm_client.generate_json(
            system_prompt=INTERPRETATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=request.temperature,
            max_completion_tokens=1200,
        )

        signals = SignalScores.model_validate(response.get("signals", {}))
        quote = str(response.get("quote", "")).strip()
        return Interpretation(
            persona=persona,
            interpretation=str(response.get("interpretation", "")).strip() or "No interpretation generated.",
            quote=quote,
            key_points=_to_clean_list(response.get("key_points")),
            risks=_to_clean_list(response.get("risks")),
            signals=signals,
            outlier=signals.trust < 30,
        )

    @staticmethod
    def _parse_personas(raw: Any, expected_count: int) -> list[Persona]:
        personas: list[Persona] = []
        if not isinstance(raw, list):
            return personas

        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                personas.append(
                    Persona(
                        name=str(item.get("name", "Unnamed Persona")).strip() or "Unnamed Persona",
                        worldview=str(item.get("worldview", "General audience perspective.")).strip()
                        or "General audience perspective.",
                        likely_priorities=_to_clean_list(item.get("likely_priorities")),
                        share=float(item.get("share", 0.0)),
                    )
                )
            except Exception:
                continue

        personas = personas[:expected_count]
        if len(personas) < expected_count:
            defaults = MeaningMapPipeline._default_personas(expected_count)
            existing_names = {p.name for p in personas}
            for default in defaults:
                if default.name not in existing_names:
                    personas.append(default)
                if len(personas) >= expected_count:
                    break
        return personas

    @staticmethod
    def _default_personas(count: int) -> list[Persona]:
        count = max(2, min(count, len(_DEFAULT_PERSONA_LIBRARY)))
        share = round(1.0 / count, 4)
        personas: list[Persona] = []
        for item in _DEFAULT_PERSONA_LIBRARY[:count]:
            personas.append(
                Persona(
                    name=item["name"],
                    worldview=item["worldview"],
                    likely_priorities=item["likely_priorities"],
                    share=share,
                )
            )

        # Ensure exact total share of 1.0.
        diff = round(1.0 - sum(p.share for p in personas), 4)
        if personas and abs(diff) > 0:
            personas[-1] = personas[-1].model_copy(update={"share": round(personas[-1].share + diff, 4)})
        return personas

    @staticmethod
    def _fallback_interpretation(persona: Persona) -> Interpretation:
        return Interpretation(
            persona=persona,
            interpretation=(
                "Interpretation unavailable from model; using conservative fallback. "
                "This persona may need manual review for final messaging decisions."
            ),
            quote="I can't form an opinion without more information.",
            key_points=["Fallback interpretation"],
            risks=["Missing model output for this persona"],
            signals=SignalScores(
                clarity=50,
                trust=50,
                hype=50,
                confusion=50,
                credibility=50,
            ),
            outlier=False,
        )


def _to_clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned[:6]

    text = str(value).strip()
    return [text] if text else []
