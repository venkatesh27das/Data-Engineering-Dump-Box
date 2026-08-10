import { describe, expect, it } from "vitest";

import type { GraphData } from "../../types/graph";
import { colorForType, filterGraph } from "./graphUtils";

const graph: GraphData = {
  nodes: [
    { data: { id: "A", label: "ACME", type: "Supplier", confidence: .96, sources: [], search_text: "acme supplier tier one" } },
    { data: { id: "B", label: "Contract", type: "Contract", confidence: .9, sources: [], search_text: "master agreement" } },
    { data: { id: "C", label: "Widget", type: "Product", confidence: .88, sources: [], search_text: "widget product" } },
  ],
  edges: [
    { data: { id: "AB", source: "A", target: "B", label: "HAS_CONTRACT", confidence: .9, search_text: "has contract" } },
    { data: { id: "BC", source: "B", target: "C", label: "COVERS", confidence: .85, search_text: "covers" } },
  ],
  counts: { nodes: 3, relationships: 2, node_types: 3, relationship_types: 2 },
};

describe("Graph Explorer filtering", () => {
  it("generates a Cytoscape-compatible deterministic color", () => {
    expect(colorForType("Supplier")).toMatch(/^hsl\(\d+, 68%, 57%\)$/);
    expect(colorForType("Supplier")).toBe(colorForType("Supplier"));
  });

  it("filters nodes and relationships by semantic fields", () => {
    expect(filterGraph(graph, "tier one", "", "", null, 2).nodes.map((node) => node.data.id)).toEqual(["A"]);
    expect(filterGraph(graph, "", "Supplier", "", null, 2).counts).toMatchObject({ nodes: 1, relationships: 0 });
    expect(filterGraph(graph, "", "", "COVERS", null, 2).edges.map((edge) => edge.data.id)).toEqual(["BC"]);
  });

  it("limits traversal around the selected node by hop depth", () => {
    const oneHop = filterGraph(graph, "", "", "", "A", 1);
    expect(oneHop.nodes.map((node) => node.data.id)).toEqual(["A", "B"]);
    expect(oneHop.edges.map((edge) => edge.data.id)).toEqual(["AB"]);
    expect(filterGraph(graph, "", "", "", "A", 2).counts.nodes).toBe(3);
  });
});
