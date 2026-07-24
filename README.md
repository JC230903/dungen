# diagen

Turn a spreadsheet into a finished diagram. Managers author plain **Nodes**
and **Edges** rows (in Excel or CSV) — entity type, label, who's nested
inside whom, who connects to whom — and the tool auto-sizes shapes, lays
them out, routes the edges, and renders SVG / draw.io / HTML output. No
manual drawing.

It's a FastAPI + React web app (`webapp/`) built on a small Python layout
engine (`webapp/backend/diagen/`). The engine is the single source of truth
for sizing, layout, and routing — the frontend is a thin client, so nothing
ever drifts between what you see on screen and what gets exported.

Everything is editable interactively too: drag shapes, drag-create from a
palette, connect two shapes with a click-click tool, edit labels/colors/
metadata, undo/redo, switch between diagrams in a multi-diagram workbook,
paste CSV, generate from a template or an indented outline, and apply live
style rules.

```
webapp/
  backend/    FastAPI app + the diagen engine (webapp/backend/diagen/) + bundled samples
  frontend/   Vite + React + TypeScript UI
```

## Quick start

**Backend**
```bash
cd webapp/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend** (separate terminal)
```bash
cd webapp/frontend
npm install
npm run dev
```
Open the URL Vite prints (usually `http://localhost:5173`).

See `webapp/README.md` for the full run/build guide and API reference, and
`webapp/backend/README.md` for the engine's data format and architecture.
