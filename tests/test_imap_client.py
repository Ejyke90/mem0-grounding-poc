"""Unit tests for the IMAP email fetcher. Mocks imaplib so no real mailbox
or network access is required.
"""

from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.email_sources.imap_client import (
    PROVIDER_HOSTS,
    _extract_body,
    fetch_recent_emails,
)


def _make_raw_email(subject: str, sender: str, body: str) -> bytes:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Date"] = "Mon, 01 Jan 2024 10:00:00 +0000"
    msg["Message-ID"] = "<test-123@example.com>"
    msg.set_content(body)
    return bytes(msg)


def test_provider_hosts_cover_gmail_and_yahoo():
    assert PROVIDER_HOSTS["gmail"] == "imap.gmail.com"
    assert PROVIDER_HOSTS["yahoo"] == "imap.mail.yahoo.com"


def test_fetch_recent_emails_unsupported_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        fetch_recent_emails(provider="outlook")


def test_fetch_recent_emails_missing_credentials(monkeypatch):
    monkeypatch.setattr("src.config.settings.gmail_user", "")
    monkeypatch.setattr("src.config.settings.gmail_app_password", "")
    with pytest.raises(RuntimeError, match="Missing credentials"):
        fetch_recent_emails(provider="gmail")


def test_fetch_recent_emails_parses_messages(monkeypatch):
    monkeypatch.setattr("src.config.settings.gmail_user", "test@gmail.com")
    monkeypatch.setattr("src.config.settings.gmail_app_password", "app-password")

    raw = _make_raw_email("Budget Review", "boss@example.com", "Please review the Q4 numbers.")

    mock_conn = MagicMock()
    mock_conn.search.return_value = ("OK", [b"1"])
    mock_conn.fetch.return_value = ("OK", [(b"1", raw)])
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = False

    with patch("src.ingestion.email_sources.imap_client.imaplib.IMAP4_SSL", return_value=mock_conn):
        emails = fetch_recent_emails(provider="gmail", max_results=5)

    assert len(emails) == 1
    assert emails[0]["subject"] == "Budget Review"
    assert emails[0]["sender"] == "boss@example.com"
    assert "Q4 numbers" in emails[0]["body"]
    assert emails[0]["message_id"] == "<test-123@example.com>"

    mock_conn.login.assert_called_once_with("test@gmail.com", "app-password")
    mock_conn.select.assert_called_once_with("INBOX", readonly=True)


def test_extract_body_prefers_plain_text():
    msg = EmailMessage()
    msg.set_content("plain text body")
    msg.add_alternative("<p>html body</p>", subtype="html")
    assert "plain text body" in _extract_body(msg)
