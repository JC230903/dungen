import { useState } from "react";

interface Props {
  unknownTypes: string[];
  onApply: (nodesCsv: string, edgesCsv: string, shapesCsv: string, linesCsv: string) => void;
}

export default function CsvPanel({ unknownTypes, onApply }: Props) {
  const [nodesCsv, setNodesCsv] = useState(
    "node_id,parent_id,entity_type,label,rank_hint,order_hint,fill_override,stroke_override,metadata\n"
  );
  const [edgesCsv, setEdgesCsv] = useState("edge_id,source_id,target_id,relation_type,label\n");
  const [showRules, setShowRules] = useState(false);
  const [shapesCsv, setShapesCsv] = useState("");
  const [linesCsv, setLinesCsv] = useState("");

  return (
    <div className="panel">
      <p className="hint">
        Paste Nodes/Edges CSV (same headers as the workbook) and apply it to the active diagram. Unknown
        entity/relation types are skipped and reported below.
      </p>
      <label className="field">
        <span>Nodes CSV</span>
        <textarea rows={8} value={nodesCsv} onChange={(e) => setNodesCsv(e.target.value)} spellCheck={false} />
      </label>
      <label className="field">
        <span>Edges CSV</span>
        <textarea rows={5} value={edgesCsv} onChange={(e) => setEdgesCsv(e.target.value)} spellCheck={false} />
      </label>
      <button className="link-btn" onClick={() => setShowRules((v) => !v)}>
        {showRules ? "Hide" : "Add"} custom Shape_Library / Line_Rules rows
      </button>
      {showRules && (
        <>
          <label className="field">
            <span>Shape_Library CSV</span>
            <textarea rows={4} value={shapesCsv} onChange={(e) => setShapesCsv(e.target.value)} spellCheck={false} />
          </label>
          <label className="field">
            <span>Line_Rules CSV</span>
            <textarea rows={4} value={linesCsv} onChange={(e) => setLinesCsv(e.target.value)} spellCheck={false} />
          </label>
        </>
      )}
      <button className="btn btn-primary" onClick={() => onApply(nodesCsv, edgesCsv, shapesCsv, linesCsv)}>
        Apply CSV to canvas
      </button>
      {unknownTypes.length > 0 && (
        <p className="warn">Skipped unknown types: {unknownTypes.join(", ")}</p>
      )}
    </div>
  );
}
