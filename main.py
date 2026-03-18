"""Entry point shim for running the application with uvicorn.

Having `main.py` at the repository root makes it convenient to run the
server with commands like `uvicorn main:app --reload` without altering
`PYTHONPATH` or referencing the `backend` package. It simply re-exports the
FastAPI `app` from `backend.app`.
"""

from backend.app import app  # type: ignore # noqa: F401 – re-export for uvicorn main:app
