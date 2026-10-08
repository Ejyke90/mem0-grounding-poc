"""OAuth2 token manager for Gmail and Yahoo.

Handles the two OAuth flows and caches access/refresh tokens on disk under
``settings.oauth_token_dir`` (gitignored). After the first interactive auth
run, all fetches are non-interactive: expired tokens are refreshed silently.

Setup (one time, per provider):

  Gmail:  Google Cloud Console -> APIs & Services -> OAuth consent screen
          -> Credentials -> "Create OAuth client ID", type "Desktop app".
          Put the client ID + secret in .env (GOOGLE_CLIENT_ID /
          GOOGLE_CLIENT_SECRET), or download client_secrets.json and set
          GOOGLE_CLIENT_SECRETS_FILE.

  Yahoo:  Yahoo Developer Network -> "Create App", enable Mail with the
          "Read" scope (mail-r), set redirect URI to
          http://localhost:8765/callback (or use "oob" and paste the code).
          Put YAHOO_CLIENT_ID / YAHOO_CLIENT_SECRET in .env.

Run the interactive auth once per provider:

  python -m src.ingestion.email_sources.oauth_flow --provider gmail
  python -m src.ingestion.email_sources.oauth_flow --provider yahoo
"""

from __future__ import annotations

import base64
import json
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from src.config import settings

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

YAHOO_AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_USERINFO_URL = "https://api.login.yahoo.com/openid/v1/userinfo"
YAHOO_SCOPES = "mail-r openid email"


# ---------------------------------------------------------------------------
# Token storage
# ---------------------------------------------------------------------------

def _token_dir() -> Path:
    path = Path(settings.oauth_token_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _token_path(provider: str) -> Path:
    return _token_dir() / f"{provider}.json"


def _load_token(provider: str) -> dict | None:
    path = _token_path(provider)
    if path.exists():
        return json.loads(path.read_text())
    return None


def _save_token(provider: str, data: dict) -> None:
    _token_path(provider).write_text(json.dumps(data, indent=2))


def oauth_configured(provider: str) -> bool:
    """True if OAuth credentials are configured for this provider."""
    if provider == "gmail":
        return bool(
            settings.google_client_secrets_file
            or (settings.google_client_id and settings.google_client_secret)
        )
    if provider == "yahoo":
        return bool(settings.yahoo_client_id and settings.yahoo_client_secret)
    return False


def oauth_authorized(provider: str) -> bool:
    """True if a cached token already exists (auth flow has been run once)."""
    return _token_path(provider).exists()


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------

def get_gmail_credentials():
    """Return valid Google OAuth credentials, refreshing if expired.

    Raises RuntimeError with setup instructions if not configured/authorized.
    """
    if not oauth_configured("gmail"):
        raise RuntimeError(
            "Gmail OAuth is not configured. Set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET (or GOOGLE_CLIENT_SECRETS_FILE) in .env. "
            "Create them at Google Cloud Console -> Credentials -> OAuth "
            "client ID (type: Desktop app)."
        )

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token_path = _token_path("gmail")
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)

    if creds is None:
        raise RuntimeError(
            "Gmail OAuth has not been authorized yet. Run once: "
            "python -m src.ingestion.email_sources.oauth_flow --provider gmail"
        )

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
        else:
            raise RuntimeError(
                "Gmail token is invalid and cannot be refreshed. Re-run: "
                "python -m src.ingestion.email_sources.oauth_flow --provider gmail"
            )
    return creds


