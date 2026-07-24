"""Parameterized diagram generators — ported 1:1 from the JS playground's
`TEMPLATES` object and outline-to-tree (`buildOutline`) mind-map mode, so the
webapp can offer the same "Generate" panels without any of this logic living
twice. Each template returns row-dicts in the same shape `Spec.load_rows()`
already expects (node_id/parent_id/entity_type/label/rank_hint/order_hint/
fill_override/metadata and source_id/target_id/relation_type/label), so
building a template or applying an outline goes through the exact same
ingestion path as a pasted CSV — no separate code path to keep in sync.
"""
from __future__ import annotations
import re


def _split(csv_text: str) -> list[str]:
    return [x.strip() for x in (csv_text or '').split(',') if x.strip()]


def _node(id, entity_type, label, parent='', rank=0, order=0, fill='', meta=''):
    return {'node_id': id, 'parent_id': parent, 'entity_type': entity_type, 'label': label,
            'rank_hint': rank, 'order_hint': order, 'fill_override': fill, 'metadata': meta}


def _edge(id, source, target, relation, label=''):
    return {'edge_id': id, 'source_id': source, 'target_id': target,
            'relation_type': relation, 'label': label}


# ---------- templates ----------
def tpl_swimlane(v: dict) -> dict:
    lanes = _split(v.get('lanes', ''))
    n = max(1, min(6, int(v.get('steps') or 2)))
    nodes = [_node(f'LN{i+1}', 'lane', lane, rank=i + 1, order=1) for i, lane in enumerate(lanes)]
    edges = []
    prev = None
    k = 0
    for _s in range(n):
        for i, _lane in enumerate(lanes):
            k += 1
            nid = f'S{k}'
            nodes.append(_node(nid, 'start_end' if k == 1 else 'process',
                                'Start' if k == 1 else f'Step {k}', parent=f'LN{i+1}', rank=1, order=k))
            if prev:
                edges.append(_edge(f'te{k}', prev, nid, 'sequence_flow'))
            prev = nid
    return {'title': 'Cross-functional Process', 'nodes': nodes, 'edges': edges}


def tpl_layered_arch(v: dict) -> dict:
    apps = _split(v.get('apps', ''))
    nodes = [
        _node('LB', 'group', 'Business Layer', rank=1, order=1, fill='#FFFDE7'),
        _node('LA', 'group', 'Application Layer', rank=2, order=1, fill='#E8F4FB'),
        _node('LT', 'group', 'Technology Layer', rank=3, order=1, fill='#EDF7ED'),
        _node('K8', 'node', 'Container Platform', parent='LT', rank=1, order=1),
        _node('DBS', 'device', 'Database Server', parent='LT', rank=1, order=2),
    ]
    edges = []
    for i, a in enumerate(apps):
        nodes.append(_node(f'BP{i}', 'business_process', f'{a} Process', parent='LB', rank=1, order=i + 1))
        nodes.append(_node(f'AP{i}', 'application_component', a, parent='LA', rank=1, order=i + 1,
                            meta='lifecycle=active'))
        edges.append(_edge(f'ts{i}', f'AP{i}', f'BP{i}', 'serving'))
        edges.append(_edge(f'ta{i}', 'K8', f'AP{i}', 'assignment'))
    if apps:
        edges.append(_edge('tdb', 'DBS', 'AP0', 'assignment'))
    return {'title': 'Layered Application Architecture', 'nodes': nodes, 'edges': edges}


def tpl_microservices(v: dict) -> dict:
    svcs = _split(v.get('svcs', ''))
    nodes = [
        _node('ZE', 'zone', 'Edge', rank=1, order=1),
        _node('ZS', 'zone', 'Services', rank=2, order=1),
        _node('ZD', 'zone', 'Data', rank=3, order=1),
        _node('GW', 'application_component', 'API Gateway', parent='ZE', rank=1, order=1),
    ]
    edges = []
    for i, s in enumerate(svcs):
        nodes.append(_node(f'SV{i}', 'application_component', f'{s}-svc', parent='ZS', rank=1, order=i + 1))
        nodes.append(_node(f'DB{i}', 'database', f'{s} db', parent='ZD', rank=1, order=i + 1))
        edges.append(_edge(f'tg{i}', 'GW', f'SV{i}', 'data_flow'))
        edges.append(_edge(f'td{i}', f'SV{i}', f'DB{i}', 'access'))
    return {'title': 'Microservices Landscape', 'nodes': nodes, 'edges': edges}


