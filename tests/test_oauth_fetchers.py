"""Unit tests for the OAuth2 email fetchers (Gmail API, Yahoo XOAUTH2) and
the auth-method dispatcher.
"""

import base64
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.email_sources.fetcher import fetch_emails, resolve_auth_method
from src.ingestion.email_sources.gmail_client import fetch_recent_emails_gmail
from src.ingestion.email_sources.yahoo_oauth_client import (
    _xoauth2_string,
    fetch_recent_emails_yahoo,
)

# ---------------------------------------------------------------------------
# Gmail API fetcher
# ---------------------------------------------------------------------------

def _gmail_message(subject: str, sender: str, body: str) -> dict:
    encoded = base64.urlsafe_b64encode(body.encode()).decode()
    return {
        "id": "msg-1",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": sender},
                {"name": "Date", "value": "Mon, 01 Jan 2024 10:00:00 +0000"},
                {"name": "Message-ID", "value": "<g-1@example.com>"},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": encoded}},
                {
                    "mimeType": "text/html",
                    "body": {"data": base64.urlsafe_b64encode(b"<p>html</p>").decode()},
                },
            ],
        },
    }


def test_gmail_fetch_uses_api_and_parses():
    msg = _gmail_message("Budget Review", "boss@example.com", "Review the Q4 numbers.")

    messages_api = MagicMock()
    messages_api.list.return_value.execute.return_value = {"messages": [{"id": "msg-1"}]}
    messages_api.get.return_value.execute.return_value = msg

    service = MagicMock()
    service.users.return_value.messages.return_value = messages_api

    with (
        patch(
            "src.ingestion.email_sources.gmail_client.get_gmail_credentials",
            return_value=MagicMock(),
        ),
        patch("googleapiclient.discovery.build", return_value=service),
    ):
        emails = fetch_recent_emails_gmail(max_results=5)

    assert len(emails) == 1
    assert emails[0]["subject"] == "Budget Review"
    assert emails[0]["sender"] == "boss@example.com"
    assert "Q4 numbers" in emails[0]["body"]
    assert emails[0]["message_id"] == "<g-1@example.com>"

    messages_api.list.assert_called_once_with(
        userId="me", labelIds=["INBOX"], maxResults=5
    )


def test_gmail_fetch_maps_mailbox_to_label():
    messages_api = MagicMock()
    messages_api.list.return_value.execute.return_value = {"messages": []}
    service = MagicMock()
    service.users.return_value.messages.return_value = messages_api

    with (
        patch(
            "src.ingestion.email_sources.gmail_client.get_gmail_credentials",
            return_value=MagicMock(),
        ),
        patch("googleapiclient.discovery.build", return_value=service),
    ):
        fetch_recent_emails_gmail(max_results=3, mailbox="SENT")

    messages_api.list.assert_called_once_with(userId="me", labelIds=["SENT"], maxResults=3)


# ---------------------------------------------------------------------------
# Yahoo XOAUTH2 fetcher
# ---------------------------------------------------------------------------

def test_xoauth2_string_format():
    s = _xoauth2_string("me@yahoo.com", "tok123")
    assert s == "user=me@yahoo.com\x01auth=Bearer tok123\x01\x01"


def test_yahoo_oauth_fetch_uses_xoauth2():
    conn = MagicMock()
    parsed = [{"subject": "Hi", "sender": "a@b.com", "date": "", "body": "x", "message_id": "1"}]

    with (
        patch(
            "src.ingestion.email_sources.yahoo_oauth_client.get_yahoo_access_token",
            return_value="tok123",
        ),
        patch(
            "src.ingestion.email_sources.yahoo_oauth_client.get_yahoo_user_email",
            return_value="me@yahoo.com",
        ),
        patch(
            "src.ingestion.email_sources.yahoo_oauth_client.imaplib.IMAP4_SSL",
            return_value=conn,
        ),
        patch(
            "src.ingestion.email_sources.yahoo_oauth_client.iter_recent_messages",
            return_value=parsed,
        ) as iter_msgs,
    ):
        emails = fetch_recent_emails_yahoo(max_results=7, mailbox="INBOX")

    assert emails == parsed
    conn.authenticate.assert_called_once()
    assert conn.authenticate.call_args[0][0] == "XOAUTH2"
    auth_fn = conn.authenticate.call_args[0][1]
    assert auth_fn(None) == "user=me@yahoo.com\x01auth=Bearer tok123\x01\x01"
    iter_msgs.assert_called_once_with(conn, 7, "INBOX")
    conn.logout.assert_called_once()


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def test_resolve_auto_picks_oauth2_when_authorized():
    with (
        patch(
            "src.ingestion.email_sources.fetcher.oauth_configured", return_value=True
        ),
        patch(
            "src.ingestion.email_sources.fetcher.oauth_authorized", return_value=True
        ),
    ):
        assert resolve_auth_method("gmail", "auto") == "oauth2"


def test_resolve_auto_raises_when_configured_but_not_authorized():
    with (
        patch(
            "src.ingestion.email_sources.fetcher.oauth_configured", return_value=True
        ),
        patch(
            "src.ingestion.email_sources.fetcher.oauth_authorized", return_value=False
        ),
    ):
        with pytest.raises(RuntimeError, match="not authorized"):
            resolve_auth_method("gmail", "auto")


def test_resolve_auto_falls_back_to_app_password():
    with patch(
        "src.ingestion.email_sources.fetcher.oauth_configured", return_value=False
    ):
        assert resolve_auth_method("yahoo", "auto") == "app_password"


def test_resolve_explicit_oauth2_requires_config():
    with patch(
        "src.ingestion.email_sources.fetcher.oauth_configured", return_value=False
    ):
        with pytest.raises(RuntimeError, match="not configured"):
            resolve_auth_method("gmail", "oauth2")


def test_resolve_explicit_app_password_skips_oauth():
    with patch(
        "src.ingestion.email_sources.fetcher.oauth_configured", return_value=True
    ):
        assert resolve_auth_method("gmail", "app_password") == "app_password"


def test_fetch_emails_dispatches_to_oauth_fetcher():
    expected = [{"subject": "s", "sender": "s", "date": "", "body": "", "message_id": "1"}]
    mock_gmail = MagicMock(return_value=expected)

    with (
        patch(
            "src.ingestion.email_sources.fetcher.resolve_auth_method",
            return_value="oauth2",
        ),
        patch.dict(
            "src.ingestion.email_sources.fetcher._OAUTH_FETCHERS", {"gmail": mock_gmail}
        ),
    ):
        result = fetch_emails("gmail", max_results=5, auth_method="oauth2")

    assert result == expected
    mock_gmail.assert_called_once_with(max_results=5, mailbox="INBOX")


def test_fetch_emails_dispatches_to_imap_for_app_password():
    expected = [{"subject": "s", "sender": "s", "date": "", "body": "", "message_id": "1"}]
    mock_imap = MagicMock(return_value=expected)

    with (
        patch(
            "src.ingestion.email_sources.fetcher.resolve_auth_method",
            return_value="app_password",
        ),
        patch(
            "src.ingestion.email_sources.fetcher.fetch_recent_emails", mock_imap
        ),
    ):
        result = fetch_emails("yahoo", max_results=5, auth_method="app_password")

    assert result == expected
    mock_imap.assert_called_once_with(provider="yahoo", max_results=5, mailbox="INBOX")


def test_resolve_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        resolve_auth_method("outlook", "auto")
