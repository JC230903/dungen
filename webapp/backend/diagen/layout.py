"""Layout engine — ranked rows + recursive container fit (SZ-08..SZ-11).

rank_hint / order_hint are OPTIONAL: when missing, ranks are derived from edge
topology (longest path); groups without internal edges fall back to a grid.
"""
from __future__ import annotations
import math
from collections import defaultdict, deque
from .model import Diagram, Node
from .spec import Spec
from . import sizing as SZ


def _auto_rank(d: Diagram) -> None:
    groups = defaultdict(list)
    for n in d.nodes.values():
        groups[n.parent].append(n)
    for parent, ns in groups.items():
        if all(n.rank > 0 for n in ns):
            continue
        ids = {n.id for n in ns}

        def lift(nid):
            n = d.nodes.get(nid)
            while n is not None and n.id not in ids:
                n = d.nodes.get(n.parent)
            return n.id if n is not None else None

        adj = defaultdict(set)
        indeg = {n.id: 0 for n in ns}
        internal = 0
        for e in d.edges:
            a, b = lift(e.source), lift(e.target)
            if e.relation == 'reports_to':
                a, b = b, a
            if a and b and a != b and b not in adj[a]:
                adj[a].add(b)
                indeg[b] += 1
                internal += 1
        rank = {}
        q = deque(i for i in indeg if indeg[i] == 0)
        for i in q:
            rank[i] = 1
        guard = 0
        while q and guard < 50000:
            guard += 1
            u = q.popleft()
            for v in adj[u]:
                rank[v] = max(rank.get(v, 1), rank[u] + 1)
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)
        maxr = max(rank.values(), default=1)
        if internal == 0 or (maxr == 1 and len(ns) > 4):
            cols = max(1, round(math.sqrt(len(ns) * 1.2)))
            for i, n in enumerate(ns):
                if n.rank == 0:
                    n.rank = i // cols + 1
                if n.order == 0:
                    n.order = i % cols + 1
            continue
        for n in ns:
            if n.rank == 0:
                n.rank = rank.get(n.id, maxr)
        # wrap over-wide ranks so wide groups stay near-square
        cap = max(4, round(math.sqrt(len(ns) * 1.2)))
        if len(ns) > 8:
            newrank = 0
            for r in sorted({n.rank for n in ns}):
                row = sorted([n for n in ns if n.rank == r], key=lambda n: n.order or 999)
                for i in range(0, len(row), cap):
                    newrank += 1
                    for j, n in enumerate(row[i:i + cap]):
                        n.rank = newrank
                        if n.order == 0:
                            n.order = j + 1
        # barycenter ordering to reduce crossings
        byrank = defaultdict(list)
        for n in ns:
            byrank[n.rank].append(n)
        pos = {}
        for r in sorted(byrank):
            row = byrank[r]

            def bary(n):
                p = [pos[a] for a in adj if n.id in adj[a] and a in pos]
                return sum(p) / len(p) if p else 1e9
            row.sort(key=lambda n: (n.order or 999, bary(n)))
            for i, n in enumerate(row):
                if n.order == 0:
                    n.order = i + 1
                pos[n.id] = n.order
    for n in d.nodes.values():          # safety net
        if n.rank == 0:
            n.rank = 1
        if n.order == 0:
            n.order = 1


