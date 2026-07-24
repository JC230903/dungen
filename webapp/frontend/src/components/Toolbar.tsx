import { useEffect, useRef, useState } from "react";
import type { DiagramInfo } from "../api";
import { listSamples } from "../api";

export type Tool = "select" | "connect";

interface Props {
  hasDiagram: boolean;
  title: string | null;
  loading: boolean;
  busy: boolean;
  error: string | null;
  diagrams: DiagramInfo[];
  activeDiagramId: string;
  direction: string;
  tool: Tool;
  search: string;
  onUpload: (file: File) => void;
  onSample: (name: string) => void;
  onBlank: () => void;
  onSwitchDiagram: (id: string) => void;
  onSetDirection: (dir: "TB" | "LR") => void;
  onAutoArrange: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onSetTool: (tool: Tool) => void;
  onSearchChange: (s: string) => void;
  onDownload: (kind: "svg" | "drawio" | "html") => void;
}

export default function Toolbar({
  hasDiagram,
  title,
  loading,
  busy,
  error,
  diagrams,
  activeDiagramId,
  direction,
  tool,
  search,
  onUpload,
  onSample,
  onBlank,
  onSwitchDiagram,
  onSetDirection,
  onAutoArrange,
  onUndo,
  onRedo,
  onSetTool,
  onSearchChange,
  onDownload,
}: Props) {
  const [samples, setSamples] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const disabled = loading || busy;

  useEffect(() => {
    listSamples().then(setSamples).catch(() => setSamples([]));
  }, []);

  return (
    <div className="topbar">
      <div className="brand">diagen</div>
      <button className="btn" onClick={() => fileRef.current?.click()} disabled={disabled}>
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
      <select
        defaultValue=""
        disabled={disabled}
        onChange={(e) => {
          if (e.target.value) onSample(e.target.value);
          e.target.value = "";
        }}
      >
        <option value="" disabled>
          Load a sample…
        </option>
        {samples.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
      <button className="btn" onClick={onBlank} disabled={disabled}>
        + Blank
      </button>

      {hasDiagram && (
        <>
          <span className="sep" />
          {diagrams.length > 1 && (
            <select
              value={activeDiagramId}
              disabled={disabled}
              onChange={(e) => onSwitchDiagram(e.target.value)}
              title="Switch between diagrams in this workbook"
            >
              {diagrams.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title || d.id}
                </option>
              ))}
            </select>
          )}

          <div className="tool-toggle" role="group" title="V = select, C = connect">
            <button className={tool === "select" ? "active" : ""} onClick={() => onSetTool("select")}>
              Select
            </button>
            <button className={tool === "connect" ? "active" : ""} onClick={() => onSetTool("connect")}>
              Connect
            </button>
          </div>

          <div className="tool-toggle" title="Layout direction">
            <button className={direction.startsWith("top") ? "active" : ""} onClick={() => onSetDirection("TB")}>
              ↓ TB
            </button>
            <button className={direction.startsWith("left") ? "active" : ""} onClick={() => onSetDirection("LR")}>
              → LR
            </button>
          </div>

          <button className="btn" onClick={onAutoArrange} disabled={disabled} title="Re-run auto-layout">
            Auto-arrange
          </button>
          <button className="btn" onClick={onUndo} disabled={disabled} title="Ctrl+Z">
            ↶ Undo
          </button>
          <button className="btn" onClick={onRedo} disabled={disabled} title="Ctrl+Y">
            ↷ Redo
          </button>

          <input
            className="search-box"
            placeholder="Search shapes…"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />

          <span className="sep" />
          <button className="btn" onClick={() => onDownload("svg")}>
            SVG
          </button>
          <button className="btn" onClick={() => onDownload("drawio")}>
            draw.io
          </button>
          <button className="btn" onClick={() => onDownload("html")}>
            HTML
          </button>
        </>
      )}

      <div className="title">{loading ? "Loading…" : title || ""}</div>
      {error && <div className="error">{error}</div>}
    </div>
  );
}
