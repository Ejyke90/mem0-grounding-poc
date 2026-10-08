"""Chat endpoint: sends user messages through the LangGraph orchestrator."""

from fastapi import APIRouter
from pydantic import BaseModel

from src.agent.orchestrator import create_orchestrator

router = APIRouter(prefix="/chat", tags=["chat"])

# Create orchestrator once at import time
orchestrator = create_orchestrator()


class ChatRequest(BaseModel):
    session_id: str = "default"
    user_id: str = "demo-user"
    message: str


class ChatResponse(BaseModel):
    session_id: str
    user_id: str
    response: str
    tool_calls_made: list[str]


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message through the LangGraph orchestrator with Mem0 memory tools."""

    from langchain_core.messages import HumanMessage

    result = orchestrator.invoke(
        {
            "messages": [HumanMessage(content=request.message)],
            "session_id": request.session_id,
            "user_id": request.user_id,
        }
    )

    # Extract the final AI response and any tool calls that were made
    tool_calls_made = []
    final_response = ""

    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_made.append(tc["name"])
        if hasattr(msg, "content") and msg.type == "ai" and not (
            hasattr(msg, "tool_calls") and msg.tool_calls
        ):
            final_response = msg.content

    return ChatResponse(
        session_id=request.session_id,
        user_id=request.user_id,
        response=final_response,
        tool_calls_made=tool_calls_made,
    )
