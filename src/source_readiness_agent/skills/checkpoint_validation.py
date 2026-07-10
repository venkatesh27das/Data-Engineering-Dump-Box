"""Auto Loader configuration validation without stream creation."""

from collections.abc import Callable
from typing import Any


class AutoLoaderConfigurationValidator:
    REQUIRED = {
        "source_path",
        "checkpoint_path",
        "schema_location",
        "file_format",
        "schema_evolution_mode",
        "trigger_mode",
    }

    def __init__(self, uniqueness_check: Callable[[str, str], bool] | None = None) -> None:
        self.uniqueness_check = uniqueness_check or (lambda _source, _checkpoint: True)

    def validate(self, configuration: dict[str, Any], source_id: str) -> list[str]:
        errors = [
            f"missing Auto Loader field: {field}"
            for field in sorted(self.REQUIRED - configuration.keys())
        ]
        checkpoint = str(configuration.get("checkpoint_path", ""))
        source = str(configuration.get("source_path", ""))
        schema = str(configuration.get("schema_location", ""))
        if checkpoint and checkpoint in {source, schema}:
            errors.append("checkpoint path must be separate from source and schema paths")
        if checkpoint and not self.uniqueness_check(source_id, checkpoint):
            errors.append("checkpoint conflicts with another source")
        if configuration.get("schema_evolution_mode") not in {
            "addNewColumns",
            "rescue",
            "failOnNewColumns",
            "none",
        }:
            errors.append("unsupported schema evolution mode")
        if configuration.get("trigger_mode") not in {"availableNow", "continuous"}:
            errors.append("unsupported Auto Loader trigger mode")
        return errors
