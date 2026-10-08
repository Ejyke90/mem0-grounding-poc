"""Interactive demo: shows the full lifecycle of Mem0 + LangGraph personalization.

Run: python demo.py

This script:
1. Seeds Mem0 with mock data from email, calendar, Slack, and Webex
2. Runs the synthesis worker to create profile-level facts
3. Sends test queries through the LangGraph agent to demonstrate memory retrieval
"""

import os
import httpx
import sys

# Disable Mem0 telemetry to avoid a second Qdrant client fighting for file locks
os.environ["MEM0_TELEMETRY"] = "false"

# Check that Ollama is running
try:
    resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
    resp.raise_for_status()
except Exception:
    print("Error: Ollama is not running. Start it with: ollama serve")
    sys.exit(1)

from langchain_core.messages import HumanMessage

from src.agent.orchestrator import create_orchestrator
from src.ingestion.seed import seed_all
from src.worker.synthesizer import synthesize_user_profile


def run_demo():
    print("=" * 70)
    print("  Mem0 Personalization PoC - Interactive Demo")
    print("=" * 70)

    # Step 1: Seed data
    print("\n--- STEP 1: Ingest mock data from email, calendar, Slack, Webex ---\n")
    seed_all()

    # Step 2: Run synthesis
    print("\n--- STEP 2: Run background synthesis (sleeptime-inspired) ---\n")
    synthesize_user_profile("demo-user")

    # Step 3: Query the agent
    print("\n--- STEP 3: Query the agent with personal context questions ---\n")

    orchestrator = create_orchestrator()

    test_queries = [
        "What meetings do I have coming up about the budget?",
        "What's the status of the QR attendance feature?",
        "Who is my manager and when is our next 1:1?",
        "What do you know about me?",
    ]

    for query in test_queries:
        print(f"\nUser: {query}")
        print("-" * 50)

        result = orchestrator.invoke(
            {
                "messages": [HumanMessage(content=query)],
                "session_id": "demo-session",
                "user_id": "demo-user",
            }
        )

        # Find tool calls and final response
        tool_calls = []
        final_response = ""
        for msg in result["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append(tc["name"])
            if hasattr(msg, "content") and msg.type == "ai" and not (
                hasattr(msg, "tool_calls") and msg.tool_calls
            ):
                final_response = msg.content

        if tool_calls:
            print(f"Tools used: {', '.join(tool_calls)}")
        print(f"Agent: {final_response}")
        print()


if __name__ == "__main__":
    run_demo()
