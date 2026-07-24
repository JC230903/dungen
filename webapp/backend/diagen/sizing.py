"""Sizing engine — implements the SZ-* rules from the Sizing_Layout sheet."""
from __future__ import annotations
from .model import Node
from .spec import Spec

CHAR_W = 7.0        # SZ-01
LINE_H = 16.0       # SZ-01
PAD_X = 12.0        # SZ-04
PAD_Y = 10.0        # SZ-04
MAX_W = 260.0       # SZ-02
GRID = 10.0         # SZ-05
TITLE_H = 30.0      # SZ-07
ROW_H = 22.0        # SZ-07
PAD_C = 20.0        # SZ-08
HEADER_H = 28.0     # SZ-08
GAP_X = 40.0        # SZ-10
GAP_Y = 60.0        # SZ-11
GAP_X_IN = 24.0     # inside containers
GAP_Y_IN = 30.0
EDGE_CLEAR = 15.0   # SZ-12
PAR_OFF = 8.0       # SZ-12
TRUNC = 60          # SZ-13
MARGIN = 40.0       # SZ-14


def snap(v: float) -> float:
    return round(v / GRID) * GRID


def wrap(text: str, inner_w: float) -> list:
    """Greedy word wrap at inner width (SZ-03)."""
    per_line = max(4, int(inner_w // CHAR_W))
    words, lines, cur = text.split(), [], ''
    for w in words:
        cand = (cur + ' ' + w).strip()
        if len(cand) <= per_line or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def size_node(n: Node, spec: Spec) -> None:
    s = spec.shape_of(n)
    if len(n.label) > TRUNC:
        n.label = n.label[:TRUNC - 1] + '…'
    if s.auto == 'rows' or 'ports=' in (n.meta or ''):    # SZ-07
        rows = n.rows()
        widest = max([len(n.label)] + [len(r) for r in rows]) if rows else len(n.label)
        n.w = max(160.0, widest * CHAR_W + 40)
        n.h = TITLE_H + ROW_H * len(rows)
        n.lines = [n.label]
    elif s.is_container:
        n.w, n.h = s.default_w, s.default_h               # grown later (SZ-08)
        n.lines = [n.label]
    elif s.auto == 'N':
        n.w, n.h = s.default_w, s.default_h
        n.lines = wrap(n.label, n.w - 2 * PAD_X)
    else:                                                  # SZ-02 / SZ-03
        n.w = min(MAX_W, max(s.min_w, len(n.label) * CHAR_W + 2 * PAD_X))
        n.lines = wrap(n.label, n.w - 2 * PAD_X)
        n.h = max(s.min_h, len(n.lines) * LINE_H + 2 * PAD_Y)
        if s.shape == 'diamond':                           # SZ-06
            n.h = max(s.min_h, n.w / 1.75, len(n.lines) * LINE_H + 2 * PAD_Y + 14)
            n.w = max(n.w, n.h * 1.75)
    if n.w_override:
        n.w = n.w_override
    if n.h_override:
        n.h = n.h_override
    n.w, n.h = snap(n.w), max(n.h, GRID)
