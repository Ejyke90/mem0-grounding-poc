"""FastAPI application: mem0-grounding-poc."""

import os

os.environ.setdefault("MEM0_TELEMETRY", "false")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.routers import health, chat, memory

app = FastAPI(
    title="Mem0 Personalization PoC",
    description="LangGraph agent with Mem0 memory tools for personalization",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(memory.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=settings.port, reload=True)
