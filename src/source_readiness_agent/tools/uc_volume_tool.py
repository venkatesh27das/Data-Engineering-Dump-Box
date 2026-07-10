"""Governed UC Volume target validation boundary."""


class UnityCatalogVolumeTool:
    async def validate_uc_volume_target(
        self, catalog: str, schema: str, volume: str
    ) -> dict[str, object]:
        raise NotImplementedError("bind Databricks SDK or governed UC function implementation")
