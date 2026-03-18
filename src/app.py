import os
import re
import uuid
from pathlib import Path
from typing import Any, Optional, cast
from urllib.parse import quote

from fastapi import Body, FastAPI, HTTPException, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import google.oauth2.id_token
import google.auth.transport.requests

from src.storage import get_storage
from src.db import complete_upload as db_complete_upload, get_file, insert_upload


BASE_DIR = Path(__file__).resolve().parents[1]
public_candidate = BASE_DIR / "public"

app = FastAPI(title="FastAPI host + API (replica)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UploadRequest(BaseModel):
    tenantId: str
    filename: str
    contentType: Optional[str] = None  # MIME type; defaults to application/octet-stream


class CompleteRequest(BaseModel):
    size: Optional[int] = None  # file size in bytes, reported by the client


ALLOW_DEV = os.getenv("ALLOW_DEV_AUTH") == "1" or os.getenv("NODE_ENV") == "test"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    first: dict[str, Any] = exc.errors()[0] if exc.errors() else {}
    msg: str = str(first.get("msg", "Invalid request"))
    return JSONResponse(status_code=400, content={"error": msg})


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


def verify_token(id_token: str) -> dict[str, Any]:
    request = google.auth.transport.requests.Request()
    payload = cast(dict[str, Any], google.oauth2.id_token.verify_oauth2_token(id_token, request, GOOGLE_CLIENT_ID))  # type: ignore[reportUnknownMemberType]
    return payload


async def require_auth(request: Request) -> dict[str, Any]:
    # If GOOGLE_OAUTH_CLIENT_ID is set and dev auth is NOT allowed, expect Authorization: Bearer <id_token>
    if GOOGLE_CLIENT_ID and not ALLOW_DEV:
        auth = request.headers.get("authorization") or ""
        m = re.match(r"^Bearer (.+)$", auth)
        if not m:
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        id_token = m.group(1)
        try:
            payload = verify_token(id_token)
            if not payload:
                raise HTTPException(status_code=401, detail="Invalid token")
            return {"id": payload.get("sub"), "email": payload.get("email"), "hd": payload.get("hd")}
        except Exception:
            raise HTTPException(status_code=401, detail="Token verification failed")

    # Dev fallback: allow X-DUMMY-USER header with email when dev auth is enabled
    dev = request.headers.get("x-dummy-user")
    if dev and ALLOW_DEV:
        return {"id": "dev:" + dev, "email": dev}

    raise HTTPException(status_code=401, detail="Unauthenticated")


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@app.get("/config")
async def config() -> dict[str, Any]:
    return {"googleClientId": GOOGLE_CLIENT_ID or None, "allowDevAuth": ALLOW_DEV}


@app.post("/uploads")
async def create_upload(
    req: UploadRequest,
    user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Generate a signed PUT URL and record the upload as 'pending' in the DB."""
    tenant = req.tenantId
    filename = req.filename
    if not tenant or not filename:
        raise HTTPException(status_code=400, detail="tenantId and filename are required")

    file_id = str(uuid.uuid4())
    content_type = req.contentType or "application/octet-stream"
    object_key = f"tenant/{quote(tenant)}/files/{file_id}/{quote(filename)}"

    try:
        storage = get_storage()
        upload_url = storage.generate_upload_url(object_key, content_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not generate upload URL: {exc}")

    insert_upload(
        id=file_id,
        tenant_id=tenant,
        filename=filename,
        object_key=object_key,
        content_type=content_type,
        owner_email=user.get("email"),
    )

    return {
        "id": file_id,
        "uploadUrl": upload_url,
        "expiresIn": 900,
        "objectKey": object_key,
        "requestedBy": user.get("email"),
    }


@app.post("/uploads/{file_id}/complete")
async def mark_upload_complete(
    file_id: str,
    req: Optional[CompleteRequest] = Body(default=None),
    user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Client calls this after a successful PUT to the signed URL.

    Transitions the metadata record from 'pending' → 'complete' and
    records the file size if provided.
    """
    size = req.size if req else None
    updated = db_complete_upload(id=file_id, size=size)
    if not updated:
        raise HTTPException(status_code=404, detail="Upload not found or already completed")
    return {"id": file_id, "status": "complete"}


@app.get("/files/{file_id}/download")
async def get_download(
    file_id: str,
    user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Look up a completed upload and return a short-lived signed GET URL."""
    row = get_file(file_id)
    if not row:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        storage = get_storage()
        download_url = storage.generate_download_url(row["object_key"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not generate download URL: {exc}")

    return {
        "downloadUrl": download_url,
        "expiresIn": 300,
        "filename": row["filename"],
        "size": row["size"],
        "requestedBy": user.get("email"),
    }


# Serve static UI last so all API routes above take priority
app.mount("/", StaticFiles(directory=public_candidate, html=True), name="public")
