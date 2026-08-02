# Deploying diagen to GCP Cloud Run

```
Cloud Run "diagen-frontend"  (Caddy + static build)
        ↓ VITE_API_BASE (cross-origin fetch, browser → backend directly)
Cloud Run "diagen-backend"   (FastAPI/uvicorn)
        ↓ TCP/TLS (DATABASE_URL)
Neon Postgres                (external, free tier — the "db service")
```

Two corrections from the original 3-Cloud-Run-services ask, both driven by
the "$4-5/month max" budget:

1. The DB tier isn't a third Cloud Run service running Postgres itself —
   Cloud Run's local disk is ephemeral (wiped on restart, not shared across
   instances), so a real database engine can't safely live inside a Cloud
   Run container without risking corruption on restart/redeploy.
2. It's also not **Cloud SQL** (GCP's managed Postgres) — even the
   cheapest Cloud SQL tier (`db-f1-micro`) runs ~$8-10/month on its own,
   over budget by itself before anything else is counted. Instead:
   **Neon** (neon.tech), a free-tier serverless Postgres host — $0/month
   at this scale, reached over the public internet (TLS) rather than
   Cloud Run's private Unix-socket integration. `app/db.py` already
   supports this exact path (`DATABASE_URL` env var), no code change
   needed — that abstraction was built with this option in mind.

Backend runs **`--max-instances=1`, `--min-instances=0`** — never more than
one copy at once (sessions live in an in-memory dict,
`app/diagram_store.py`; two instances would each get their own copy and
requests would randomly 404 on the wrong one), and scales to zero when
idle so it costs nothing between requests. Trade-off: a cold start (a few
seconds) on the first request after idling, and if the one instance
happens to recycle mid-edit, whoever's actively editing loses their undo
history and anything since the last auto-save (every 2 min) — saved
projects themselves are safe regardless, they're in Neon now, not that
in-memory dict. Frontend (stateless static files) scales to zero too.

**Cost at this config: effectively $0/month** at low/personal traffic —
Neon's free tier (0.5GB storage, auto-suspends when idle) plus Cloud Run's
free tier (per-service monthly vCPU/memory/request allowances) covers it.
You'd only see a bill if traffic or stored-project volume grows past those
free-tier ceilings — comfortably under the $4-5/month target either way at
the scale this app is built for.

## 1. Neon (Postgres, free tier)

