#!/bin/sh
# Entrypoint for the frontend Docker image.
# Switches between Vite dev server (HMR) and a static-file server based on
# the NODE_ENV environment variable.
set -e

if [ "${NODE_ENV}" = "production" ]; then
    echo "[ui] Production mode: building assets with Vite…"
    # Run vite build from the frontend/ directory so that:
    #   root: '.'    → /app/frontend/   (where index.html lives)
    #   outDir: '../public' → /app/public/  (output served by FastAPI or serve)
    cd /app/frontend && npx vite build

    echo "[ui] Serving built assets on :5173…"
    exec serve -s /app/public -l 5173
else
    echo "[ui] Development mode: starting Vite dev server with HMR…"
    # cd into frontend/ so that vite.config.js's `root: '.'` resolves to the
    # directory that contains index.html.  node_modules stay at /app/node_modules
    # and are found automatically via Node's directory-walk resolution.
    cd /app/frontend && exec npx vite --host
fi
