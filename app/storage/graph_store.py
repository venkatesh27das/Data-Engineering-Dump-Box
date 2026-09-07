import json
from pathlib import Path

import networkx as nx


def save_graph(graph: nx.DiGraph, directory: Path) -> dict:
    # Explicit format avoids NetworkX version-specific node-link defaults.
    payload = {
        "directed": True,
        "multigraph": False,
        "schema_version": 1,
        "nodes": [{"id": n, **attrs} for n, attrs in graph.nodes(data=True)],
        "edges": [{"source": a, "target": b, **attrs} for a, b, attrs in graph.edges(data=True)],
    }
    (directory / "dependency_graph.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    nx.write_graphml(graph, directory / "dependency_graph.graphml")
    return payload
