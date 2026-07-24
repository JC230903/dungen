import { useMemo, useState } from "react";
import type { ShapeOut } from "../api";

interface Props {
  shapes: ShapeOut[];
  onCreate: (entityType: string) => void;
}

export const PALETTE_DRAG_MIME = "application/x-diagen-entity-type";

export default function Palette({ shapes, onCreate }: Props) {
  const [q, setQ] = useState("");

  const families = useMemo(() => {
    const filtered = shapes.filter(
      (s) => !q.trim() || s.entity_type.toLowerCase().includes(q.toLowerCase())
    );
    const byFamily = new Map<string, ShapeOut[]>();
    for (const s of filtered) {
      const fam = s.family || "Other";
      if (!byFamily.has(fam)) byFamily.set(fam, []);
      byFamily.get(fam)!.push(s);
    }
    return [...byFamily.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [shapes, q]);

  return (
    <div className="panel palette-panel">
      <input
        className="search-box"
        placeholder="Filter shapes…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <p className="hint">Drag a shape onto the canvas, or click to add it.</p>
      {families.map(([fam, list]) => (
        <div key={fam} className="palette-family">
          <div className="palette-family-title">{fam}</div>
          <div className="palette-chips">
            {list.map((s) => (
              <div
                key={s.entity_type}
                className="palette-chip"
                draggable
                title={s.entity_type}
                style={{ background: s.fill, borderColor: s.stroke }}
                onDragStart={(e) => {
                  e.dataTransfer.setData(PALETTE_DRAG_MIME, s.entity_type);
                  e.dataTransfer.effectAllowed = "copy";
                }}
                onClick={() => onCreate(s.entity_type)}
              >
                {s.entity_type}
              </div>
            ))}
          </div>
        </div>
      ))}
      {families.length === 0 && <p className="hint">No shapes match "{q}".</p>}
    </div>
  );
}
