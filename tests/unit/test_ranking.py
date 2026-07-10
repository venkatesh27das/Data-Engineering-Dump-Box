from processing_quality_agent.skills.parser_comparison import rank_parsers


def test_parser_ranking_returns_components():
    result = rank_parsers(
        [
            {
                "parser_id": "a",
                "quality": 0.9,
                "success": 0.9,
                "latency": 0.8,
                "cost": 0.8,
                "stability": 0.9,
            },
            {
                "parser_id": "b",
                "quality": 0.5,
                "success": 0.9,
                "latency": 0.9,
                "cost": 0.9,
                "stability": 0.9,
            },
        ]
    )
    assert result.recommended_parser_id == "a"
    assert result.rankings[0].overall_score > result.rankings[1].overall_score
