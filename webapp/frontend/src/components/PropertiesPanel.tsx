import { useEffect, useState } from "react";
import type { ConnectionOut, EdgeOut, LineOut, NodeOut, ShapeOut } from "../api";

interface Props {
  nodes: NodeOut[];
  edges: EdgeOut[];
  shapes: ShapeOut[];
  lines: LineOut[];
  connections: Record<string, ConnectionOut[]>;
  selectedNodeIds: string[];
  selectedEdgeId: string | null;
  onSelectNode: (id: string | null) => void;
  onUpdateNode: (nodeId: string, patch: { label?: string; entity_type?: string; fill_override?: string; stroke_override?: string; metadata?: string }) => void;
  onDeleteNode: (nodeId: string) => void;
  onDuplicateNode: (nodeId: string) => void;
  onReparentNode: (nodeId: string, parent: string) => void;
  onBulkDeleteNodes: (nodeIds: string[]) => void;
  onUpdateEdge: (edgeId: string, patch: { relation_type?: string; label?: string; reverse?: boolean }) => void;
  onDeleteEdge: (edgeId: string) => void;
}

export default function PropertiesPanel({
  nodes,
  edges,
  shapes,
  lines,
  connections,
  selectedNodeIds,
  selectedEdgeId,
  onSelectNode,
  onUpdateNode,
  onDeleteNode,
  onDuplicateNode,
  onReparentNode,
  onBulkDeleteNodes,
  onUpdateEdge,
  onDeleteEdge,
}: Props) {
  const edge = selectedEdgeId ? edges.find((e) => e.id === selectedEdgeId) : null;
  const node = !edge && selectedNodeIds.length === 1 ? nodes.find((n) => n.id === selectedNodeIds[0]) : null;

  const [label, setLabel] = useState("");
  const [fill, setFill] = useState("");
  const [stroke, setStroke] = useState("");
  const [meta, setMeta] = useState("");
  const [edgeLabel, setEdgeLabel] = useState("");

  useEffect(() => {
    if (node) {
      setLabel(node.label);
      setFill(node.fill_override || "");
      setStroke(node.stroke_override || "");
      setMeta(node.metadata || "");
    }
  }, [node?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (edge) setEdgeLabel(edge.label || "");
  }, [edge?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (edge) {
    return (
      <div className="panel">
        <h3>Connection</h3>
        <label className="field">
          <span>Relation type</span>
          <select
            value={edge.relation}
            onChange={(e) => onUpdateEdge(edge.id, { relation_type: e.target.value })}
          >
            {lines.map((l) => (
              <option key={l.relation_type} value={l.relation_type}>
                {l.relation_type}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Label</span>
          <input
            value={edgeLabel}
            onChange={(e) => setEdgeLabel(e.target.value)}
            onBlur={() => onUpdateEdge(edge.id, { label: edgeLabel })}
          />
        </label>
        <p className="hint">
          {nodes.find((n) => n.id === edge.source)?.label ?? edge.source} → {nodes.find((n) => n.id === edge.target)?.label ?? edge.target}
        </p>
        <div className="btn-row">
          <button className="btn" onClick={() => onUpdateEdge(edge.id, { reverse: true })}>
            Reverse
          </button>
          <button className="btn btn-danger" onClick={() => onDeleteEdge(edge.id)}>
            Delete
          </button>
        </div>
        <button className="link-btn" onClick={() => onSelectNode(null)}>
          Clear selection
        </button>
      </div>
    );
  }

  if (selectedNodeIds.length > 1) {
    return (
      <div className="panel">
        <h3>{selectedNodeIds.length} shapes selected</h3>
        <div className="btn-row">
          <button className="btn btn-danger" onClick={() => onBulkDeleteNodes(selectedNodeIds)}>
            Delete all
          </button>
          <button className="link-btn" onClick={() => onSelectNode(null)}>
            Clear selection
          </button>
        </div>
      </div>
    );
  }

  if (!node) {
    return (
      <div className="panel">
        <p className="hint">Click a shape or connection to edit it here.</p>
      </div>
    );
  }

  const conns = connections[node.id] || [];

  return (
    <div className="panel">
      <h3>{node.label}</h3>
      <label className="field">
        <span>Label</span>
        <input value={label} onChange={(e) => setLabel(e.target.value)} onBlur={() => onUpdateNode(node.id, { label })} />
      </label>
      <label className="field">
        <span>Entity type</span>
        <select value={node.type} onChange={(e) => onUpdateNode(node.id, { entity_type: e.target.value })}>
          {shapes.map((s) => (
            <option key={s.entity_type} value={s.entity_type}>
              {s.entity_type}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Parent container</span>
        <select value={node.parent || ""} onChange={(e) => onReparentNode(node.id, e.target.value)}>
          <option value="">(none — top level)</option>
          {nodes
            .filter((n) => n.id !== node.id)
            .map((n) => (
              <option key={n.id} value={n.id}>
                {n.label}
              </option>
            ))}
        </select>
      </label>
      <div className="field-row">
        <label className="field">
          <span>Fill override</span>
          <input
            type="color"
            value={fill || "#ffffff"}
            onChange={(e) => setFill(e.target.value)}
            onBlur={() => onUpdateNode(node.id, { fill_override: fill })}
          />
        </label>
        <label className="field">
          <span>Stroke override</span>
          <input
            type="color"
            value={stroke || "#333333"}
            onChange={(e) => setStroke(e.target.value)}
            onBlur={() => onUpdateNode(node.id, { stroke_override: stroke })}
          />
        </label>
        <button className="link-btn" onClick={() => { setFill(""); setStroke(""); onUpdateNode(node.id, { fill_override: "", stroke_override: "" }); }}>
          Reset colors
        </button>
      </div>
      <label className="field">
        <span>Metadata (key=value;key=value)</span>
        <textarea rows={2} value={meta} onChange={(e) => setMeta(e.target.value)} onBlur={() => onUpdateNode(node.id, { metadata: meta })} />
      </label>

      <div className="btn-row">
        <button className="btn" onClick={() => onDuplicateNode(node.id)}>
          Duplicate
        </button>
        <button className="btn btn-danger" onClick={() => onDeleteNode(node.id)}>
          Delete
        </button>
      </div>

      <p className="hint" style={{ marginTop: 10 }}>
        Connections ({conns.length})
      </p>
      <ul className="conn-list">
        {conns.map((c) => (
          <li key={c.edge_id} onClick={() => onSelectNode(c.other_id)}>
            <span className={`dir dir-${c.dir}`}>{c.dir === "out" ? "→" : "←"}</span>
            <span className="conn-other">{c.other_label}</span>
            {c.label && <span className="conn-label">{c.label}</span>}
          </li>
        ))}
        {conns.length === 0 && <li className="hint">No connections.</li>}
      </ul>
    </div>
  );
}
