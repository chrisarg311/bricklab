"""
Storage helpers — S3 in production, local filesystem fallback when
S3_BUCKET env var is not set (enables Docker Compose dev without AWS creds).

Local mode writes files under LOCAL_STORAGE_DIR (default /app/storage),
which should be a named Docker volume shared between fastapi and worker.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from functools import lru_cache

log = logging.getLogger(__name__)

S3_BUCKET = os.environ.get("S3_BUCKET", "").strip()
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", "").strip() or None
LOCAL_STORAGE_DIR = Path(os.environ.get("LOCAL_STORAGE_DIR", "/app/storage"))

_using_s3 = bool(S3_BUCKET)

if _using_s3:
    log.info("Storage: S3 bucket '%s' (region %s)", S3_BUCKET, AWS_REGION)
else:
    log.info("Storage: local filesystem at %s", LOCAL_STORAGE_DIR)
    LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def _s3_client():
    import boto3
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        endpoint_url=AWS_ENDPOINT_URL,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload_bytes(data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    """Upload raw bytes under *key*.  Returns the key."""
    if _using_s3:
        _s3_client().put_object(
            Bucket=S3_BUCKET, Key=key, Body=data, ContentType=content_type
        )
    else:
        dest = LOCAL_STORAGE_DIR / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return key


def download_to_path(key: str, local_path: Path) -> Path:
    """Download the object at *key* to *local_path*.  Returns local_path."""
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if _using_s3:
        _s3_client().download_file(S3_BUCKET, key, str(local_path))
    else:
        src = LOCAL_STORAGE_DIR / key
        shutil.copy2(src, local_path)
    return local_path


def read_bytes(key: str) -> bytes:
    """Return the raw bytes stored at *key*."""
    if _using_s3:
        resp = _s3_client().get_object(Bucket=S3_BUCKET, Key=key)
        return resp["Body"].read()
    return (LOCAL_STORAGE_DIR / key).read_bytes()


def presign_url(key: str, expires_in: int = 3600) -> str:
    """
    Return a URL that grants temporary read access to *key*.

    In S3 mode: a real pre-signed URL valid for *expires_in* seconds.
    In local mode: a path under /api/storage/ that the Next.js proxy can serve
    (not yet implemented — returns a placeholder for Phase 1).
    """
    if _using_s3:
        return _s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=expires_in,
        )
    # Local fallback: return the relative key so the frontend can request it
    # from a future /api/storage/{key} route.  For now thumbnails are embedded
    # as base64 in the result payload instead.
    return f"/__local_storage__/{key}"
