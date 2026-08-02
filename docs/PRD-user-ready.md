# diagen — "user-ready" platform PRD

Scope: what's missing to take diagen from "works on my machine for me" to
"safe to hand a URL to other people." Written after auditing the current
codebase (`webapp/backend`, `webapp/frontend`, `webapp/deploy`).

## Current state (as of this doc)

- FastAPI + in-memory session store (`app/diagram_store.py`), TTL 1h.
- SQLite-backed named project save/load (`app/projects.py`) — global,
  no ownership, anyone who can reach the API can list/load/delete anyone
  else's saved projects.
- No authentication anywhere. CORS wide open (mitigated today only because
  the browser talks same-origin through Caddy).
- No upload/request size limits, no rate limiting.
- Deployed via Cloudflare Quick Tunnel (`webapp/deploy/`) — public URL,
  currently reachable by anyone who has it.
- No automated tests for the projects API (endpoints added last session).
- No backup automation for `projects.db`.
- No auto-save — an active editing session is lost on backend restart
  unless the user explicitly clicks Save.

## Bug found during this audit

`DiagramStore._gc()` (`diagram_store.py`) expires sessions off
`created_at`, never updated after creation. A session open and actively
edited for >1h (TTL default) gets garbage-collected out from under the
user mid-edit, not just idle ones. Needs `last_active`, bumped on every
`_get_session()` call. **Fixing regardless of what else ships** — this is
a correctness bug, not a nice-to-have.

## Requirements, by area

### 1. Hardening (do first — cheap, no architecture decisions, no breakage)
- Fix the TTL/last-active bug above.
- Cap `.xlsx` upload size (Starlette doesn't enforce one by default —
  today a multi-GB upload is accepted and `openpyxl` loads it fully into
  memory).
- Cap CSV paste body size (same class of issue, text field not a file).
- Turn unhandled `KeyError`s from unknown `entity_type`/`relation_type`
  into proper `400`s instead of an opaque `500` (a few code paths reach
  `spec.shape_of`/`spec.line_of` without the existing "skip unknown types"
  guard that `load_rows` already has).
- Basic per-IP rate limiting on mutating endpoints (cheap protection once
  this has a public URL — a scripted loop hitting `/api/node/create` in a
  tight loop today has nothing stopping it).
- Cap saved-project count / name length (SQLite has no natural limit;
  without one, an abusive client can grow `projects.db` unbounded).

### 2. Reliability
- Auto-save: while a session is tied to a saved project (`currentProjectId`
  set in the frontend), periodically re-save in the background so a crash
  doesn't lose unsaved edits. Debounced/interval-based, not on every
  keystroke.
- Scheduled backup of `projects.db` (it's the only durable state in this
  system) — timestamped copy on a schedule, pruned after N days. Fits the
  existing Task Scheduler pattern in `webapp/deploy/`.
- Tests for `app/projects.py` + the new endpoints, mirroring the existing
  `tests/` fixture-based style (no hand-rolled mocks).

### 3. Auth — **architecture decision needed before building**
Two materially different shapes, pick one:
- **Shared password (simple gate):** one password protects the whole app
  (e.g. HTTP Basic Auth in front, or a single login screen + signed
  cookie/token). No per-user data separation — matches today's "one global
  project list" model exactly, just adds a lock on the door. Minutes of
  work, no schema change.
- **Real multi-user accounts:** users table, password hashes, project
  ownership (`projects.user_id`), session tied to a logged-in user, one
  user can't see/load/delete another's projects. More correct for a
  team tool, meaningfully more work (new `users` table + migration of
  existing `projects` rows, login/signup UI, auth middleware on every
  route, "forgot password" is out of scope for a self-hosted tool without
  email sending configured).

Not building this without picking one first — the two are different
enough in shape that guessing wrong means throwing work away.

### 4. Onboarding / UX polish
- Replace the current one-line empty state with a short "pick a starting
  point" screen (blank / sample / upload / template — all already exist as
  actions, just not surfaced together).
- Keyboard-shortcut reference (V/C/Ctrl+Z/Delete already exist, undocumented
  in the UI itself).
- Friendlier error surface — right now `error` renders as raw
  `e.response.data.detail` text in the toolbar; fine for a dev tool, a bit
  raw for "hand someone a URL."
- Mobile/responsive: **proposed non-goal.** This is a drag/click diagram
  editor over an SVG canvas — genuinely not a mobile use case. Flag if
  that's wrong.

## Priority / sequencing

1. Hardening (§1) + the TTL bug fix — no decisions needed, ships now.
2. Auto-save + backup script + tests (§2) — no decisions needed, ships now.
3. Auth (§3) — **blocked on which model** (see question asked in chat).
4. Onboarding/UX (§4) — after auth, since login/signup screens are part of
   "first thing a new user sees" and should be designed together.

## Status (shipped this pass)

All four sections shipped: §1 hardening, §2 auto-save + backup + tests, §3 multi-user
accounts (chosen over shared-password), §4 onboarding (empty-state screen, keyboard
shortcuts reference). Verified: 72 pytest (16 new, rest pre-existing engine suite still
green), manual curl battery for signup/login/ownership-isolation/rate-limit/upload-cap/
CSV-cap, both `tsc -b` and `vite build` clean.

Deliberately deferred / out of scope for this pass:
- Password reset / email verification — no mail server in this deployment; noted as a
  known gap in `webapp/deploy/README.md`.
- Friendlier error-message redesign in the toolbar (still raw `detail` text) — cosmetic,
  low priority next to everything else that shipped.
- Mobile/responsive — confirmed non-goal, not revisited.
