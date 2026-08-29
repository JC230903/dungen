import { useEffect, useRef, useState } from "react";
import type { LineOut, ShapeOut } from "../api";
import { getPalette, listSamples } from "../api";
import TemplatesPanel from "./TemplatesPanel";
import OutlinePanel from "./OutlinePanel";

interface Props {
  onBlank: () => void;
  onSample: (name: string) => void;
  onUpload: (file: File) => void;
  onGenerateTemplate: (templateName: string, params: Record<string, string>) => void;
  onGenerateOutline: (text: string, entityType: string, relationType: string) => void;
}

type Expanded = "template" | "outline" | null;

export default function EmptyState({ onBlank, onSample, onUpload, onGenerateTemplate, onGenerateOutline }: Props) {
  const [samples, setSamples] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<Expanded>(null);
  const [shapes, setShapes] = useState<ShapeOut[]>([]);
  const [lines, setLines] = useState<LineOut[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listSamples().then(setSamples).catch(() => setSamples([]));
    getPalette()
      .then((p) => {
        setShapes(p.shapes);
        setLines(p.lines);
      })
      .catch(() => {});
  }, []);

  const toggle = (which: Expanded) => setExpanded((cur) => (cur === which ? null : which));

  return (
    <div className="empty-state">
      <div className="empty-card">
        <h2>Start a diagram</h2>
        <p className="hint">Pick a starting point — you can switch approaches any time.</p>

        <div className="empty-actions">
          <button className="btn btn-primary" onClick={onBlank}>
            + Blank canvas
          </button>
          <button className="btn" onClick={() => fileRef.current?.click()}>
            Upload .xlsx
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onUpload(f);
              e.target.value = "";
            }}
          />
        </div>

        <div className="empty-actions">
          <button className={`btn ${expanded === "template" ? "active" : ""}`} onClick={() => toggle("template")}>
            From a template
          </button>
          <button className={`btn ${expanded === "outline" ? "active" : ""}`} onClick={() => toggle("outline")}>
            From an outline
          </button>
        </div>

        {expanded === "template" && (
          <div className="empty-expanded">
            <TemplatesPanel onGenerate={onGenerateTemplate} />
          </div>
        )}
        {expanded === "outline" && (
          <div className="empty-expanded">
            <OutlinePanel shapes={shapes} lines={lines} onGenerate={onGenerateOutline} />
          </div>
        )}

        {samples.length > 0 && (
          <label className="field">
            <span>Or load a sample workbook</span>
            <select
              defaultValue=""
              onChange={(e) => {
                if (e.target.value) onSample(e.target.value);
                e.target.value = "";
              }}
            >
              <option value="" disabled>
                Choose a sample…
              </option>
              {samples.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
    </div>
  );
}
