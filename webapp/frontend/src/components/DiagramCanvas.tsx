import { useEffect, useRef, useState, useCallback } from "react";
import type { NodeOut, EdgeOut, ConnectionOut } from "../api";
import type { Tool } from "./Toolbar";
import { PALETTE_DRAG_MIME } from "./Palette";

interface Props {
  svg: string;
  nodes: NodeOut[];
  edges: EdgeOut[];
  connections: Record<string, ConnectionOut[]>;
  selectedNodeIds: string[];
  selectedEdgeId: string | null;
  tool: Tool;
  search: string;
  onSelectNode: (id: string | null, additive?: boolean) => void;
  onSelectEdge: (id: string | null) => void;
  onDragEnd: (nodeId: string, x: number, y: number) => void;
  onConnectCreate: (sourceId: string, targetId: string) => void;
  onDropCreate: (entityType: string, x: number, y: number) => void;
  busy: boolean;
}

const MIN_ZOOM = 0.15;
const MAX_ZOOM = 4;

/** Renders the backend-provided SVG string and layers interactivity on top of
 * it (click-to-highlight, drag-to-reposition, connect-tool, palette
 * drag-drop, pan/zoom, search dimming). No layout or routing math lives here
 * — every geometry change is round-tripped through the Python engine so
 * there is exactly one source of truth for where things sit on the canvas. */
