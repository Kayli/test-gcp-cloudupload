# GCP Docstore Prototype

Full-stack prototype for a GCP Document Storage Service. A React/Vite frontend backed by a FastAPI server that issues signed object-storage URLs (MinIO in dev, GCS in prod) and tracks uploads in a SQLite metadata DB.

## Project layout

```
backend/          FastAPI app, DB, storage helpers, Dockerfile.api, pyproject.toml
frontend/         React/Vite source, package.json, vite.config.js, Dockerfile.ui
public/           Vite build output (served as static files by the API)
test/
  unit/           Pure Python unit tests (no services required)
  integration/    End-to-end tests (spin up Docker services automatically)
docker-compose.yml
pyproject.toml    Root config — pytest settings only
```

## Quick start (devcontainer — recommended)

1. Copy the example env file and fill in any local values:

```bash
cp .devcontainer/.env.example .devcontainer/.env
# edit .devcontainer/.env as needed (GOOGLE_OAUTH_CLIENT_ID, GCS_BUCKET, …)
```

2. Rebuild / re-open the devcontainer so the environment is loaded.

3. Start the full stack (MinIO + API + Vite dev server):

```bash
docker compose up
```

| Service | URL |
|---------|-----|
| Vite dev server (React UI, HMR) | http://localhost:5173 |
| FastAPI backend | http://localhost:3000 |
| MinIO S3 API | http://localhost:9000 |
| MinIO Console | http://localhost:9001 |

4. Run the test suite:

```bash
pytest           # all tests (unit + integration)
pytest test/unit # unit tests only (no Docker required)
```

The integration tests detect whether the Docker services are already running and start them automatically if not.

## Running without devcontainer

**Backend:**

```bash
pip install ./backend
uvicorn backend.app:app --reload --host 0.0.0.0 --port 3000
```

**Frontend (separate terminal):**

```bash
npm ci --prefix frontend
npm run dev --prefix frontend   # Vite dev server on :5173
```

**Build the frontend for production:**

```bash
npm run build --prefix frontend  # outputs to public/
```

## API

All endpoints except `/health` and `/config` require authentication.

**Auth:** Pass a Google ID token as `Authorization: Bearer <token>`.  
**Dev mode:** Set `ALLOW_DEV_AUTH=1` and send `X-DUMMY-USER: user@example.com` instead.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Returns `{"status":"ok"}` |
| `GET` | `/config` | Returns OAuth client ID and dev-auth flag |
| `POST` | `/uploads` | Create a pending upload; returns a signed PUT URL |
| `POST` | `/uploads/{id}/complete` | Mark an upload complete after the PUT succeeds |
| `GET` | `/files` | List all uploads belonging to the authenticated user |
| `GET` | `/files/{id}/download` | Return a short-lived signed GET URL for a file |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOW_DEV_AUTH` | `0` | Set to `1` to enable the `X-DUMMY-USER` dev auth bypass |
| `GOOGLE_OAUTH_CLIENT_ID` | *(unset)* | Google OAuth client ID for token verification |
| `MINIO_ENDPOINT` | `http://localhost:9000` | MinIO S3 API endpoint (inside compose: `http://minio:9000`) |
| `MINIO_PUBLIC_URL` | `http://localhost:5173` | Base URL embedded in presigned URLs (must be reachable by the browser) |
| `MINIO_BUCKET` | `objstore` | Bucket name |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `GCS_BUCKET` | *(unset)* | Set to use GCS instead of MinIO |

## UI tests against a host browser

To run browser tests against Chrome Canary on the host machine, start it first (from the host):

```bash
bash scripts/host-start-browser.sh
```

The devcontainer sets `USE_HOST_BROWSER=1` by default, which connects Playwright to the host via `CHROME_REMOTE_DEBUGGING_URL`. To force headless mode:

```bash
USE_HOST_BROWSER=0 pytest test/integration
```
