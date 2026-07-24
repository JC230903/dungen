# diagen engine (backend-internal)

The `diagen/` package in this directory generates finished diagrams (SVG +
editable draw.io XML) from plain tabular data — it's the engine `app/`
wraps as a web API. It's plain local source now (not a separately
pip-installed package): it lives here because the FastAPI app is its only
consumer.

Rules live in a spec workbook (`Shape_Library`/`Line_Rules` sheets, or the
~50-entity/~25-relation built-in default palette in `diagen/defaults.py`);
authors only provide **Nodes** and **Edges** rows.

## Data format (the part end users touch)
`Nodes`: diagram_id, node_id, parent_id, entity_type, label, rank_hint, order_hint,
w_override, h_override, fill_override, stroke_override, metadata
`Edges`: diagram_id, edge_id, source_id, target_id, relation_type, label, waypoint_hint

- `parent_id` nests nodes inside containers (layers, zones, departments) — containers
  auto-size to fit children (rule SZ-08).
- `rank_hint` = row/level, `order_hint` = position within the row. That is the entire
  layout contract (or skip both and let edge topology infer them).
- ERD entities list attributes in metadata: `rows=id(PK);name;email`.
- `waypoint_hint` `route:right` sends an edge around the right side (reject loops).

## Architecture
| Module | Responsibility |
|---|---|
| `spec.py` | Loads Shape_Library / Line_Rules / data sheets, CSVs, or in-memory rows |
| `defaults.py` | Built-in default shape/line palette |
| `sizing.py` | SZ-01..SZ-16 sizing rules: label-driven W×H, wrapping, row-list shapes |
| `layout.py` | Ranked-row placement, recursive container fit, layer-band stretching |
| `render_svg.py` | 15+ shape painters, orthogonal/straight routing, obstruction detours, parallel-edge offsets, arrowhead markers |
| `render_drawio.py` | Same model → mxGraph XML for diagrams.net |
| `interop.py` | Node/edge/connection dicts for the API layer |
| `templates.py` | Parameterized diagram generators + outline (mind-map) mode |
| `cli.py` / `__main__.py` | Standalone `python -m diagen` command line, still usable for scripting |

## CLI (optional, for scripting outside the web app)
```bash
cd webapp/backend
python -m diagen tests/fixtures/Diagram_Automation_CSV_Spec.xlsx -o out
python -m diagen spec.xlsx -o out --diagram D2 --format svg
python -m diagen spec.xlsx --nodes examples/nodes.csv --edges examples/edges.csv -o out
```
Outputs: `out/<id>.svg`, `out/<id>.drawio`, and `out/index.html` gallery.

## Extending
- New entity type → add one row to Shape_Library, or to `defaults.py` for a built-in.
- New relationship → one row in Line_Rules, or to `defaults.py`.
- New layout (e.g. force-directed) → one function in `layout.py`.

## Tests
```bash
cd webapp/backend
pip install -r requirements-dev.txt
pytest
```
`tests/conftest.py` uses the real fixture workbooks in `tests/fixtures/` and the
example CSVs in `examples/` instead of hand-rolled mocks.
