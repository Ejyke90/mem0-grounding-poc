"""Email source fetchers: Gmail and Yahoo via OAuth2 (primary) or IMAP
app-password (fallback). `fetch_emails` picks the right path automatically.
"""

from src.ingestion.email_sources.fetcher import fetch_emails

__all__ = ["fetch_emails"]
