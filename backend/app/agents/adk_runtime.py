class GoogleADKRuntime:
    """Reserved adapter boundary for a future Google ADK implementation."""

    framework_name = "google_adk_not_implemented"

    def __init__(self, *_args, **_kwargs):
        raise NotImplementedError("Google ADK is an adapter boundary only in this release")
