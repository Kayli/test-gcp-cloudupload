# GCP Docstore Prototype

Minimal prototype for the GCP Document Storage Service. Contains a small Express app with a health endpoint and tests.

Run locally:

```bash
npm install
npm test
npm start
```

Devcontainer (recommended)

1. Copy the example env file and fill in any local values:

```bash
cp .devcontainer/.env.example .devcontainer/.env
# edit .devcontainer/.env as needed
```

2. Rebuild / re-open the devcontainer so the environment is loaded.

3. (Optional) To run UI tests against your host's Chrome Canary, start it on the host:

```bash
bash host-start-browser.sh
```

4. Run tests inside the devcontainer. By default the devcontainer uses the `.env` setting
	`USE_HOST_BROWSER=1` to connect to the host browser. To force headless you can prefix the
	command with `USE_HOST_BROWSER=0`, for example:

```bash
USE_HOST_BROWSER=0 npm test
```

## Python / FastAPI (new)

This workspace now includes a FastAPI server to serve the `legacy/public/` static files and a small API that mirrors the legacy Express app.

- Install dependencies (recommend using a venv):

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
```

- Run the server with `uvicorn`:

```bash
uvicorn src.app:app --reload --host 0.0.0.0 --port 3000
```

- The site will be served from `http://localhost:3000/` and the health endpoint is `http://localhost:3000/health`.

- The upload endpoints mirror the legacy API:
	- `POST /uploads` (requires auth) — returns a signed upload URL placeholder
	- `GET /files/:id/download` (requires auth) — returns a signed download URL placeholder

- To allow dev auth, set `ALLOW_DEV_AUTH=1` or run with `NODE_ENV=test`.

