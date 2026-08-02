"""FastAPI backend for the diagen web app.

Design in one line: the Python `diagen` engine (spec parsing, layout,
routing, SVG/draw.io/HTML rendering, templates, outline mode) is the ONLY
place diagram geometry or diagram-editing logic is ever computed. This API
is a thin wrapper around it — every mutating endpoint (create/edit/delete a
node or edge, reparent, auto-arrange, undo/redo, apply a CSV paste, generate
a template) mutates the same live `Diagram` object in the session and
re-renders through the exact same renderer used for the initial render.
There is no second, JS/TS-side copy of layout, routing, or editing logic
anywhere in this project — the React frontend is a thin client over this API.
"""
from __future__ import annotations
import copy
import csv
import io
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from diagen.spec import Spec
from diagen.layout import layout, _shift
from diagen.render_svg import SvgRenderer
from diagen.render_drawio import to_drawio
from diagen.interop import node_dicts, edge_dicts, connections_map
from diagen.defaults import DEFAULT_SHAPES, DEFAULT_LINES
from diagen.templates import TEMPLATES, build_outline
from diagen.model import Node, Edge

from .diagram_store import store, Session
from . import projects as project_store
from . import auth as auth_store
from .ratelimit import RateLimiter

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"

MAX_UPLOAD_BYTES = 15 * 1024 * 1024   # .xlsx workbooks; generous, catches abuse not real files
MAX_CSV_BYTES = 5 * 1024 * 1024       # per CSV-paste field
MAX_PROJECT_NAME_LEN = 200
MAX_PROJECTS_PER_USER = 500

app = FastAPI(title="diagen API")

