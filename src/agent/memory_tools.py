"""LangChain tools that wrap Mem0 for agent-driven memory retrieval and storage.

These tools are registered in the LangGraph orchestrator's tool registry,
allowing the agent to decide when personal context is useful.
"""

from langchain_core.tools import tool

from src.agent.memory_store import get_memory


@tool
def search_memory(query: str, user_id: str) -> list[dict]:
    """Search the user's personal context from emails, calendars, Webex, and Slack.

    Use this tool when the user's question might benefit from their personal
    context: upcoming meetings, recent emails, Slack conversations, or
    previously learned preferences.

    Args:
        query: Natural language query describing what context you need.
        user_id: The user's unique identifier.

    Returns:
        List of relevant memories, each with 'memory' text and 'metadata'.
    """
    mem = get_memory()
    results = mem.search(query, user_id=user_id)

    # Normalize: mem0 v2 returns {"results": [...]} or a list directly
    if isinstance(results, dict) and "results" in results:
        memories = results["results"]
    elif isinstance(results, list):
        memories = results
    else:
        memories = []

    return [
        {
            "memory": m.get("memory", ""),
            "score": m.get("score", 0),
            "metadata": m.get("metadata", {}),
        }
        for m in memories[:10]  # cap at 10 to protect token budget
    ]


@tool
def add_memory(content: str, user_id: str, source: str = "conversation") -> dict:
    """Store a new fact or preference learned during the conversation.

    Use this tool when the user shares a durable fact about themselves:
    a preference, a goal, a constraint, or a piece of personal context
    that would be useful in future conversations.

    Args:
        content: The fact to remember, stated clearly.
        user_id: The user's unique identifier.
        source: Where this fact came from (conversation, email, calendar, webex, slack).

    Returns:
        Confirmation with the stored memory ID.
    """
    mem = get_memory()
    result = mem.add(
        [{"role": "user", "content": content}],
        user_id=user_id,
        metadata={"source": source},
    )
    return {"status": "stored", "result": str(result)}
