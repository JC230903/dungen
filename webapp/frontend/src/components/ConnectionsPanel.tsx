import type { ConnectionOut, NodeOut } from "../api";

interface Props {
  selectedId: string | null;
  nodes: NodeOut[];
  connections: Record<string, ConnectionOut[]>;
  onSelect: (id: string | null) => void;
}

export default function ConnectionsPanel({ selectedId, nodes, connections, onSelect }: Props) {
  if (!selectedId) {
    return (
      <div className="panel">
        <p className="hint">Click any shape to see its connections here.</p>
      </div>
    );
  }
  const node = nodes.find((n) => n.id === selectedId);
  const conns = connections[selectedId] || [];
  return (
    <div className="panel">
      <h3>{node?.label ?? selectedId}</h3>
      <p className="hint">
        Connections ({conns.length})
      </p>
      <ul className="conn-list">
        {conns.map((c) => (
          <li key={c.edge_id} onClick={() => onSelect(c.other_id)}>
            <span className={`dir dir-${c.dir}`}>{c.dir === "out" ? "→" : "←"}</span>
            <span className="conn-other">{c.other_label}</span>
            {c.label && <span className="conn-label">{c.label}</span>}
          </li>
        ))}
        {conns.length === 0 && <li className="hint">No connections.</li>}
      </ul>
      <button className="link-btn" onClick={() => onSelect(null)}>
        Clear selection
      </button>
    </div>
  );
}
