"""Mem0 memory store singleton.

Initializes Mem0 once and exposes it to the rest of the application.
In dev mode this uses local Qdrant (on-disk) and SQLite history.
In production, swap to pgvector via Memory.from_config().
"""

from mem0 import Memory

from src.config import settings

_memory: Memory | None = None


def get_memory() -> Memory:
    """Return the global Mem0 instance (lazy-initialized)."""
    global _memory
    if _memory is None:
        config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": settings.mem0_llm_model,
                    "temperature": 0.1,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": settings.mem0_embedding_model,
                },
            },
        }
        _memory = Memory.from_config(config)
    return _memory
