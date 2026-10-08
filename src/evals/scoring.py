"""Deterministic scorers + trace extraction for evals.

These functions are pure -- no Ollama, no Mem0 -- so they're unit-tested
directly. The runner feeds them real LangGraph output.
"""

from __future__ import annotations

from src.evals.dataset import EvalCase


def extract_trace(messages: list) -> dict:
    """Pull tool-call names, tool outputs, and the final answer out of the
    orchestrator's message list.

    Handles both LangChain message objects (msg.type / msg.tool_calls) and
    plain dict-shaped tool results produced by the orchestrator's tool node.
    """
    called_tools: list[str] = []
    tool_outputs: list[str] = []
    final_answer = ""

    for msg in messages:
        mtype = getattr(msg, "type", None) or (
            msg.get("role") if isinstance(msg, dict) else None
        )
        content = getattr(msg, "content", None) or (
            msg.get("content") if isinstance(msg, dict) else ""
        )
        tool_calls = getattr(msg, "tool_calls", None) or []

        if mtype in ("ai", "assistant"):
            if tool_calls:
                for tc in tool_calls:
                    called_tools.append(tc["name"])
            elif content:
                final_answer = content
        elif mtype == "tool":
            tool_outputs.append(str(content))

    return {
        "called_tools": called_tools,
        "tool_outputs": tool_outputs,
        "final_answer": final_answer,
    }


def score_tool_selection(called: list[str], case: EvalCase) -> tuple[float, list[str]]:
    """1.0 if all expected tools were called and no forbidden tools were.
    0.0 otherwise, with a list of problems."""
    problems = []
    missing = [t for t in case.expect_tools if t not in called]
    forbidden_hit = [t for t in case.forbidden_tools if t in called]

    if missing:
        problems.append(f"expected tools not called: {missing}")
    if forbidden_hit:
        problems.append(f"forbidden tools called: {forbidden_hit}")

    return (0.0 if problems else 1.0), problems


def score_answer_keywords(answer: str, case: EvalCase) -> tuple[float, list[str]]:
    """Score the final answer against required keywords.

    `answer_must_contain` = all required; `answer_must_contain_any` = at least
    one. Returns (score, problems). No requirements -> 1.0.
    """
    if not case.answer_must_contain and not case.answer_must_contain_any:
        return 1.0, []

    problems = []
    checks = 0
    hits = 0
    lowered = answer.lower()

    for kw in case.answer_must_contain:
        checks += 1
        if kw.lower() in lowered:
            hits += 1
        else:
            problems.append(f"missing required keyword: '{kw}'")

    if case.answer_must_contain_any:
        checks += 1
        if any(kw.lower() in lowered for kw in case.answer_must_contain_any):
            hits += 1
        else:
            problems.append(
                f"answer contained none of: {case.answer_must_contain_any}"
            )

    return (hits / checks if checks else 1.0), problems
