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

