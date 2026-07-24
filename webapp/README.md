# diagen web app

React + TypeScript + Axios frontend on top of a FastAPI backend that wraps
the existing `diagen` Python engine. There is exactly **one** place layout,
routing, and diagram-editing logic ever run — the Python engine — so the
frontend is a thin client and can never drift out of sync the way the
standalone JS playground had to be kept in sync by hand. The frontend has
full parity with `diagen_playground.html`: palette drag-to-create, connect
tool, node/edge editing, undo/redo, multi-diagram workbooks, CSV paste,
template generator, outline (mind-map) mode, live style rules, and
SVG/draw.io/HTML export.

```
webapp/
  backend/    FastAPI app (main.py, diagram_store.py) + bundled sample .xlsx files
  frontend/   Vite + React + TypeScript + Axios app
```

## How it fits together

1. You upload an `.xlsx`, pick a bundled sample, generate from a template/outline, or
   start blank → the backend builds/loads a `diagen.Spec`, runs `layout()`, renders SVG +
   draw.io + an HTML snapshot, and caches the live multi-diagram `Spec` in memory under a
   `session_id`.
2. Every edit — drag, palette-create, connect-tool edge, label/color/metadata change,
   delete, duplicate, reparent, auto-arrange, undo/redo, CSV re-apply, style rules — is a
   POST to the backend. It mutates the *same* cached `Diagram` object and re-renders
   through the exact same renderer used for the initial load, so nothing is ever
   recomputed twice or drifts between what you see and what exports.
3. The frontend renders the returned SVG and layers interactivity on top of it: click to
   select/inspect (`PropertiesPanel`), drag to reposition, palette drag-drop or click to
   create, connect-tool click-click to wire two shapes together, search to dim
   non-matching shapes.

One disclosed scope boundary: creating/deleting/reparenting a node triggers a full
auto-layout recompute, rather than the JS playground's precise "resize only the touched
container, leave everyone else exactly where they were" behavior — Python's layout engine
has no in-place container-resize primitive equivalent to that yet.

## Run it

**Backend**
```bash
cd webapp/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
The `diagen` engine lives right here as `webapp/backend/diagen/` (plain local
source, not a separate package) — `app/` imports it directly, nothing extra
to install. See `webapp/backend/README.md` for the engine's own docs.

**Frontend** (separate terminal)
```bash
cd webapp/frontend
npm install
npm run dev
```
Open the URL Vite prints (usually `http://localhost:5173`). The dev server proxies
`/api/*` to `http://127.0.0.1:8000` (see `vite.config.ts`), so there's no CORS setup
needed locally.

## Production build
```bash
cd webapp/frontend
npm run build        # outputs frontend/dist — serve it with any static host
```
Point `VITE_API_BASE` (a build-time env var) at wherever you deploy the FastAPI
backend if it isn't reachable at `/api` in that environment.

## API

| Endpoint | Method | Body | Notes |
|---|---|---|---|
| `/api/health` | GET | — | liveness check |
| `/api/samples` | GET | — | bundled sample filenames |
| `/api/palette` | GET | — | standalone default shape/line palette |
| `/api/sample` | POST | `{name}` | load a bundled workbook |
| `/api/upload` | POST | multipart `file` (.xlsx) | load an uploaded workbook |
| `/api/blank` | POST | `{title?}` | start an empty diagram |
| `/api/diagram/{session_id}/list` | GET | — | diagrams in this session's workbook |
| `/api/diagram/switch` | POST | `{session_id, diagram_id}` | switch the active diagram |
| `/api/reposition` | POST | `{session_id, node_id, x, y}` | drag-to-move |
| `/api/node/create` | POST | `{session_id, entity_type, label?, parent?, x?, y?}` | palette/drop create |
| `/api/node/update` | POST | `{session_id, node_id, label?, entity_type?, fill_override?, stroke_override?, metadata?}` | |
| `/api/node/delete` | POST | `{session_id, node_id}` | also removes descendants + incident edges |
| `/api/node/duplicate` | POST | `{session_id, node_id}` | |
| `/api/node/reparent` | POST | `{session_id, node_id, parent}` | |
| `/api/edge/create` | POST | `{session_id, source_id, target_id, relation_type, label?}` | connect tool |
| `/api/edge/update` | POST | `{session_id, edge_id, relation_type?, label?, reverse?}` | |
| `/api/edge/delete` | POST | `{session_id, edge_id}` | |
| `/api/auto-arrange` | POST | `{session_id, direction?}` | `direction`: `TB` \| `LR` |
| `/api/undo` / `/api/redo` | POST | `{session_id}` | per-diagram snapshot history |
| `/api/csv/apply` | POST | `{session_id, nodes_csv, edges_csv?, shapes_csv?, lines_csv?}` | replaces active diagram's data |
| `/api/templates` | GET | — | parameterized diagram generators + their fields |
| `/api/template/generate` | POST | `{template_name, params}` | starts a fresh session |
| `/api/outline/generate` | POST | `{text, entity_type, relation_type}` | indented-text mind-map, fresh session |
| `/api/style-rules` | POST | `{session_id, rules_text}` | transient display-only fill/stroke overlay |

Every mutating endpoint returns the full diagram payload (svg, drawio, html, nodes, edges,
connections, the session's diagrams/shapes/lines, style_rules) so the frontend always has
a complete, consistent snapshot to render from.

Sessions are kept in an in-memory, TTL'd dict (`app/diagram_store.py`) — fine for local
use; swap for Redis if this ever needs to survive a backend restart or run multi-process.
