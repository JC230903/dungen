import { useEffect, useRef, useState } from "react";
import type { DiagramInfo, SampleInfo } from "../api";
import { downloadSample, listSamples, sampleLabel, sampleMeta } from "../api";
import ShortcutsHelp from "./ShortcutsHelp";

export type Tool = "select" | "connect";

interface Props {
  hasDiagram: boolean;
  title: string | null;
  loading: boolean;
  busy: boolean;
  error: string | null;
  onDismissError: () => void;
  source: string | null;
  sourceSample: string | null;
  nodeCount: number;
  edgeCount: number;
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
  hasSavedProject: boolean;
  onQuickSave: () => void;
  lastSavedAt: number | null;
  dirty: boolean;
  username: string;
  onLogout: () => void;
}

function useRelativeTime(ts: number | null): string | null {
  const [, force] = useState(0);
  useEffect(() => {
    if (ts == null) return;
    const id = setInterval(() => force((n) => n + 1), 15000);
    return () => clearInterval(id);
  }, [ts]);
  if (ts == null) return null;
  const secs = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (secs < 10) return "Saved just now";
  if (secs < 60) return `Saved ${secs}s ago`;
  return `Saved ${Math.round(secs / 60)}m ago`;
}

export default function Toolbar({
  hasDiagram,
  title,
  loading,
  busy,
  error,
  onDismissError,
  source,
  sourceSample,
  nodeCount,
  edgeCount,
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
  hasSavedProject,
  onQuickSave,
  lastSavedAt,
  dirty,
  username,
  onLogout,
}: Props) {
  const [samples, setSamples] = useState<SampleInfo[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const disabled = loading || busy;
  const savedLabel = useRelativeTime(lastSavedAt);

  useEffect(() => {
    listSamples().then(setSamples).catch(() => setSamples([]));
  }, []);

  return (
    <div className="topbar">
      <div className="brand">DrawGen</div>

      <div className="toolbar-group" title="Start a new diagram from a source">
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
            <option key={s.name} value={s.name} title={s.name}>
              {sampleLabel(s)}
              {sampleMeta(s) ? ` — ${sampleMeta(s)}` : ""}
            </option>
          ))}
        </select>
        <button className="btn" onClick={onBlank} disabled={disabled}>
          + Blank
        </button>
      </div>

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

          <div className="toolbar-group" title="Edit">
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
          </div>

          <input
            className="search-box"
            placeholder="Search shapes…"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />

          <span className="sep" />
          <div className="toolbar-group" title="Save">
            <button
              className="btn btn-primary"
              onClick={onQuickSave}
              disabled={disabled}
              title="Save to this machine's local database (Ctrl+S)"
            >
              {hasSavedProject ? "Save" : "Save as…"}
            </button>
            {dirty ? (
              <span className="unsaved-label" title="You have edits that aren't saved yet">
                ● Unsaved
              </span>
            ) : (
              savedLabel && <span className="saved-label">{savedLabel}</span>
            )}
          </div>

          <span className="sep" />
          <div className="toolbar-group" title="Export">
            <button className="btn" onClick={() => onDownload("svg")}>
              SVG
            </button>
            <button className="btn" onClick={() => onDownload("drawio")}>
              draw.io
            </button>
            <button className="btn" onClick={() => onDownload("html")}>
              HTML
            </button>
          </div>
        </>
      )}

      <div className="title">
        {loading ? (
          "Loading…"
        ) : (
          <>
            {title && <span className="title-name">{title}</span>}
            {hasDiagram && source && (
              sourceSample ? (
                <button
                  className="title-source title-source-link"
                  title={`Download ${sourceSample}`}
                  onClick={() => downloadSample(sourceSample).catch(() => {})}
                >
                  {source} ↓
                </button>
              ) : (
                <span className="title-source" title={source}>
                  {source}
                </span>
              )
            )}
            {hasDiagram && (
              <span className="title-stats">
                {nodeCount} shapes · {edgeCount} links
              </span>
            )}
          </>
        )}
      </div>
      {error && (
        <div className="error">
          {error}
          <button className="error-dismiss" onClick={onDismissError} title="Dismiss">
            ×
          </button>
        </div>
      )}

      <ShortcutsHelp />
      <span className="sep" />
      <span className="user-badge" title={username}>
        {username}
      </span>
      <button className="btn" onClick={onLogout}>
        Log out
      </button>
    </div>
  );
}
