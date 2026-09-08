import json

import networkx as nx

from app.models.assets import FormulaAsset, TableAsset
from app.models.region import Region
from app.models.workbook import Sheet, Workbook


def cell_node(workbook_id: str, sheet: str, address: str, external: bool = False) -> str:
    # JSON encoding keeps sheet names and delimiters unambiguous.
    return json.dumps(
        [workbook_id, "external" if external else "local", sheet, address], separators=(",", ":")
    )


def build_graph(
    workbook: Workbook,
    sheets: list[Sheet],
    regions: list[Region],
    tables: list[TableAsset],
    formulas: list[FormulaAsset],
    texts=None,
    images=None,
    charts=None,
) -> nx.DiGraph:
    graph = nx.DiGraph(schema_version="1")
    graph.add_node(workbook.workbook_id, type="WORKBOOK", filename=workbook.filename)
    by_name = {s.name: s.sheet_id for s in sheets}
    by_id = {s.sheet_id: s.name for s in sheets}
    for s in sheets:
        graph.add_node(s.sheet_id, type="SHEET", name=s.name, visibility=s.visibility)
        graph.add_edge(workbook.workbook_id, s.sheet_id, relationship="CONTAINS")
    for r in regions:
        graph.add_node(r.region_id, type="REGION", source_range=r.range)
        graph.add_edge(r.sheet_id, r.region_id, relationship="CONTAINS")
    for t in tables:
        graph.add_node(t.table_id, type="TABLE", name=t.table_name, source_range=t.source_range)
        graph.add_edge(t.region_id, t.table_id, relationship="CONTAINS")

    def add_location(sheet, address, kind, external=False):
        node = cell_node(workbook.workbook_id, sheet, address, external)
        graph.add_node(node, type=kind, sheet=sheet, address=address, external=external)
        if sheet in by_name and not external:
            graph.add_edge(by_name[sheet], node, relationship="CONTAINS")
        return node

    for f in formulas:
        source = add_location(by_id[f.sheet_id], f.cell, "CELL")
        graph.nodes[source]["formula"] = f.formula
        for ref in f.references:
            target = add_location(ref.sheet, ref.address, ref.kind, ref.external)
            graph.add_edge(source, target, relationship="DEPENDS_ON")
    for assets, id_field, kind in (
        (texts or [], "text_asset_id", "TEXT_ASSET"),
        (images or [], "image_id", "IMAGE"),
        (charts or [], "chart_id", "CHART"),
    ):
        for asset in assets:
            identifier = getattr(asset, id_field)
            graph.add_node(identifier, type=kind)
            graph.add_edge(
                asset.region_id or asset.sheet_id or workbook.workbook_id, identifier, relationship="CONTAINS"
            )
    return graph