No gcloud command for this part — it's a separate provider, done via
their dashboard (a CLI, `neonctl`, exists too if you'd rather script it):

1. Sign up at https://neon.tech (free, no credit card required for the free tier).
2. Create a project → creates a default Postgres database + connection string for you.
3. Copy the connection string from the dashboard — looks like
   `postgresql://<user>:<password>@<host>/<dbname>?sslmode=require`. Neon
   requires TLS (`sslmode=require`); `psycopg2` handles that automatically
   from the URL, no extra config on the app side.

```bash
DATABASE_URL="postgresql://...you copied this..."   # keep this in your shell for the Secrets step below
```

## Prerequisites

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com \
    artifactregistry.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com
```

## 2. Secrets

Two secrets, both consumed as env vars by the backend service:

```bash
echo -n "$DATABASE_URL" | gcloud secrets create diagen-database-url --data-file=-

# The token-signing secret (see app/auth.py) — MUST be set on Cloud Run,
# there's no file-based fallback there (ephemeral, per-instance disk).
openssl rand -hex 32 | tr -d '\n' | gcloud secrets create diagen-auth-secret --data-file=-
```

## 3. Artifact Registry (image storage)

```bash
gcloud artifacts repositories create diagen \
    --repository-format=docker \
    --location=us-central1

REGION=us-central1
REPO="$REGION-docker.pkg.dev/$(gcloud config get-value project)/diagen"
```

No local Docker needed anywhere below — every image is built by **Cloud
Build** (`gcloud builds submit`), which uploads your source and builds the
image on GCP's side, so this works even on a machine without Docker
Desktop installed. If you do have Docker locally and prefer it, swap the
`gcloud builds submit` line in each step for `docker build ... && docker push ...`
— functionally identical.

## 4. Build + deploy the backend

```bash
cd webapp/backend
gcloud builds submit --tag "$REPO/backend:latest"

gcloud run deploy diagen-backend \
    --image "$REPO/backend:latest" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --min-instances=0 \
    --max-instances=1 \
    --cpu-boost \
    --set-secrets="DATABASE_URL=diagen-database-url:latest,AUTH_SECRET_KEY=diagen-auth-secret:latest"

BACKEND_URL=$(gcloud run services describe diagen-backend --region "$REGION" --format='value(status.url)')
echo "$BACKEND_URL"
```

`--allow-unauthenticated`: this app has its own login (see
`webapp/README.md` § Accounts) — that's the access control. If you'd rather
also gate it behind Google/IAM auth (e.g. only people in your GCP org can
even reach it), drop that flag and front it with Identity-Aware Proxy
instead; out of scope here.

## 5. Build + deploy the frontend

Needs the backend's URL baked in at build time (Vite env vars are
build-time, not runtime):

```bash
cd ../frontend
gcloud builds submit --config cloudbuild.yaml \
    --substitutions=_VITE_API_BASE="$BACKEND_URL/api",_IMAGE="$REPO/frontend:latest"

gcloud run deploy diagen-frontend \
    --image "$REPO/frontend:latest" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated

FRONTEND_URL=$(gcloud run services describe diagen-frontend --region "$REGION" --format='value(status.url)')
echo "$FRONTEND_URL"
```

## 6. Lock CORS down to the real frontend URL

Step 4 deployed the backend before the frontend URL existed, so CORS is
still wide open (`FRONTEND_ORIGIN` unset → `allow_origins=["*"]`, see
`app/main.py`). Tighten it now that you have a real URL:

```bash
gcloud run services update diagen-backend \
    --region "$REGION" \
    --set-env-vars="FRONTEND_ORIGIN=$FRONTEND_URL"
```

(Keeps every other env var/secret already set — `update` merges, doesn't replace.)

## 7. Verify

```bash
curl "$BACKEND_URL/api/health"      # {"status":"ok"}
open "$FRONTEND_URL"                # or just visit it — sign up, save a diagram
```

Confirm data survives a backend restart/cold-start (this is the actual point of Neon over the in-memory session dict):

```bash
gcloud run services update diagen-backend --region "$REGION" --update-env-vars="_=$(date +%s)"  # force new revision
# reload the frontend, log back in, saved project should still be there
```

## Redeploying after a code change

```bash
# backend:
cd webapp/backend
gcloud builds submit --tag "$REPO/backend:latest"
gcloud run deploy diagen-backend --image "$REPO/backend:latest" --region "$REGION"

# frontend (VITE_API_BASE doesn't change unless the backend URL changes):
cd ../frontend
gcloud builds submit --config cloudbuild.yaml \
    --substitutions=_VITE_API_BASE="$BACKEND_URL/api",_IMAGE="$REPO/frontend:latest"
gcloud run deploy diagen-frontend --image "$REPO/frontend:latest" --region "$REGION"
```

## Testing the Postgres path locally before you deploy

The dual-backend logic (`app/db.py`) picks Postgres automatically whenever
`DATABASE_URL` (or `INSTANCE_CONNECTION_NAME`, if you ever do move to Cloud
SQL later) is set — test it against a throwaway local Postgres before
trusting it against the real Neon database:

```bash
docker run -d --name diagen-pg-test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=diagen -p 5432:5432 postgres:16

cd webapp/backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
DATABASE_URL="postgresql://postgres:test@localhost:5432/diagen" \
    .venv/bin/uvicorn app.main:app --port 8000
# in another terminal: curl -X POST localhost:8000/api/auth/signup -d '{"username":"test","password":"correcthorse1"}' -H 'Content-Type: application/json'
```

If that round-trips (signup → save a project → restart uvicorn → project
still there), the Cloud SQL path will too — same code path, same driver,
only the connection method differs (TCP here vs. Unix socket on Cloud Run).

## Cost note

Everything here scales to zero or free-tiers at low/personal traffic:
Cloud Run backend + frontend (`min-instances=0`), Neon Postgres (free tier,
auto-suspends when idle), Artifact Registry (free tier covers one image),
Cloud Build (free build-minutes/month). Realistic total: **$0/month** at
this app's scale, growing only if usage genuinely outgrows Neon's free
0.5GB storage or Cloud Run's free monthly request/compute allowances —
still meaningfully less ops than the home-hosted path (`webapp/deploy/`),
and cheaper than the Cloud SQL version of this same architecture.

## What's NOT handled here

- No custom domain / managed TLS cert mapping — Cloud Run gives you a
  `*.run.app` URL out of the box; domain mapping is a separate
  `gcloud run domain-mappings create` step if you want one.
- No CI/CD — these are manual `gcloud builds submit && gcloud run deploy`
  commands. Wire up Cloud Build triggers if you want push-to-deploy.
- No automated backups beyond whatever Neon does on its free tier by
  default — check their retention policy if that matters; paid Neon tiers
  add point-in-time restore.
- Neon free tier auto-suspends after inactivity — combined with the
  backend also scaling to zero, the very first request after both have
  been idle a while can take noticeably longer (two cold starts stacked,
  not one). Later requests are fast again. Acceptable trade for $0/month
  at low-traffic personal use; mention it if that latency ever becomes a
  problem and we can revisit (e.g. pin backend `min-instances=1` again,
  ~$12-15/mo, to at least remove the Cloud Run side of it).
