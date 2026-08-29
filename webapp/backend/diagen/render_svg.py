"""SVG renderer: shapes per Shape_Library, edges per Line_Rules."""
from __future__ import annotations
import zlib
import math
from xml.sax.saxutils import escape
from .model import Diagram, Node, Edge
from .spec import Spec
from . import sizing as SZ
from .routing import Router

FONT = "Arial, Helvetica, sans-serif"
TEXT = '#333333'
DASH = {'solid': None, 'dashed': '6,4', 'dotted': '2,3', 'dash-dot': '8,3,2,3'}

MARKERS = {
    'filled arrow':    ('<path d="M0,0 L10,4 L0,8 z" fill="{c}"/>', 10, 4, 12, 10),
    'open arrow':      ('<path d="M1,1 L9,4.5 L1,8" fill="none" stroke="{c}" stroke-width="1.4"/>', 9, 4.5, 12, 10),
    'hollow triangle': ('<path d="M0,0 L12,5 L0,10 z" fill="white" stroke="{c}" stroke-width="1.2"/>', 12, 5, 14, 12),
    'filled diamond':  ('<path d="M0,4.5 L7,0 L14,4.5 L7,9 z" fill="{c}"/>', 14, 4.5, 16, 10),
    'open diamond':    ('<path d="M0,4.5 L7,0 L14,4.5 L7,9 z" fill="white" stroke="{c}" stroke-width="1.2"/>', 14, 4.5, 16, 10),
    'filled ball':     ('<circle cx="5" cy="5" r="4" fill="{c}"/>', 9, 5, 12, 10),
    'open circle':     ('<circle cx="5" cy="5" r="4" fill="white" stroke="{c}" stroke-width="1.2"/>', 9, 5, 12, 10),
    "crow's foot (N)": ('<path d="M0,5 L12,0 M0,5 L12,5 M0,5 L12,10" fill="none" stroke="{c}" stroke-width="1.2"/>', 12, 5, 14, 12),
    "crow's foot":     ('<path d="M0,5 L12,0 M0,5 L12,5 M0,5 L12,10" fill="none" stroke="{c}" stroke-width="1.2"/>', 12, 5, 14, 12),
    'single tick':     ('<path d="M6,0 L6,10" fill="none" stroke="{c}" stroke-width="1.4"/>', 10, 5, 12, 12),
    'single tick (1)': ('<path d="M6,0 L6,10" fill="none" stroke="{c}" stroke-width="1.4"/>', 10, 5, 12, 12),
}


def _mid(pts):
    seg = len(pts) // 2
    (x1, y1), (x2, y2) = pts[seg - 1], pts[seg]
    return (x1 + x2) / 2, (y1 + y2) / 2


def _stable_hash(*parts) -> int:
    """Process-independent hash.

    Python randomises str/tuple hashing per process, so anything derived from
    the built-in hash() changed on every backend restart — the same workbook
    rendered with different edge offsets and different marker ids each time.
    """
    return zlib.crc32('\x1f'.join(str(p) for p in parts).encode('utf-8'))


# Separation between two parallel horizontal edge runs, and the clearance an
# edge keeps from a node box it passes.
LANE_GAP = 9.0
LANE_CLEAR = 5.0


