"""Email ingestion endpoints: fetch -> object storage archive -> Mem0.

REST counterpart to the tools exposed in src/mcp_server/server.py, useful
for testing the pipeline without an MCP client.

Auth defaults to OAuth2 when configured (Gmail API / Yahoo XOAUTH2), falling
back to IMAP app passwords.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.ingestion.adapters import ingest_email
from src.ingestion.email_sources import fetch_emails
from src.storage.object_store import list_archived_emails, upload_email_archive

router = APIRouter(prefix="/email", tags=["email"])


class SyncMailboxRequest(BaseModel):
    provider: Literal["gmail", "yahoo"]
    user_id: str = "demo-user"
    max_results: int = 10
    archive: bool = True
    auth_method: Literal["auto", "oauth2", "app_password"] = "auto"


@router.post("/sync")
async def sync_mailbox(request: SyncMailboxRequest) -> dict:
    """Fetch recent emails, archive them to object storage, and ingest into Mem0."""
    try:
        emails = fetch_emails(
            provider=request.provider,
            max_results=request.max_results,
            auth_method=request.auth_method,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    archived_keys = (
        [upload_email_archive(request.user_id, e) for e in emails] if request.archive else []
    )
    ingested = [
        ingest_email(request.user_id, e["subject"], e["sender"], e["body"], e["date"])
        for e in emails
    ]

    return {
        "provider": request.provider,
        "fetched": len(emails),
        "archived": len(archived_keys),
        "ingested": len(ingested),
    }


@router.get("/archive/{user_id}")
async def list_archive(user_id: str) -> dict:
    """List object storage keys for a user's archived emails."""
    keys = list_archived_emails(user_id)
    return {"user_id": user_id, "count": len(keys), "keys": keys}