def tpl_capability_map(v: dict) -> dict:
    caps = _split(v.get('caps', ''))
    k_per = max(1, min(6, int(v.get('kids') or 3)))
    nodes = []
    for i, c in enumerate(caps):
        nodes.append(_node(f'C{i}', 'group', c, rank=1, order=i + 1, fill='#FFFDE7'))
        for j in range(k_per):
            nodes.append(_node(f'C{i}_{j}', 'capability', f"{c.split(' ')[0]} L2.{j+1}",
                                parent=f'C{i}', rank=j // 2 + 1, order=j % 2 + 1))
    return {'title': 'Capability Map', 'nodes': nodes, 'edges': []}


def tpl_c4_context(v: dict) -> dict:
    sys_name = v.get('sys') or 'System'
    actors = _split(v.get('actors', ''))
    ext = _split(v.get('ext', ''))
    nodes = [_node('SYS', 'application_component', sys_name, rank=2, order=1, meta='criticality=high')]
    edges = []
    for i, a in enumerate(actors):
        nodes.append(_node(f'AC{i}', 'business_actor', a, rank=1, order=i + 1))
        edges.append(_edge(f'tu{i}', f'AC{i}', 'SYS', 'association', 'uses'))
    for i, x in enumerate(ext):
        nodes.append(_node(f'EX{i}', 'application_component', x, rank=3, order=i + 1, fill='#EDEDED'))
        edges.append(_edge(f'tx{i}', 'SYS', f'EX{i}', 'flow'))
    return {'title': f'{sys_name} — Context', 'nodes': nodes, 'edges': edges}


def tpl_erd_starter(v: dict) -> dict:
    ents = _split(v.get('ents', ''))
    nodes = []
    for i, e in enumerate(ents):
        fk = f'{ents[i-1]}_id(FK);' if i else ''
        nodes.append(_node(f'E{i}', 'entity', e.upper(), rank=i // 3 + 1, order=i % 3 + 1,
                            meta=f'rows=id(PK);{fk}name;created_at'))
    edges = [_edge(f'tr{i}', f'E{i-1}', f'E{i}', 'one_to_many', '1 : N') for i in range(1, len(ents))]
    return {'title': 'Data Model', 'nodes': nodes, 'edges': edges}


TEMPLATES = {
    'Swimlane process': {
        'description': 'Cross-functional flow: one lane per team, steps chained across lanes.',
        'fields': [('lanes', 'Lanes (comma-separated)', 'Sales, Finance, Operations'),
                   ('steps', 'Steps per lane', '2')],
        'build': tpl_swimlane,
    },
    'Layered application architecture': {
        'description': 'ArchiMate-style Business / Application / Technology stack for a set of applications.',
        'fields': [('apps', 'Applications (comma-separated)', 'Web Shop, CRM, Billing')],
        'build': tpl_layered_arch,
    },
    'Microservices landscape': {
        'description': 'API gateway, service tier and datastore tier in zones, wired with data flows.',
        'fields': [('svcs', 'Services (comma-separated)', 'orders, payments, inventory, shipping')],
        'build': tpl_microservices,
    },
    'Capability map': {
        'description': 'Nested L1/L2 business capability tiles (containers auto-size).',
        'fields': [('caps', 'L1 capabilities (comma-separated)', 'Customer Mgmt, Product Mgmt, Fulfilment'),
                   ('kids', 'L2 per capability', '3')],
        'build': tpl_capability_map,
    },
    'System context (C4-style)': {
        'description': 'One system in the middle, actors above, external systems below.',
        'fields': [('sys', 'System name', 'Order Platform'),
                   ('actors', 'Actors (comma)', 'Customer, Support Agent'),
                   ('ext', 'External systems (comma)', 'Payment Provider, Email Service')],
        'build': tpl_c4_context,
    },
    'ERD starter': {
        'description': 'Entity chain with PK/FK rows and 1:N cardinality.',
        'fields': [('ents', 'Entities (comma-separated)', 'customer, order, order_item')],
        'build': tpl_erd_starter,
    },
}


# ---------- outline (mind-map) mode ----------
def build_outline(text: str, entity_type: str, relation_type: str) -> dict:
    """Indented-text -> node tree (2-space or tab = one depth level), with a
    parent->child edge of `relation_type` for every line under a shallower
    ancestor. Mirrors the JS `buildOutline` exactly, including its depth
    calc (leading whitespace, tabs counted as 2 spaces, floor(len/2))."""
    nodes, edges, stack = [], [], []
    order_by_rank: dict[int, int] = {}
    for raw_line in (text or '').split('\n'):
        if not raw_line.strip():
            continue
        leading = re.match(r'^\s*', raw_line).group(0).replace('\t', '  ')
        depth = len(leading) // 2
        nid = f'o{len(nodes) + 1}'
        d = min(depth, len(stack))
        del stack[d:]
        parent = stack[-1] if stack else None
        rank = d + 1
        order_by_rank[rank] = order_by_rank.get(rank, 0) + 1
        nodes.append(_node(nid, entity_type, raw_line.strip(), parent='', rank=rank, order=order_by_rank[rank]))
        if parent:
            edges.append(_edge(f'oe{len(edges) + 1}', parent, nid, relation_type))
        stack.append(nid)
    return {'nodes': nodes, 'edges': edges}
