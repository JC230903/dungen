import { useEffect, useState } from "react";
import type { ProjectInfo } from "../api";

interface Props {
  projects: ProjectInfo[];
  currentProjectId: string | null;
  currentName: string;
  busy: boolean;
  onSave: (name: string) => void;
  onSaveAsCopy: (name: string) => void;
  onLoad: (id: string, name: string) => void;
  onDelete: (id: string) => void;
}

function timeAgo(unixSeconds: number): string {
  const diffMs = Date.now() - unixSeconds * 1000;
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export default function ProjectsPanel({
  projects,
  currentProjectId,
  currentName,
  busy,
  onSave,
  onSaveAsCopy,
  onLoad,
  onDelete,
}: Props) {
  const [name, setName] = useState(currentName);

  useEffect(() => {
    setName(currentName);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProjectId]);

  return (
    <div className="panel">
      <p className="hint">
        Save the current diagram (all sub-diagrams, palette, style rules) to this machine's local
        database so it survives a backend restart and can be reopened later.
      </p>
      <label className="field">
        <span>Name</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Untitled" />
      </label>
      <button
        className="btn btn-primary"
        disabled={busy || !name.trim()}
        onClick={() => onSave(name.trim())}
      >
        {currentProjectId ? "Save" : "Save as new"}
      </button>
      {currentProjectId && (
        <button className="btn" disabled={busy || !name.trim()} onClick={() => onSaveAsCopy(name.trim())}>
          Save as a copy
        </button>
      )}

      <p className="hint" style={{ marginTop: 16 }}>
        Saved projects
      </p>
      {projects.length === 0 && <p className="hint">Nothing saved yet.</p>}
      <ul className="project-list">
        {projects.map((p) => (
          <li key={p.id} className={p.id === currentProjectId ? "active" : ""}>
            <div className="project-row-main" onClick={() => onLoad(p.id, p.name)}>
              <span className="project-name">{p.name}</span>
              <span className="project-time">{timeAgo(p.updated_at)}</span>
            </div>
            <button
              className="btn btn-danger project-delete"
              title="Delete"
              onClick={() => {
                if (window.confirm(`Delete "${p.name}"? This can't be undone.`)) onDelete(p.id);
              }}
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
