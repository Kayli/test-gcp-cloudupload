"""Storage backend abstraction.

Dev  → MinIO (S3-compatible).  Presigned PUT/GET URLs are generated locally by
       boto3 (HMAC-SHA256) — MinIO does not need to be reachable at URL-generation
       time, only when the client actually uploads/downloads.

Prod → GCS.  Signed URLs require a service-account key or ADC with
       iam.serviceAccounts.signBlob permission.

Backend selection (automatic):
  GCS_BUCKET set   → GcsStorage
  otherwise        → MinioStorage   ← default (dev / test)

MINIO_PUBLIC_URL
  boto3 embeds the endpoint_url into the presigned URL host.  When FastAPI runs
  inside a devcontainer and MinIO is reached via host.docker.internal:9000, the
  browser on the host machine can't resolve that name.  Set MINIO_PUBLIC_URL to
  the publicly reachable base URL (e.g. http://localhost:9000) and the module
  will rewrite the host portion before returning the URL to the client.
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse, urlunparse

# ── MinIO / S3-compatible ─────────────────────────────────────────────────────

MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT",    "http://localhost:9000")
MINIO_PUBLIC_URL = os.getenv("MINIO_PUBLIC_URL",  "")   # empty → same as MINIO_ENDPOINT
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY",  "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY",  "minioadmin")
MINIO_BUCKET     = os.getenv("MINIO_BUCKET",      "uploads")

# ── GCS ──────────────────────────────────────────────────────────────────────

GCS_BUCKET = os.getenv("GCS_BUCKET", "")


# ── Shared protocol (structural subtyping — no ABC overhead) ──────────────────

class StorageBackend:  # pragma: no cover
    def ensure_bucket(self) -> None: ...
    def generate_upload_url(self, key: str, content_type: str, expires: int = 900) -> str: ...
    def generate_download_url(self, key: str, expires: int = 300) -> str: ...


# ── MinIO ─────────────────────────────────────────────────────────────────────

class MinioStorage:
    """S3-compatible object storage (MinIO) using boto3 presigned URLs."""

    def __init__(self) -> None:
        import boto3  # type: ignore[import]
        from botocore.config import Config  # type: ignore[import]

        self._bucket = MINIO_BUCKET
        cfg = Config(signature_version="s3v4")

        # Used for bucket management (head_bucket, create_bucket) — connects to
        # the internal Docker service name so it works inside the compose network.
        self._client = boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            config=cfg,
            region_name="us-east-1",
        )

        # Used ONLY for presigning.
        # boto3 embeds endpoint_url as the Host in the HMAC signature.  If we
        # sign against the internal name (minio:9000) and then textually rewrite
        # the URL to localhost:9000, the Host header the browser sends won't match
        # the signed Host → MinIO returns 403 SignatureDoesNotMatch.
        # Fix: sign against the public URL from the start — no rewriting needed.
        presign_endpoint = MINIO_PUBLIC_URL or MINIO_ENDPOINT
        self._presign_client = boto3.client(
            "s3",
            endpoint_url=presign_endpoint,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            config=cfg,
            region_name="us-east-1",
        )

    # -- public API -----------------------------------------------------------

    def ensure_bucket(self) -> None:
        """Create the bucket if it does not exist."""
        import botocore.exceptions  # type: ignore[import]
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except botocore.exceptions.ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                print(f"[storage] bucket '{self._bucket}' not found, creating…")
                self._client.create_bucket(Bucket=self._bucket)
                print(f"[storage] bucket '{self._bucket}' created.")
            else:
                raise

    def generate_upload_url(self, key: str, content_type: str, expires: int = 900) -> str:
        url: str = self._presign_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires,
            HttpMethod="PUT",
        )
        return url

    def generate_download_url(self, key: str, expires: int = 300) -> str:
        url: str = self._presign_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires,
        )
        return url


# ── GCS ───────────────────────────────────────────────────────────────────────

class GcsStorage:
    """Google Cloud Storage using v4 signed URLs."""

    def __init__(self) -> None:
        from google.cloud import storage as gcs  # type: ignore[import]

        self._client = gcs.Client()
        self._bucket = self._client.bucket(GCS_BUCKET)

    def ensure_bucket(self) -> None:
        pass  # bucket is managed externally (Terraform / Cloud Console)

    def generate_upload_url(self, key: str, content_type: str, expires: int = 900) -> str:
        import datetime
        blob = self._bucket.blob(key)
        return blob.generate_signed_url(  # type: ignore[no-any-return]
            version="v4",
            expiration=datetime.timedelta(seconds=expires),
            method="PUT",
            content_type=content_type,
        )

    def generate_download_url(self, key: str, expires: int = 300) -> str:
        import datetime
        blob = self._bucket.blob(key)
        return blob.generate_signed_url(  # type: ignore[no-any-return]
            version="v4",
            expiration=datetime.timedelta(seconds=expires),
            method="GET",
        )


# ── Singleton factory ─────────────────────────────────────────────────────────

_storage: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    """Return the singleton storage backend, initialising it on first call."""
    global _storage
    if _storage is None:
        _storage = GcsStorage() if GCS_BUCKET else MinioStorage()
        try:
            _storage.ensure_bucket()
        except Exception as exc:
            # Non-fatal: presigned URL generation still works even when the
            # bucket doesn't exist yet (the client's upload will fail though).
            print(f"[storage] warn: ensure_bucket failed: {exc}")
    return _storage
