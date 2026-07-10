"""Landing, checkpoint, schema, and quarantine path validation."""

import re

from source_readiness_agent.models.contracts import LandingConfiguration

SAFE_PATH = re.compile(r"^/[A-Za-z0-9_{}=./-]+/$")


def validate_landing(
    config: LandingConfiguration,
    approved_accounts: set[str] | None = None,
    approved_filesystems: set[str] | None = None,
    environment: str | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if approved_accounts and config.storage_account_reference not in approved_accounts:
        errors.append("storage account reference is not approved")
    if approved_filesystems and config.filesystem not in approved_filesystems:
        errors.append("filesystem is not approved")
    if ".." in config.root_path or not SAFE_PATH.match(config.root_path):
        errors.append("landing root path is invalid")
    for token in (
        "{source_system}",
        "{application}",
        "{use_case}",
        "{ingestion_date}",
        "{batch_id}",
    ):
        if token not in config.partition_pattern:
            errors.append(f"partition pattern is missing {token}")
    paths = [
        config.root_path,
        config.checkpoint_path,
        config.schema_location,
        config.quarantine_path,
    ]
    if len(paths) != len(set(paths)):
        errors.append("landing, checkpoint, schema, and quarantine paths must be distinct")
    if not config.append_only:
        errors.append("landing storage must be append-only")
    if environment and environment not in config.root_path:
        warnings.append("landing path does not explicitly include the target environment")
    return errors, warnings
