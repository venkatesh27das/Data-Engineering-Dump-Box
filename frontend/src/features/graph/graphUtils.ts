import type { GraphData } from "../../types/graph";

export function colorForType(type: string): string {
  let hash = 0;
  for (const character of type) hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  return `hsl(${hash % 360}, 68%, 57%)`;
}

export function filterGraph(graph: GraphData, search: string, nodeType: string, relationshipType: string, selectedId: string | null, depth: number): GraphData {
  const query = search.trim().toLowerCase();
  let nodes = graph.nodes.filter((node) => !nodeType || node.data.type === nodeType);
  let nodeIds = new Set(nodes.map((node) => node.data.id));
  let edges = graph.edges.filter((edge) => nodeIds.has(edge.data.source) && nodeIds.has(edge.data.target) && (!relationshipType || edge.data.label === relationshipType));

  if (query) {
    const matchedNodes = new Set(nodes.filter((node) => `${node.data.label} ${node.data.type} ${node.data.search_text}`.toLowerCase().includes(query)).map((node) => node.data.id));
    const matchedEdges = edges.filter((edge) => `${edge.data.label} ${edge.data.search_text}`.toLowerCase().includes(query));
    matchedEdges.forEach((edge) => { matchedNodes.add(edge.data.source); matchedNodes.add(edge.data.target); });
    nodes = nodes.filter((node) => matchedNodes.has(node.data.id));
    nodeIds = new Set(nodes.map((node) => node.data.id));
    edges = edges.filter((edge) => nodeIds.has(edge.data.source) && nodeIds.has(edge.data.target));
  }

  if (selectedId && nodeIds.has(selectedId)) {
    const visible = new Set([selectedId]);
    let frontier = new Set([selectedId]);
    for (let hop = 0; hop < depth; hop += 1) {
      const next = new Set<string>();
      edges.forEach((edge) => {
        if (frontier.has(edge.data.source)) next.add(edge.data.target);
        if (frontier.has(edge.data.target)) next.add(edge.data.source);
      });
      next.forEach((id) => visible.add(id));
      frontier = next;
    }
    nodes = nodes.filter((node) => visible.has(node.data.id));
    nodeIds = new Set(nodes.map((node) => node.data.id));
    edges = edges.filter((edge) => nodeIds.has(edge.data.source) && nodeIds.has(edge.data.target));
  }

  return { nodes, edges, counts: { nodes: nodes.length, relationships: edges.length, node_types: new Set(nodes.map((node) => node.data.type)).size, relationship_types: new Set(edges.map((edge) => edge.data.label)).size } };
}
