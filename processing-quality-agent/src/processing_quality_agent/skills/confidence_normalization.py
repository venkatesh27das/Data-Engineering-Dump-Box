from __future__ import annotations


def normalize_confidence(
    value: float | None, *, minimum: float = 0.0, maximum: float = 1.0
) -> float:
    """Normalize parser confidence to [0, 1], accepting common 0-100 values."""
    if value is None:
        return 0.5
    if value > 1 and value <= 100:
        value /= 100
    if maximum <= minimum:
        raise ValueError("maximum must be greater than minimum")
    return max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))
