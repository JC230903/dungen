"""Plain-data helpers for exposing a laid-out Diagram to external consumers
(e.g. a web API + React frontend). Kept separate from render_svg.py — that
module's job is SVG generation, this one is data shaping for callers that
just need geometry/connections without touching the renderer at all."""
from __future__ import annotations
from .model import Diagram


def node_dicts(d: Diagram) -> list[dict]:
    """Every node's id/label/type/geometry, post-layout, PLUS the raw
    authoring fields (rank/order hints, overrides, metadata). x/y/w/h are the
    values render_svg.py itself will draw from — this is the same source of
    truth, not a re-derived copy. The raw fields round-trip losslessly back
    into a Nodes CSV row (see webapp's CSV export) and back into
    `Spec.load_rows`/the node-update endpoint without re-deriving anything."""
    return [
        {
            'id': n.id, 'label': n.label, 'type': n.type,
            'x': n.x, 'y': n.y, 'w': n.w, 'h': n.h,
            'parent': n.parent or None,
            'rank_hint': n.rank, 'order_hint': n.order,
            'w_override': n.w_override, 'h_override': n.h_override,
            'fill_override': n.fill_override, 'stroke_override': n.stroke_override,
            'metadata': n.meta,
        }
        for n in d.nodes.values()
    ]


def edge_dicts(d: Diagram) -> list[dict]:
    return [
        {
            'id': e.id, 'source': e.source, 'target': e.target,
            'label': e.label, 'relation': e.relation,
            'waypoint_hint': e.hint, 'source_port': e.sport, 'target_port': e.tport,
        }
        for e in d.edges
    ]


def connections_map(d: Diagram) -> dict[str, list[dict]]:
    """node_id -> every edge touching that node (in and out), each as
    {edge_id, other_id, other_label, label, dir}. Powers the "click a shape,
    see its connections" panel without the frontend needing to know anything
    about layout or routing."""
    out: dict[str, list[dict]] = {n.id: [] for n in d.nodes.values()}
    for e in d.edges:
        s, t = d.nodes.get(e.source), d.nodes.get(e.target)
        if s is None or t is None:
            continue
        out.setdefault(e.source, []).append({
            'edge_id': e.id, 'other_id': t.id, 'other_label': t.label,
            'label': e.label, 'dir': 'out',
        })
        out.setdefault(e.target, []).append({
            'edge_id': e.id, 'other_id': s.id, 'other_label': s.label,
            'label': e.label, 'dir': 'in',
        })
    return out
