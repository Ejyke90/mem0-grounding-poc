"""Free S3-compatible object storage for archiving raw ingested data.

Works with any S3-compatible provider that offers a free tier:

  Cloudflare R2  https://dash.cloudflare.com -> R2  (10 GB storage, zero egress)
  Backblaze B2   https://www.backblaze.com/b2       (10 GB storage)
  MinIO          self-hosted, unlimited (good for local dev)

Only `boto3` is required since all three speak the S3 API. Configure via
OBJECT_STORAGE_* environment variables (see .env.example). Raw emails are
archived as JSON so the original source data survives independently of
whatever Mem0 extracts from it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256

import boto3
from botocore.config import Config as BotoConfig

from src.config import settings


@lru_cache(maxsize=1)
def _client():
    if not settings.object_storage_endpoint_url or not settings.object_storage_bucket:
        raise RuntimeError(
            "Object storage is not configured. Set OBJECT_STORAGE_ENDPOINT_URL, "
            "OBJECT_STORAGE_ACCESS_KEY, OBJECT_STORAGE_SECRET_KEY, and "
            "OBJECT_STORAGE_BUCKET in your .env file. See README.md for free-tier "
            "setup instructions (Cloudflare R2 or Backblaze B2)."
        )
    return boto3.client(
        "s3",
        endpoint_url=settings.object_storage_endpoint_url,
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key,
        region_name=settings.object_storage_region,
        config=BotoConfig(signature_version="s3v4"),
    )


def _object_key(user_id: str, unique_part: str) -> str:
    digest = sha256(unique_part.encode()).hexdigest()[:16]
    return f"emails/{user_id}/{digest}.json"


def upload_email_archive(user_id: str, email_data: dict) -> str:
    """Upload a raw email as a JSON object. Returns the object key.

    Idempotent: the key is derived from the email's message_id, so re-syncing
    the same mailbox overwrites rather than duplicates.
    """
    unique_part = email_data.get("message_id") or email_data.get("subject", "")
    key = _object_key(user_id, unique_part)
    body = json.dumps(
        {**email_data, "archived_at": datetime.now(timezone.utc).isoformat()}
    ).encode("utf-8")

    _client().put_object(
        Bucket=settings.object_storage_bucket,
        Key=key,
        Body=body,
        ContentType="application/json",
    )
    return key


def list_archived_emails(user_id: str) -> list[str]:
    """List archived email object keys for a user."""
    prefix = f"emails/{user_id}/"
    resp = _client().list_objects_v2(Bucket=settings.object_storage_bucket, Prefix=prefix)
    return [obj["Key"] for obj in resp.get("Contents", [])]


def download_email_archive(key: str) -> dict:
    """Download and parse an archived email by its object key."""
    resp = _client().get_object(Bucket=settings.object_storage_bucket, Key=key)
    return json.loads(resp["Body"].read())
