import os
import re
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import google.oauth2.id_token
import google.auth.transport.requests


BASE_DIR = Path(__file__).resolve().parents[1]

# Prefer legacy/public if present, else public/
public_candidate = BASE_DIR / "legacy" / "public"
if not public_candidate.exists():
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


ALLOW_DEV = os.getenv("ALLOW_DEV_AUTH") == "1" or os.getenv("NODE_ENV") == "test"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    msg = first.get("msg", "Invalid request")
    return JSONResponse(status_code=400, content={"error": msg})


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


def verify_token(id_token: str):
    request = google.auth.transport.requests.Request()
    payload = google.oauth2.id_token.verify_oauth2_token(id_token, request, GOOGLE_CLIENT_ID)
    return payload


async def require_auth(request: Request):
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
async def config():
    allow_dev = ALLOW_DEV
    return {"googleClientId": GOOGLE_CLIENT_ID or None, "allowDevAuth": allow_dev}


@app.post("/uploads")
async def create_upload(req: UploadRequest, user=Depends(require_auth)):
    tenant = req.tenantId
    filename = req.filename
    if not tenant or not filename:
        raise HTTPException(status_code=400, detail="tenantId and filename are required")

    id = str(uuid.uuid4())
    upload_url = (
        f"https://storage.googleapis.com/fake-bucket/tenant/{quote(tenant)}/files/{id}/{quote(filename)}?signature=placeholder"
    )
    return {"id": id, "uploadUrl": upload_url, "expiresIn": 900, "requestedBy": (user and user.get("email"))}


@app.get("/files/{id}/download")
async def get_download(id: str, user=Depends(require_auth)):
    if not id:
        raise HTTPException(status_code=400, detail="id required")
    download_url = f"https://storage.googleapis.com/fake-bucket/files/{quote(id)}?signature=placeholder"
    return {"downloadUrl": download_url, "expiresIn": 300, "requestedBy": (user and user.get("email"))}


# Serve static UI last so all API routes above take priority
app.mount("/", StaticFiles(directory=public_candidate, html=True), name="public")
