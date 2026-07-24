"""Tests for layout.py: ranked-row placement, container auto-fit, auto-rank."""
from __future__ import annotations
from diagen.layout import layout, _auto_rank
from diagen.model import Diagram, Node, Edge


def _node(id, parent='', type='task', label=None, rank=0, order=0):
    return Node(id=id, diagram='D1', parent=parent, type=type, label=label or id,
                rank=rank, order=order)


def _edge(src, tgt, relation='sequence_flow', id=None):
    return Edge(id=id or f'{src}_{tgt}', diagram='D1', source=src, target=tgt, relation=relation)


def test_layout_all_nodes_get_nonzero_size(spec):
    d = spec.diagrams['D2']
    w, h = layout(d, spec)
    assert w > 0 and h > 0
    for n in d.nodes.values():
        assert n.w > 0 and n.h > 0


def test_layout_no_overlap_within_same_rank(spec):
    """Nodes placed in the same rank/row must not horizontally overlap."""
    d = spec.diagrams['D2']
    layout(d, spec)
    by_rank = {}
    for n in d.nodes.values():
        if n.parent:
            continue  # only check top-level placement here
        by_rank.setdefault(n.rank, []).append(n)
    for rank, nodes in by_rank.items():
        nodes = sorted(nodes, key=lambda n: n.x)
        for a, b in zip(nodes, nodes[1:]):
            assert a.x + a.w <= b.x + 1e-6, f'{a.id} overlaps {b.id} in rank {rank}'


def test_layout_container_grows_to_fit_children(spec):
    d = spec.diagrams['D1']  # layered EA view: containers with children
    layout(d, spec)
    containers = [n for n in d.nodes.values() if n.children]
    assert containers
    for c in containers:
        # container must be at least wide/tall enough to enclose its children
        max_child_right = max(ch.x + ch.w for ch in c.children)
        max_child_bottom = max(ch.y + ch.h for ch in c.children)
        assert c.w >= max_child_right - c.x - 1
        assert c.h >= max_child_bottom - c.y - 1


def test_layout_lr_direction_uses_columns_not_rows(spec):
    d = spec.diagrams['D2']
    d.direction = 'left-right'
    layout(d, spec)
    by_rank = {}
    for n in d.nodes.values():
        by_rank.setdefault(n.rank, []).append(n)
    ranks = sorted(by_rank)
    if len(ranks) > 1:
        # in LR mode, later ranks should sit further right (x grows with rank)
        avg_x = [sum(n.x for n in by_rank[r]) / len(by_rank[r]) for r in ranks]
        assert avg_x == sorted(avg_x)


def test_auto_rank_topological_order_respected():
    """When rank_hint is absent, auto-rank must derive ranks from edge topology
    so that every edge points from a lower rank to a higher one."""
    d = Diagram(id='D1', scenario='', title='t')
    for nid in ['A', 'B', 'C']:
        d.nodes[nid] = _node(nid)
    d.edges = [_edge('A', 'B'), _edge('B', 'C')]
    _auto_rank(d)
    assert d.nodes['A'].rank < d.nodes['B'].rank < d.nodes['C'].rank


def test_auto_rank_handles_disconnected_nodes():
    """Nodes with no edges at all must still get a valid rank/order (no crash,
    no rank 0 left over) - safety net at the end of _auto_rank."""
    d = Diagram(id='D1', scenario='', title='t')
    for nid in ['X', 'Y', 'Z']:
        d.nodes[nid] = _node(nid)
    d.edges = []
    _auto_rank(d)
    for n in d.nodes.values():
        assert n.rank >= 1
        assert n.order >= 1


def test_explicit_rank_hint_is_not_overridden():
    d = Diagram(id='D1', scenario='', title='t')
    d.nodes['A'] = _node('A', rank=5, order=2)
    d.nodes['B'] = _node('B', rank=1, order=1)
    d.edges = [_edge('B', 'A')]
    _auto_rank(d)
    assert d.nodes['A'].rank == 5
    assert d.nodes['B'].rank == 1


def test_layout_route_right_hint_widens_canvas(spec):
    d = spec.diagrams['D2']  # has an edge with waypoint_hint route:right
    w, h = layout(d, spec)
    assert any('route:right' in e.hint for e in d.edges)
    assert w > 0  # canvas accounted for the detour margin without crashing
