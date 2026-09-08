from statistics import mean


def assess_quality(regions, tables, formulas, images, charts, workbook, warnings) -> dict:
    components = {
        "structure_detection_score": mean(r.confidence for r in regions) if regions else 1.0,
        "table_extraction_score": mean(
            t.quality_score if t.quality_score is not None else (1.0 if not t.warnings else 0.8)
            for t in tables
        )
        if tables
        else 1.0,
        "formula_parse_score": sum(f.parse_status == "parsed" for f in formulas) / len(formulas)
        if formulas
        else 1.0,
        "dependency_resolution_score": sum(not f.issues for f in formulas) / len(formulas)
        if formulas
        else 1.0,
        "visual_processing_score": min(
            1.0, (len(images) + len(charts)) / (workbook.image_count + workbook.chart_count)
        )
        if workbook.image_count + workbook.chart_count
        else 1.0,
    }
    return {
        "overall_quality_score": round(mean(components.values()), 4),
        "components": components,
        "review_required": sum(r.requires_agent_review for r in regions),
        "warnings": [w.model_dump(mode="json") for w in warnings],
        "method": "Unweighted mean of applicable extraction coverage/confidence components; not formula correctness.",
    }
