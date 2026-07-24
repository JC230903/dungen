import { useCallback, useEffect, useRef, useState } from "react";
import type { DiagramResponse } from "./api";
import {
  autoArrange,
  createBlank,
  createEdge,
  createNode,
  deleteEdge,
  deleteNode,
  duplicateNode,
  generateOutline,
  generateTemplate,
  applyCsv,
  loadSample,
  redo,
  reparentNode,
  reposition as apiReposition,
  setStyleRules,
  switchDiagram,
  undo,
  updateEdge,
  updateNode,
  uploadWorkbook,
} from "./api";
import DiagramCanvas from "./components/DiagramCanvas";
import Toolbar, { type Tool } from "./components/Toolbar";
import Palette from "./components/Palette";
import PropertiesPanel from "./components/PropertiesPanel";
import CsvPanel from "./components/CsvPanel";
import TemplatesPanel from "./components/TemplatesPanel";
import OutlinePanel from "./components/OutlinePanel";
import StyleRulesPanel from "./components/StyleRulesPanel";
import "./styles.css";

type SidebarTab = "properties" | "palette" | "csv" | "templates" | "outline" | "style";

function download(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function isTypingTarget(el: EventTarget | null): boolean {
  const e = el as HTMLElement | null;
  if (!e) return false;
  const tag = e.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || e.isContentEditable;
}

export default function App() {
  const [diagram, setDiagram] = useState<DiagramResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [tool, setTool] = useState<Tool>("select");
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<SidebarTab>("properties");
  const diagramRef = useRef(diagram);
  diagramRef.current = diagram;

  const handleErr = (e: any) =>
    setError(e?.response?.data?.detail || e.message || "Request failed");

  const runLoad = useCallback((p: Promise<DiagramResponse>) => {
    setLoading(true);
    setError(null);
    setSelectedNodeIds([]);
    setSelectedEdgeId(null);
    p.then(setDiagram).catch(handleErr).finally(() => setLoading(false));
  }, []);

  const runMutate = useCallback(
    (p: Promise<DiagramResponse>, after?: (d: DiagramResponse, prevNodeIds: Set<string>) => void) => {
      const prevIds = new Set((diagramRef.current?.nodes ?? []).map((n) => n.id));
      setBusy(true);
      setError(null);
      p.then((d) => {
        setDiagram(d);
        after?.(d, prevIds);
      })
        .catch(handleErr)
        .finally(() => setBusy(false));
    },
    []
  );

  // ---------- load / bootstrap ----------
  const onUpload = useCallback((file: File) => runLoad(uploadWorkbook(file)), [runLoad]);
  const onSample = useCallback((name: string) => runLoad(loadSample(name)), [runLoad]);
  const onBlank = useCallback(() => runLoad(createBlank()), [runLoad]);
  const onSwitchDiagram = useCallback(
    (id: string) => {
      if (!diagram) return;
      runLoad(switchDiagram(diagram.session_id, id));
    },
    [diagram, runLoad]
  );

  // ---------- selection ----------
  const onSelectNode = useCallback((id: string | null, additive = false) => {
    setSelectedEdgeId(null);
    if (id === null) {
      setSelectedNodeIds([]);
      return;
    }
    if (additive) {
      setSelectedNodeIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
    } else {
      setSelectedNodeIds([id]);
    }
  }, []);

  const onSelectEdge = useCallback((id: string | null) => {
    setSelectedNodeIds([]);
    setSelectedEdgeId(id);
  }, []);

  // ---------- node/edge mutation ----------
  const onDragEnd = useCallback(
    (nodeId: string, x: number, y: number) => {
      if (!diagram) return;
      runMutate(apiReposition(diagram.session_id, nodeId, x, y));
    },
    [diagram, runMutate]
  );

  const onCreateFromPalette = useCallback(
    (entityType: string) => {
      if (!diagram) return;
      const x = diagram.canvas_w / 2 - 60;
      const y = diagram.canvas_h / 2 - 25;
      runMutate(createNode(diagram.session_id, entityType, { x, y }), (d, prevIds) => {
        const added = d.nodes.find((n) => !prevIds.has(n.id));
        if (added) onSelectNode(added.id);
      });
    },
    [diagram, runMutate, onSelectNode]
  );

  const onDropCreate = useCallback(
    (entityType: string, x: number, y: number) => {
      if (!diagram) return;
      runMutate(createNode(diagram.session_id, entityType, { x, y }), (d, prevIds) => {
        const added = d.nodes.find((n) => !prevIds.has(n.id));
        if (added) onSelectNode(added.id);
      });
    },
    [diagram, runMutate, onSelectNode]
  );

  const onUpdateNode = useCallback(
    (nodeId: string, patch: Parameters<typeof updateNode>[2]) => {
      if (!diagram) return;
      runMutate(updateNode(diagram.session_id, nodeId, patch));
    },
    [diagram, runMutate]
  );

  const onDeleteNode = useCallback(
    (nodeId: string) => {
      if (!diagram) return;
      setSelectedNodeIds([]);
      setSelectedEdgeId(null);
      runMutate(deleteNode(diagram.session_id, nodeId));
    },
    [diagram, runMutate]
  );

  const onBulkDeleteNodes = useCallback(
    async (ids: string[]) => {
      if (!diagram) return;
      setSelectedNodeIds([]);
      setSelectedEdgeId(null);
      setBusy(true);
      setError(null);
      let sid = diagram.session_id;
      let last: DiagramResponse | null = null;
      for (const id of ids) {
        try {
          last = await deleteNode(sid, id);
        } catch (e: any) {
          if (e?.response?.status !== 404) {
            handleErr(e);
            break;
          }
          // already gone (deleted as a descendant of an earlier node in this batch) — continue
        }
      }
      if (last) setDiagram(last);
      setBusy(false);
    },
    [diagram]
  );

  const onDuplicateNode = useCallback(
    (nodeId: string) => {
      if (!diagram) return;
      runMutate(duplicateNode(diagram.session_id, nodeId), (d, prevIds) => {
        const added = d.nodes.find((n) => !prevIds.has(n.id));
        if (added) onSelectNode(added.id);
      });
    },
    [diagram, runMutate, onSelectNode]
  );

  const onReparentNode = useCallback(
    (nodeId: string, parent: string) => {
      if (!diagram) return;
      runMutate(reparentNode(diagram.session_id, nodeId, parent));
    },
    [diagram, runMutate]
  );

  const onConnectCreate = useCallback(
    (sourceId: string, targetId: string) => {
      if (!diagram) return;
      const relationType = diagram.lines[0]?.relation_type || "association";
      runMutate(createEdge(diagram.session_id, sourceId, targetId, relationType));
    },
    [diagram, runMutate]
  );

  const onUpdateEdge = useCallback(
    (edgeId: string, patch: Parameters<typeof updateEdge>[2]) => {
      if (!diagram) return;
      runMutate(updateEdge(diagram.session_id, edgeId, patch));
    },
    [diagram, runMutate]
  );

  const onDeleteEdge = useCallback(
    (edgeId: string) => {
      if (!diagram) return;
      setSelectedEdgeId(null);
      runMutate(deleteEdge(diagram.session_id, edgeId));
    },
    [diagram, runMutate]
  );

  // ---------- layout / history ----------
  const onAutoArrange = useCallback(() => {
    if (!diagram) return;
    runMutate(autoArrange(diagram.session_id));
  }, [diagram, runMutate]);

  const onSetDirection = useCallback(
    (dir: "TB" | "LR") => {
      if (!diagram) return;
      runMutate(autoArrange(diagram.session_id, dir));
    },
    [diagram, runMutate]
  );

  const onUndo = useCallback(() => {
    if (!diagram) return;
    runMutate(undo(diagram.session_id));
  }, [diagram, runMutate]);

  const onRedo = useCallback(() => {
    if (!diagram) return;
    runMutate(redo(diagram.session_id));
  }, [diagram, runMutate]);

  // ---------- CSV / templates / outline / style rules ----------
  const onApplyCsv = useCallback(
    (nodesCsv: string, edgesCsv: string, shapesCsv: string, linesCsv: string) => {
      if (!diagram) return;
      runMutate(applyCsv(diagram.session_id, nodesCsv, edgesCsv, shapesCsv, linesCsv));
    },
    [diagram, runMutate]
  );

  const onGenerateTemplate = useCallback(
    (name: string, params: Record<string, string>) => runLoad(generateTemplate(name, params)),
    [runLoad]
  );

  const onGenerateOutline = useCallback(
    (text: string, entityType: string, relationType: string) =>
      runLoad(generateOutline(text, entityType, relationType)),
    [runLoad]
  );

  const onApplyStyleRules = useCallback(
    (rulesText: string) => {
      if (!diagram) return;
      runMutate(setStyleRules(diagram.session_id, rulesText));
    },
    [diagram, runMutate]
  );

  const onDownload = useCallback(
    (kind: "svg" | "drawio" | "html") => {
      if (!diagram) return;
      const base = diagram.title || "diagram";
      if (kind === "svg") download(`${base}.svg`, diagram.svg, "image/svg+xml");
      else if (kind === "drawio") download(`${base}.drawio`, diagram.drawio, "application/xml");
      else download(`${base}.html`, diagram.html, "text/html");
    },
    [diagram]
  );

  // ---------- keyboard shortcuts ----------
  useEffect(() => {
    const onKeyDown = (ev: KeyboardEvent) => {
      if (isTypingTarget(ev.target)) return;
      const d = diagramRef.current;
      if (!d) return;
      if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "z") {
        ev.preventDefault();
        if (ev.shiftKey) onRedo();
        else onUndo();
        return;
      }
      if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "y") {
        ev.preventDefault();
        onRedo();
        return;
      }
      if (ev.key === "v" || ev.key === "V") setTool("select");
      else if (ev.key === "c" || ev.key === "C") setTool("connect");
      else if (ev.key === "Escape") {
        setSelectedNodeIds([]);
        setSelectedEdgeId(null);
      } else if (ev.key === "Delete" || ev.key === "Backspace") {
        if (selectedEdgeId) onDeleteEdge(selectedEdgeId);
        else if (selectedNodeIds.length === 1) onDeleteNode(selectedNodeIds[0]);
        else if (selectedNodeIds.length > 1) onBulkDeleteNodes(selectedNodeIds);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedNodeIds, selectedEdgeId, onUndo, onRedo, onDeleteEdge, onDeleteNode, onBulkDeleteNodes]);

  return (
    <div className="app">
      <Toolbar
        hasDiagram={!!diagram}
        title={diagram?.title ?? null}
        loading={loading}
        busy={busy}
        error={error}
        diagrams={diagram?.diagrams ?? []}
        activeDiagramId={diagram?.diagram_id ?? ""}
        direction={diagram?.direction ?? "top-down"}
        tool={tool}
        search={search}
        onUpload={onUpload}
        onSample={onSample}
        onBlank={onBlank}
        onSwitchDiagram={onSwitchDiagram}
        onSetDirection={onSetDirection}
        onAutoArrange={onAutoArrange}
        onUndo={onUndo}
        onRedo={onRedo}
        onSetTool={setTool}
        onSearchChange={setSearch}
        onDownload={onDownload}
      />
      <div className="body">
        <div className="canvas-area">
          {diagram ? (
            <DiagramCanvas
              svg={diagram.svg}
              nodes={diagram.nodes}
              edges={diagram.edges}
              connections={diagram.connections}
              selectedNodeIds={selectedNodeIds}
              selectedEdgeId={selectedEdgeId}
              tool={tool}
              search={search}
              onSelectNode={onSelectNode}
              onSelectEdge={onSelectEdge}
              onDragEnd={onDragEnd}
              onConnectCreate={onConnectCreate}
              onDropCreate={onDropCreate}
              busy={busy}
            />
          ) : (
            <div className="empty-state">
              Upload a Nodes/Edges workbook, load a sample, or start a blank canvas to see it rendered here.
            </div>
          )}
        </div>
        {diagram && (
          <aside className="sidebar">
            <div className="tab-bar">
              {(
                [
                  ["properties", "Properties"],
                  ["palette", "Palette"],
                  ["csv", "CSV"],
                  ["templates", "Templates"],
                  ["outline", "Outline"],
                  ["style", "Style rules"],
                ] as [SidebarTab, string][]
              ).map(([key, label]) => (
                <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
                  {label}
                </button>
              ))}
            </div>

            {tab === "properties" && (
              <PropertiesPanel
                nodes={diagram.nodes}
                edges={diagram.edges}
                shapes={diagram.shapes}
                lines={diagram.lines}
                connections={diagram.connections}
                selectedNodeIds={selectedNodeIds}
                selectedEdgeId={selectedEdgeId}
                onSelectNode={onSelectNode}
                onUpdateNode={onUpdateNode}
                onDeleteNode={onDeleteNode}
                onDuplicateNode={onDuplicateNode}
                onReparentNode={onReparentNode}
                onBulkDeleteNodes={onBulkDeleteNodes}
                onUpdateEdge={onUpdateEdge}
                onDeleteEdge={onDeleteEdge}
              />
            )}
            {tab === "palette" && <Palette shapes={diagram.shapes} onCreate={onCreateFromPalette} />}
            {tab === "csv" && <CsvPanel unknownTypes={diagram.unknown_types} onApply={onApplyCsv} />}
            {tab === "templates" && <TemplatesPanel onGenerate={onGenerateTemplate} />}
            {tab === "outline" && (
              <OutlinePanel shapes={diagram.shapes} lines={diagram.lines} onGenerate={onGenerateOutline} />
            )}
            {tab === "style" && <StyleRulesPanel rulesText={diagram.style_rules} onApply={onApplyStyleRules} />}
          </aside>
        )}
      </div>
    </div>
  );
}
