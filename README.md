# mem0-grounding-poc

Proof of concept: **Mem0 memory layer** integrated with a **LangGraph agent** for personalization.

Demonstrates the full lifecycle:
1. **Ingest** personal data from email (Gmail/Yahoo via IMAP), calendar, Webex, and Slack into Mem0
2. **Archive** raw emails to free S3-compatible object storage (Cloudflare R2, Backblaze B2, or MinIO)
3. **Synthesize** durable profile facts via a background worker (sleeptime-inspired)
4. **Retrieve** personal context on demand through agent-driven tool calls, or expose the same tools over MCP

## Architecture

```
Gmail / Yahoo (IMAP)  --fetch-->  [raw emails]
                                        |
                                        +--> Object Storage (R2/B2/MinIO)  [archive, raw JSON]
                                        |
                                        +--> Mem0 Memory Store              [ingest, mem0.add()]
                                                     ^
                                                     | tool calls: search_memory() / add_memory()
                                                     |
                               +---------------------+---------------------+
                               |                                           |
                     LangGraph Orchestrator                        MCP Server (stdio)
                     (agent-driven tool use)                (any MCP client: Claude Desktop, etc.)
```

Calendar, Slack, and Webex still ingest via the mock adapters in `src/ingestion/adapters.py`
(same pattern as email, just without a live IMAP/API source wired up yet).

The agent decides when memory is useful. No proxy, no silent injection.
The LLM calls `search_memory` when a question benefits from personal context,
and `add_memory` when the user shares a durable fact.

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running (completely free, runs locally)

### Setup

```bash
# 1. Install Ollama models (one-time)
ollama pull llama3.2           # 3B param, supports tool calling
ollama pull nomic-embed-text   # embedding model for Mem0

# 2. Clone and install
git clone https://github.com/Ejyke90/mem0-grounding-poc.git
cd mem0-grounding-poc
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
```

No API keys needed. Everything runs locally via Ollama.

### Run the Demo

The demo seeds mock data, runs synthesis, and queries the agent:

```bash
python demo.py
```

Expected output:

```
--- STEP 1: Ingest mock data from email, calendar, Slack, Webex ---
  Ingested email: Q4 Budget Review - Action Items
  Ingested calendar: Q4 Budget Review
  ...

--- STEP 2: Run background synthesis (sleeptime-inspired) ---
  Stored: User is involved in the Q4 budget planning process
  Stored: User's manager is Sarah Chen
  ...

--- STEP 3: Query the agent with personal context questions ---

User: What meetings do I have coming up about the budget?
Tools used: search_memory
Agent: You have a Q4 Budget Review meeting on October 10th...
```

### Run the API Server

```bash
python -m src.main
# or: uvicorn src.main:app --reload --port 8000
```

Endpoints:
- `GET /health` - health check
- `POST /chat` - send a message through the agent (with memory tools)
- `POST /memory/add` - add a memory directly
- `POST /memory/search` - search memories directly
- `GET /memory/all/{user_id}` - list all memories for a user
- `POST /email/sync` - fetch Gmail/Yahoo over IMAP, archive to object storage, ingest to Mem0
- `GET /email/archive/{user_id}` - list a user's archived email object keys

### Run Individual Components

```bash
# Seed mock data only
python -m src.ingestion.seed

# Run synthesis only
python -m src.worker.synthesizer
```

## Email Ingestion + Object Storage + MCP

Fetches real email from Gmail or Yahoo over IMAP, archives the raw messages to
free object storage, and stores them as searchable Mem0 memories.

### 1. Generate IMAP app passwords (not your login password)

- **Gmail**: enable 2-Step Verification, then create one at
  https://myaccount.google.com/apppasswords
- **Yahoo**: https://login.yahoo.com/account/security -> "Generate app password"

Add to `.env`:
```bash
GMAIL_USER=you@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
# or
YAHOO_USER=you@yahoo.com
YAHOO_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

### 2. Set up free object storage

Any S3-compatible provider works via `boto3`. Two free options:

- **Cloudflare R2** (recommended: 10 GB storage, zero egress fees) -- create a
  bucket and API token at https://dash.cloudflare.com -> R2
- **Backblaze B2** (10 GB free) -- create a bucket and application key at
  https://www.backblaze.com/b2

Add to `.env`:
```bash
OBJECT_STORAGE_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
OBJECT_STORAGE_ACCESS_KEY=...
OBJECT_STORAGE_SECRET_KEY=...
OBJECT_STORAGE_BUCKET=mem0-email-archive
OBJECT_STORAGE_REGION=auto
```

### 3. Sync a mailbox

Via REST:
```bash
curl -X POST http://localhost:8000/email/sync \
  -H "Content-Type: application/json" \
  -d '{"provider": "gmail", "user_id": "demo-user", "max_results": 10}'
