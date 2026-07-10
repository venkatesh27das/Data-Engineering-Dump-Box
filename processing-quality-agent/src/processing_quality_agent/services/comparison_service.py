from processing_quality_agent.models.responses import ParserComparison
from processing_quality_agent.skills.parser_comparison import rank_parsers


class ComparisonService:
    def compare(self, metrics: list[dict[str, float | str]], profile: str) -> ParserComparison:
        return rank_parsers(metrics, profile)