class SvgRenderer:
    def __init__(self, spec: Spec):
        self.spec = spec
        self.defs = {}
        self._obst = None
        self._lanes_used = []
        self._router = None

    # ---------- markers ----------
    def _marker(self, end: str, color: str) -> str:
        key = None
        for k in MARKERS:
            if k in end.lower() or end.lower() in k:
                key = k
                break
        if key is None:
            return ''
        mid = f"m{_stable_hash(key, color) % 10**8}"
        if mid not in self.defs:
            body, refx, refy, mw, mh = MARKERS[key]
            self.defs[mid] = (
                f'<marker id="{mid}" viewBox="0 0 {mw} {mh}" markerWidth="{mw}" markerHeight="{mh}" '
                f'refX="{refx}" refY="{refy}" orient="auto-start-reverse" '
                f'markerUnits="userSpaceOnUse">{body.format(c=color)}</marker>')
        return mid

    # ---------- text ----------
    def _text(self, x, y, lines, size=12, weight='normal', anchor='middle', color=TEXT):
        out = []
        total = len(lines)
        y0 = y - (total - 1) * SZ.LINE_H / 2
        for i, ln in enumerate(lines):
            out.append(f'<text x="{x:.0f}" y="{y0 + i*SZ.LINE_H:.1f}" font-family="{FONT}" '
                       f'font-size="{size}" font-weight="{weight}" fill="{color}" '
                       f'text-anchor="{anchor}" dominant-baseline="middle">{escape(ln)}</text>')
        return ''.join(out)

    # ---------- shapes ----------
    def _node_svg(self, n: Node) -> str:
        s = self.spec.shape_of(n)
        fill = n.fill_override or s.fill
        st = n.stroke_override or s.stroke
        x, y, w, h = n.x, n.y, n.w, n.h
        shape = s.shape.lower()
        label = self._text(n.cx, n.cy, n.lines)
        A = f'stroke="{st}" stroke-width="1.2"'

        if s.is_container:
            dash = ' stroke-dasharray="6,4"' if 'dashed' in shape else ''
            return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill}" {A}{dash}/>'
                    + self._text(x + 10, y + 15, [n.label], 13, 'bold', 'start', '#555555'))
        if s.auto == 'rows':
            rows = n.rows()
            out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="white" {A}/>',
                   f'<rect x="{x}" y="{y}" width="{w}" height="{SZ.TITLE_H}" fill="{fill if fill != "#FFFFFF" else "#E8E8E8"}" {A}/>',
                   self._text(n.cx, y + SZ.TITLE_H / 2, [n.label], 12, 'bold')]
            has_ports = 'ports=' in (n.meta or '')
            for i, r in enumerate(rows):
                ry = y + SZ.TITLE_H + i * SZ.ROW_H
                if i:
                    out.append(f'<line x1="{x}" y1="{ry}" x2="{x+w}" y2="{ry}" stroke="#DDDDDD"/>')
                bold = 'bold' if '(PK)' in r else 'normal'
                out.append(self._text(x + 10, ry + SZ.ROW_H / 2, [r], 11, bold, 'start'))
                if has_ports:
                    py = ry + SZ.ROW_H / 2
                    out.append(f'<circle cx="{x}" cy="{py}" r="2.6" fill="{st}"/>')
                    out.append(f'<circle cx="{x+w}" cy="{py}" r="2.6" fill="{st}"/>')
            return ''.join(out)
        if 'person_card' in n.type:
            name, _, title = n.label.partition(' — ')
            return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" {A}/>'
                    f'<circle cx="{x+22}" cy="{n.cy}" r="14" fill="#E8EEF9" stroke="{st}"/>'
                    f'<circle cx="{x+22}" cy="{n.cy-4}" r="5" fill="{st}"/>'
                    f'<path d="M{x+13},{n.cy+9} a9,7 0 0 1 18,0" fill="{st}"/>'
                    + self._text(x + 44, n.cy - 8, [name], 12, 'bold', 'start')
                    + self._text(x + 44, n.cy + 9, [title or ''], 10.5, 'normal', 'start', '#666666'))
        if 'stadium' in shape or 'pill' in shape:
            return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="{fill}" {A}/>' + label
        if 'diamond' in shape:
            pts = f'{n.cx},{y} {x+w},{n.cy} {n.cx},{y+h} {x},{n.cy}'
            return f'<polygon points="{pts}" fill="{fill}" {A}/>' + label
        if 'parallelogram' in shape:
            k = 14
            pts = f'{x+k},{y} {x+w},{y} {x+w-k},{y+h} {x},{y+h}'
            return f'<polygon points="{pts}" fill="{fill}" {A}/>' + label
        if 'hexagon' in shape:
            k = min(22, w * 0.16)
            pts = f'{x+k},{y} {x+w-k},{y} {x+w},{n.cy} {x+w-k},{y+h} {x+k},{y+h} {x},{n.cy}'
            return f'<polygon points="{pts}" fill="{fill}" {A}/>' + label
        if 'cylinder' in shape:
            ry = 9
            return (f'<path d="M{x},{y+ry} a{w/2},{ry} 0 0 1 {w},0 v{h-2*ry} a{w/2},{ry} 0 0 1 -{w},0 z" fill="{fill}" {A}/>'
                    f'<path d="M{x},{y+ry} a{w/2},{ry} 0 0 0 {w},0" fill="none" {A}/>'
                    + self._text(n.cx, n.cy + ry / 2, n.lines))
        if 'cloud' in shape:
            return (f'<path d="M{x+w*.25},{y+h*.9} h{w*.55} a{w*.16},{h*.22} 0 0 0 {w*.13},-{h*.38} '
                    f'a{w*.15},{h*.25} 0 0 0 -{w*.15},-{h*.30} a{w*.18},{h*.28} 0 0 0 -{w*.34},-{h*.08} '
                    f'a{w*.16},{h*.25} 0 0 0 -{w*.27},{h*.12} a{w*.15},{h*.24} 0 0 0 {w*.08},{h*.64} z" '
                    f'fill="{fill}" {A}/>' + label)
        if '3d box' in shape:
            d = 10
            return (f'<rect x="{x}" y="{y+d}" width="{w-d}" height="{h-d}" fill="{fill}" {A}/>'
                    f'<polygon points="{x},{y+d} {x+d},{y} {x+w},{y} {x+w-d},{y+d}" fill="{fill}" {A}/>'
                    f'<polygon points="{x+w-d},{y+d} {x+w},{y} {x+w},{y+h-d} {x+w-d},{y+h}" fill="{fill}" {A}/>'
                    + self._text(n.cx - d / 2, n.cy + d / 2, n.lines))
        if 'chevron' in shape:
            k = 18
            pts = f'{x},{y} {x+w-k},{y} {x+w},{n.cy} {x+w-k},{y+h} {x},{y+h} {x+k},{n.cy}'
            return f'<polygon points="{pts}" fill="{fill}" {A}/>' + label
        if 'wavy bottom' in shape:
            return (f'<path d="M{x},{y} h{w} v{h*.75} c{-w*.25},{h*.35} {-w*.5},{-h*.2} {-w},{h*.1} z" '
                    f'fill="{fill}" {A}/>' + self._text(n.cx, n.cy - 4, n.lines))
        if 'circle' in shape:
            r = min(w, h) / 2
            return f'<circle cx="{n.cx}" cy="{n.cy}" r="{r}" fill="{fill}" {A}/>' + label
        if 'title band' in shape:
            return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" {A}/>'
                    f'<line x1="{x}" y1="{y+16}" x2="{x+w}" y2="{y+16}" {A}/>'
                    + self._text(n.cx, n.cy + 8, n.lines))
        rx = 8 if 'rounded' in shape else 0
        icon = ''
        if n.type == 'firewall':
            icon = (f'<g stroke="{st}" stroke-width="0.8">'
                    + ''.join(f'<line x1="{x+6}" y1="{y+8+i*7}" x2="{x+w-6}" y2="{y+8+i*7}"/>' for i in range(2))
                    + '</g>')
        if 'icon=gears' in (n.meta or ''):
            # small settings/cog glyphs under the label, e.g. an "(API)"
            # service box — purely decorative, driven by node metadata so any
            # box shape can opt in without a dedicated entity_type. Needs the
            # box tall enough (h_override) to clear the label text above it.
            gy = y + h - 15
            icon += self._gear(n.cx - 20, gy, 7) + self._gear(n.cx + 20, gy, 7)
        if 'icon=predefined' in (n.meta or ''):
            # "predefined process / subroutine" flowchart shape — a plain
            # rectangle with a second vertical rule inset from each side.
            inset = min(12, w * 0.12)
            icon += (f'<g stroke="{st}" stroke-width="1">'
                     f'<line x1="{x+inset}" y1="{y}" x2="{x+inset}" y2="{y+h}"/>'
                     f'<line x1="{x+w-inset}" y1="{y}" x2="{x+w-inset}" y2="{y+h}"/>'
                     f'</g>')
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" {A}/>' + icon + label

    def _gear(self, cx, cy, r=8, color='#2AA7A0'):
        teeth = 8
        pts = []
        for i in range(teeth * 2):
            ang = math.pi * i / teeth
            rad = r if i % 2 == 0 else r * 0.62
            pts.append(f'{cx + rad * math.cos(ang):.1f},{cy + rad * math.sin(ang):.1f}')
        return (f'<polygon points="{" ".join(pts)}" fill="{color}"/>'
                f'<circle cx="{cx}" cy="{cy}" r="{r*0.38:.1f}" fill="white"/>')

    # ---------- edges ----------
    def _blocked(self, d, x1, x2, y, exclude=()):
        """Nodes crossed by horizontal segment y between x1..x2 -> max bottom."""
        lo, hi = min(x1, x2), max(x1, x2)
        bot = None
        for n in d.nodes.values():
            if n.id in exclude or n.children or self.spec.shape_of(n).is_container:
                continue
            if n.x + 2 > hi or n.x + n.w - 2 < lo:
                continue
            if n.y < y < n.y + n.h:
                bot = max(bot or 0, n.y + n.h)
        return bot

    def _port_pt(self, n: Node, port: str, other: Node):
        rows = n.rows()
        if port and port in rows:
            y = n.y + SZ.TITLE_H + rows.index(port) * SZ.ROW_H + SZ.ROW_H / 2
        else:
            y = n.cy
        right = other.cx >= n.cx
        return (n.x + n.w if right else n.x, y)

    def _obstacles(self, d):
        """Leaf boxes edges must not be drawn through (cached per render)."""
        if self._obst is None:
            self._obst = [(n.x, n.y, n.x + n.w, n.y + n.h) for n in d.nodes.values()
                          if not n.children and not self.spec.shape_of(n).is_container]
        return self._obst

    def _route_around(self, pts, s, t, e):
        """Re-route an edge through the corridors between boxes.

        Only kicks in when the simple route actually misbehaves — cutting
        through a box, or retracing a corridor another edge already uses. A
        clean short route is left exactly as it was, so small diagrams keep
        their existing (already good) appearance.
        """
        r = self._router
        # An explicit route: hint is the author overriding us on purpose. Ports
        # are *not* an override — they pin which side of a box the line leaves
        # from, and the path between those points still has to dodge obstacles.
        if r is None or 'route:' in (e.hint or ''):
            return None
        if not self._path_is_bad(pts, s, t):
            r.commit(pts)
            return None
        routed = r.route(pts[0], pts[-1])
        if not routed or len(routed) > 8:
            r.commit(pts)
            return None
        r.commit(routed)
        return routed

    def _path_is_bad(self, pts, s, t):
        """True if this route crosses a box it shouldn't, or doubles up."""
        r = self._router
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            if abs(ay - by) < 1.0:
                if r._blocked_h(ay, ax, bx) or r._congestion('h', ay, ax, bx):
                    return True
            elif abs(ax - bx) < 1.0:
                if r._blocked_v(ax, ay, by) or r._congestion('v', ax, ay, by):
                    return True
        return False

    def _free_bands(self, d, x1, x2, lo, hi):
        """Sub-intervals of [lo, hi] where a run from x1..x2 crosses no box.

        In a ranked layout the gaps between rows are exactly these bands, so
        this is what steers a long horizontal run into the gutter between ranks
        instead of straight across the boxes sitting in them.
        """
        lo_x, hi_x = (x1, x2) if x1 <= x2 else (x2, x1)
        blocked = []
        for bx1, by1, bx2, by2 in self._obstacles(d):
            if bx2 - 2 <= lo_x or bx1 + 2 >= hi_x:
                continue
            blocked.append((by1 - LANE_CLEAR, by2 + LANE_CLEAR))
        blocked.sort()
        free, cur = [], lo
        for a, b in blocked:
            if b <= lo or a >= hi:
                continue
            a, b = max(a, lo), min(b, hi)
            if a > cur:
                free.append((cur, a))
            cur = max(cur, b)
        if cur < hi:
            free.append((cur, hi))
        return free

    def _lane_conflict(self, x1, x2, y):
        """Does a run at `y` sit on top of one already committed to?"""
        lo, hi = (x1, x2) if x1 <= x2 else (x2, x1)
        for (olo, ohi, oy) in self._lanes_used:
            if abs(oy - y) < LANE_GAP and not (ohi - 1 <= lo or olo + 1 >= hi):
                return True
        return False

    def _plan_jog(self, d, eid, p1, p2, ideal_y):
        """Choose the y for an edge's horizontal jog.

        Previously every jog sat at a fixed fraction of the gap it crossed, so
        edges spanning the same band were drawn on top of one another and cut
        straight through any box in between. Now the run is placed in a band
        that is actually free of boxes — preferring the one nearest its ideal
        position — and then nudged within that band to avoid runs already
        placed, so parallel connections read as separate lines.
        """
        lo_y, hi_y = sorted((p1[1], p2[1]))
        if hi_y - lo_y < 2:
            return ideal_y
        lo_b, hi_b = lo_y + 3, hi_y - 3
        if hi_b <= lo_b:
            return ideal_y

        bands = self._free_bands(d, p1[0], p2[0], lo_b, hi_b)
        if not bands:
            return ideal_y
        # nearest band to the ideal y (0 distance if the ideal already sits in one)
        def dist(band):
            a, b = band
            return 0.0 if a <= ideal_y <= b else min(abs(ideal_y - a), abs(ideal_y - b))
        bands.sort(key=dist)

        for a, b in bands:
            if b - a < 2:
                continue
            base = min(max(ideal_y, a + 1), b - 1)
            step = LANE_GAP
            k = 0
            while step * k <= (b - a):
                for cand in ((base + step * k), (base - step * k)) if k else (base,):
                    if a + 1 <= cand <= b - 1 and not self._lane_conflict(p1[0], p2[0], cand):
                        self._lanes_used.append((min(p1[0], p2[0]), max(p1[0], p2[0]), cand))
                        return cand
                k += 1
            # band is full — still better inside it than through a box
            self._lanes_used.append((min(p1[0], p2[0]), max(p1[0], p2[0]), base))
            return base
        return ideal_y

    def _anchor_pts(self, s: Node, t: Node, hint: str, d=None, sp='', tp='', fan=None, twin=None,
                    eid='', plan=True):
        if sp or tp:
            p1 = self._port_pt(s, sp, t)
            p2 = self._port_pt(t, tp, s)
            if abs(p1[1] - p2[1]) < 1:
                return [p1, p2]
            off = (_stable_hash(sp, tp, s.id, t.id) % 7 - 3) * 8
            mx = (p1[0] + p2[0]) / 2 + off
            return [p1, (mx, p1[1]), (mx, p2[1]), p2]
        if 'route:right' in hint:
            xr = max(s.x + s.w, t.x + t.w) + 50
            return [(s.x + s.w, s.cy), (xr, s.cy), (xr, t.cy), (t.x + t.w, t.cy)]
        dx, dy = t.cx - s.cx, t.cy - s.cy
        if abs(dy) >= 10:  # different rows -> vertical routing (flow reads top-down)
            if dy > 0:
                p1, p2 = (s.cx, s.y + s.h), (t.cx, t.y)
            else:
                p1, p2 = (s.cx, s.y), (t.cx, t.y + t.h)
            if abs(p1[0] - p2[0]) < 1:
                return [p1, p2]
            if fan and fan[1] > 1:
                # SZ-12b: hub/bus fan-out — spread the horizontal jog across a band
                # instead of stacking every sibling edge at the exact same midpoint,
                # so parallel risers (and their labels) stay visually distinct.
                idx, n = fan
                if n <= 6:
                    frac = 0.24 + 0.52 * (idx / (n - 1))
                else:
                    # SZ-13: large hub (>6 siblings, e.g. a bus box) — proportional
                    # spread packs everything into a near-identical height (tiny
                    # frac deltas), which forces the label-collision search to
                    # cascade labels far away from their own line. Use a small,
                    # fixed number of height "shelves" instead so vertical
                    # separation stays large and bounded regardless of n.
                    k = min(5, max(3, (n + 2) // 3))
                    shelf = idx % k
                    frac = 0.12 + 0.76 * (shelf / (k - 1))
                # also spread the exit point across the hub's own width — otherwise
                # every riser leaves from the exact same center point and only
                # diverges after the jog, stacking near the source.
                p1 = (s.x + (idx + 1) * s.w / (n + 1), p1[1])
            else:
                frac = 0.5
            if twin and twin[1] > 1:
                # multiple edges converging on the same target: spread the arrival
                # point across its width instead of every arrow piling into its
                # exact center.
                tidx, tn = twin
                p2 = (t.x + (tidx + 1) * t.w / (tn + 1), p2[1])
            my = p1[1] + frac * (p2[1] - p1[1])
            if d and plan:
                # Global lane assignment: keep this jog clear of node boxes *and*
                # of every jog already placed, instead of the old single-obstacle
                # nudge that still let parallel runs stack on one line.
                my = self._plan_jog(d, eid, p1, p2, my)
            return [p1, (p1[0], my), (p2[0], my), p2]
        else:  # horizontal
            if dx > 0:
                p1, p2 = (s.x + s.w, s.cy), (t.x, t.cy)
            else:
                p1, p2 = (s.x, s.cy), (t.x + t.w, t.cy)
            if abs(p1[1] - p2[1]) < 12:
                bot = d and self._blocked(d, p1[0], p2[0], p1[1])
                if bot:  # detour under the obstructing node(s)
                    yd = bot + 10
                    return [(s.cx, s.y + s.h), (s.cx, yd), (t.cx, yd), (t.cx, t.y + t.h)]
                return [p1, p2]
            mx = (p1[0] + p2[0]) / 2
            return [p1, (mx, p1[1]), (mx, p2[1]), p2]

    def _edge_svg(self, e: Edge, d: Diagram, par_idx=0, par_n=1, fan=None) -> str:
        l = self.spec.line_of(e)
        s, t = d.nodes[e.source], d.nodes[e.target]
        if 'route:arc-top' in e.hint:
            return self._edge_svg_arc(e, l, s, t)
        twin = (par_idx, par_n) if par_n > 1 else None
        pts = self._anchor_pts(s, t, e.hint, d, e.sport, e.tport, fan=fan, twin=twin, eid=e.id)
        # SZ-12 old parallel offset: only needed when the newer fan/twin spread
        # above didn't already separate these edges (e.g. non-hub same-pair
        # edges elsewhere in the diagram); skip it here to avoid double-shifting.
        if par_n > 1 and not (e.sport or e.tport) and not fan:
            off = SZ.PAR_OFF * (par_idx - (par_n - 1) / 2) * 2
            vertical = abs(pts[0][0] - pts[-1][0]) < abs(pts[0][1] - pts[-1][1])
            pts = [(px + off, py) if vertical else (px, py + off) for px, py in pts]
        if l.routing == 'straight' and 'route:' not in e.hint:
            pts = [pts[0], pts[-1]]
        else:
            # Obstacle-avoiding pass runs last, on the final geometry — an
            # earlier pass would have its work undone by the offset above.
            routed = self._route_around(pts, s, t, e)
            if routed:
                pts = routed
        path = 'M' + ' L'.join(f'{px:.0f},{py:.0f}' for px, py in pts)
        dash = DASH.get(l.style)
        attrs = f'stroke="{l.color}" stroke-width="{l.width}" fill="none"'
        if dash:
            attrs += f' stroke-dasharray="{dash}"'
        ms = self._marker(l.source_end, l.color)
        mt = self._marker(l.target_end, l.color)
        if ms:
            attrs += f' marker-start="url(#{ms})"'
        if mt:
            attrs += f' marker-end="url(#{mt})"'
        out = [f'<path d="{path}" {attrs}/>']
        if e.label:
            if 'near source' in l.label_pos:
                lx, ly = pts[0][0] + 18, pts[0][1] + 14
            else:
                lx, ly = _mid(pts)
            wpx = len(e.label) * 6 + 8
            lx, ly = self._place_label(lx, ly, wpx)
            out.append(f'<rect x="{lx - wpx/2:.0f}" y="{ly - 9:.0f}" width="{wpx}" height="16" '
                       f'fill="white" fill-opacity="0.9" rx="3"/>')
            out.append(self._text(lx, ly, [e.label], 10.5, 'normal', 'middle', '#555555'))
        return ''.join(out)

    def _edge_svg_arc(self, e: Edge, l, s: Node, t: Node) -> str:
        """Smooth arc over the top of both boxes. Reserved for waypoint_hint
        'route:arc-top' — used for a feedback/"return request" edge running
        opposite the main flow (e.g. a downstream stage calling back to an
        upstream one), so it reads as a distinct loop rather than tangling
        through the ordinary forward-flow lines underneath the same row."""
        p1 = (s.cx, s.y)
        p2 = (t.cx, t.y)
        arc_h = max(36, abs(p1[0] - p2[0]) * 0.16)
        top = min(p1[1], p2[1]) - arc_h
        cx = (p1[0] + p2[0]) / 2
        path = f'M{p1[0]:.0f},{p1[1]:.0f} Q{cx:.0f},{top:.0f} {p2[0]:.0f},{p2[1]:.0f}'
        dash = DASH.get(l.style)
        attrs = f'stroke="{l.color}" stroke-width="{l.width}" fill="none"'
        if dash:
            attrs += f' stroke-dasharray="{dash}"'
        ms = self._marker(l.source_end, l.color)
        mt = self._marker(l.target_end, l.color)
        if ms:
            attrs += f' marker-start="url(#{ms})"'
        if mt:
            attrs += f' marker-end="url(#{mt})"'
        out = [f'<path d="{path}" {attrs}/>']
        if e.label:
            lx, ly = cx, top + 13
            wpx = len(e.label) * 6 + 8
            lx, ly = self._place_label(lx, ly, wpx)
            out.append(f'<rect x="{lx - wpx/2:.0f}" y="{ly - 9:.0f}" width="{wpx}" height="16" '
                       f'fill="white" fill-opacity="0.9" rx="3"/>')
            out.append(self._text(lx, ly, [e.label], 10.5, 'normal', 'middle', '#555555'))
        return ''.join(out)

    # ---------- label collision avoidance ----------
    def _place_label(self, lx, ly, wpx, h=16, pad=3):
        """Search a small 2-D grid of nudges (closest first, both axes) until the
        label clears previously placed labels AND node boxes. Searching sideways
        as well as up/down finds free room in tight spots without needing a big
        vertical excursion — which is what let labels drift far from their own
        line in dense hub/bus areas. The search radius is capped either way so a
        label can never end up looking disconnected from the line it belongs to."""
        def overlaps(a, b):
            return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]

        def box_at(cx, cy):
            return [cx - wpx / 2 - pad, cy - h / 2 - pad, cx + wpx / 2 + pad, cy + h / 2 + pad]
        step_y = h + 2
        step_x = max(wpx * 0.55, 40)
        offsets = sorted(
            {(dxm, dym) for dym in range(-4, 5) for dxm in range(-3, 4)},
            key=lambda o: (o[0] * step_x) ** 2 + (o[1] * step_y) ** 2)
        best = None
        for dxm, dym in offsets:
            cx, cy = lx + dxm * step_x, ly + dym * step_y
            box = box_at(cx, cy)
            if not any(overlaps(box, r) for r in self.label_rects):
                best = (cx, cy, box)
                break
        if best is None:  # nothing clear found in the search grid; fall back as-is
            best = (lx, ly, box_at(lx, ly))
        lx, ly, box = best
        self.label_rects.append(box)
        return lx, ly

    # ---------- diagram ----------
    def render(self, d: Diagram, canvas_w: float, canvas_h: float) -> str:
        self.defs = {}
        # Route planning state is per-render: obstacle boxes for this diagram,
        # and the running list of horizontal runs already committed to.
        self._obst = None
        self._lanes_used = []
        self._router = None
        # Seed with every leaf node's box (shrunk slightly) so edge labels steer
        # clear of boxes too, not just other labels. Containers are excluded —
        # they're just background panels, labels are expected to sit on them.
        self.label_rects = [[n.x + 4, n.y + 4, n.x + n.w - 4, n.y + n.h - 4]
                             for n in d.nodes.values() if not self.spec.shape_of(n).is_container]
        # also protect each container's own title text (top-left corner) so
        # edge labels don't get drawn right over "TAKSY" / "VPM A-D" etc.
        self.label_rects += [[n.x + 6, n.y + 4, n.x + 16 + len(n.label) * 7, n.y + 24]
                              for n in d.nodes.values() if self.spec.shape_of(n).is_container]
        containers, leaves = [], []

        def collect(n: Node, depth=0):
            (containers if self.spec.shape_of(n).is_container else leaves).append((depth, n))
            for c in n.children:
                collect(c, depth + 1)
        for n in d.top_level():
            collect(n)
        body = []
        for _, n in sorted(containers, key=lambda p: p[0]):
            body.append(f'<g data-node-id="{escape(n.id)}">' + self._node_svg(n) + '</g>')
        pairs = {}
        for e in d.edges:
            pairs.setdefault(frozenset((e.source, e.target)), []).append(e)
        # SZ-12b: group edges that fan out from the same hub node (e.g. a bus
        # lane feeding many different targets) so their risers can be spread
        # across a band instead of colliding on the same midpoint line.
        fan_groups = {}
        for e in d.edges:
            s, t = d.nodes.get(e.source), d.nodes.get(e.target)
            if s and t and abs(t.cy - s.cy) >= 10:
                fan_groups.setdefault(e.source, []).append(e)
        for grp in fan_groups.values():
            grp.sort(key=lambda e: d.nodes[e.target].cx)

        def fan_of(e):
            s, t = d.nodes.get(e.source), d.nodes.get(e.target)
            # only look this edge up in its source's fan group if it actually
            # qualifies for one itself (same abs(dy)>=10 test used to build the
            # group) — a same-source edge that lands in a *different* row band
            # (e.g. a near-horizontal feedback loop next to mostly-vertical
            # siblings) must not be searched for in a list it was never put in.
            if s and t and abs(t.cy - s.cy) >= 10:
                fgrp = fan_groups.get(e.source)
                if fgrp and len(fgrp) > 1:
                    return (fgrp.index(e), len(fgrp))
            return None

        # Dry pass: work out where every edge starts and ends so the router's
        # grid can include those points once, instead of being rebuilt (and
        # re-masked) for each edge in turn.
        router = Router(self._obstacles(d), canvas_w, canvas_h)
        terminals = []
        for e in d.edges:
            s, t = d.nodes.get(e.source), d.nodes.get(e.target)
            if not s or not t or 'route:arc-top' in e.hint:
                continue
            grp = pairs[frozenset((e.source, e.target))]
            twin = (grp.index(e), len(grp)) if len(grp) > 1 else None
            pts = self._anchor_pts(s, t, e.hint, d, e.sport, e.tport,
                                   fan=fan_of(e), twin=twin, eid=e.id, plan=False)
            terminals.append(pts[0])
            terminals.append(pts[-1])
        router.set_terminals(terminals)
        # A very dense diagram makes the channel grid too big to A* quickly;
        # there the simple routes stand on their own rather than stalling.
        self._router = router if router.usable() else None

        for e in d.edges:
            grp = pairs[frozenset((e.source, e.target))]
            fan = fan_of(e)
            body.append(f'<g data-edge-id="{escape(e.id)}" data-source="{escape(e.source)}" '
                        f'data-target="{escape(e.target)}">'
                        + self._edge_svg(e, d, grp.index(e), len(grp), fan=fan) + '</g>')
        for _, n in leaves:
            body.append(f'<g data-node-id="{escape(n.id)}">' + self._node_svg(n) + '</g>')
        title = (f'<text x="{SZ.MARGIN}" y="{SZ.MARGIN - 8}" font-family="{FONT}" font-size="16" '
                 f'font-weight="bold" fill="#222222">{escape(d.title)}</text>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w:.0f}" '
                f'height="{canvas_h:.0f}" viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}" '
                f'font-family="{FONT}">'
                f'<defs>{"".join(self.defs.values())}</defs>'
                f'<rect width="100%" height="100%" fill="white"/>'
                + title + ''.join(body) + '</svg>')
