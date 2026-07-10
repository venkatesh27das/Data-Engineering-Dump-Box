"""No free-form execution planning: modes map to fixed service operations."""

MODE_TO_SERVICE = {
    "ASSESS_SOURCE": "assessment_service",
    "GENERATE_CONFIGURATION": "configuration_service",
    "VALIDATE_CONFIGURATION": "validation_service",
    "SAMPLE_RUN": "sample_run_service",
    "ACTIVATE_CONFIGURATION": "activation_service",
}


def plan(mode: str) -> str:
    try:
        return MODE_TO_SERVICE[mode]
    except KeyError as exc:
        raise ValueError("unsupported operating mode") from exc
