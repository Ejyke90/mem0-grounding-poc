"""Unit tests for the OAuth2 token manager. Token files are written to a
pytest tmp_path; HTTP calls to Yahoo are mocked.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

import src.ingestion.email_sources.oauth_manager as oauth


@pytest.fixture(autouse=True)
def _tmp_token_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("src.config.settings.oauth_token_dir", str(tmp_path / "tokens"))
    yield


def _save_token(provider: str, token: dict):
    path = oauth._token_dir() / f"{provider}.json"
    path.write_text(json.dumps(token))


def test_oauth_configured_gmail(monkeypatch):
    monkeypatch.setattr("src.config.settings.google_client_id", "")
    monkeypatch.setattr("src.config.settings.google_client_secret", "")
    monkeypatch.setattr("src.config.settings.google_client_secrets_file", "")
    assert not oauth.oauth_configured("gmail")

    monkeypatch.setattr("src.config.settings.google_client_id", "id")
    monkeypatch.setattr("src.config.settings.google_client_secret", "secret")
    assert oauth.oauth_configured("gmail")


def test_oauth_configured_yahoo(monkeypatch):
    monkeypatch.setattr("src.config.settings.yahoo_client_id", "")
    monkeypatch.setattr("src.config.settings.yahoo_client_secret", "")
    assert not oauth.oauth_configured("yahoo")

    monkeypatch.setattr("src.config.settings.yahoo_client_id", "id")
    monkeypatch.setattr("src.config.settings.yahoo_client_secret", "secret")
    assert oauth.oauth_configured("yahoo")


def test_oauth_authorized_requires_token_file():
    assert not oauth.oauth_authorized("gmail")
    _save_token("gmail", {"access_token": "x"})
    assert oauth.oauth_authorized("gmail")


def test_get_gmail_credentials_requires_config(monkeypatch):
    monkeypatch.setattr("src.config.settings.google_client_id", "")
    monkeypatch.setattr("src.config.settings.google_client_secret", "")
    monkeypatch.setattr("src.config.settings.google_client_secrets_file", "")
    with pytest.raises(RuntimeError, match="not configured"):
        oauth.get_gmail_credentials()


def test_get_gmail_credentials_requires_authorization(monkeypatch):
    monkeypatch.setattr("src.config.settings.google_client_id", "id")
    monkeypatch.setattr("src.config.settings.google_client_secret", "secret")
    monkeypatch.setattr("src.config.settings.google_client_secrets_file", "")
    with pytest.raises(RuntimeError, match="not been authorized"):
        oauth.get_gmail_credentials()


def test_yahoo_access_token_returned_when_valid(monkeypatch):
    monkeypatch.setattr("src.config.settings.yahoo_client_id", "id")
    monkeypatch.setattr("src.config.settings.yahoo_client_secret", "secret")
    _save_token(
        "yahoo",
        {
            "access_token": "valid-token",
            "refresh_token": "refresh",
            "expires_at": time.time() + 3600,
        },
    )
    assert oauth.get_yahoo_access_token() == "valid-token"


def test_yahoo_access_token_refreshes_when_expired(monkeypatch):
    monkeypatch.setattr("src.config.settings.yahoo_client_id", "id")
    monkeypatch.setattr("src.config.settings.yahoo_client_secret", "secret")
    monkeypatch.setattr("src.config.settings.yahoo_redirect_uri", "http://localhost:8765/callback")
    _save_token(
        "yahoo",
        {
            "access_token": "old-token",
            "refresh_token": "refresh-me",
            "expires_at": time.time() - 10,
        },
    )

    resp = MagicMock()
    resp.json.return_value = {
        "access_token": "new-token",
        "refresh_token": "new-refresh",
        "expires_in": 3600,
    }
    resp.raise_for_status = MagicMock()

    with patch("src.ingestion.email_sources.oauth_manager.httpx.post", return_value=resp) as post:
        token = oauth.get_yahoo_access_token()

    assert token == "new-token"
    post.assert_called_once()
    assert post.call_args.kwargs["data"]["grant_type"] == "refresh_token"
    assert post.call_args.kwargs["data"]["refresh_token"] == "refresh-me"
    assert post.call_args.kwargs["headers"]["Authorization"].startswith("Basic ")

    saved = json.loads(oauth._token_path("yahoo").read_text())
    assert saved["access_token"] == "new-token"
    assert saved["refresh_token"] == "new-refresh"


def test_yahoo_access_token_raises_without_cached_token(monkeypatch):
    monkeypatch.setattr("src.config.settings.yahoo_client_id", "id")
    monkeypatch.setattr("src.config.settings.yahoo_client_secret", "secret")
    with pytest.raises(RuntimeError, match="not been authorized"):
        oauth.get_yahoo_access_token()


def test_yahoo_user_email_falls_back_to_env(monkeypatch):
    monkeypatch.setattr("src.config.settings.yahoo_user", "me@yahoo.com")

    resp = MagicMock()
    resp.status_code = 401

    with (
        patch(
            "src.ingestion.email_sources.oauth_manager.get_yahoo_access_token",
            return_value="tok",
        ),
        patch(
            "src.ingestion.email_sources.oauth_manager.httpx.get", return_value=resp
        ),
    ):
        assert oauth.get_yahoo_user_email() == "me@yahoo.com"


def test_yahoo_user_email_from_userinfo(monkeypatch):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"email": "real@yahoo.com"}

    with (
        patch(
            "src.ingestion.email_sources.oauth_manager.get_yahoo_access_token",
            return_value="tok",
        ),
        patch(
            "src.ingestion.email_sources.oauth_manager.httpx.get", return_value=resp
        ),
    ):
        assert oauth.get_yahoo_user_email() == "real@yahoo.com"
