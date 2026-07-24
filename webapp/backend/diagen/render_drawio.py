"""draw.io / diagrams.net XML exporter — open generated files directly in the
tool the team already uses, fully editable."""
from __future__ import annotations
from xml.sax.saxutils import escape, quoteattr
from .model import Diagram
from .spec import Spec
from . import sizing as SZ

SHAPE_STYLE = {
    'stadium': 'rounded=1;arcSize=50;',
    'diamond': 'rhombus;',
    'parallelogram': 'shape=parallelogram;perimeter=parallelogramPerimeter;',
    'cylinder': 'shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=9;',
    'cloud': 'shape=cloud;',
    '3d box': 'shape=cube;boundedLbl=1;backgroundOutline=1;darkOpacity=0.05;',
    'chevron': 'shape=step;perimeter=stepPerimeter;',
    'wavy bottom': 'shape=document;boundedLbl=1;',
    'circle': 'ellipse;',
    'rounded': 'rounded=1;',
}
END = {
    'filled arrow': ('block', 1), 'open arrow': ('open', 0),
    'hollow triangle': ('block', 0), 'filled diamond': ('diamond', 1),
    'open diamond': ('diamond', 0), 'filled ball': ('oval', 1),
    'open circle': ('oval', 0), "crow's foot (N)": ('ERmany', 0),
    "crow's foot": ('ERmany', 0), 'single tick': ('ERone', 0),
    'single tick (1)': ('ERone', 0), 'none': ('none', 0),
}


def _end(name, prefix):
    for k, (arrow, fill) in END.items():
        if k in name.lower() or name.lower() in k:
            return f'{prefix}Arrow={arrow};{prefix}Fill={fill};'
    return f'{prefix}Arrow=none;'


def to_drawio(d: Diagram, spec: Spec) -> str:
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']

    def vertex(cid, label, style, x, y, w, h, parent='1'):
        cells.append(
            f'<mxCell id={quoteattr(cid)} value={quoteattr(label)} style={quoteattr(style)} '
            f'vertex="1" parent={quoteattr(parent)}>'
            f'<mxGeometry x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" as="geometry"/></mxCell>')

    def emit(n, depth=0):
        s = spec.shape_of(n)
        fill = n.fill_override or s.fill
        base = f'fillColor={fill};strokeColor={s.stroke};fontColor=#333333;whiteSpace=wrap;html=1;'
        if s.is_container:
            style = base + 'verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;'
            if 'dashed' in s.shape:
                style += 'dashed=1;'
        elif s.auto == 'rows':
            style = f'swimlane;startSize={SZ.TITLE_H:.0f};fontStyle=1;' + base
        else:
            style = base
            for key, st in SHAPE_STYLE.items():
                if key in s.shape.lower():
                    style = st + base
                    break
        vertex(n.id, n.label, style, n.x, n.y, n.w, n.h)
        if s.auto == 'rows':
            for i, r in enumerate(n.rows()):
                vertex(f'{n.id}_r{i}', r,
                       'text;html=1;align=left;spacingLeft=6;strokeColor=none;fillColor=none;',
                       0, SZ.TITLE_H + i * SZ.ROW_H, n.w, SZ.ROW_H, parent=n.id)
        for c in n.children:
            emit(c, depth + 1)

    for n in d.top_level():
        emit(n)
    for e in d.edges:
        l = spec.line_of(e)
        style = (f'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
                 f'strokeColor={l.color};strokeWidth={l.width:g};'
                 + _end(l.target_end, 'end') + _end(l.source_end, 'start'))
        if l.style == 'dashed':
            style += 'dashed=1;'
        elif l.style == 'dotted':
            style += 'dashed=1;dashPattern=1 3;'
        elif l.style == 'dash-dot':
            style += 'dashed=1;dashPattern=8 3 2 3;'
        cells.append(
            f'<mxCell id={quoteattr(e.id or e.source + "_" + e.target)} value={quoteattr(e.label)} '
            f'style={quoteattr(style)} edge="1" parent="1" source={quoteattr(e.source)} '
            f'target={quoteattr(e.target)}><mxGeometry relative="1" as="geometry"/></mxCell>')
    return (f'<mxfile><diagram name={quoteattr(d.title)}>'
            f'<mxGraphModel dx="800" dy="600" grid="1" gridSize="10" guides="1" tooltips="1" '
            f'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1169" '
            f'pageHeight="826" math="0" shadow="0"><root>{"".join(cells)}</root>'
            f'</mxGraphModel></diagram></mxfile>')
