import { useCallback, useEffect, useRef, useState } from "react";
import type { DiagramResponse, ProjectInfo } from "./api";
import {
  autoArrange,
  createBlank,
  createEdge,
  createNode,
  deleteEdge,
  deleteNode,
  deleteProject,
  duplicateNode,
  generateOutline,
  generateTemplate,
  applyCsv,
  getToken,
  listProjects,
  loadProject,
  loadSample,
  me,
  onUnauthorized,
  redo,
  reparentNode,
  reposition as apiReposition,
  saveProject,
  setStyleRules,
  setToken,
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
import ProjectsPanel from "./components/ProjectsPanel";
import LoginScreen from "./components/LoginScreen";
import EmptyState from "./components/EmptyState";
import Sidebar, { SIDEBAR_DEFAULT } from "./components/Sidebar";
import { usePersistentState } from "./usePersistentState";
import "./styles.css";

type SidebarTab = "properties" | "palette" | "csv" | "templates" | "outline" | "style" | "projects";

// [key, full label, short label for the collapsed rail]
const SIDEBAR_TABS: [SidebarTab, string, string][] = [
  ["properties", "Properties", "Prop"],
  ["palette", "Palette", "Pal"],
  ["csv", "CSV", "CSV"],
  ["templates", "Templates", "Tpl"],
  ["outline", "Outline", "Out"],
  ["style", "Style rules", "Sty"],
  ["projects", "Projects", "Proj"],
];

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

function DiagramApp({ username, onLogout }: { username: string; onLogout: () => void }) {
  const [diagram, setDiagram] = useState<DiagramResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [tool, setTool] = useState<Tool>("select");
  const [search, setSearch] = useState("");
  const [tab, setTab] = usePersistentState<SidebarTab>("drawgen.sidebarTab", "properties");
  const [sidebarWidth, setSidebarWidth] = usePersistentState("drawgen.sidebarWidth", SIDEBAR_DEFAULT);
  const [sidebarCollapsed, setSidebarCollapsed] = usePersistentState("drawgen.sidebarCollapsed", false);
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [currentProjectName, setCurrentProjectName] = useState<string>("");
  const [autosaveAt, setAutosaveAt] = useState<number | null>(null);
  // Every successful mutation marks the diagram dirty; saving clears it. Drives
  // both the toolbar's saved/unsaved indicator and the leave-page guard.
  const [dirty, setDirty] = useState(false);
  // Where the open diagram came from ("Sample: S1_…", "Uploaded: foo.xlsx", …).
  // The API response only carries the diagram itself, so provenance is tracked
  // here at the point of loading.
  const [source, setSource] = useState<string | null>(null);
  const diagramRef = useRef(diagram);
  diagramRef.current = diagram;

  const handleErr = (e: any) => {
    const status = e?.response?.status;
    const detail = e?.response?.data?.detail;
    if (status && status >= 500) {
      console.error("server error:", e);
      setError("Something went wrong on the server. Try again — if it keeps happening, reload the page.");
    } else if (detail) {
      // 4xx details from the API are already written for a human (e.g. "Unknown entity_type: foo").
      setError(detail);
    } else if (e?.message === "Network Error") {
      setError("Can't reach the server. Check your connection and try again.");
    } else {
      setError(e?.message || "That didn't work. Try again.");
    }
  };

  const refreshProjects = useCallback(() => {
    listProjects().then(setProjects).catch(() => {});
  }, []);

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  // `after` fires once the new diagram is in state — used by project-load to
  // re-attach the project id/name once loading actually succeeds.
  const runLoad = useCallback((p: Promise<DiagramResponse>, sourceLabel: string | null = null, after?: (d: DiagramResponse) => void) => {
    setLoading(true);
    setSource(sourceLabel);
    setError(null);
    setSelectedNodeIds([]);
    setSelectedEdgeId(null);
    setCurrentProjectId(null);
    setCurrentProjectName("");
    setAutosaveAt(null);
    p.then((d) => {
      setDiagram(d);
      setDirty(false); // freshly loaded == exactly what the server has
      after?.(d);
    })
      .catch(handleErr)
      .finally(() => setLoading(false));
  }, []);

  const runMutate = useCallback(
    (p: Promise<DiagramResponse>, after?: (d: DiagramResponse, prevNodeIds: Set<string>) => void) => {
      const prevIds = new Set((diagramRef.current?.nodes ?? []).map((n) => n.id));
      setBusy(true);
      setError(null);
      p.then((d) => {
        setDiagram(d);
        setDirty(true);
        after?.(d, prevIds);
      })
        .catch(handleErr)
        .finally(() => setBusy(false));
    },
    []
  );

  // ---------- load / bootstrap ----------
  const onUpload = useCallback(
    (file: File) => runLoad(uploadWorkbook(file), `Uploaded: ${file.name}`),
    [runLoad]
  );
  const onSample = useCallback((name: string) => runLoad(loadSample(name), `Sample: ${name}`), [runLoad]);
  const onBlank = useCallback(() => runLoad(createBlank(), "Blank canvas"), [runLoad]);
  const onSwitchDiagram = useCallback(
    (id: string) => {
      if (!diagram) return;
      // Switching sheets inside the same workbook doesn't change where it came from.
      runLoad(switchDiagram(diagram.session_id, id), source);
    },
    [diagram, runLoad, source]
  );

  // ---------- saved projects ----------
  const onLoadProject = useCallback(
    (id: string, name: string) => {
      runLoad(loadProject(id), `Project: ${name}`, () => {
        setCurrentProjectId(id);
        setCurrentProjectName(name);
        setAutosaveAt(Date.now());
      });
    },
    [runLoad]
  );

  const doSave = useCallback(
    (name: string, projectId: string | null, silent = false) => {
      if (!diagram) return;
      if (!silent) {
        setBusy(true);
        setError(null);
      }
      saveProject(diagram.session_id, name, projectId)
        .then((info) => {
          setCurrentProjectId(info.id);
          setCurrentProjectName(info.name);
          setAutosaveAt(Date.now());
          setDirty(false);
          refreshProjects();
        })
        .catch((e) => {
          // Autosave failing quietly (e.g. a transient network blip) shouldn't
          // interrupt someone mid-edit with an error banner — explicit Save
          // still surfaces failures normally.
          if (silent) console.warn("autosave failed:", e);
          else handleErr(e);
        })
        .finally(() => {
          if (!silent) setBusy(false);
        });
    },
    [diagram, refreshProjects]
  );

  const onSaveProject = useCallback((name: string) => doSave(name, currentProjectId), [doSave, currentProjectId]);
  const onSaveProjectAsCopy = useCallback((name: string) => doSave(name, null), [doSave]);

  // ---------- auto-save ----------
  // While the open diagram is tied to a saved project, silently re-save it
  // every 2 minutes so a crash/restart doesn't lose more than that much
  // work — on top of, not instead of, the explicit Save button.
  const AUTOSAVE_INTERVAL_MS = 2 * 60 * 1000;
  const currentProjectIdRef = useRef(currentProjectId);
  currentProjectIdRef.current = currentProjectId;
  const currentProjectNameRef = useRef(currentProjectName);
  currentProjectNameRef.current = currentProjectName;

  useEffect(() => {
    const t = setInterval(() => {
      const pid = currentProjectIdRef.current;
      if (pid) doSave(currentProjectNameRef.current, pid, true);
    }, AUTOSAVE_INTERVAL_MS);
    return () => clearInterval(t);
  }, [doSave]);

  const onQuickSave = useCallback(() => {
    if (currentProjectId) {
      onSaveProject(currentProjectName);
      return;
    }
    const name = window.prompt("Save as:", diagram?.title || "Untitled");
    if (name && name.trim()) onSaveProject(name.trim());
  }, [currentProjectId, currentProjectName, diagram, onSaveProject]);

  const onDeleteProject = useCallback(
    (id: string) => {
      deleteProject(id)
        .then(() => {
          if (id === currentProjectId) {
            setCurrentProjectId(null);
            setCurrentProjectName("");
          }
          refreshProjects();
        })
        .catch(handleErr);
    },
    [currentProjectId, refreshProjects]
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
    (name: string, params: Record<string, string>) =>
      runLoad(generateTemplate(name, params), `Template: ${name}`),
    [runLoad]
  );

  const onGenerateOutline = useCallback(
    (text: string, entityType: string, relationType: string) =>
      runLoad(generateOutline(text, entityType, relationType), "Generated from outline"),
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
      // Save is the one shortcut that must survive focus being in a text field —
      // it also has to beat the browser's own "save page" dialog to preventDefault.
      if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "s") {
        ev.preventDefault();
        if (diagramRef.current) onQuickSave();
        return;
      }
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
  }, [
    selectedNodeIds,
    selectedEdgeId,
    onUndo,
    onRedo,
    onDeleteEdge,
    onDeleteNode,
    onBulkDeleteNodes,
    onQuickSave,
  ]);

  // ---------- leave-page guard ----------
  // Only edits made since the last save are at risk: autosave covers a diagram
  // already tied to a project, but an unsaved one lives purely in the session.
  useEffect(() => {
    if (!dirty) return;
    const warn = (ev: BeforeUnloadEvent) => {
      ev.preventDefault();
      ev.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  return (
    <div className="app">
      <Toolbar
        hasDiagram={!!diagram}
        title={diagram?.title ?? null}
        loading={loading}
        busy={busy}
        error={error}
        onDismissError={() => setError(null)}
        source={source}
        nodeCount={diagram?.nodes.length ?? 0}
        edgeCount={diagram?.edges.length ?? 0}
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
        hasSavedProject={!!currentProjectId}
        onQuickSave={onQuickSave}
        lastSavedAt={autosaveAt}
        dirty={dirty}
        username={username}
        onLogout={onLogout}
      />
      <div className="body">
        <div className="canvas-area">
          {diagram ? (
            <DiagramCanvas
              // Remount on a genuinely different diagram so the canvas re-fits to
              // it; plain edits keep the same key and so keep the user's view.
              key={`${diagram.session_id}:${diagram.diagram_id}`}
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
            <EmptyState
              onBlank={onBlank}
              onSample={onSample}
              onUpload={onUpload}
              onGenerateTemplate={onGenerateTemplate}
              onGenerateOutline={onGenerateOutline}
            />
          )}
        </div>
        {diagram && (
          <Sidebar
            tabs={SIDEBAR_TABS}
            tab={tab}
            onTabChange={setTab}
            width={sidebarWidth}
            onWidthChange={setSidebarWidth}
            collapsed={sidebarCollapsed}
            onSetCollapsed={setSidebarCollapsed}
          >
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
            {tab === "csv" && (
              <CsvPanel
                unknownTypes={diagram.unknown_types}
                shapes={diagram.shapes}
                lines={diagram.lines}
                onApply={onApplyCsv}
              />
            )}
            {tab === "templates" && <TemplatesPanel onGenerate={onGenerateTemplate} />}
            {tab === "outline" && (
              <OutlinePanel shapes={diagram.shapes} lines={diagram.lines} onGenerate={onGenerateOutline} />
            )}
            {tab === "style" && <StyleRulesPanel rulesText={diagram.style_rules} onApply={onApplyStyleRules} />}
            {tab === "projects" && (
              <ProjectsPanel
                projects={projects}
                currentProjectId={currentProjectId}
                currentName={currentProjectName || diagram.title}
                busy={busy}
                onSave={onSaveProject}
                onSaveAsCopy={onSaveProjectAsCopy}
                onLoad={onLoadProject}
                onDelete={onDeleteProject}
              />
            )}
          </Sidebar>
        )}
      </div>
    </div>
  );
}

// ---------- auth gate ----------
// Wraps DiagramApp: validates any stored token on mount (a token can be
// stale — expired, or the DB it was issued against got wiped), shows
// LoginScreen otherwise, and drops back to LoginScreen on any 401 from the
// API (onUnauthorized, wired in api.ts) rather than each caller handling it.
export default function App() {
  const [checked, setChecked] = useState(false);
  const [user, setUser] = useState<{ username: string } | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setChecked(true);
      return;
    }
    me()
      .then((u) => setUser(u))
      .catch(() => setToken(null))
      .finally(() => setChecked(true));
  }, []);

  useEffect(() => {
    onUnauthorized.handler = () => setUser(null);
    return () => {
      onUnauthorized.handler = null;
    };
  }, []);

  const onAuthed = useCallback((token: string, username: string) => {
    setToken(token);
    setUser({ username });
  }, []);

  const onLogout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  if (!checked) return null;
  if (!user) return <LoginScreen onAuthed={onAuthed} />;
  return <DiagramApp key={user.username} username={user.username} onLogout={onLogout} />;
}
