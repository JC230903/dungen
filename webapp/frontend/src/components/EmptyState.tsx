import { useEffect, useRef, useState } from "react";
import type { LineOut, SampleInfo, ShapeOut } from "../api";
import { getPalette, listSamples, sampleLabel, sampleMeta } from "../api";
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
  const [samples, setSamples] = useState<SampleInfo[]>([]);
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
          <div className="field">
            <span>Or open a sample workbook</span>
            <ul className="sample-list">
              {samples.map((s) => (
                <li key={s.name}>
                  <button className="sample-item" onClick={() => onSample(s.name)} title={s.name}>
                    <span className="sample-name">{sampleLabel(s)}</span>
                    {sampleMeta(s) && <span className="sample-meta">{sampleMeta(s)}</span>}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
