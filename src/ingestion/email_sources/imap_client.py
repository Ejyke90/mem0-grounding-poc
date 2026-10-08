"""Shared email parsing + IMAP app-password fetcher for Gmail and Yahoo.

Both providers also support OAuth2 (see oauth_manager.py / gmail_client.py /
yahoo_oauth_client.py); this module is the app-password fallback used when
OAuth credentials are not configured.

App-password IMAP requires enabling the option in the provider:

  Gmail:  https://myaccount.google.com/apppasswords  (requires 2-Step Verification)
  Yahoo:  https://login.yahoo.com/account/security -> "Generate app password"

Credentials are read from environment variables only (see .env.example) and
are never accepted as tool/function arguments, so they can't leak into agent
conversation logs or MCP tool-call traces.
"""

from __future__ import annotations

import email
import imaplib
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime

from src.config import settings

PROVIDER_HOSTS = {
    "gmail": "imap.gmail.com",
    "yahoo": "imap.mail.yahoo.com",
}

_MAX_BODY_CHARS = 5000


def decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    return "".join(
        part.decode(encoding or "utf-8", errors="replace") if isinstance(part, bytes) else part
        for part, encoding in parts
    )


def extract_body(msg: Message) -> str:
    """Prefer text/plain, fall back to text/html, skipping attachments."""
    if msg.is_multipart():
        parts = list(msg.walk())
        for content_type in ("text/plain", "text/html"):
            for part in parts:
                if part.get_content_type() == content_type and not part.get("Content-Disposition"):
                    charset = part.get_content_charset() or "utf-8"
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(charset, errors="replace")
        return ""

    charset = msg.get_content_charset() or "utf-8"
    payload = msg.get_payload(decode=True)
    return payload.decode(charset, errors="replace") if payload else ""


def parse_raw_message(raw: bytes, fallback_id: str) -> dict:
    """Parse an RFC822 blob into the normalized email dict shape."""
    msg = email.message_from_bytes(raw)

    date_header = msg.get("Date")
    try:
        date_str = parsedate_to_datetime(date_header).isoformat() if date_header else ""
    except (TypeError, ValueError):
        date_str = date_header or ""

    return {
        "message_id": decode_header_value(msg.get("Message-ID")) or fallback_id,
        "subject": decode_header_value(msg.get("Subject")),
        "sender": decode_header_value(msg.get("From")),
        "date": date_str,
        "body": extract_body(msg)[:_MAX_BODY_CHARS],
    }


def iter_recent_messages(conn: imaplib.IMAP4, max_results: int, mailbox: str) -> list[dict]:
    """Select a mailbox read-only and fetch+parse the newest `max_results` messages."""
    conn.select(mailbox, readonly=True)

    _, data = conn.search(None, "ALL")
    all_ids = data[0].split()
    recent_ids = all_ids[-max_results:] if max_results else all_ids

    emails: list[dict] = []
    for msg_id in reversed(recent_ids):
        _, msg_data = conn.fetch(msg_id, "(RFC822)")
        emails.append(parse_raw_message(msg_data[0][1], msg_id.decode()))
    return emails


def _credentials_for(provider: str) -> tuple[str, str]:
    if provider == "gmail":
        username, app_password = settings.gmail_user, settings.gmail_app_password
    elif provider == "yahoo":
        username, app_password = settings.yahoo_user, settings.yahoo_app_password
    else:
        raise ValueError(f"Unsupported provider '{provider}'. Use 'gmail' or 'yahoo'.")

    if not username or not app_password:
        env_prefix = provider.upper()
        raise RuntimeError(
            f"Missing credentials for '{provider}'. Set {env_prefix}_USER and "
            f"{env_prefix}_APP_PASSWORD in your .env file (use an app password, "
            "not your account login password), or configure OAuth2 instead "
            "(see README.md)."
        )
    return username, app_password


def fetch_recent_emails(provider: str, max_results: int = 10, mailbox: str = "INBOX") -> list[dict]:
    """Fetch recent emails from Gmail or Yahoo over IMAP with an app password.

    Returns a list of dicts with keys: message_id, subject, sender, date, body.
    Connects read-only; nothing is deleted or marked as read.
    """
    host = PROVIDER_HOSTS.get(provider)
    if host is None:
        raise ValueError(f"Unsupported provider '{provider}'. Use 'gmail' or 'yahoo'.")

    username, app_password = _credentials_for(provider)

    with imaplib.IMAP4_SSL(host) as conn:
        conn.login(username, app_password)
        return iter_recent_messages(conn, max_results, mailbox)
