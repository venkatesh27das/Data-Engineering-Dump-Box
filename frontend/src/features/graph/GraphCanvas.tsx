import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { Hand, Maximize, Minus, MousePointer2, Plus } from "lucide-react";
import { useEffect, useRef } from "react";

import type { GraphData } from "../../types/graph";
import { colorForType } from "./graphUtils";

export function GraphCanvas({ graph, selectedId, onSelect }: { graph: GraphData; selectedId: string | null; onSelect: (nodeId: string | null) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    if (!container.current) return;
    const elements: ElementDefinition[] = [
      ...graph.nodes.map((node) => ({ data: { ...node.data, color: colorForType(node.data.type) } })),
      ...graph.edges,
    ];
    const cy = cytoscape({
      container: container.current,
      elements,
      minZoom: 0.25,
      maxZoom: 2.5,
      boxSelectionEnabled: true,
      style: [
        { selector: "node", style: { "background-color": "data(color)", "background-opacity": .1, "border-color": "data(color)", "border-width": 2, "label": "data(label)", "color": "#17203a", "font-size": 10, "font-weight": 600, "text-valign": "center", "text-halign": "center", "text-wrap": "wrap", "text-max-width": "78px", "width": 74, "height": 74 } },
        { selector: "node:selected", style: { "border-width": 4, "background-opacity": .2, "overlay-color": "#5b3fd3", "overlay-opacity": .08 } },
        { selector: "edge", style: { "width": 1.4, "line-color": "#aeb7ca", "target-arrow-color": "#aeb7ca", "target-arrow-shape": "triangle", "curve-style": "bezier", "label": "data(label)", "font-size": 7, "color": "#546078", "text-background-color": "#ffffff", "text-background-opacity": .9, "text-background-padding": "2px", "text-rotation": "autorotate" } },
        { selector: "edge:selected", style: { "line-color": "#5b3fd3", "target-arrow-color": "#5b3fd3", "width": 2.5 } },
      ],
      layout: { name: "cose", animate: false, padding: 34, nodeRepulsion: () => 7200, idealEdgeLength: () => 115, gravity: .2 },
    });
    cy.on("tap", "node", (event) => onSelect(event.target.id()));
    cy.on("tap", (event) => { if (event.target === cy) onSelect(null); });
    const fitGraph = () => cy.fit(undefined, 35);
    window.addEventListener("knowledge-graph-fit", fitGraph);
    cyRef.current = cy;
    return () => { window.removeEventListener("knowledge-graph-fit", fitGraph); cy.destroy(); cyRef.current = null; };
  }, [graph, onSelect]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().unselect();
    if (selectedId) cy.getElementById(selectedId).select();
  }, [selectedId]);

  return (
    <div className="cytoscape-shell">
      <div aria-label="Interactive knowledge graph" className="cytoscape-canvas" ref={container} />
      <div className="canvas-controls">
        <button aria-label="Selection mode" type="button"><MousePointer2 size={14} /></button>
        <button aria-label="Pan by dragging" type="button"><Hand size={14} /></button>
        <button aria-label="Zoom in" onClick={() => cyRef.current?.zoom({ level: Math.min(2.5, cyRef.current.zoom() * 1.18), renderedPosition: { x: 280, y: 240 } })} type="button"><Plus size={14} /></button>
        <button aria-label="Zoom out" onClick={() => cyRef.current?.zoom({ level: Math.max(.25, cyRef.current.zoom() / 1.18), renderedPosition: { x: 280, y: 240 } })} type="button"><Minus size={14} /></button>
        <button aria-label="Fit graph" onClick={() => cyRef.current?.fit(undefined, 35)} type="button"><Maximize size={14} /></button>
      </div>
    </div>
  );
}
