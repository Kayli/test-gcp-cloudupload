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
    """Google Cloud Storage using v4 signed URLs.

    On Cloud Run / GCE the default credentials are short-lived tokens with no
    private key, so blob.generate_signed_url() fails with "you need a private
    key".  We work around this by building an IAM-backed signer: the Cloud Run
    service account calls the IAM SignBlob API on behalf of itself, which works
    as long as it has roles/iam.serviceAccountTokenCreator on itself (granted in
    wif.tf via google_service_account_iam_member.api_self_sign).
    """

    def __init__(self) -> None:
        import google.auth  # type: ignore[import]
        import google.auth.transport.requests  # type: ignore[import]
        from google.auth import iam as google_iam  # type: ignore[import]
        from google.oauth2 import service_account  # type: ignore[import]
        from google.cloud import storage as gcs  # type: ignore[import]

        _GCS_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

        credentials, _ = google.auth.default(scopes=_GCS_SCOPES)

        # Detect token-only credentials (Compute Engine / Cloud Run metadata
        # server) and replace them with IAM-backed signing credentials.
        if not getattr(credentials, "service_account_email", None) or \
                getattr(credentials, "_signer", None) is None:
            # Resolve the SA email: env var wins, then ADC attribute, then
            # the GCE metadata server.
            sa_email = os.getenv("GCS_SERVICE_ACCOUNT", "") or \
                       getattr(credentials, "service_account_email", "")
            # Compute Engine credentials expose "default" as a placeholder —
            # treat it the same as missing and resolve via the metadata server.
            if not sa_email or sa_email == "default":
                import urllib.request
                _meta_url = (
                    "http://metadata.google.internal/computeMetadata/v1"
                    "/instance/service-accounts/default/email"
                )
                req = urllib.request.Request(
                    _meta_url, headers={"Metadata-Flavor": "Google"}
                )
                with urllib.request.urlopen(req, timeout=2) as resp:
                    sa_email = resp.read().decode()

            auth_req = google.auth.transport.requests.Request()
            credentials.refresh(auth_req)

            signer = google_iam.Signer(auth_req, credentials, sa_email)
            credentials = service_account.Credentials(
                signer=signer,
                service_account_email=sa_email,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=_GCS_SCOPES,
            )

        self._client = gcs.Client(credentials=credentials)
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