```

Via the MCP server (any MCP client, e.g. Claude Desktop or the `mcp` CLI):
```bash
python -m src.mcp_server.server       # stdio transport
mcp dev src/mcp_server/server.py      # MCP Inspector, for interactive debugging
```

Example Claude Desktop config (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "mem0-personalization": {
      "command": "/absolute/path/to/mem0-grounding-poc/.venv/bin/python",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "/absolute/path/to/mem0-grounding-poc"
    }
  }
}
```

MCP tools exposed: `fetch_emails`, `archive_emails`, `list_email_archive`,
`ingest_emails_to_memory`, `sync_mailbox` (does all three in one call),
`search_personal_memory`, `add_personal_memory`.

## Project Structure

```
src/
  config.py                  # Pydantic settings (Ollama, Mem0, IMAP, object storage)
  main.py                    # FastAPI app
  agent/
    memory_store.py          # Mem0 singleton initialization
    memory_tools.py          # LangChain tools: search_memory, add_memory
    orchestrator.py          # LangGraph state machine with memory tools
  ingestion/
    adapters.py              # Source adapters: email, calendar, Slack, Webex
    seed.py                  # Mock data seeder
    email_sources/
      imap_client.py         # Gmail/Yahoo IMAP fetcher (app password auth)
  storage/
    object_store.py          # S3-compatible archive (Cloudflare R2 / B2 / MinIO)
  mcp_server/
    server.py                # MCP server: email + memory tools over stdio
  routers/
    health.py                # Health check endpoint
    chat.py                  # Chat endpoint (agent + memory)
    memory.py                # Direct memory CRUD endpoints
    email.py                 # Email sync endpoint (REST counterpart to MCP)
  worker/
    synthesizer.py           # Background synthesis (sleeptime-inspired)
demo.py                      # Full lifecycle demo script
```

## What This Proves

1. **Mem0 as a drop-in memory layer.** `pip install mem0ai`, configure Ollama as the provider, and you have persistent user-scoped memory with hybrid retrieval. No API keys, no cloud dependency.

2. **Agent-driven retrieval.** The agent decides when to use memory, not a proxy. `search_memory` and `add_memory` are LangChain tools in the LangGraph tool registry, same pattern as any other tool.

3. **Source-agnostic ingestion.** The same `mem0.add()` call works for emails, calendar events, Slack messages, and Webex messages. Metadata tags track the source.

4. **Background synthesis works.** A simple LLM-based synthesis pass reads raw memories and produces durable profile-level facts, similar to Letta's sleeptime compute but without the framework overhead.

5. **Real email ingestion with zero paid infrastructure.** Gmail/Yahoo over IMAP (app passwords, no OAuth app registration), Mem0 for searchable memory, and any S3-compatible free tier for raw archival. No managed queue, no managed API gateway.

6. **MCP as the integration surface.** The same fetch/archive/ingest/search/add tools are available to any MCP client (Claude Desktop, `mcp` CLI, or a custom agent gateway) without that client ever touching IMAP or object storage credentials directly.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Tests mock IMAP (`imaplib`) and S3 (`boto3`) so they run without real credentials.

## Next Steps (Production)

- Swap local Qdrant for pgvector (`Memory.from_config({vector_store: {provider: "pgvector", ...}})`)
- Connect real APIs (IMAP, Google Calendar, Webex SDK, Slack SDK) in the ingestion adapters
- Add token budget limits to `search_memory` results
- Run the synthesis worker on a schedule (cron or Celery beat)
- Add Graphiti as a specialized layer if temporal supersession becomes critical

## Related

- [Mem0 Docs](https://docs.mem0.ai)
- [Mem0 Python SDK](https://github.com/mem0ai/mem0)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [Research Plan](https://github.com/Ejyke90/mem0-grounding-poc/blob/main/PLAN.md) (validated findings on Letta, Zep, Cognee, Mem0)