def run_gmail_oauth_flow() -> None:
    """Interactive Gmail auth: opens a browser, runs a local callback server,
    and caches the token. Run this once from a terminal."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    secrets_file = settings.google_client_secrets_file
    if secrets_file:
        flow = InstalledAppFlow.from_client_secrets_file(secrets_file, GMAIL_SCOPES)
    else:
        client_config = {
            "installed": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, GMAIL_SCOPES)

    creds = flow.run_local_server(port=0)
    _save_token("gmail", json.loads(creds.to_json()))
    print(f"Gmail authorized. Token saved to {_token_path('gmail')}")


# ---------------------------------------------------------------------------
# Yahoo
# ---------------------------------------------------------------------------

class _YahooCallbackHandler(BaseHTTPRequestHandler):
    """Captures ?code=... from the Yahoo redirect on the local server."""

    auth_code: str | None = None
    state: str | None = None

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        code = query.get("code", [None])[0]
        state = query.get("state", [None])[0]
        if code:
            _YahooCallbackHandler.auth_code = code
            _YahooCallbackHandler.state = state
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Yahoo auth complete. You can close this tab.")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing ?code= in callback.")

    def log_message(self, *args):  # silence request logs
        pass


def _yahoo_basic_auth() -> dict:
    cred = f"{settings.yahoo_client_id}:{settings.yahoo_client_secret}"
    return {"Authorization": f"Basic {base64.b64encode(cred.encode()).decode()}"}


def _exchange_yahoo_code(code: str) -> dict:
    resp = httpx.post(
        YAHOO_TOKEN_URL,
        headers=_yahoo_basic_auth(),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.yahoo_redirect_uri,
        },
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json()
    token["expires_at"] = time.time() + int(token.get("expires_in", 3600))
    return token


def run_yahoo_oauth_flow() -> None:
    """Interactive Yahoo auth: prints/opens the consent URL, waits for the
    local redirect (or accepts a pasted code for 'oob' setups), then caches
    the token. Run this once from a terminal."""
    if not oauth_configured("yahoo"):
        raise RuntimeError(
            "Yahoo OAuth is not configured. Set YAHOO_CLIENT_ID and "
            "YAHOO_CLIENT_SECRET in .env (Yahoo Developer Network app with "
            "mail-r scope)."
        )

    state = secrets.token_urlsafe(16)
    auth_params = {
        "client_id": settings.yahoo_client_id,
        "redirect_uri": settings.yahoo_redirect_uri,
        "response_type": "code",
        "scope": YAHOO_SCOPES,
        "state": state,
    }
    auth_url = f"{YAHOO_AUTH_URL}?{urlencode(auth_params)}"

    code: str | None = None
    if settings.yahoo_redirect_uri == "oob":
        print(f"Open this URL in your browser:\n\n{auth_url}\n")
        code = input("Paste the authorization code Yahoo shows: ").strip()
    else:
        parsed = urlparse(settings.yahoo_redirect_uri)
        port = parsed.port or 8765
        server = HTTPServer(("localhost", port), _YahooCallbackHandler)
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()

        print(f"Opening browser for Yahoo auth...\n{auth_url}\n")
        webbrowser.open(auth_url)
        thread.join(timeout=300)
        server.server_close()
        code = _YahooCallbackHandler.auth_code

        if not code:
            raise RuntimeError(
                "Timed out waiting for Yahoo redirect. If your Yahoo app uses "
                "'oob' as the redirect URI, set YAHOO_REDIRECT_URI=oob and "
                "re-run; Yahoo will show a code to paste."
            )
        if _YahooCallbackHandler.state != state:
            raise RuntimeError("State mismatch in Yahoo OAuth callback (possible CSRF). Aborting.")

    token = _exchange_yahoo_code(code)
    _save_token("yahoo", token)
    print(f"Yahoo authorized. Token saved to {_token_path('yahoo')}")


def get_yahoo_access_token() -> str:
    """Return a valid Yahoo access token, refreshing if expired."""
    if not oauth_configured("yahoo"):
        raise RuntimeError(
            "Yahoo OAuth is not configured. Set YAHOO_CLIENT_ID and "
            "YAHOO_CLIENT_SECRET in .env."
        )

    token = _load_token("yahoo")
    if token is None:
        raise RuntimeError(
            "Yahoo OAuth has not been authorized yet. Run once: "
            "python -m src.ingestion.email_sources.oauth_flow --provider yahoo"
        )

    if time.time() < token.get("expires_at", 0) - 60:
        return token["access_token"]

    if not token.get("refresh_token"):
        raise RuntimeError(
            "Yahoo token expired with no refresh token. Re-run: "
            "python -m src.ingestion.email_sources.oauth_flow --provider yahoo"
        )

    resp = httpx.post(
        YAHOO_TOKEN_URL,
        headers=_yahoo_basic_auth(),
        data={
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
            "redirect_uri": settings.yahoo_redirect_uri,
        },
        timeout=30,
    )
    resp.raise_for_status()
    new_token = resp.json()
    new_token["expires_at"] = time.time() + int(new_token.get("expires_in", 3600))
    if "refresh_token" not in new_token:
        new_token["refresh_token"] = token["refresh_token"]
    _save_token("yahoo", new_token)
    return new_token["access_token"]


def get_yahoo_user_email() -> str:
    """Get the authenticated Yahoo user's email via the userinfo endpoint.

    Falls back to the YAHOO_USER env var if the token lacks openid/email scope.
    """
    token = get_yahoo_access_token()
    resp = httpx.get(
        YAHOO_USERINFO_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code == 200:
        email = resp.json().get("email")
        if email:
            return email

    if settings.yahoo_user:
        return settings.yahoo_user
    raise RuntimeError(
        "Could not determine Yahoo mailbox address. Either grant the token "
        "openid+email scopes or set YAHOO_USER in .env."
    )
