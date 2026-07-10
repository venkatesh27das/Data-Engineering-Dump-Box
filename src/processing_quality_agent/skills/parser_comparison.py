from __future__ import annotations

from processing_quality_agent.models.responses import ParserComparison, ParserScore

PROFILES: dict[str, dict[str, float]] = {
    "QUALITY_FIRST": {
        "quality": 0.65,
        "success": 0.15,
        "latency": 0.05,
        "cost": 0.05,
        "stability": 0.10,
    },
    "BALANCED": {
        "quality": 0.45,
        "success": 0.15,
        "latency": 0.15,
        "cost": 0.15,
        "stability": 0.10,
    },
    "COST_FIRST": {
        "quality": 0.30,
        "success": 0.15,
        "latency": 0.10,
        "cost": 0.35,
        "stability": 0.10,
    },
    "LATENCY_FIRST": {
        "quality": 0.30,
        "success": 0.15,
        "latency": 0.35,
        "cost": 0.10,
        "stability": 0.10,
    },
}


def rank_parsers(
    metrics: list[dict[str, float | str]], profile: str = "BALANCED"
) -> ParserComparison:
    weights = PROFILES.get(profile, PROFILES["BALANCED"])
    rankings: list[ParserScore] = []
    for row in metrics:
        components = {key: float(row.get(key, 0)) for key in weights}
        overall = sum(components[key] * weight for key, weight in weights.items())
        rankings.append(
            ParserScore(
                parser_id=str(row["parser_id"]),
                overall_score=overall,
                quality_score=components["quality"],
                success_score=components["success"],
                latency_score=components["latency"],
                cost_score=components["cost"],
                stability_score=components["stability"],
                rationale=f"Weighted using {profile} profile.",
            )
        )
    rankings.sort(key=lambda item: item.overall_score, reverse=True)
    return ParserComparison(
        rankings=rankings,
        recommended_parser_id=rankings[0].parser_id if rankings else None,
        profile=profile,
    )
