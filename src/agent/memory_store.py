"""Mem0 memory store singleton.

Initializes Mem0 once and exposes it to the rest of the application.
Uses Qdrant in-memory mode for the PoC (no file locks).
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
                "provider": "ollama",
                "config": {
                    "model": settings.mem0_llm_model,
                    "temperature": 0.1,
                    "ollama_base_url": settings.ollama_base_url,
                },
            },
            "embedder": {
                "provider": "ollama",
                "config": {
                    "model": settings.mem0_embedding_model,
                    "ollama_base_url": settings.ollama_base_url,
                    "embedding_dims": 768,
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "embedding_model_dims": 768,
                    "collection_name": "mem0_grounding",
                    "path": ":memory:",
                    "on_disk": False,
                },
            },
        }
        _memory = Memory.from_config(config)
    return _memory
