from __future__ import annotations

import math

from .schemas import Interpretation, MapPoint, MeaningMapSummary, PairwiseDistance, Persona, SignalScores

_SIGNAL_KEYS = ("clarity", "trust", "hype", "confusion", "credibility")
_MAX_DISTANCE = math.sqrt(len(_SIGNAL_KEYS) * (100.0**2))


def normalize_personas(personas: list[Persona]) -> list[Persona]:
    if not personas:
        return []
    total_share = sum(max(0.0, p.share) for p in personas)
    if total_share <= 0:
        equal_share = round(1.0 / len(personas), 4)
        return [p.model_copy(update={"share": equal_share}) for p in personas]

    normalized = []
    running_sum = 0.0
    for idx, persona in enumerate(personas):
        if idx == len(personas) - 1:
            share = max(0.0, min(1.0, 1.0 - running_sum))
        else:
            share = max(0.0, min(1.0, persona.share / total_share))
            running_sum += share
        normalized.append(persona.model_copy(update={"share": round(share, 4)}))

    # Ensure total is exactly 1 after rounding.
    diff = round(1.0 - sum(p.share for p in normalized), 4)
    if abs(diff) > 0 and normalized:
        last = normalized[-1]
        normalized[-1] = last.model_copy(update={"share": round(max(0.0, min(1.0, last.share + diff)), 4)})
    return normalized


def signal_vector(signals: SignalScores) -> tuple[float, ...]:
    return (
        signals.clarity,
        signals.trust,
        signals.hype,
        signals.confusion,
        signals.credibility,
    )


def compute_pairwise_distances(interpretations: list[Interpretation]) -> list[PairwiseDistance]:
    distances: list[PairwiseDistance] = []
    for i in range(len(interpretations)):
        for j in range(i + 1, len(interpretations)):
            first = interpretations[i]
            second = interpretations[j]
            dist = _euclidean(signal_vector(first.signals), signal_vector(second.signals))
            normalized_dist = round((dist / _MAX_DISTANCE) * 100.0, 2)
            distances.append(
                PairwiseDistance(
                    persona_a=first.persona.name,
                    persona_b=second.persona.name,
                    distance=normalized_dist,
                )
            )
    return sorted(distances, key=lambda d: d.distance, reverse=True)


def build_map_points(interpretations: list[Interpretation]) -> list[MapPoint]:
    points: list[MapPoint] = []
    for item in interpretations:
        x = _to_axis(item.signals.trust)
        y = _to_axis(item.signals.credibility)
        points.append(
            MapPoint(
                persona_name=item.persona.name,
                audience_share=item.persona.share,
                x=x,
                y=y,
                signals=item.signals,
                interpretation_excerpt=item.interpretation[:180],
                outlier=item.outlier,
            )
        )
    return points


def build_summary(interpretations: list[Interpretation], distances: list[PairwiseDistance]) -> MeaningMapSummary:
    if not interpretations:
        return MeaningMapSummary(
            alignment_score=0.0,
            divergence_score=0.0,
            risk_index=0.0,
            top_confusion_personas=[],
            low_trust_personas=[],
            key_misunderstanding_risks=[],
        )

    avg_distance = sum(d.distance for d in distances) / len(distances) if distances else 0.0
    divergence_score = round(max(0.0, min(100.0, avg_distance)), 2)
    alignment_score = round(100.0 - divergence_score, 2)

    weighted_confusion = sum(i.signals.confusion * i.persona.share for i in interpretations)
    weighted_trust = sum(i.signals.trust * i.persona.share for i in interpretations)
    weighted_hype_cred_gap = sum(abs(i.signals.hype - i.signals.credibility) * i.persona.share for i in interpretations)

    risk_index = (
        0.45 * weighted_confusion
        + 0.35 * (100.0 - weighted_trust)
        + 0.20 * weighted_hype_cred_gap
    )

    top_confusion = sorted(interpretations, key=lambda i: i.signals.confusion, reverse=True)[:3]
    low_trust = sorted(interpretations, key=lambda i: i.signals.trust)[:3]

    # Build structured risks with severity and persona attribution
    risk_map: dict[str, list[Interpretation]] = {}
    for item in interpretations:
        for risk in item.risks:
            cleaned = risk.strip()
            if cleaned:
                risk_map.setdefault(cleaned, []).append(item)

    # Sort by number of personas affected (descending), take top 5
    sorted_risks = sorted(risk_map.items(), key=lambda r: len(r[1]), reverse=True)[:5]

    key_risks = []
    for risk_text, affected in sorted_risks:
        min_trust = min(i.signals.trust for i in affected)
        if min_trust < 30:
            severity = "high"
        elif min_trust <= 55:
            severity = "medium"
        else:
            severity = "low"
        key_risks.append({
            "text": risk_text,
            "severity": severity,
            "personas": [i.persona.name for i in affected],
        })

    # Sort by severity: high first, then medium, then low
    severity_order = {"high": 0, "medium": 1, "low": 2}
    key_risks.sort(key=lambda r: severity_order.get(r["severity"], 2))

    return MeaningMapSummary(
        alignment_score=alignment_score,
        divergence_score=divergence_score,
        risk_index=round(max(0.0, min(100.0, risk_index)), 2),
        top_confusion_personas=[item.persona.name for item in top_confusion],
        low_trust_personas=[item.persona.name for item in low_trust],
        key_misunderstanding_risks=key_risks,
    )


def _euclidean(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def _to_axis(value: float) -> float:
    """Map a 0-100 signal value to the [-1, 1] axis range."""
    return round(max(-1.0, min(1.0, (value - 50.0) / 50.0)), 4)
