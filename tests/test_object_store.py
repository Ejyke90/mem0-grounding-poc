"""Unit tests for the S3-compatible object storage client. Mocks boto3 so no
real bucket or network access is required.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import src.storage.object_store as object_store


@pytest.fixture(autouse=True)
def _clear_client_cache():
    object_store._client.cache_clear()
    yield
    object_store._client.cache_clear()


def test_client_requires_configuration(monkeypatch):
    monkeypatch.setattr("src.config.settings.object_storage_endpoint_url", "")
    monkeypatch.setattr("src.config.settings.object_storage_bucket", "")
    with pytest.raises(RuntimeError, match="Object storage is not configured"):
        object_store.upload_email_archive("user-1", {"message_id": "abc", "subject": "Hi"})


def test_upload_email_archive_builds_key_and_uploads(monkeypatch):
    monkeypatch.setattr("src.config.settings.object_storage_endpoint_url", "https://fake.r2.cloudflarestorage.com")
    monkeypatch.setattr("src.config.settings.object_storage_access_key", "key")
    monkeypatch.setattr("src.config.settings.object_storage_secret_key", "secret")
    monkeypatch.setattr("src.config.settings.object_storage_bucket", "test-bucket")
    monkeypatch.setattr("src.config.settings.object_storage_region", "auto")

    mock_client = MagicMock()
    with patch("src.storage.object_store.boto3.client", return_value=mock_client):
        key = object_store.upload_email_archive(
            "user-1", {"message_id": "<abc@example.com>", "subject": "Hi", "body": "Hello"}
        )

    assert key.startswith("emails/user-1/")
    assert key.endswith(".json")

    mock_client.put_object.assert_called_once()
    call_kwargs = mock_client.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "test-bucket"
    assert call_kwargs["Key"] == key
    body = json.loads(call_kwargs["Body"])
    assert body["subject"] == "Hi"
    assert "archived_at" in body


def test_upload_email_archive_is_idempotent_per_message_id(monkeypatch):
    monkeypatch.setattr("src.config.settings.object_storage_endpoint_url", "https://fake.r2.cloudflarestorage.com")
    monkeypatch.setattr("src.config.settings.object_storage_access_key", "key")
    monkeypatch.setattr("src.config.settings.object_storage_secret_key", "secret")
    monkeypatch.setattr("src.config.settings.object_storage_bucket", "test-bucket")
    monkeypatch.setattr("src.config.settings.object_storage_region", "auto")

    mock_client = MagicMock()
    with patch("src.storage.object_store.boto3.client", return_value=mock_client):
        key1 = object_store.upload_email_archive(
            "user-1", {"message_id": "same-id", "subject": "A"}
        )
        key2 = object_store.upload_email_archive(
            "user-1", {"message_id": "same-id", "subject": "B"}
        )

    assert key1 == key2


def test_list_archived_emails(monkeypatch):
    monkeypatch.setattr("src.config.settings.object_storage_endpoint_url", "https://fake.r2.cloudflarestorage.com")
    monkeypatch.setattr("src.config.settings.object_storage_access_key", "key")
    monkeypatch.setattr("src.config.settings.object_storage_secret_key", "secret")
    monkeypatch.setattr("src.config.settings.object_storage_bucket", "test-bucket")
    monkeypatch.setattr("src.config.settings.object_storage_region", "auto")

    mock_client = MagicMock()
    mock_client.list_objects_v2.return_value = {
        "Contents": [{"Key": "emails/user-1/abc.json"}, {"Key": "emails/user-1/def.json"}]
    }
    with patch("src.storage.object_store.boto3.client", return_value=mock_client):
        keys = object_store.list_archived_emails("user-1")

    assert keys == ["emails/user-1/abc.json", "emails/user-1/def.json"]
    mock_client.list_objects_v2.assert_called_once_with(
        Bucket="test-bucket", Prefix="emails/user-1/"
    )
