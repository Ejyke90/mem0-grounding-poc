"""Yahoo Mail fetcher using OAuth2 (XOAUTH2 over IMAP).

Yahoo supports OAuth-authenticated IMAP via the XOAUTH2 SASL mechanism on
imap.mail.yahoo.com:993, provided the app was registered with the "Mail
Read" scope (mail-r). The token itself is managed by oauth_manager.py.

One-time setup:
    python -m src.ingestion.email_sources.oauth_flow --provider yahoo
"""

from __future__ import annotations

import imaplib

from src.ingestion.email_sources.imap_client import PROVIDER_HOSTS, iter_recent_messages
from src.ingestion.email_sources.oauth_manager import (
    get_yahoo_access_token,
    get_yahoo_user_email,
)


def _xoauth2_string(user: str, access_token: str) -> str:
    return f"user={user}\x01auth=Bearer {access_token}\x01\x01"


def fetch_recent_emails_yahoo(max_results: int = 10, mailbox: str = "INBOX") -> list[dict]:
    """Fetch recent emails from Yahoo over IMAP using an OAuth2 access token.

    Returns dicts with keys: message_id, subject, sender, date, body
    (same shape as the other fetchers).
    """
    access_token = get_yahoo_access_token()
    user_email = get_yahoo_user_email()

    conn = imaplib.IMAP4_SSL(PROVIDER_HOSTS["yahoo"])
    try:
        conn.authenticate("XOAUTH2", lambda _: _xoauth2_string(user_email, access_token))
        return iter_recent_messages(conn, max_results, mailbox)
    finally:
        try:
            conn.close()
            conn.logout()
        except Exception:
            pass
