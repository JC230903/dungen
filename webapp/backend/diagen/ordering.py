"""Crossing-reduction for ranked layouts (the ordering phase of Sugiyama).

`layout.py` decides which rank (row in top-down, column in left-right) each node
belongs to. This module decides the order *within* each rank, which is what
actually determines how tangled the edges look.

The pipeline is the standard one:

  1. break cycles so ranking and sweeping terminate,
  2. seed each rank by the barycentre of already-placed neighbours,
  3. alternate down/up median sweeps, each followed by an adjacent-transpose
     pass, keeping whichever arrangement crossed least.

Everything here works on plain node-id strings so it stays independent of the
Node/Diagram model.
"""
from __future__ import annotations
from collections import defaultdict

# Sweeps are cheap on the graph sizes this engine sees (hundreds of nodes at
# most) and each one is monotonically checked, so a generous cap costs nothing
# and lets big diagrams keep improving.
MAX_SWEEPS = 8


def acyclic(ids, adj):
    """Copy of `adj` with DFS back-edges dropped.

    A cyclic graph has no valid ranking; without this a cycle's nodes never
    reach in-degree zero and all get dumped into the last rank together.
    Iterative rather than recursive so a long chain can't blow the stack.
    """
    WHITE, GREY, BLACK = 0, 1, 2
    color = defaultdict(int)
    out = defaultdict(set)
    # `ids` is a set, and set iteration order for strings varies between
    # processes. Which edges get cut as back-edges depends on where the DFS
    # starts, so an unsorted walk here would give the same workbook a different
    # layout on every reload.
    for root in sorted(ids):
        if color[root] != WHITE:
            continue
        stack = [(root, iter(sorted(adj.get(root, ()))))]
        color[root] = GREY
        while stack:
            u, it = stack[-1]
            for v in it:
                if v not in ids or v == u:
                    continue
                if color[v] == GREY:
                    continue          # back edge — drop, this is the cycle cut
                out[u].add(v)
                if color[v] == WHITE:
                    color[v] = GREY
                    stack.append((v, iter(sorted(adj.get(v, ())))))
                    break
            else:
                color[u] = BLACK
                stack.pop()
    return out


def count_crossings(order, adj):
    """Total edge crossings between every pair of adjacent ranks."""
    total = 0
    ranks = sorted(order)
    for r1, r2 in zip(ranks, ranks[1:]):
        pos2 = {nid: i for i, nid in enumerate(order[r2])}
        pairs = []
        for i, u in enumerate(order[r1]):
            for v in adj.get(u, ()):
                if v in pos2:
                    pairs.append((i, pos2[v]))
        for a in range(len(pairs)):
            ua, va = pairs[a]
            for b in range(a + 1, len(pairs)):
                ub, vb = pairs[b]
                if (ua - ub) * (va - vb) < 0:
                    total += 1
    return total


def _median_of(nid, ref_pos, nbrs):
    """Median neighbour position, or -1 when the node has none in that rank.

    -1 is the conventional marker for "no opinion": such nodes keep their
    current slot instead of all collapsing to position 0.
    """
    ps = sorted(ref_pos[v] for v in nbrs.get(nid, ()) if v in ref_pos)
    if not ps:
        return -1.0
    m = len(ps) // 2
    return float(ps[m]) if len(ps) % 2 else (ps[m - 1] + ps[m]) / 2.0


def _sort_by_median(rank_ids, medians):
    """Reorder by median, leaving no-opinion nodes (-1) at their current index."""
    fixed = [(i, nid) for i, nid in enumerate(rank_ids) if medians[nid] < 0]
    movable = sorted((nid for nid in rank_ids if medians[nid] >= 0), key=lambda n: medians[n])
    out = []
    it = iter(movable)
    fixed_at = dict(fixed)
    for i in range(len(rank_ids)):
        if i in fixed_at:
            out.append(fixed_at[i])
        else:
            out.append(next(it))
    return out


def _transpose(order, adj, rev):
    """Swap adjacent same-rank pairs while that reduces crossings."""
    ranks = sorted(order)
    improved = True
    guard = 0
    while improved and guard < 40:
        improved = False
        guard += 1
        for r in ranks:
            row = order[r]
            for i in range(len(row) - 1):
                before = _local_crossings(order, adj, rev, r)
                row[i], row[i + 1] = row[i + 1], row[i]
                after = _local_crossings(order, adj, rev, r)
                if after < before:
                    improved = True
                else:
                    row[i], row[i + 1] = row[i + 1], row[i]
    return order


def _local_crossings(order, adj, rev, r):
    """Crossings on just the rank boundaries touching rank r."""
    sub = {}
    for rr in (r - 1, r, r + 1):
        if rr in order:
            sub[rr] = order[rr]
    return count_crossings(sub, adj)


def order_ranks(byrank, adj, seed=None):
    """Return {rank: [node_id, ...]} ordered to minimise edge crossings.

    `byrank` maps rank -> iterable of node ids; `adj` maps node id -> successor
    ids. `seed` optionally gives a starting order (e.g. the author's
    order_hint) which is used as the initial arrangement.
    """
    order = {r: list(ids) for r, ids in byrank.items() if ids}
    if not order:
        return {}
    if seed:
        for r in order:
            order[r].sort(key=lambda n: seed.get(n, 0))

    rev = defaultdict(set)
    for u, vs in adj.items():
        for v in vs:
            rev[v].add(u)

    ranks = sorted(order)
    best = {r: list(v) for r, v in order.items()}
    best_score = count_crossings(order, adj)

    for sweep in range(MAX_SWEEPS):
        if best_score == 0:
            break
        down = sweep % 2 == 0
        seq = ranks[1:] if down else ranks[:-1][::-1]
        for r in seq:
            ref_rank = r - 1 if down else r + 1
            # Ranks need not be contiguous, so fall back to the actual
            # neighbouring rank rather than assuming r±1 exists.
            if ref_rank not in order:
                idx = ranks.index(r)
                nb = idx - 1 if down else idx + 1
                if nb < 0 or nb >= len(ranks):
                    continue
                ref_rank = ranks[nb]
            ref_pos = {nid: i for i, nid in enumerate(order[ref_rank])}
            nbrs = rev if down else adj
            medians = {nid: _median_of(nid, ref_pos, nbrs) for nid in order[r]}
            order[r] = _sort_by_median(order[r], medians)

        _transpose(order, adj, rev)
        score = count_crossings(order, adj)
        if score < best_score:
            best_score = score
            best = {r: list(v) for r, v in order.items()}
        else:
            # keep sweeping from the best-known arrangement rather than drifting
            order = {r: list(v) for r, v in best.items()}
    return best
