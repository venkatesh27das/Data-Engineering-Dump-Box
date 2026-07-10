"""ADLS Gen2 connector using managed identity/DefaultAzureCredential."""

from __future__ import annotations

from urllib.parse import urlparse

from source_readiness_agent.models.contracts import (
    ConnectionValidationResult,
    SampleReadRequest,
    SourceDefinition,
    SourceInventoryEstimate,
    SourceListRequest,
    SourceObject,
    SourceObjectMetadata,
    SourceSample,
)


class ADLSConnector:
    source_type = "ADLS"

    def __init__(self, allowed_account_references: set[str], allowed_filesystems: set[str]) -> None:
        self.allowed_accounts = allowed_account_references
        self.allowed_filesystems = allowed_filesystems

    def _parts(self, source: SourceDefinition) -> tuple[str, str, str]:
        parsed = urlparse(source.source_location)
        if parsed.scheme != "abfss" or "@" not in parsed.netloc:
            raise ValueError("ADLS location must be an abfss URI")
        filesystem, host = parsed.netloc.split("@", 1)
        account = host.split(".", 1)[0]
        if account not in self.allowed_accounts or filesystem not in self.allowed_filesystems:
            raise PermissionError("ADLS account or filesystem is not allowlisted")
        return account, filesystem, parsed.path.lstrip("/")

    def _client(self, source: SourceDefinition):  # type: ignore[no-untyped-def]
        try:
            from azure.identity.aio import DefaultAzureCredential
            from azure.storage.filedatalake.aio import DataLakeServiceClient
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("install Azure connector dependencies") from exc
        account, filesystem, directory = self._parts(source)
        service = DataLakeServiceClient(
            f"https://{account}.dfs.core.windows.net", credential=DefaultAzureCredential()
        )
        return service, service.get_file_system_client(filesystem), directory

    async def validate_connection(self, source: SourceDefinition) -> ConnectionValidationResult:
        try:
            service, fs, directory = self._client(source)
            iterator = fs.get_paths(path=directory, recursive=False, max_results=1)
            async for _ in iterator:
                break
            await service.close()
            return ConnectionValidationResult(
                accessible=True, allowed=True, permissions=["READ", "LIST"]
            )
        except PermissionError as exc:
            return ConnectionValidationResult(accessible=False, allowed=False, issues=[str(exc)])
        except Exception as exc:
            return ConnectionValidationResult(
                accessible=False,
                allowed=True,
                issues=[f"ADLS validation failed: {type(exc).__name__}"],
            )

    async def list_objects(self, request: SourceListRequest) -> list[SourceObject]:
        service, fs, directory = self._client(request.source)
        results: list[SourceObject] = []
        try:
            async for item in fs.get_paths(path=directory, recursive=False):
                if len(results) >= request.maximum_objects:
                    break
                if item.is_directory:
                    continue
                name = item.name.rsplit("/", 1)[-1]
                results.append(
                    SourceObject(
                        object_id=f"{request.source.source_id}:{item.name}",
                        source_id=request.source.source_id,
                        path_or_uri=f"abfss://{item.name}",
                        file_name=name,
                        extension=name.rsplit(".", 1)[-1].lower() if "." in name else "",
                        file_size_bytes=item.content_length or 0,
                        last_modified_at=item.last_modified,
                        source_metadata={"etag": item.etag},
                    )
                )
            return results
        finally:
            await service.close()

    async def read_metadata(self, source_object: SourceObject) -> SourceObjectMetadata:
        return SourceObjectMetadata(
            object_id=source_object.object_id, values=source_object.source_metadata
        )

    async def read_sample(self, request: SampleReadRequest) -> SourceSample:
        raise NotImplementedError("bind a governed ADLS range-read adapter for production")

    async def estimate_inventory(self, source: SourceDefinition) -> SourceInventoryEstimate:
        objects = await self.list_objects(SourceListRequest(source=source, maximum_objects=10_000))
        return SourceInventoryEstimate(
            estimated_file_count=len(objects),
            estimated_total_bytes=sum(x.file_size_bytes for x in objects),
            complete=len(objects) < 10_000,
        )
