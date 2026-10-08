"""LLM-as-judge for groundedness scoring.

Uses the same Ollama model as the agent (free, local). Scores 1-5 on whether
the answer is actually grounded in the retrieved memory context rather than
hallucinated. Parsing is deliberately lenient -- a 3B judge sometimes adds
surrounding prose, so we extract the first digit in the response.
"""

from __future__ import annotations

import re

from langchain_ollama import ChatOllama

from src.config import settings

_JUDGE_PROMPT = """You are evaluating an AI assistant's answer for groundedness.

User question:
{query}

Context the assistant retrieved from the user's personal memory:
{context}

Assistant answer:
{answer}

Score the answer 1-5:
5 = fully grounded in the retrieved context, accurate and specific
3 = partially grounded, or correct but vague
1 = hallucinated, contradicts the context, or fails to answer the question

Reply with ONLY the number (1-5), nothing else."""


def judge_answer(query: str, context: str, answer: str) -> tuple[int, str]:
    """Return (score 1-5, rationale). Score is 0 if the judge response
    couldn't be parsed."""
    llm = ChatOllama(
        model=settings.llm_model,
        temperature=0.0,
        num_predict=64,
        base_url=settings.ollama_base_url,
    )
    response = llm.invoke(
        _JUDGE_PROMPT.format(query=query, context=context or "(none)", answer=answer)
    )
    raw = response.content.strip()
    match = re.search(r"[1-5]", raw)
    if match:
        return int(match.group()), raw
    return 0, f"unparseable judge output: {raw!r}"
