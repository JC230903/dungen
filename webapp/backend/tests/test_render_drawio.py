"""Tests for render_drawio.py: valid mxGraph XML, one cell per node/edge."""
from __future__ import annotations
import xml.etree.ElementTree as ET
from diagen.layout import layout
from diagen.render_drawio import to_drawio


def _render(spec, diagram_id):
    d = spec.diagrams[diagram_id]
    layout(d, spec)
    return to_drawio(d, spec), d


def test_drawio_produces_well_formed_xml(spec):
    xml_out, _ = _render(spec, 'D2')
    root = ET.fromstring(xml_out)  # raises if not well-formed
    assert root.tag == 'mxfile'


def test_drawio_has_a_cell_per_node(spec):
    xml_out, d = _render(spec, 'D2')
    for n in d.nodes.values():
        assert f'id="{n.id}"' in xml_out


def test_drawio_has_a_cell_per_edge(spec):
    xml_out, d = _render(spec, 'D2')
    edge_cells = xml_out.count('edge="1"')
    assert edge_cells == len(d.edges)


def test_drawio_escapes_labels(spec):
    d = spec.diagrams['D2']
    n = next(iter(d.nodes.values()))
    n.label = 'A & B "quoted"'
    xml_out = to_drawio(d, spec)
    ET.fromstring(xml_out)  # must still be well-formed with special chars


def test_drawio_diagram_title_present(spec):
    xml_out, d = _render(spec, 'D2')
    assert f'name="{d.title}"' in xml_out
