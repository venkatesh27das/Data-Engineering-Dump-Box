def complexity_from_signals(table_probability: float, image_probability: float) -> float:
    return min(1.0, max(0.0, (table_probability + image_probability) / 2))
