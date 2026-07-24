"""diagen CLI.

Examples:
  python -m diagen spec.xlsx -o out
  python -m diagen spec.xlsx -o out --diagram D2 --format svg
  python -m diagen spec.xlsx --nodes my_nodes.csv --edges my_edges.csv -o out
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from .spec import Spec
from .layout import layout
from .render_svg import SvgRenderer
from .render_drawio import to_drawio

GALLERY = """<!doctype html><html><head><meta charset="utf-8"><title>diagen output</title>
<style>body{{font-family:Arial;margin:24px;background:#FAFAFA}}h1{{font-size:20px}}
.card{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:16px;margin:16px 0}}
img{{max-width:100%%}}</style></head><body><h1>Generated diagrams</h1>{cards}</body></html>"""


def main(argv=None):
    p = argparse.ArgumentParser(prog='diagen', description='Generate diagrams from CSV/Excel data.')
    p.add_argument('spec', help='Spec workbook (.xlsx) with rule sheets (+ optional sample data)')
    p.add_argument('-o', '--out', default='out', help='Output directory (default: out)')
    p.add_argument('--diagram', action='append', help='Only render these diagram_id(s)')
    p.add_argument('--format', choices=['svg', 'drawio', 'both'], default='both')
    p.add_argument('--nodes', help='External Nodes CSV (replaces workbook sample data)')
    p.add_argument('--edges', help='External Edges CSV')
    p.add_argument('--title', help='Title when using external CSVs')
    p.add_argument('--direction', choices=['TB', 'LR'], help='Layout direction: top-bottom (default) or left-right (wiring)')
    args = p.parse_args(argv)

    spec = Spec(args.spec)
    if args.nodes:
        spec.load_csv(args.nodes, args.edges, title=args.title)
    elif args.title:
        for d in spec.diagrams.values():
            d.title = args.title
    if args.direction:
        for d in spec.diagrams.values():
            d.direction = args.direction
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    renderer = SvgRenderer(spec)
    cards = []
    for did, d in spec.diagrams.items():
        if args.diagram and did not in args.diagram:
            continue
        if not d.nodes:
            continue
        try:
            w, h = layout(d, spec)
        except KeyError as e:
            print(f'[{did}] SKIPPED: {e}', file=sys.stderr)
            continue
        if args.format in ('svg', 'both'):
            (out / f'{did}.svg').write_text(renderer.render(d, w, h), encoding='utf-8')
        if args.format in ('drawio', 'both'):
            (out / f'{did}.drawio').write_text(to_drawio(d, spec), encoding='utf-8')
        cards.append(f'<div class="card"><h2>{did} — {d.title}</h2><img src="{did}.svg"></div>')
        print(f'[{did}] {d.title}: {len(d.nodes)} nodes, {len(d.edges)} edges -> {out}/{did}.svg')
    if cards and args.format != 'drawio':
        (out / 'index.html').write_text(GALLERY.format(cards=''.join(cards)), encoding='utf-8')
        print(f'Gallery: {out}/index.html')


if __name__ == '__main__':
    main()
