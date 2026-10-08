"""Direct memory endpoints for debugging and testing.

These bypass the agent and let you interact with Mem0 directly.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from src.agent.memory_store import get_memory

router = APIRouter(prefix="/memory", tags=["memory"])


class AddMemoryRequest(BaseModel):
    user_id: str = "demo-user"
    content: str
    source: str = "manual"
    metadata: dict = {}


class SearchMemoryRequest(BaseModel):
    user_id: str = "demo-user"
    query: str


@router.post("/add")
async def add_memory_direct(request: AddMemoryRequest) -> dict:
    """Add a memory directly to Mem0 (bypasses the agent)."""
    mem = get_memory()
    result = mem.add(
        [{"role": "user", "content": request.content}],
        user_id=request.user_id,
        metadata={"source": request.source, **request.metadata},
    )
    return {"status": "stored", "result": str(result)}


@router.post("/search")
async def search_memory_direct(request: SearchMemoryRequest) -> dict:
    """Search memories directly in Mem0 (bypasses the agent)."""
    mem = get_memory()
    results = mem.search(request.query, filters={"user_id": request.user_id})

    if isinstance(results, dict) and "results" in results:
        memories = results["results"]
    elif isinstance(results, list):
        memories = results
    else:
        memories = []

    return {"query": request.query, "user_id": request.user_id, "memories": memories}


@router.get("/all/{user_id}")
async def get_all_memories(user_id: str) -> dict:
    """Get all memories for a user."""
    mem = get_memory()
    results = mem.get_all(filters={"user_id": user_id})

    if isinstance(results, dict) and "results" in results:
        memories = results["results"]
    elif isinstance(results, list):
        memories = results
    else:
        memories = []

    return {"user_id": user_id, "count": len(memories), "memories": memories}
