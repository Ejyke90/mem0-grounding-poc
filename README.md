# mem0-grounding-poc

Proof of concept: **Mem0 memory layer** integrated with a **LangGraph agent** for personal grounding.

Demonstrates the full lifecycle:
1. **Ingest** personal data from email, calendar, Webex, and Slack into Mem0
2. **Synthesize** durable profile facts via a background worker (sleeptime-inspired)
3. **Retrieve** personal context on demand through agent-driven tool calls

## Architecture

```
Personal Grounding Sources (email, calendar, Webex, Slack)
        |
        | ingest -> mem0.add()
        v
+-------------------+
| Mem0 Memory Store |  (local Qdrant + SQLite)
+-------------------+
        ^
        | tool calls: search_memory() / add_memory()
        |
LangGraph Orchestrator
        |
        +-- search_memory: agent retrieves personal context on demand
        +-- add_memory: agent stores new facts from conversation
```

The agent decides when memory is useful. No proxy, no silent injection.
The LLM calls `search_memory` when a question benefits from personal context,
and `add_memory` when the user shares a durable fact.

## Quick Start

### Prerequisites

- Python 3.11+
- An OpenAI API key

### Setup

```bash
# Clone
git clone https://github.com/Ejyke90/mem0-grounding-poc.git
cd mem0-grounding-poc

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install
pip install -e .

# Configure
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

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

### Run Individual Components

```bash
# Seed mock data only
python -m src.ingestion.seed

# Run synthesis only
python -m src.worker.synthesizer
```

## Project Structure

```
src/
  config.py                  # Pydantic settings (OpenAI key, Mem0 config)
  main.py                    # FastAPI app
  agent/
    memory_store.py          # Mem0 singleton initialization
    memory_tools.py          # LangChain tools: search_memory, add_memory
    orchestrator.py          # LangGraph state machine with memory tools
  ingestion/
    adapters.py              # Source adapters: email, calendar, Slack, Webex
    seed.py                  # Mock data seeder
  routers/
    health.py                # Health check endpoint
    chat.py                  # Chat endpoint (agent + memory)
    memory.py                # Direct memory CRUD endpoints
  worker/
    synthesizer.py           # Background synthesis (sleeptime-inspired)
demo.py                      # Full lifecycle demo script
```

## What This Proves

1. **Mem0 as a drop-in memory layer.** `pip install mem0ai`, call `Memory()`, and you have persistent user-scoped memory with hybrid retrieval (semantic + BM25 + entity linking).

2. **Agent-driven retrieval.** The agent decides when to use memory, not a proxy. `search_memory` and `add_memory` are LangChain tools in the LangGraph tool registry, same pattern as any other tool.

3. **Source-agnostic ingestion.** The same `mem0.add()` call works for emails, calendar events, Slack messages, and Webex messages. Metadata tags track the source.

4. **Background synthesis works.** A simple LLM-based synthesis pass reads raw memories and produces durable profile-level facts, similar to Letta's sleeptime compute but without the framework overhead.

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
