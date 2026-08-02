"""Saved-project persistence + per-user ownership isolation."""
from __future__ import annotations


def _make_session(client, headers) -> str:
    r = client.post('/api/blank', json={}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()['session_id']


def test_save_list_load_round_trip(client, auth_headers):
    headers = auth_headers
    session_id = _make_session(client, headers)

    r = client.post(
        '/api/node/create',
        json={'session_id': session_id, 'entity_type': 'business_actor', 'label': 'Hello', 'x': 10, 'y': 10},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    r = client.post(
        '/api/projects/save', json={'session_id': session_id, 'name': 'My Diagram'}, headers=headers
    )
    assert r.status_code == 200, r.text
    project_id = r.json()['id']
    assert r.json()['name'] == 'My Diagram'

    r = client.get('/api/projects', headers=headers)
    assert r.status_code == 200
    assert [p['id'] for p in r.json()] == [project_id]

    r = client.post('/api/projects/load', json={'project_id': project_id}, headers=headers)
    assert r.status_code == 200, r.text
    labels = [n['label'] for n in r.json()['nodes']]
    assert 'Hello' in labels


def test_resave_same_id_updates_in_place(client, auth_headers):
    headers = auth_headers
    session_id = _make_session(client, headers)
    r = client.post('/api/projects/save', json={'session_id': session_id, 'name': 'First'}, headers=headers)
    project_id = r.json()['id']

    r = client.post(
        '/api/projects/save',
        json={'session_id': session_id, 'name': 'Renamed', 'project_id': project_id},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()['id'] == project_id
    assert r.json()['name'] == 'Renamed'

    rows = client.get('/api/projects', headers=headers).json()
    assert len(rows) == 1
    assert rows[0]['name'] == 'Renamed'


def test_delete_then_404_on_load(client, auth_headers):
    headers = auth_headers
    session_id = _make_session(client, headers)
    r = client.post('/api/projects/save', json={'session_id': session_id, 'name': 'Doomed'}, headers=headers)
    project_id = r.json()['id']

    r = client.post('/api/projects/delete', json={'project_id': project_id}, headers=headers)
    assert r.status_code == 200
    assert r.json() == {'deleted': True}

    r = client.post('/api/projects/load', json={'project_id': project_id}, headers=headers)
    assert r.status_code == 404


def _signup(client, username: str) -> dict:
    r = client.post('/api/auth/signup', json={'username': username, 'password': 'correcthorse1'})
    assert r.status_code == 200, r.text
    token = r.json()['token']
    return {'Authorization': f'Bearer {token}'}


def test_users_cannot_see_or_touch_each_others_projects(client):
    alice = _signup(client, 'alice')
    bob = _signup(client, 'bob')

    session_id = _make_session(client, alice)
    r = client.post('/api/projects/save', json={'session_id': session_id, 'name': 'Alice Only'}, headers=alice)
    project_id = r.json()['id']

    # bob's list is empty, doesn't include alice's project
    assert client.get('/api/projects', headers=bob).json() == []

    # bob can't load it
    r = client.post('/api/projects/load', json={'project_id': project_id}, headers=bob)
    assert r.status_code == 404

    # bob can't delete it
    r = client.post('/api/projects/delete', json={'project_id': project_id}, headers=bob)
    assert r.status_code == 404

    # ...and it's still there for alice
    r = client.post('/api/projects/load', json={'project_id': project_id}, headers=alice)
    assert r.status_code == 200

    # bob can't overwrite it by "saving" with alice's project_id either
    bob_session = _make_session(client, bob)
    r = client.post(
        '/api/projects/save',
        json={'session_id': bob_session, 'name': 'Hijacked', 'project_id': project_id},
        headers=bob,
    )
    assert r.status_code == 403

    # confirm alice's copy is untouched
    r = client.get('/api/projects', headers=alice)
    assert r.json()[0]['name'] == 'Alice Only'


def test_multi_diagram_workbook_round_trips_all_diagrams(client, auth_headers):
    headers = auth_headers
    r = client.post('/api/sample', json={'name': 'ZZ_multi_diagram_test.xlsx'}, headers=headers)
    assert r.status_code == 200, r.text
    session_id = r.json()['session_id']
    original_ids = sorted(d['id'] for d in r.json()['diagrams'])
    assert len(original_ids) > 1

    r = client.post('/api/projects/save', json={'session_id': session_id, 'name': 'Multi'}, headers=headers)
    project_id = r.json()['id']

    r = client.post('/api/projects/load', json={'project_id': project_id}, headers=headers)
    assert sorted(d['id'] for d in r.json()['diagrams']) == original_ids


def test_project_name_required(client, auth_headers):
    headers = auth_headers
    session_id = _make_session(client, headers)
    r = client.post('/api/projects/save', json={'session_id': session_id, 'name': '   '}, headers=headers)
    assert r.status_code == 400