export default function DiagramCanvas({
  svg,
  nodes,
  edges,
  connections,
  selectedNodeIds,
  selectedEdgeId,
  tool,
  search,
  onSelectNode,
  onSelectEdge,
  onDragEnd,
  onConnectCreate,
  onDropCreate,
  busy,
}: Props) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const worldRef = useRef<HTMLDivElement>(null);
  const svgElRef = useRef<SVGSVGElement | null>(null);
  const [view, setView] = useState({ x: 0, y: 0, scale: 1 });
  const [connectSource, setConnectSource] = useState<string | null>(null);
  const dragState = useRef<{
    id: string;
    startClientX: number;
    startClientY: number;
    origX: number;
    origY: number;
    el: SVGGElement;
    shiftKey: boolean;
  } | null>(null);
  const panState = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(
    null
  );
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);

  // refs mirroring the latest props, read from inside the SVG-injection
  // effect so that effect doesn't need to re-run (and re-parse the whole SVG
  // string) every time a callback identity or the active tool changes.
  const toolRef = useRef(tool);
  const busyRef = useRef(busy);
  const onSelectNodeRef = useRef(onSelectNode);
  const onSelectEdgeRef = useRef(onSelectEdge);
  const onDragEndRef = useRef(onDragEnd);
  const onConnectCreateRef = useRef(onConnectCreate);
  const nodesRef = useRef(nodes);
  useEffect(() => {
    toolRef.current = tool;
    busyRef.current = busy;
    onSelectNodeRef.current = onSelectNode;
    onSelectEdgeRef.current = onSelectEdge;
    onDragEndRef.current = onDragEnd;
    onConnectCreateRef.current = onConnectCreate;
    nodesRef.current = nodes;
  });

  // connect-tool: clicking a node picks source then target; re-clicking the
  // source cancels; switching tools clears any pending pick.
  useEffect(() => {
    if (tool !== "connect") setConnectSource(null);
  }, [tool]);

  const handleConnectClick = useCallback((id: string) => {
    setConnectSource((cur) => {
      if (!cur) return id;
      if (cur === id) return null;
      onConnectCreateRef.current(cur, id);
      return null;
    });
  }, []);

  const nodeById = useCallback((id: string) => nodes.find((n) => n.id === id), [nodes]);

  // ---------- inject the raw SVG string, then wire up interactivity ----------
  useEffect(() => {
    const world = worldRef.current;
    if (!world) return;
    world.innerHTML = svg;
    const svgEl = world.querySelector("svg") as SVGSVGElement | null;
    svgElRef.current = svgEl;
    if (!svgEl) return;

    const nodeGroups = Array.from(
      svgEl.querySelectorAll<SVGGElement>("[data-node-id]")
    );

    const onPointerDown = (ev: PointerEvent, g: SVGGElement, id: string) => {
      if (busyRef.current) return;
      ev.stopPropagation();
      if (toolRef.current === "connect") {
        handleConnectClick(id);
        return;
      }
      const n = nodesRef.current.find((x) => x.id === id);
      if (!n) return;
      dragState.current = {
        id,
        startClientX: ev.clientX,
        startClientY: ev.clientY,
        origX: n.x,
        origY: n.y,
        el: g,
        shiftKey: ev.shiftKey,
      };
      window.addEventListener("pointermove", onPointerMove);
      window.addEventListener("pointerup", onPointerUp);
    };

    const onPointerMove = (ev: PointerEvent) => {
      const ds = dragState.current;
      const svgNode = svgElRef.current;
      if (!ds || !svgNode) return;
      const rect = svgNode.getBoundingClientRect();
      const vb = svgNode.viewBox.baseVal;
      const scaleX = vb.width / rect.width;
      const scaleY = vb.height / rect.height;
      const dx = (ev.clientX - ds.startClientX) * scaleX;
      const dy = (ev.clientY - ds.startClientY) * scaleY;
      ds.el.setAttribute("transform", `translate(${dx},${dy})`);
    };

    const onPointerUp = (ev: PointerEvent) => {
      const ds = dragState.current;
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      if (!ds) return;
      const svgNode = svgElRef.current;
      dragState.current = null;
      if (!svgNode) return;
      const rect = svgNode.getBoundingClientRect();
      const vb = svgNode.viewBox.baseVal;
      const scaleX = vb.width / rect.width;
      const scaleY = vb.height / rect.height;
      const dx = (ev.clientX - ds.startClientX) * scaleX;
      const dy = (ev.clientY - ds.startClientY) * scaleY;
      ds.el.removeAttribute("transform");
      const moved = Math.abs(dx) > 2 || Math.abs(dy) > 2;
      if (moved) {
        onDragEndRef.current(ds.id, ds.origX + dx, ds.origY + dy);
      } else {
        onSelectNodeRef.current(ds.id, ds.shiftKey);
      }
    };

    for (const g of nodeGroups) {
      const id = g.getAttribute("data-node-id");
      if (!id) continue;
      g.style.cursor = "grab";
      g.addEventListener("pointerdown", (ev) => onPointerDown(ev, g, id));
    }
    svgEl.addEventListener("click", (ev) => {
      const target = ev.target as Element;
      if (target.closest("[data-node-id]")) return; // handled via pointerup above
      const edgeEl = target.closest("[data-edge-id]");
      if (edgeEl) {
        onSelectEdgeRef.current(edgeEl.getAttribute("data-edge-id"));
        return;
      }
      onSelectNodeRef.current(null);
      onSelectEdgeRef.current(null);
    });

    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [svg, handleConnectClick]);

  // ---------- highlight selection / search / connect-pending ----------
  useEffect(() => {
    const svgEl = svgElRef.current;
    if (!svgEl) return;
    const nodeGroups = svgEl.querySelectorAll<SVGGElement>("[data-node-id]");
    const edgeGroups = svgEl.querySelectorAll<SVGGElement>("[data-edge-id]");
    const searchQ = search.trim().toLowerCase();

    let nodeVisible: (id: string) => boolean;
    let edgeVisible: (id: string) => boolean;

    if (selectedEdgeId) {
      const e = edges.find((x) => x.id === selectedEdgeId);
      const related = new Set(e ? [e.source, e.target] : []);
      nodeVisible = (id) => related.has(id);
      edgeVisible = (id) => id === selectedEdgeId;
    } else if (selectedNodeIds.length === 1) {
      const conns = connections[selectedNodeIds[0]] || [];
      const relatedNodeIds = new Set([selectedNodeIds[0], ...conns.map((c) => c.other_id)]);
      const relatedEdgeIds = new Set(conns.map((c) => c.edge_id));
      nodeVisible = (id) => relatedNodeIds.has(id);
      edgeVisible = (id) => relatedEdgeIds.has(id);
    } else if (selectedNodeIds.length > 1) {
      const set = new Set(selectedNodeIds);
      nodeVisible = (id) => set.has(id);
      edgeVisible = (id) => {
        const e = edges.find((x) => x.id === id);
        return !!e && set.has(e.source) && set.has(e.target);
      };
    } else {
      nodeVisible = () => true;
      edgeVisible = () => true;
    }

    nodeGroups.forEach((g) => {
      const id = g.getAttribute("data-node-id")!;
      const n = nodeById(id);
      const matchesSearch = !searchQ || (n?.label.toLowerCase().includes(searchQ) ?? false);
      g.style.opacity = matchesSearch && nodeVisible(id) ? "1" : "0.15";
      g.classList.toggle("connect-source", id === connectSource);
    });
    edgeGroups.forEach((g) => {
      const id = g.getAttribute("data-edge-id")!;
      g.style.opacity = edgeVisible(id) ? "1" : "0.12";
    });
  }, [selectedNodeIds, selectedEdgeId, connections, svg, search, edges, connectSource, nodeById]);

  // ---------- bring a newly selected node into view if it's off-screen ----------
  useEffect(() => {
    const svgEl = svgElRef.current;
    const viewport = viewportRef.current;
    const soleId = selectedNodeIds.length === 1 ? selectedNodeIds[0] : null;
    if (!svgEl || !viewport || !soleId) return;
    const n = nodeById(soleId);
    const nodeEl = svgEl.querySelector<SVGGElement>(`[data-node-id="${CSS.escape(soleId)}"]`);
    if (!n || !nodeEl) return;
    const vpRect = viewport.getBoundingClientRect();
    const nodeRect = nodeEl.getBoundingClientRect();
    const margin = 48;
    const visible =
      nodeRect.left >= vpRect.left + margin &&
      nodeRect.right <= vpRect.right - margin &&
      nodeRect.top >= vpRect.top + margin &&
      nodeRect.bottom <= vpRect.bottom - margin;
    if (visible) return;
    const cx = n.x + n.w / 2;
    const cy = n.y + n.h / 2;
    setView((v) => ({
      ...v,
      x: vpRect.width / 2 - v.scale * cx,
      y: vpRect.height / 2 - v.scale * cy,
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodeIds]);

  // ---------- track the selected node's screen position for the tooltip ----------
  useEffect(() => {
    const svgEl = svgElRef.current;
    const viewport = viewportRef.current;
    const soleId = !selectedEdgeId && selectedNodeIds.length === 1 ? selectedNodeIds[0] : null;
    if (!svgEl || !viewport || !soleId) {
      setTooltipPos(null);
      return;
    }
    const computePos = () => {
      const nodeEl = svgEl.querySelector<SVGGElement>(`[data-node-id="${CSS.escape(soleId)}"]`);
      if (!nodeEl) {
        setTooltipPos(null);
        return;
      }
      const vpRect = viewport.getBoundingClientRect();
      const nodeRect = nodeEl.getBoundingClientRect();
      setTooltipPos({
        x: nodeRect.left - vpRect.left + nodeRect.width / 2,
        y: nodeRect.top - vpRect.top,
      });
    };
    computePos();
    window.addEventListener("resize", computePos);
    return () => window.removeEventListener("resize", computePos);
  }, [selectedNodeIds, selectedEdgeId, view, svg]);

  // ---------- pan / zoom ----------
  const onWheel = (ev: React.WheelEvent) => {
    ev.preventDefault();
    const factor = Math.exp(-ev.deltaY * 0.001);
    setView((v) => {
      const scale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, v.scale * factor));
      return { ...v, scale };
    });
  };

  const onBgPointerDown = (ev: React.PointerEvent) => {
    if ((ev.target as Element).closest("[data-node-id]")) return;
    panState.current = { startX: ev.clientX, startY: ev.clientY, origX: view.x, origY: view.y };
    const onMove = (mv: PointerEvent) => {
      const ps = panState.current;
      if (!ps) return;
      setView((v) => ({ ...v, x: ps.origX + (mv.clientX - ps.startX), y: ps.origY + (mv.clientY - ps.startY) }));
    };
    const onUp = () => {
      panState.current = null;
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const fit = () => setView({ x: 0, y: 0, scale: 1 });
  const zoomBy = (f: number) =>
    setView((v) => ({ ...v, scale: Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, v.scale * f)) }));

  // ---------- drop a palette shape onto the canvas ----------
  const onDragOver = (ev: React.DragEvent) => {
    if (ev.dataTransfer.types.includes(PALETTE_DRAG_MIME)) {
      ev.preventDefault();
      ev.dataTransfer.dropEffect = "copy";
    }
  };
  const onDrop = (ev: React.DragEvent) => {
    const entityType = ev.dataTransfer.getData(PALETTE_DRAG_MIME);
    if (!entityType) return;
    ev.preventDefault();
    const svgNode = svgElRef.current;
    if (!svgNode) return;
    const rect = svgNode.getBoundingClientRect();
    const vb = svgNode.viewBox.baseVal;
    const scaleX = vb.width / rect.width;
    const scaleY = vb.height / rect.height;
    const x = vb.x + (ev.clientX - rect.left) * scaleX;
    const y = vb.y + (ev.clientY - rect.top) * scaleY;
    onDropCreate(entityType, x, y);
  };

  const selectedSoleId = !selectedEdgeId && selectedNodeIds.length === 1 ? selectedNodeIds[0] : null;

  return (
    <div
      className="diagram-viewport"
      ref={viewportRef}
      onWheel={onWheel}
      onPointerDown={onBgPointerDown}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      {tool === "connect" && (
        <div className="canvas-hint">
          {connectSource
            ? "Click the target shape (or click the source again to cancel)"
            : "Click a source shape to start a connection"}
        </div>
      )}
      <div className="zoom-controls">
        <button onClick={() => zoomBy(1.2)} title="Zoom in">+</button>
        <button onClick={() => zoomBy(1 / 1.2)} title="Zoom out">−</button>
        <button onClick={fit} title="Reset view">⤢</button>
      </div>
      {busy && <div className="canvas-busy">Recomputing…</div>}
      <div
        className="diagram-world"
        ref={worldRef}
        style={{
          transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
          transformOrigin: "0 0",
        }}
      />
      {selectedSoleId && tooltipPos && (
        <div
          className="node-tooltip"
          style={{ left: tooltipPos.x, top: tooltipPos.y }}
          onPointerDown={(ev) => ev.stopPropagation()}
        >
          <div className="node-tooltip-title">{nodeById(selectedSoleId)?.label ?? selectedSoleId}</div>
          <ul className="node-tooltip-links">
            {(connections[selectedSoleId] || []).map((c) => (
              <li key={c.edge_id}>
                <a
                  href="#"
                  onClick={(ev) => {
                    ev.preventDefault();
                    onSelectNode(c.other_id);
                  }}
                >
                  <span className={`dir dir-${c.dir}`}>{c.dir === "out" ? "→" : "←"}</span>
                  {c.other_label}
                </a>
              </li>
            ))}
            {(connections[selectedSoleId] || []).length === 0 && (
              <li className="hint">No connections.</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
