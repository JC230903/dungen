"""Unit tests for sizing.py (SZ-01..SZ-14 rules)."""
from __future__ import annotations
import pytest
from diagen import sizing as SZ
from diagen.model import Node, ShapeDef


def make_shape(**kw):
    defaults = dict(entity_type='t', family='F', shape='rectangle',
                     default_w=120, default_h=50, min_w=100, min_h=40,
                     fill='#FFFFFF', stroke='#333333', auto='Y')
    defaults.update(kw)
    return ShapeDef(**defaults)


def make_node(label='Hello World', **kw):
    defaults = dict(id='n1', diagram='D1', parent='', type='t', label=label)
    defaults.update(kw)
    return Node(**defaults)


class FakeSpec:
    def __init__(self, shape):
        self._shape = shape

    def shape_of(self, node):
        return self._shape


# ---------- snap ----------
# note: uses Python's round-half-to-even, so 5/15/25 snap down/up per banker's rounding
@pytest.mark.parametrize('v,expected', [(0, 0), (4, 0), (5, 0), (14, 10), (15, 20), (16, 20)])
def test_snap_rounds_to_grid(v, expected):
    assert SZ.snap(v) == expected


# ---------- wrap ----------
def test_wrap_short_text_single_line():
    assert SZ.wrap('Hi', 200) == ['Hi']


def test_wrap_splits_long_text_at_width():
    lines = SZ.wrap('one two three four five six seven eight', 60)
    assert len(lines) > 1
    per_line = max(4, int(60 // SZ.CHAR_W))
    assert all(len(l) <= per_line or ' ' not in l for l in lines)


def test_wrap_never_drops_words():
    text = 'alpha beta gamma delta epsilon'
    lines = SZ.wrap(text, 50)
    assert ' '.join(lines).split() == text.split()


def test_wrap_single_overlong_word_kept_whole():
    lines = SZ.wrap('supercalifragilisticexpialidocious', 40)
    assert lines == ['supercalifragilisticexpialidocious']


# ---------- size_node: auto == 'Y' (SZ-02/SZ-03) ----------
def test_size_node_grows_with_label_length():
    spec = FakeSpec(make_shape())
    short = make_node('Hi')
    long = make_node('A much longer label that needs more room')
    SZ.size_node(short, spec)
    SZ.size_node(long, spec)
    assert long.w >= short.w


def test_size_node_caps_at_max_w():
    spec = FakeSpec(make_shape())
    n = make_node('word ' * 60)
    SZ.size_node(n, spec)
    assert n.w <= SZ.MAX_W


def test_size_node_respects_min_w_min_h():
    spec = FakeSpec(make_shape(min_w=150, min_h=60))
    n = make_node('x')
    SZ.size_node(n, spec)
    assert n.w >= 150
    assert n.h >= 60


def test_size_node_truncates_very_long_label():
    spec = FakeSpec(make_shape())
    n = make_node('x' * 100)
    SZ.size_node(n, spec)
    assert len(n.label) == SZ.TRUNC
    assert n.label.endswith('...') or len(n.label) == SZ.TRUNC


def test_size_node_overrides_win():
    spec = FakeSpec(make_shape())
    n = make_node('Hi', w_override=330, h_override=222)
    SZ.size_node(n, spec)
    assert n.w == 330
    assert n.h == 222


def test_size_node_diamond_keeps_aspect():
    spec = FakeSpec(make_shape(shape='diamond'))
    n = make_node('Approved?')
    SZ.size_node(n, spec)
    assert n.w >= n.h
    assert abs(n.w - n.h * 1.75) < 1e-6 or n.w > n.h * 1.75 - 1


# ---------- size_node: auto == 'N' ----------
def test_size_node_fixed_size_ignores_label():
    spec = FakeSpec(make_shape(auto='N', default_w=200, default_h=80))
    short = make_node('x')
    long = make_node('a very long label indeed here')
    SZ.size_node(short, spec)
    SZ.size_node(long, spec)
    assert short.w == long.w == 200
    assert short.h == long.h == 80


# ---------- size_node: container (SZ-08, grown later by layout) ----------
def test_size_node_container_uses_default_dims():
    spec = FakeSpec(make_shape(auto='container', default_w=300, default_h=200))
    n = make_node('Layer')
    SZ.size_node(n, spec)
    assert n.w == 300
    assert n.h == 200


# ---------- size_node: row-list shapes (ERD / ports, SZ-07) ----------
def test_size_node_rows_grows_with_row_count():
    spec = FakeSpec(make_shape(auto='rows'))
    n = make_node('Orders', meta='rows=id(PK);customer_id;total')
    SZ.size_node(n, spec)
    assert n.h == SZ.TITLE_H + SZ.ROW_H * 3


def test_size_node_rows_empty_falls_back_to_title_only():
    spec = FakeSpec(make_shape(auto='rows'))
    n = make_node('Nothing', meta='rows=')
    SZ.size_node(n, spec)
    assert n.h == SZ.TITLE_H
