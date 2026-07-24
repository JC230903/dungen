"""Tests for render_svg.py: valid SVG output, labels present, edges drawn."""
from __future__ import annotations
import xml.etree.ElementTree as ET
from diagen.layout import layout
from diagen.render_svg import SvgRenderer


def _render(spec, diagram_id):
    d = spec.diagrams[diagram_id]
    w, h = layout(d, spec)
    return SvgRenderer(spec).render(d, w, h), d


def test_render_produces_well_formed_xml(spec):
    svg, _ = _render(spec, 'D2')
    root = ET.fromstring(svg)  # raises if not well-formed
    assert root.tag.endswith('svg')


def test_render_includes_every_node_label(spec):
    svg, d = _render(spec, 'D2')
    for n in d.nodes.values():
        assert n.label in svg or all(part in svg for part in n.lines), \
            f'label for {n.id} missing from SVG output'


def test_render_escapes_special_characters(spec):
    d = spec.diagrams['D2']
    n = next(iter(d.nodes.values()))
    n.label = 'A & B <script>'
    n.lines = [n.label]
    svg = SvgRenderer(spec).render(d, 800, 600)
    assert '<script>' not in svg
    assert '&amp;' in svg


def test_render_draws_a_path_per_edge(spec):
    svg, d = _render(spec, 'D2')
    assert svg.count('<path') >= len(d.edges)


def test_render_title_present(spec):
    svg, d = _render(spec, 'D2')
    assert d.title in svg


def test_render_erd_diagram_shows_row_lists(spec):
    """D5 is the ERD scenario - row-list shapes must render each attribute row."""
    if 'D5' not in spec.diagrams or not spec.diagrams['D5'].nodes:
        return  # sample data optional in some spec workbook variants
    svg, d = _render(spec, 'D5')
    row_nodes = [n for n in d.nodes.values() if spec.shape_of(n).auto == 'rows']
    assert row_nodes
    for n in row_nodes:
        for r in n.rows():
            assert r.split('(')[0].strip() in svg