# `FRONTEND_ORIGIN` (comma-separated) restricts CORS to real cross-origin
# deployments — e.g. GCP Cloud Run, where frontend and backend are two
# separate services on two separate URLs (see webapp/deploy-gcp/). Unset
# (the default, and what webapp/deploy/ uses) falls back to wide-open,
# which is low-risk there specifically because the browser only ever talks
# to Caddy same-origin — Caddy forwards to this backend server-side, so no
# real cross-origin browser request ever happens.
_frontend_origins = [o.strip() for o in os.environ.get("FRONTEND_ORIGIN", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths reachable without a token. Everything else under /api/* requires
# `Authorization: Bearer <token>` — see auth_middleware below.
PUBLIC_API_PATHS = {"/api/health", "/api/auth/signup", "/api/auth/login"}

_limiter = RateLimiter()


def _client_ip(request: Request) -> str:
    # Cloudflare Tunnel sets this to the real visitor IP; fall back for direct/local access.
    return (
        request.headers.get("cf-connecting-ip")
        or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
        or (request.client.host if request.client else "unknown")
    )


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        ip = _client_ip(request)
        # Tighter limit on auth endpoints — this is the brute-force-guessing surface.
        if request.url.path.startswith("/api/auth/"):
            allowed = _limiter.check(f"auth:{ip}", max_requests=20, window_seconds=60)
        else:
            allowed = _limiter.check(f"api:{ip}", max_requests=300, window_seconds=60)
        if not allowed:
            return JSONResponse({"detail": "Too many requests — slow down."}, status_code=429)
    return await call_next(request)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path not in PUBLIC_API_PATHS:
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else None
        payload = auth_store.verify_token(token) if token else None
        if payload is None:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        request.state.user_id = payload["user_id"]
        request.state.username = payload["username"]
    return await call_next(request)


# ---------- schemas ----------
class NodeOut(BaseModel):
    id: str
    label: str
    type: str
    x: float
    y: float
    w: float
    h: float
    parent: Optional[str] = None
    rank_hint: int = 0
    order_hint: int = 0
    w_override: Optional[float] = None
    h_override: Optional[float] = None
    fill_override: str = ''
    stroke_override: str = ''
    metadata: str = ''


class EdgeOut(BaseModel):
    id: str
    source: str
    target: str
    label: str
    relation: str
    waypoint_hint: str = ''
    source_port: str = ''
    target_port: str = ''


class ConnectionOut(BaseModel):
    edge_id: str
    other_id: str
    other_label: str
    label: str
    dir: str


class DiagramInfo(BaseModel):
    id: str
    title: str
    node_count: int


class ShapeOut(BaseModel):
    entity_type: str
    family: str
    shape: str
    fill: str
    stroke: str
    auto: str
    default_w: float
    default_h: float
    min_w: float
    min_h: float


class LineOut(BaseModel):
    relation_type: str
    family: str
    style: str
    width: float
    source_end: str
    target_end: str
    routing: str
    label_pos: str
    color: str


class DiagramResponse(BaseModel):
    session_id: str
    diagram_id: str
    title: str
    direction: str
    svg: str
    drawio: str
    html: str
    canvas_w: float
    canvas_h: float
    nodes: list[NodeOut]
    edges: list[EdgeOut]
    connections: dict[str, list[ConnectionOut]]
    diagrams: list[DiagramInfo]
    shapes: list[ShapeOut]
    lines: list[LineOut]
    style_rules: str
    unknown_types: list[str] = []


class PaletteResponse(BaseModel):
    shapes: list[ShapeOut]
    lines: list[LineOut]


class SampleRequest(BaseModel):
    name: str


class BlankRequest(BaseModel):
    title: Optional[str] = None


class DiagramSwitchRequest(BaseModel):
    session_id: str
    diagram_id: str


class RepositionRequest(BaseModel):
    session_id: str
    node_id: str
    x: float
    y: float


class NodeCreateRequest(BaseModel):
    session_id: str
    entity_type: str
    label: str = ''
    parent: str = ''
    x: float = 100
    y: float = 100


class NodeUpdateRequest(BaseModel):
    session_id: str
    node_id: str
    label: Optional[str] = None
    entity_type: Optional[str] = None
    fill_override: Optional[str] = None
    stroke_override: Optional[str] = None
    metadata: Optional[str] = None


class NodeIdRequest(BaseModel):
    session_id: str
    node_id: str


class NodeReparentRequest(BaseModel):
    session_id: str
    node_id: str
    parent: str = ''


class EdgeCreateRequest(BaseModel):
    session_id: str
    source_id: str
    target_id: str
    relation_type: str
    label: str = ''


class EdgeUpdateRequest(BaseModel):
    session_id: str
    edge_id: str
    relation_type: Optional[str] = None
    label: Optional[str] = None
    reverse: bool = False


class EdgeIdRequest(BaseModel):
    session_id: str
    edge_id: str


class AutoArrangeRequest(BaseModel):
    session_id: str
    direction: Optional[str] = None  # 'TB' | 'LR'


class SessionIdRequest(BaseModel):
    session_id: str


class CsvApplyRequest(BaseModel):
    session_id: str
    nodes_csv: str = Field(max_length=MAX_CSV_BYTES)
    edges_csv: str = Field('', max_length=MAX_CSV_BYTES)
    shapes_csv: str = Field('', max_length=MAX_CSV_BYTES)
    lines_csv: str = Field('', max_length=MAX_CSV_BYTES)


class TemplateRequest(BaseModel):
    template_name: str
    params: dict[str, str] = {}


class OutlineRequest(BaseModel):
    text: str
    entity_type: str = 'business_actor'
    relation_type: str = 'association'


class StyleRulesRequest(BaseModel):
    session_id: str
    rules_text: str


class ProjectInfo(BaseModel):
    id: str
    name: str
    created_at: float
    updated_at: float


class ProjectSaveRequest(BaseModel):
    session_id: str
    name: str = Field(min_length=1, max_length=MAX_PROJECT_NAME_LEN)
    project_id: Optional[str] = None


class ProjectIdRequest(BaseModel):
    project_id: str


class SignupRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    username: str


class MeResponse(BaseModel):
    username: str


# ---------- helpers ----------
def _first_diagram_id(spec: Spec) -> str:
    for did, d in spec.diagrams.items():
        if d.nodes:
            return did
    # no diagram has nodes yet (e.g. a freshly-uploaded rules-only workbook) —
    # fall back to the first declared diagram, or synthesize one
    if spec.diagrams:
        return next(iter(spec.diagrams))
    from diagen.model import Diagram
    spec.diagrams['D1'] = Diagram('D1', '', 'Untitled diagram')
    return 'D1'


def _html_snapshot(title: str, svg: str) -> str:
    esc_title = (title or 'Diagram').replace('<', '&lt;').replace('>', '&gt;')
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<title>{esc_title}</title>'
        '<style>body{margin:0;padding:32px;background:#F7F7F8;'
        'font-family:Arial,Helvetica,sans-serif;display:flex;justify-content:center}'
        '.sheet{background:#fff;border:1px solid #ddd;border-radius:8px;'
        'padding:24px;box-shadow:0 1px 4px rgba(0,0,0,.08);max-width:100%}'
        'svg{max-width:100%;height:auto;display:block}</style></head>'
        f'<body><div class="sheet">{svg}</div></body></html>'
    )


def _parse_style_rules(text: str):
    rules = []
    for line in (text or '').split('\n'):
        line = line.strip()
        if not line or ':' not in line:
            continue
        cond, styles = line.split(':', 1)
        if '=' not in cond:
            continue
        mkey, mval = (x.strip() for x in cond.split('=', 1))
        fill = stroke = ''
        for part in styles.split(','):
            part = part.strip()
            if part.lower().startswith('fill='):
                fill = part[5:].strip()
            elif part.lower().startswith('stroke='):
                stroke = part[7:].strip()
        rules.append(((mkey, mval), (fill, stroke)))
    return rules


def _apply_style_rules_transient(d, rules_text: str):
    """Temporarily overlays fill/stroke for nodes whose metadata matches a
    rule, for THIS render only — restore() puts the node's real stored
    fill_override/stroke_override back afterward. Rules never mutate the
    authored data, only what gets drawn (mirrors the playground's live
    rule-preview, which is a display layer, not an edit)."""
    rules = _parse_style_rules(rules_text)
    if not rules:
        return lambda: None
    originals = {}
    for n in d.nodes.values():
        meta = n.meta_dict()
        for (mkey, mval), (fill, stroke) in rules:
            if meta.get(mkey) == mval:
                originals[n.id] = (n.fill_override, n.stroke_override)
                if fill:
                    n.fill_override = fill
                if stroke:
                    n.stroke_override = stroke
                break

    def restore():
        for nid, (f, s) in originals.items():
            node = d.nodes.get(nid)
            if node:
                node.fill_override, node.stroke_override = f, s
    return restore


def _gen_id(prefix: str, existing: set) -> str:
    i = len(existing) + 1
    while f'{prefix}{i}' in existing:
        i += 1
    return f'{prefix}{i}'


def _relayout(session: Session):
    w, h = layout(session.diagram, session.spec)
    session.canvas_w, session.canvas_h = w, h


def _build_response(session: Session, unknown_types: list[str] = None) -> DiagramResponse:
    spec, d = session.spec, session.diagram
    restore = _apply_style_rules_transient(d, session.style_rules) if session.style_rules else (lambda: None)
    try:
        renderer = SvgRenderer(spec)
        svg = renderer.render(d, session.canvas_w, session.canvas_h)
        drawio = to_drawio(d, spec)
    finally:
        restore()
    html = _html_snapshot(d.title, svg)
    return DiagramResponse(
        session_id=session.session_id,
        diagram_id=session.active_id,
        title=d.title,
        direction=d.direction or 'top-down',
        svg=svg, drawio=drawio, html=html,
        canvas_w=session.canvas_w, canvas_h=session.canvas_h,
        nodes=[NodeOut(**nd) for nd in node_dicts(d)],
        edges=[EdgeOut(**ed) for ed in edge_dicts(d)],
        connections={k: [ConnectionOut(**c) for c in v] for k, v in connections_map(d).items()},
        diagrams=[DiagramInfo(**di) for di in session.diagram_list()],
        shapes=[ShapeOut(entity_type=s.entity_type, family=s.family, shape=s.shape, fill=s.fill,
                          stroke=s.stroke, auto=s.auto, default_w=s.default_w, default_h=s.default_h,
                          min_w=s.min_w, min_h=s.min_h) for s in spec.shapes.values()],
        lines=[LineOut(relation_type=l.relation_type, family=l.family, style=l.style, width=l.width,
                        source_end=l.source_end, target_end=l.target_end, routing=l.routing,
                        label_pos=l.label_pos, color=l.color) for l in spec.lines.values()],
        style_rules=session.style_rules,
        unknown_types=unknown_types or [],
    )


def _get_session(session_id: str) -> Session:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(404, "Session expired or not found — reload the diagram")
    return session


def _get_node(session: Session, node_id: str) -> Node:
    node = session.diagram.nodes.get(node_id)
    if node is None:
        raise HTTPException(404, f"No such node: {node_id}")
    return node


def _get_edge(session: Session, edge_id: str) -> Edge:
    for e in session.diagram.edges:
        if e.id == edge_id:
            return e
    raise HTTPException(404, f"No such edge: {edge_id}")


def _descendants(d, node_id: str) -> set:
    out = set()

    def walk(nid):
        for n in d.nodes.values():
            if n.parent == nid and n.id not in out:
                out.add(n.id)
                walk(n.id)
    walk(node_id)
    return out


def _csv_rows(text: str) -> list[dict]:
    if not text or not text.strip():
        return []
    return list(csv.DictReader(io.StringIO(text)))


# ---------- routes: auth ----------
@app.post("/api/auth/signup", response_model=AuthResponse)
def auth_signup(req: SignupRequest):
    err = auth_store.validate_username(req.username) or auth_store.validate_password(req.password)
    if err:
        raise HTTPException(400, err)
    try:
        user = auth_store.create_user(req.username, req.password)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    token = auth_store.make_token(user["id"], user["username"])
    return AuthResponse(token=token, username=user["username"])


@app.post("/api/auth/login", response_model=AuthResponse)
def auth_login(req: LoginRequest):
    user = auth_store.get_user_by_username(req.username)
    if user is None or not auth_store.verify_password(req.password, user["salt"], user["pw_hash"]):
        raise HTTPException(401, "Wrong username or password")
    token = auth_store.make_token(user["id"], user["username"])
    return AuthResponse(token=token, username=user["username"])


@app.get("/api/auth/me", response_model=MeResponse)
def auth_me(request: Request):
    return MeResponse(username=request.state.username)


# ---------- routes: load / bootstrap ----------
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/samples")
def list_samples() -> list[str]:
    if not SAMPLES_DIR.exists():
        return []
    return sorted(p.name for p in SAMPLES_DIR.glob("*.xlsx"))


@app.get("/api/palette", response_model=PaletteResponse)
def palette():
    """The built-in ~40-entity/~25-relation default palette, standalone — for
    bootstrapping the shape picker / template / outline UI before any
    session exists yet. Once a session is loaded, prefer the `shapes`/`lines`
    already embedded in its DiagramResponse (defaults + that workbook's own
    custom types merged)."""
    return PaletteResponse(
        shapes=[ShapeOut(entity_type=s.entity_type, family=s.family, shape=s.shape, fill=s.fill,
                          stroke=s.stroke, auto=s.auto, default_w=s.default_w, default_h=s.default_h,
                          min_w=s.min_w, min_h=s.min_h) for s in DEFAULT_SHAPES.values()],
        lines=[LineOut(relation_type=l.relation_type, family=l.family, style=l.style, width=l.width,
                        source_end=l.source_end, target_end=l.target_end, routing=l.routing,
                        label_pos=l.label_pos, color=l.color) for l in DEFAULT_LINES.values()],
    )


@app.post("/api/sample", response_model=DiagramResponse)
def load_sample(req: SampleRequest):
    path = SAMPLES_DIR / req.name
    if not path.exists() or path.suffix != ".xlsx":
        raise HTTPException(404, f"No such sample: {req.name}")
    spec = Spec(str(path), use_defaults=True)
    active = _first_diagram_id(spec)
    canvas_w, canvas_h = layout(spec.diagrams[active], spec)
    session = store.put(spec, active, canvas_w, canvas_h)
    return _build_response(session)


@app.post("/api/upload", response_model=DiagramResponse)
async def upload(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Please upload a .xlsx workbook")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)}MB)")
    try:
        spec = Spec(io.BytesIO(raw), use_defaults=True)
    except Exception as exc:  # bad workbook shape, missing sheet, etc.
        raise HTTPException(400, f"Could not read workbook: {exc}") from exc
    active = _first_diagram_id(spec)
    try:
        canvas_w, canvas_h = layout(spec.diagrams[active], spec)
    except KeyError as exc:
        raise HTTPException(400, f"Layout failed: {exc}") from exc
    session = store.put(spec, active, canvas_w, canvas_h)
    return _build_response(session)


@app.post("/api/blank", response_model=DiagramResponse)
def blank(req: BlankRequest):
    """Start a fresh empty diagram (default palette only) — the entry point
    for 'just start dragging shapes' / before using a template or outline."""
    from diagen.model import Diagram
    spec = Spec.blank(use_defaults=True)
    spec.diagrams['D1'] = Diagram('D1', '', req.title or 'Untitled diagram')
    canvas_w, canvas_h = layout(spec.diagrams['D1'], spec)
    session = store.put(spec, 'D1', canvas_w, canvas_h)
    return _build_response(session)


# ---------- routes: multi-diagram ----------
@app.get("/api/diagram/{session_id}/list", response_model=list[DiagramInfo])
def diagram_list(session_id: str):
    session = _get_session(session_id)
    return [DiagramInfo(**di) for di in session.diagram_list()]


@app.post("/api/diagram/switch", response_model=DiagramResponse)
def diagram_switch(req: DiagramSwitchRequest):
    session = _get_session(req.session_id)
    if req.diagram_id not in session.spec.diagrams:
        raise HTTPException(404, f"No such diagram: {req.diagram_id}")
    session.active_id = req.diagram_id
    _relayout(session)
    return _build_response(session)


# ---------- routes: node/edge mutation ----------
@app.post("/api/reposition", response_model=DiagramResponse)
def reposition(req: RepositionRequest):
    session = _get_session(req.session_id)
    node = _get_node(session, req.node_id)
    session.push_undo()
    dx, dy = req.x - node.x, req.y - node.y
    _shift(node, dx, dy)  # moves the node and, if it's a container, its children too
    return _build_response(session)


@app.post("/api/node/create", response_model=DiagramResponse)
def node_create(req: NodeCreateRequest):
    session = _get_session(req.session_id)
    spec, d = session.spec, session.diagram
    if req.entity_type not in spec.shapes:
        raise HTTPException(400, f"Unknown entity_type: {req.entity_type}")
    if req.parent and req.parent not in d.nodes:
        raise HTTPException(404, f"No such parent node: {req.parent}")
    session.push_undo()
    nid = _gen_id('n', set(d.nodes))
    n = Node(id=nid, diagram=session.active_id, parent=req.parent, type=req.entity_type,
             label=req.label or nid)
    from diagen import sizing
    sizing.size_node(n, spec)
    n.x, n.y = req.x, req.y
    d.nodes[nid] = n
    spec._link()
    if req.parent:
        _relayout(session)  # container needs to grow to fit its new child
    return _build_response(session)


@app.post("/api/node/update", response_model=DiagramResponse)
def node_update(req: NodeUpdateRequest):
    session = _get_session(req.session_id)
    spec, d = session.spec, session.diagram
    n = _get_node(session, req.node_id)
    if req.entity_type is not None and req.entity_type not in spec.shapes:
        raise HTTPException(400, f"Unknown entity_type: {req.entity_type}")
    session.push_undo()
    if req.label is not None:
        n.label = req.label
    if req.entity_type is not None:
        n.type = req.entity_type
    if req.fill_override is not None:
        n.fill_override = req.fill_override
    if req.stroke_override is not None:
        n.stroke_override = req.stroke_override
    if req.metadata is not None:
        n.meta = req.metadata
    from diagen import sizing
    sizing.size_node(n, spec)  # label/type changes can change size
    return _build_response(session)


@app.post("/api/node/delete", response_model=DiagramResponse)
def node_delete(req: NodeIdRequest):
    session = _get_session(req.session_id)
    d = session.diagram
    _get_node(session, req.node_id)  # 404s if missing
    session.push_undo()
    doomed = {req.node_id} | _descendants(d, req.node_id)
    for nid in doomed:
        d.nodes.pop(nid, None)
    d.edges = [e for e in d.edges if e.source not in doomed and e.target not in doomed]
    session.spec._link()
    return _build_response(session)


@app.post("/api/node/duplicate", response_model=DiagramResponse)
def node_duplicate(req: NodeIdRequest):
    session = _get_session(req.session_id)
    d = session.diagram
    n = _get_node(session, req.node_id)
    session.push_undo()
    nid = _gen_id('n', set(d.nodes))
    clone = copy.deepcopy(n)
    clone.id = nid
    clone.label = f'{n.label} copy'
    clone.x, clone.y = n.x + 24, n.y + 24
    clone.children = []
    d.nodes[nid] = clone
    session.spec._link()
    return _build_response(session)


@app.post("/api/node/reparent", response_model=DiagramResponse)
def node_reparent(req: NodeReparentRequest):
    session = _get_session(req.session_id)
    d = session.diagram
    n = _get_node(session, req.node_id)
    if req.parent and req.parent not in d.nodes:
        raise HTTPException(404, f"No such parent node: {req.parent}")
    if req.parent in ({req.node_id} | _descendants(d, req.node_id)):
        raise HTTPException(400, "Can't move a node inside itself or its own descendant")
    session.push_undo()
    n.parent = req.parent
    session.spec._link()
    _relayout(session)  # old and new parent containers both need to re-fit
    return _build_response(session)


@app.post("/api/edge/create", response_model=DiagramResponse)
def edge_create(req: EdgeCreateRequest):
    session = _get_session(req.session_id)
    spec, d = session.spec, session.diagram
    if req.source_id not in d.nodes or req.target_id not in d.nodes:
        raise HTTPException(404, "source_id/target_id must both be nodes in the active diagram")
    if req.relation_type not in spec.lines:
        raise HTTPException(400, f"Unknown relation_type: {req.relation_type}")
    session.push_undo()
    eid = _gen_id('e', {e.id for e in d.edges})
    d.edges.append(Edge(id=eid, diagram=session.active_id, source=req.source_id,
                         target=req.target_id, relation=req.relation_type, label=req.label))
    return _build_response(session)


@app.post("/api/edge/update", response_model=DiagramResponse)
def edge_update(req: EdgeUpdateRequest):
    session = _get_session(req.session_id)
    spec = session.spec
    e = _get_edge(session, req.edge_id)
    if req.relation_type is not None and req.relation_type not in spec.lines:
        raise HTTPException(400, f"Unknown relation_type: {req.relation_type}")
    session.push_undo()
    if req.relation_type is not None:
        e.relation = req.relation_type
    if req.label is not None:
        e.label = req.label
    if req.reverse:
        e.source, e.target = e.target, e.source
    return _build_response(session)


@app.post("/api/edge/delete", response_model=DiagramResponse)
def edge_delete(req: EdgeIdRequest):
    session = _get_session(req.session_id)
    d = session.diagram
    _get_edge(session, req.edge_id)  # 404s if missing
    session.push_undo()
    d.edges = [e for e in d.edges if e.id != req.edge_id]
    return _build_response(session)


# ---------- routes: layout ----------
@app.post("/api/auto-arrange", response_model=DiagramResponse)
def auto_arrange(req: AutoArrangeRequest):
    session = _get_session(req.session_id)
    d = session.diagram
    session.push_undo()
    if req.direction:
        d.direction = 'left-right' if req.direction.upper() == 'LR' else 'top-down'
    for n in d.nodes.values():
        n.rank, n.order = 0, 0  # force a fresh topological pass in layout()
    _relayout(session)
    return _build_response(session)


@app.post("/api/undo", response_model=DiagramResponse)
def undo(req: SessionIdRequest):
    session = _get_session(req.session_id)
    if not session.undo():
        raise HTTPException(400, "Nothing to undo")
    return _build_response(session)


@app.post("/api/redo", response_model=DiagramResponse)
def redo(req: SessionIdRequest):
    session = _get_session(req.session_id)
    if not session.redo():
        raise HTTPException(400, "Nothing to redo")
    return _build_response(session)


# ---------- routes: CSV / templates / outline ----------
@app.post("/api/csv/apply", response_model=DiagramResponse)
def csv_apply(req: CsvApplyRequest):
    """Replace the ACTIVE diagram's nodes/edges from pasted CSV text — other
    diagrams in this session are untouched. Mirrors the playground's
    'Apply CSV → canvas'. Since pasted rows carry rank/order hints rather
    than x/y, this always ends with a full layout pass."""
    session = _get_session(req.session_id)
    session.push_undo()
    unknown = session.spec.replace_diagram_data(
        session.active_id,
        node_rows=_csv_rows(req.nodes_csv),
        edge_rows=_csv_rows(req.edges_csv),
        shape_rows=_csv_rows(req.shapes_csv),
        line_rows=_csv_rows(req.lines_csv),
    )
    if not session.diagram.nodes:
        raise HTTPException(400, "No usable node rows found" +
                             (f" (unknown entity types: {', '.join(unknown)})" if unknown else ""))
    _relayout(session)
    return _build_response(session, unknown_types=unknown)


@app.get("/api/templates")
def list_templates():
    return {name: {'description': t['description'],
                    'fields': [{'key': k, 'label': lbl, 'default': d} for k, lbl, d in t['fields']]}
            for name, t in TEMPLATES.items()}


@app.post("/api/template/generate", response_model=DiagramResponse)
def template_generate(req: TemplateRequest):
    tpl = TEMPLATES.get(req.template_name)
    if tpl is None:
        raise HTTPException(404, f"No such template: {req.template_name}")
    vals = {k: req.params.get(k, default) for k, _label, default in tpl['fields']}
    built = tpl['build'](vals)
    spec = Spec.blank(use_defaults=True)
    spec.load_rows(built['nodes'], built['edges'], title=built['title'])
    d = spec.diagrams['D1']
    canvas_w, canvas_h = layout(d, spec)
    session = store.put(spec, 'D1', canvas_w, canvas_h)
    return _build_response(session)


@app.post("/api/outline/generate", response_model=DiagramResponse)
def outline_generate(req: OutlineRequest):
    spec = Spec.blank(use_defaults=True)
    if req.entity_type not in spec.shapes:
        raise HTTPException(400, f"Unknown entity_type: {req.entity_type}")
    if req.relation_type not in spec.lines:
        raise HTTPException(400, f"Unknown relation_type: {req.relation_type}")
    built = build_outline(req.text, req.entity_type, req.relation_type)
    spec.load_rows(built['nodes'], built['edges'], title='Outline')
    d = spec.diagrams['D1']
    canvas_w, canvas_h = layout(d, spec)
    session = store.put(spec, 'D1', canvas_w, canvas_h)
    return _build_response(session)


# ---------- routes: style rules ----------
@app.post("/api/style-rules", response_model=DiagramResponse)
def style_rules(req: StyleRulesRequest):
    session = _get_session(req.session_id)
    session.style_rules = req.rules_text
    return _build_response(session)


# ---------- routes: saved projects (SQLite-backed, survives restarts) ----------
# Every route here reads `request.state.user_id`, set by auth_middleware —
# these paths are never in PUBLIC_API_PATHS, so it's always present.
@app.get("/api/projects", response_model=list[ProjectInfo])
def projects_list(request: Request):
    return project_store.list_projects(request.state.user_id)


@app.post("/api/projects/save", response_model=ProjectInfo)
def projects_save(req: ProjectSaveRequest, request: Request):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "Project name can't be empty")
    user_id = request.state.user_id
    session = _get_session(req.session_id)
    if not req.project_id and project_store.count_projects(user_id) >= MAX_PROJECTS_PER_USER:
        raise HTTPException(409, f"Saved-project limit reached ({MAX_PROJECTS_PER_USER})")
    data = project_store.spec_to_dict(session.spec)
    try:
        pid = project_store.save_project(name, data, user_id, req.project_id)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    row = next(p for p in project_store.list_projects(user_id) if p["id"] == pid)
    return ProjectInfo(**row)


@app.post("/api/projects/load", response_model=DiagramResponse)
def projects_load(req: ProjectIdRequest, request: Request):
    project = project_store.get_project(req.project_id, request.state.user_id)
    if project is None:
        raise HTTPException(404, f"No such project: {req.project_id}")
    try:
        spec = project_store.spec_from_dict(project["data"])
        active = _first_diagram_id(spec)
        canvas_w, canvas_h = layout(spec.diagrams[active], spec)
        session = store.put(spec, active, canvas_w, canvas_h)
        return _build_response(session)
    except (KeyError, ValueError) as exc:  # corrupt/old-format row, shouldn't happen but don't 500 opaquely
        raise HTTPException(400, f"Could not load project: {exc}") from exc


@app.post("/api/projects/delete")
def projects_delete(req: ProjectIdRequest, request: Request):
    deleted = project_store.delete_project(req.project_id, request.state.user_id)
    if not deleted:
        raise HTTPException(404, f"No such project: {req.project_id}")
    return {"deleted": True}
