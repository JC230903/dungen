"""Named-project persistence: save/load a full `diagen.Spec` (every diagram,
its shapes/lines palette) to durable storage so work survives backend
restarts and can be reopened later — separate from the ephemeral, TTL'd
in-memory sessions in `diagram_store.py`. Backed by SQLite or Postgres/Cloud
SQL depending on environment — see `app/db.py`.

Serialization mirrors `Spec`'s own row-shaped ingestion contract
(`add_shape_row` / `_add_node` / `_add_edge` take the same dict shape as a
Shape_Library/Nodes/Edges worksheet row) so save/load is exactly "dump every
row Spec would have read from a workbook, read them back the same way" —
no separate schema to keep in sync with `diagen.model`.
"""
from __future__ import annotations
import json
import time
import uuid
from typing import Optional

from diagen.model import Diagram
from diagen.spec import Spec

from . import db


def _conn():
    conn = db.connect()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        )"""
    )
    # Added when multi-user auth landed. Rows from before this migration
    # have user_id = NULL and become unreachable through the ownership-
    # scoped queries below — acceptable for a pre-auth dev DB, not a
    # data-loss path (the rows aren't deleted, just orphaned).
    db.add_column_if_missing(conn, "projects", "user_id", "TEXT")
    return conn


# ---------- Spec <-> plain dict (JSON-able) ----------
def spec_to_dict(spec: Spec) -> dict:
    return {
        "shapes": [
            {
                "entity_type": s.entity_type, "family": s.family, "shape": s.shape,
                "default_w": s.default_w, "default_h": s.default_h,
                "min_w": s.min_w, "min_h": s.min_h,
                "fill_hex": s.fill, "stroke_hex": s.stroke, "auto_size": s.auto,
            }
            for s in spec.shapes.values()
        ],
        "lines": [
            {
                "relation_type": l.relation_type, "family": l.family,
                "line_style": l.style, "width_px": l.width,
                "source_end": l.source_end, "target_end": l.target_end,
                "routing": l.routing, "label_position": l.label_pos, "color_hex": l.color,
            }
            for l in spec.lines.values()
        ],
        "diagrams": [
            {
                "id": d.id, "scenario": d.scenario, "title": d.title,
                "direction": d.direction, "theme": d.theme,
                "nodes": [
                    {
                        "node_id": n.id, "diagram_id": n.diagram, "parent_id": n.parent,
                        "entity_type": n.type, "label": n.label,
                        "rank_hint": n.rank, "order_hint": n.order,
                        "w_override": n.w_override, "h_override": n.h_override,
                        "fill_override": n.fill_override, "stroke_override": n.stroke_override,
                        "metadata": n.meta,
                    }
                    for n in d.nodes.values()
                ],
                "edges": [
                    {
                        "edge_id": e.id, "diagram_id": e.diagram,
                        "source_id": e.source, "target_id": e.target,
                        "relation_type": e.relation, "label": e.label,
                        "waypoint_hint": e.hint, "source_port": e.sport, "target_port": e.tport,
                    }
                    for e in d.edges
                ],
            }
            for d in spec.diagrams.values()
        ],
    }


def spec_from_dict(data: dict) -> Spec:
    spec = Spec(None, use_defaults=False)
    for row in data.get("shapes", []):
        spec.add_shape_row(row)
    for row in data.get("lines", []):
        spec.add_line_row(row)
    for dd in data.get("diagrams", []):
        diagram = Diagram(
            id=dd["id"], scenario=dd.get("scenario", ""),
            title=dd.get("title") or dd["id"],
            direction=dd.get("direction") or "top-down", theme=dd.get("theme", ""),
        )
        spec.diagrams[diagram.id] = diagram
        for row in dd.get("nodes", []):
            spec._add_node(row)
        for row in dd.get("edges", []):
            spec._add_edge(row)
    spec._link()
    return spec


# ---------- CRUD (all scoped to owning user_id — never cross a user boundary) ----------
def list_projects(user_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at, updated_at FROM projects "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [{"id": r[0], "name": r[1], "created_at": r[2], "updated_at": r[3]} for r in rows]


def count_projects(user_id: str) -> int:
    with _conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM projects WHERE user_id = ?", (user_id,)).fetchone()
    return row[0] if row else 0


def save_project(name: str, data: dict, user_id: str, project_id: Optional[str] = None) -> str:
    """Insert a new project, or update `project_id` IN PLACE if it exists
    AND is owned by `user_id`. Raises PermissionError if `project_id` exists
    but belongs to someone else — callers must turn that into a 403/404,
    never silently fall through to creating a new row (that would look like
    a successful overwrite to the caller while quietly not touching the
    other user's data — worse than a clear error)."""
    now = time.time()
    payload = json.dumps(data)
    with _conn() as conn:
        if project_id:
            owner = conn.execute("SELECT user_id FROM projects WHERE id = ?", (project_id,)).fetchone()
            if owner is not None and owner[0] != user_id:
                raise PermissionError("Not your project")
            if owner is not None:
                conn.execute(
                    "UPDATE projects SET name = ?, data = ?, updated_at = ? WHERE id = ?",
                    (name, payload, now, project_id),
                )
                return project_id
        pid = project_id or str(uuid.uuid4())
        conn.execute(
            "INSERT INTO projects (id, name, data, created_at, updated_at, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pid, name, payload, now, now, user_id),
        )
    return pid


def get_project(project_id: str, user_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT name, data FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id)
        ).fetchone()
    if row is None:
        return None
    return {"name": row[0], "data": json.loads(row[1])}


def delete_project(project_id: str, user_id: str) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id)
        )
    return cur.rowcount > 0