def _rank_rows(nodes, gap_x, gap_y, lr=False):
    """Place nodes rank by rank. TB: ranks = rows. LR: ranks = columns."""
    if not nodes:  # empty diagram/container (e.g. a fresh blank canvas) — no rows to place
        return 0.0, 0.0
    ranks = sorted({n.rank for n in nodes})
    if lr:
        cols = []
        for r in ranks:
            col = sorted([n for n in nodes if n.rank == r], key=lambda n: n.order)
            ch = sum(n.h for n in col) + gap_y * (len(col) - 1)
            cw = max(n.w for n in col)
            cols.append((col, cw, ch))
        total_h = max(ch for _, _, ch in cols)
        x = 0.0
        for col, cw, ch in cols:
            y = (total_h - ch) / 2
            for n in col:
                n.x, n.y = SZ.snap(x + (cw - n.w) / 2), SZ.snap(y)
                y += n.h + gap_y
            x += cw + gap_x
        return x - gap_x, total_h
    rows = []
    for r in ranks:
        row = sorted([n for n in nodes if n.rank == r], key=lambda n: n.order)
        rw = sum(n.w for n in row) + gap_x * (len(row) - 1)
        rh = max(n.h for n in row)
        rows.append((row, rw, rh))
    total_w = max(rw for _, rw, _ in rows)
    y = 0.0
    for row, rw, rh in rows:
        x = (total_w - rw) / 2
        for n in row:
            n.x, n.y = SZ.snap(x), SZ.snap(y + (rh - n.h) / 2)
            x += n.w + gap_x
        y += rh + gap_y
    return total_w, y - gap_y


def _shift(n: Node, dx: float, dy: float):
    n.x += dx
    n.y += dy
    for c in n.children:
        _shift(c, dx, dy)


def _layout_container(n: Node, spec: Spec, lr=False):
    for c in n.children:
        _layout_container(c, spec, lr)
    if n.children:
        w, h = _rank_rows(n.children, SZ.GAP_X_IN, SZ.GAP_Y_IN, lr)
        # SZ-08: container wraps children
        n.w = max(n.w if spec.shape_of(n).is_container is False else 0,
                  w + 2 * SZ.PAD_C)
        n.h = h + SZ.PAD_C + SZ.HEADER_H
        for c in n.children:
            _shift(c, SZ.PAD_C, SZ.HEADER_H)
        n.w, n.h = SZ.snap(n.w), SZ.snap(n.h)


def layout(d: Diagram, spec: Spec):
    _auto_rank(d)
    lr = 'lr' in (d.direction or '').lower() or 'left' in (d.direction or '').lower()
    for n in d.nodes.values():
        SZ.size_node(n, spec)
    tops = d.top_level()
    for n in tops:
        _layout_container(n, spec, lr)
    # EA layer bands: if every top-level node is a container, unify widths
    if not lr and all(spec.shape_of(n).is_container for n in tops) and len(tops) > 1:
        target = max(n.w for n in tops)
        for n in tops:
            extra = target - n.w
            if extra > 0:
                n.w = target
                for c in n.children:
                    _shift(c, extra / 2, 0)
    _rank_rows(tops, SZ.GAP_X + (30 if lr else 0), SZ.GAP_Y, lr)
    # make positions absolute (children were local to parent).
    # NOTE: must shift only the immediate child here, NOT via the recursive
    # _shift() (which also walks grandchildren) — this function's own
    # recursion already visits each level exactly once. Using _shift's
    # recursive walk here double-counts every container nested 2+ levels
    # deep once that container isn't sitting at x=0/y=0 within its parent
    # (a 1-level-deep container, or one that happens to land at the origin,
    # never showed the bug — which is exactly how it stayed latent).
    def absolutize(n: Node):
        for c in n.children:
            c.x += n.x
            c.y += n.y
            absolutize(c)
    for n in tops:
        absolutize(n)
    # canvas (SZ-14)
    def walk(n):
        yield n
        for c in n.children:
            yield from walk(c)
    all_nodes = [x for t in tops for x in walk(t)]
    max_x = max((n.x + n.w for n in all_nodes), default=0.0)
    max_y = max((n.y + n.h for n in all_nodes), default=0.0)
    for t in tops:
        _shift(t, SZ.MARGIN, SZ.MARGIN + 34)  # room for title
    extra = 70 if any('route:right' in e.hint for e in d.edges) else 0
    return max_x + 2 * SZ.MARGIN + extra, max_y + 2 * SZ.MARGIN + 34
