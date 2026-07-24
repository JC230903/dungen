"""Data model for diagen."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ShapeDef:
    entity_type: str
    family: str
    shape: str
    default_w: float
    default_h: float
    min_w: float
    min_h: float
    fill: str
    stroke: str
    auto: str  # 'Y' | 'N' | 'container' | 'rows'

    @property
    def is_container(self) -> bool:
        return self.auto == 'container'


@dataclass
class LineDef:
    relation_type: str
    family: str
    style: str        # solid | dashed | dotted | dash-dot
    width: float
    source_end: str
    target_end: str
    routing: str      # orthogonal | straight | curved
    label_pos: str
    color: str


@dataclass
class Node:
    id: str
    diagram: str
    parent: str
    type: str
    label: str
    rank: int = 0
    order: int = 0
    w_override: Optional[float] = None
    h_override: Optional[float] = None
    fill_override: str = ''
    stroke_override: str = ''
    meta: str = ''
    # computed
    w: float = 0.0
    h: float = 0.0
    x: float = 0.0
    y: float = 0.0
    lines: list = field(default_factory=list)
    children: list = field(default_factory=list)

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def meta_dict(self):
        out = {}
        for part in (self.meta or '').split(','):
            if '=' in part:
                k, v = part.split('=', 1)
                out[k.strip()] = v.strip()
        return out

    def rows(self):
        """Attribute rows for row-list shapes (ERD): meta 'rows=a;b;c'."""
        m = self.meta or ''
        for key in ('rows=', 'ports='):
            if key in m:
                return [r.strip() for r in m.split(key, 1)[1].split(';') if r.strip()]
        return []


@dataclass
class Edge:
    id: str
    diagram: str
    source: str
    target: str
    relation: str
    label: str = ''
    hint: str = ''
    sport: str = ''
    tport: str = ''


@dataclass
class Diagram:
    id: str
    scenario: str
    title: str
    direction: str = 'top-down'
    theme: str = ''
    nodes: dict = field(default_factory=dict)
    edges: list = field(default_factory=list)

    def top_level(self):
        return [n for n in self.nodes.values() if not n.parent]
