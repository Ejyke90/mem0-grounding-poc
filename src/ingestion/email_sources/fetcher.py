"""Provider/auth-method dispatcher for email fetching.

Auth selection logic (auth_method="auto", the default):

  - If OAuth2 is configured *and* a cached token exists -> use OAuth2.
  - If OAuth2 is configured but not yet authorized -> tell the caller how
    to run the one-time auth flow.
  - Otherwise -> fall back to IMAP app-password auth.
"""

from __future__ import annotations

from typing import Literal

from src.config import settings
from src.ingestion.email_sources.gmail_client import fetch_recent_emails_gmail
from src.ingestion.email_sources.imap_client import fetch_recent_emails
from src.ingestion.email_sources.oauth_manager import oauth_authorized, oauth_configured
from src.ingestion.email_sources.yahoo_oauth_client import fetch_recent_emails_yahoo

AuthMethod = Literal["auto", "oauth2", "app_password"]
Provider = Literal["gmail", "yahoo"]

_OAUTH_FETCHERS = {
    "gmail": fetch_recent_emails_gmail,
    "yahoo": fetch_recent_emails_yahoo,
}


def resolve_auth_method(provider: Provider, auth_method: AuthMethod = "auto") -> str:
    """Decide which auth mechanism to use for a provider."""
    if provider not in ("gmail", "yahoo"):
        raise ValueError(f"Unsupported provider '{provider}'. Use 'gmail' or 'yahoo'.")

    if auth_method not in ("auto", "oauth2", "app_password"):
        raise ValueError(
            f"Invalid auth_method '{auth_method}'. Use 'auto', 'oauth2', or 'app_password'."
        )

    if auth_method != "auto":
        if auth_method == "oauth2" and not oauth_configured(provider):
            raise RuntimeError(
                f"OAuth2 requested for '{provider}' but not configured. Set the "
                f"{provider.upper()} client ID/secret env vars (see .env.example)."
            )
        return auth_method

    if oauth_configured(provider) and oauth_authorized(provider):
        return "oauth2"
    if oauth_configured(provider):
        raise RuntimeError(
            f"OAuth2 is configured for '{provider}' but not authorized. Run once: "
            f"python -m src.ingestion.email_sources.oauth_flow --provider {provider}"
        )
    return "app_password"


def fetch_emails(
    provider: Provider,
    max_results: int = 10,
    mailbox: str = "INBOX",
    auth_method: AuthMethod | None = None,
) -> list[dict]:
    """Fetch recent emails from Gmail or Yahoo, choosing the best auth method.

    auth_method defaults to the EMAIL_AUTH_METHOD env var ("auto" if unset).
    """
    method = resolve_auth_method(provider, auth_method or settings.email_auth_method)
    if method == "oauth2":
        return _OAUTH_FETCHERS[provider](max_results=max_results, mailbox=mailbox)
    return fetch_recent_emails(provider=provider, max_results=max_results, mailbox=mailbox)
