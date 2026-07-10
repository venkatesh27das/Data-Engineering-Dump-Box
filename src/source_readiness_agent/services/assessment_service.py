"""Read-only assessment workflow."""

from collections.abc import Mapping

from source_readiness_agent.config import Settings
from source_readiness_agent.connectors.base import SourceConnector
from source_readiness_agent.models.contracts import (
    ReadinessAssessment,
    SampleReadRequest,
    SourceInventoryEstimate,
)
from source_readiness_agent.models.requests import AssessSourceRequest
from source_readiness_agent.skills.file_type_detection import profile_file
from source_readiness_agent.skills.ingestion_strategy import recommend_ingestion
from source_readiness_agent.skills.readiness_scoring import score_readiness
from source_readiness_agent.skills.sample_selection import select_sample
from source_readiness_agent.skills.source_profiling import build_source_profile
from source_readiness_agent.tools.repository import InMemoryRepository


class AssessmentService:
    def __init__(
        self,
        repository: InMemoryRepository,
        settings: Settings,
        connectors: Mapping[str, SourceConnector],
        supported_extensions: set[str],
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.connectors = connectors
        self.supported_extensions = supported_extensions

    async def assess(self, request: AssessSourceRequest) -> ReadinessAssessment:
        source = request.source
        if source.source_type.value not in self.connectors:
            raise ValueError(
                f"unsupported or disabled source connector: {source.source_type.value}"
            )
        if not any(
            source.source_location.startswith(prefix) for prefix in self.settings.source_allowlist
        ):
            from source_readiness_agent.models.contracts import (
                ConnectionValidationResult,
                SourceProfile,
            )

            access = ConnectionValidationResult(
                accessible=False, allowed=False, issues=["source path is outside allowlist"]
            )
            profile = SourceProfile(
                source_id=source.source_id, access_validation=access, issues=access.issues
            )
            assessment = score_readiness(profile)
            self.repository.save_assessment(assessment, source)
            return assessment
        connector = self.connectors[source.source_type.value]
        access = await connector.validate_connection(source)
        if not access.accessible or not access.allowed:
            inventory = SourceInventoryEstimate(estimated_file_count=0, estimated_total_bytes=0)
            selections = []
        else:
            from source_readiness_agent.models.contracts import SourceListRequest

            objects = await connector.list_objects(
                SourceListRequest(
                    source=source, maximum_objects=self.settings.maximum_listing_objects
                )
            )
            inventory = await connector.estimate_inventory(source)
            selections = select_sample(objects, request.sample_policy)
        profiles = []
        for selection in selections:
            item = selection.source_object
            content = None
            if (
                item.file_size_bytes
                and item.file_size_bytes <= request.sample_policy.maximum_individual_file_size
            ):
                try:
                    sample = await connector.read_sample(
                        SampleReadRequest(
                            source_object=item,
                            maximum_bytes=min(item.file_size_bytes, 1_048_576) or 1,
                        )
                    )
                    content = sample.content
                except (NotImplementedError, RuntimeError, ValueError):
                    content = None
            profiles.append(
                profile_file(
                    item,
                    self.supported_extensions,
                    request.sample_policy.maximum_individual_file_size,
                    content,
                    set(source.metadata_requirements),
                )
            )
        profile = build_source_profile(source.source_id, inventory, access, profiles)
        assessment = score_readiness(profile)
        assessment.recommended_ingestion_strategy = recommend_ingestion(source, profile)
        self.repository.save_assessment(assessment, source)
        return assessment
