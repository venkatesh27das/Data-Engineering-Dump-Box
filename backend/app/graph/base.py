from abc import ABC, abstractmethod

from app.domain.assets import KnowledgeAssetPackage
from app.domain.publication import PublicationResult


class GraphStoreError(RuntimeError):
    pass


class GraphStoreNotConfigured(GraphStoreError):
    pass


class GraphStore(ABC):
    @property
    @abstractmethod
    def configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def publish_package(self, package: KnowledgeAssetPackage) -> PublicationResult:
        raise NotImplementedError

    @abstractmethod
    async def get_subgraph(self, project_id: str) -> dict[str, list[dict[str, object]]]:
        raise NotImplementedError

    @abstractmethod
    async def get_node(self, project_id: str, node_id: str) -> dict[str, object] | None:
        raise NotImplementedError

    @abstractmethod
    async def query(self, project_id: str, cypher: str, parameters: dict[str, object] | None = None) -> list[dict[str, object]]:
        raise NotImplementedError
