from source_readiness_agent.models.contracts import SampleRun

from .repository import InMemoryRepository


class SampleResultReader:
    def __init__(self, repository: InMemoryRepository) -> None:
        self.repository = repository

    def get_sample_run_status(self, run_id: str) -> SampleRun:
        return self.repository.sample_runs[run_id]
