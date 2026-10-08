"""LangGraph orchestrator with Mem0 memory tools.

This is the core proof-of-concept: a LangGraph agent that has access to
search_memory and add_memory tools alongside domain tools. The agent
decides when personal context is useful and retrieves it on demand.
"""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from src.agent.memory_tools import search_memory, add_memory
from src.config import settings

SYSTEM_PROMPT = """You are a personal assistant with access to the user's grounded context.

You have memory tools that let you search and store personal context from the user's
emails, calendars, Webex messages, and Slack conversations.

WHEN TO USE search_memory:
- The user asks about meetings, schedules, or deadlines
- The user references something they told you before
- The user asks a question that might benefit from their personal history
- The user asks "what do you know about me"

WHEN TO USE add_memory:
- The user shares a preference ("I prefer morning meetings")
- The user states a fact about themselves ("I work on the Q4 budget project")
- The user corrects you ("Actually, my manager is Sarah, not John")

WHEN NOT TO USE memory tools:
- General knowledge questions ("What is Python?")
- Requests that are clearly not personal ("Tell me a joke")

Always pass the user_id from the conversation context when calling memory tools.
The current user_id is provided in the conversation metadata.
"""

# All tools the agent can call
TOOLS = [search_memory, add_memory]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    user_id: str


def create_orchestrator():
    """Create and compile the LangGraph orchestrator."""

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0.2,
        max_tokens=2048,
    )
    llm_with_tools = llm.bind_tools(TOOLS)

    def call_model(state: AgentState) -> dict:
        messages = state["messages"]

        # Prepend system message with user_id context
        user_id = state.get("user_id", "anonymous")
        sys_msg = SystemMessage(
            content=SYSTEM_PROMPT + f"\n\nCurrent user_id: {user_id}"
        )

        response = llm_with_tools.invoke([sys_msg] + messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    def call_tools(state: AgentState) -> dict:
        last_message = state["messages"][-1]
        tool_results = []

        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            for t in TOOLS:
                if t.name == tool_name:
                    result = t.invoke(tool_args)
                    tool_results.append(
                        {
                            "role": "tool",
                            "content": str(result),
                            "tool_call_id": tool_call["id"],
                        }
                    )
                    break

        return {"messages": tool_results}

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", call_tools)

    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")

    return workflow.compile()
