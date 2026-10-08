"""MCP server: email ingestion + Mem0 personalization memory, exposed as tools.

Lets any MCP client (Claude Desktop, the `mcp` CLI, or your own agent gateway)
fetch Gmail/Yahoo email over IMAP, archive the raw messages to free
S3-compatible object storage, store them as searchable memories in Mem0, and
search/add personalization facts, all without the client ever handling
credentials directly.

Run:
    python -m src.mcp_server.server              # stdio transport
    mcp dev src/mcp_server/server.py              # MCP inspector (dev/debug)

Register with Claude Desktop or any MCP client by pointing it at this module
via stdio. See README.md for an example client config.
"""

from __future__ import annotations

import os
from typing import Literal

os.environ.setdefault("MEM0_TELEMETRY", "false")

from mcp.server.fastmcp import FastMCP

from src.agent.memory_tools import add_memory, search_memory
from src.ingestion.adapters import ingest_email
from src.ingestion.email_sources.imap_client import fetch_recent_emails
from src.storage.object_store import list_archived_emails, upload_email_archive

mcp = FastMCP("mem0-personalization")

Provider = Literal["gmail", "yahoo"]


@mcp.tool()
def fetch_emails(provider: Provider, max_results: int = 10) -> list[dict]:
    """Fetch recent emails from Gmail or Yahoo Mail over IMAP (read-only).

    Credentials come from the server's .env file, never from the caller.
    Returns raw email dicts with subject, sender, date, and body.
    """
    return fetch_recent_emails(provider=provider, max_results=max_results)


@mcp.tool()
def archive_emails(user_id: str, emails: list[dict]) -> dict:
    """Archive raw emails as JSON to free S3-compatible object storage.

    Preserves the original source data independently of what Mem0 extracts,
    so nothing is lost if memory extraction misses something.
    """
    keys = [upload_email_archive(user_id, e) for e in emails]
    return {"archived": len(keys), "keys": keys}


@mcp.tool()
def list_email_archive(user_id: str) -> list[str]:
    """List object storage keys for a user's archived emails."""
    return list_archived_emails(user_id)


@mcp.tool()
def ingest_emails_to_memory(user_id: str, emails: list[dict]) -> dict:
    """Store emails as searchable personalization memories in Mem0."""
    results = [
        ingest_email(user_id, e["subject"], e["sender"], e["body"], e["date"]) for e in emails
    ]
    return {"ingested": len(results), "results": results}


@mcp.tool()
def sync_mailbox(
    provider: Provider, user_id: str, max_results: int = 10, archive: bool = True
) -> dict:
    """Fetch, archive, and ingest a mailbox in one call.

    This is the end-to-end flow: IMAP fetch -> object storage archive ->
    Mem0 ingestion. Use the individual tools instead if you need to inspect
    or filter emails between steps.
    """
    emails = fetch_recent_emails(provider=provider, max_results=max_results)
    archived_keys = [upload_email_archive(user_id, e) for e in emails] if archive else []
    ingested = [
        ingest_email(user_id, e["subject"], e["sender"], e["body"], e["date"]) for e in emails
    ]
    return {
        "provider": provider,
        "fetched": len(emails),
        "archived": len(archived_keys),
        "ingested": len(ingested),
    }


@mcp.tool()
def search_personal_memory(query: str, user_id: str) -> list[dict]:
    """Search the user's ingested personal context (emails, calendar, Slack, Webex)."""
    return search_memory.invoke({"query": query, "user_id": user_id})


@mcp.tool()
def add_personal_memory(content: str, user_id: str, source: str = "conversation") -> dict:
    """Store a new durable fact or preference about the user."""
    return add_memory.invoke({"content": content, "user_id": user_id, "source": source})


if __name__ == "__main__":
    mcp.run()
