"""Unity Catalog permission check adapter boundary."""


class PermissionsChecker:
    async def check_unity_catalog_permissions(
        self, securable: str, actor: str
    ) -> dict[str, object]:
        raise NotImplementedError("bind an approved Unity Catalog grants adapter")
