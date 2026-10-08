"""Background synthesis worker (sleeptime-inspired).

Reads recent raw memories, clusters related facts, and synthesizes
durable profile-level entries. This is a simplified version of
Letta's sleeptime compute pattern.

Usage: python -m src.worker.synthesizer
"""

from langchain_openai import ChatOpenAI

from src.agent.memory_store import get_memory
from src.config import settings


def synthesize_user_profile(user_id: str) -> list[dict]:
    """Read all memories for a user, cluster them, and synthesize profile facts."""

    mem = get_memory()
    all_memories = mem.get_all(user_id=user_id)

    if isinstance(all_memories, dict) and "results" in all_memories:
        memories = all_memories["results"]
    elif isinstance(all_memories, list):
        memories = all_memories
    else:
        memories = []

    if not memories:
        print(f"No memories found for user {user_id}. Nothing to synthesize.")
        return []

    # Filter out already-synthesized memories to avoid loops
    raw_memories = [
        m for m in memories if not m.get("metadata", {}).get("synthesized", False)
    ]

    if not raw_memories:
        print("All memories are already synthesized. Nothing new to process.")
        return []

    print(f"Found {len(raw_memories)} raw memories to synthesize.")

    # Build a context block from raw memories
    memory_texts = []
    for i, m in enumerate(raw_memories[:30], 1):  # cap at 30 to stay in token budget
        source = m.get("metadata", {}).get("source", "unknown")
        text = m.get("memory", "")
        memory_texts.append(f"{i}. [{source}] {text}")

    context = "\n".join(memory_texts)

    # Use the LLM to synthesize profile-level facts
    llm = ChatOpenAI(model=settings.llm_model, temperature=0.1, max_tokens=1024)

    synthesis_prompt = f"""You are a personal knowledge synthesizer. Given the following raw memories
from a user's emails, calendar, Slack, and Webex, extract 3-7 durable profile-level facts.

Each fact should be:
- A clear, standalone statement about the user
- Something that would be useful context in future conversations
- Not a duplicate of another fact you're writing

Format: One fact per line, no numbering.

Raw memories:
{context}

Synthesized facts:"""

    response = llm.invoke(synthesis_prompt)
    facts = [line.strip() for line in response.content.strip().split("\n") if line.strip()]

    # Store synthesized facts back into Mem0
    stored = []
    for fact in facts:
        result = mem.add(
            [{"role": "user", "content": fact}],
            user_id=user_id,
            metadata={
                "source": "synthesis",
                "synthesized": True,
                "para_category": "area",
            },
        )
        stored.append({"fact": fact, "result": str(result)})
        print(f"  Stored: {fact}")

    return stored


def run_synthesis():
    """Run synthesis for the demo user."""
    print("Running background synthesis (sleeptime-inspired)...\n")
    results = synthesize_user_profile("demo-user")
    print(f"\nSynthesis complete. Stored {len(results)} profile-level facts.")


if __name__ == "__main__":
    run_synthesis()
