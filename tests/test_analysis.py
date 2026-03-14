from backend.core.analysis import build_map_points, build_summary, compute_pairwise_distances, normalize_personas
from backend.core.schemas import Interpretation, Persona, SignalScores


def _mk_persona(name: str, share: float) -> Persona:
    return Persona(name=name, worldview="Test", likely_priorities=["x"], share=share)


def _mk_interp(name: str, share: float, signals: dict) -> Interpretation:
    persona = _mk_persona(name, share)
    return Interpretation(
        persona=persona,
        interpretation=f"{name} interpretation",
        quote=f"I am {name}.",
        key_points=["k1"],
        risks=["risk-a"],
        signals=SignalScores(**signals),
        outlier=signals.get("trust", 50) < 30,
    )


def test_normalize_personas_sums_to_one() -> None:
    personas = [_mk_persona("A", 0.1), _mk_persona("B", 0.2), _mk_persona("C", 0.3)]
    normalized = normalize_personas(personas)

    assert len(normalized) == 3
    assert round(sum(p.share for p in normalized), 4) == 1.0


def test_pairwise_distance_count_and_range() -> None:
    interpretations = [
        _mk_interp(
            "A",
            0.5,
            {"clarity": 90, "trust": 80, "hype": 20, "confusion": 10, "credibility": 85},
        ),
        _mk_interp(
            "B",
            0.3,
            {"clarity": 10, "trust": 20, "hype": 90, "confusion": 80, "credibility": 15},
        ),
        _mk_interp(
            "C",
            0.2,
            {"clarity": 50, "trust": 50, "hype": 50, "confusion": 50, "credibility": 50},
        ),
    ]

    distances = compute_pairwise_distances(interpretations)

    assert len(distances) == 3
    assert all(0 <= item.distance <= 100 for item in distances)


def test_summary_alignment_for_identical_signals_is_high() -> None:
    interpretations = [
        _mk_interp(
            "A",
            0.5,
            {"clarity": 70, "trust": 70, "hype": 40, "confusion": 20, "credibility": 80},
        ),
        _mk_interp(
            "B",
            0.5,
            {"clarity": 70, "trust": 70, "hype": 40, "confusion": 20, "credibility": 80},
        ),
    ]
    distances = compute_pairwise_distances(interpretations)
    summary = build_summary(interpretations, distances)

    assert summary.alignment_score == 100.0
    assert summary.divergence_score == 0.0


def test_map_points_in_bounds() -> None:
    interpretations = [
        _mk_interp(
            "A",
            1.0,
            {"clarity": 70, "trust": 90, "hype": 20, "confusion": 10, "credibility": 80},
        )
    ]

    points = build_map_points(interpretations)
    assert len(points) == 1
    assert -1.0 <= points[0].x <= 1.0
    assert -1.0 <= points[0].y <= 1.0
