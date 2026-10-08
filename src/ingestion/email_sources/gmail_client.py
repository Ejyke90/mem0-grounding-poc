"""Gmail API fetcher using OAuth2 credentials.

Uses the official Google API client (gmail.users.messages.list + .get) rather
than IMAP, so no app passwords are involved. Credentials come from the OAuth
token cache managed by oauth_manager.py.

One-time setup:
    python -m src.ingestion.email_sources.oauth_flow --provider gmail
"""

from __future__ import annotations

import base64

from src.ingestion.email_sources.imap_client import decode_header_value
from src.ingestion.email_sources.oauth_manager import get_gmail_credentials

_MAX_BODY_CHARS = 5000

# Map IMAP-style mailbox names to Gmail label IDs
_MAILBOX_LABELS = {
    "INBOX": "INBOX",
    "SENT": "SENT",
    "DRAFT": "DRAFT",
    "SPAM": "SPAM",
    "TRASH": "TRASH",
}


def _decode_body_part(part: dict) -> str:
    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def _extract_body(payload: dict) -> str:
    """Walk a Gmail message payload, preferring text/plain over text/html."""
    mime = payload.get("mimeType", "")

    if mime == "text/plain":
        return _decode_body_part(payload)

    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            return _decode_body_part(part)

    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/html":
            return _decode_body_part(part)

    if mime == "text/html":
        return _decode_body_part(payload)

    return ""


def _headers_to_dict(headers: list[dict]) -> dict:
    return {h["name"].lower(): h["value"] for h in headers}


def fetch_recent_emails_gmail(max_results: int = 10, mailbox: str = "INBOX") -> list[dict]:
    """Fetch recent emails via the Gmail API.

    Returns dicts with keys: message_id, subject, sender, date, body
    (same shape as the IMAP fetcher, so downstream adapters don't care).
    """
    from googleapiclient.discovery import build

    creds = get_gmail_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    label_id = _MAILBOX_LABELS.get(mailbox.upper(), mailbox)
    listed = (
        service.users()
        .messages()
        .list(userId="me", labelIds=[label_id], maxResults=max_results)
        .execute()
    )

    emails: list[dict] = []
    for ref in listed.get("messages", []):
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=ref["id"], format="full")
            .execute()
        )
        headers = _headers_to_dict(msg.get("payload", {}).get("headers", []))
        emails.append(
            {
                "message_id": headers.get("message-id", ref["id"]),
                "subject": decode_header_value(headers.get("subject")),
                "sender": decode_header_value(headers.get("from")),
                "date": headers.get("date", ""),
                "body": _extract_body(msg.get("payload", {}))[:_MAX_BODY_CHARS],
            }
        )
    return emails
