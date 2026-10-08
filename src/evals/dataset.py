"""Golden eval dataset for the personalization agent.

Each case is keyed to the mock corpus in src/ingestion/seed.py so expected
answers are deterministic. Three question types:

  - retrieval cases: must call search_memory and ground the answer
  - write cases: must call add_memory when the user states a preference
  - negative cases: must NOT call memory tools for general questions

Keyword checks are intentionally loose (substring, case-insensitive) because
a 3B local model phrases things differently every run -- the eval asserts the
agent *found* the right memory, not that it worded it perfectly.
"""

from dataclasses import dataclass, field


@dataclass
class EvalCase:
    name: str
    query: str
    user_id: str = "demo-user"
    expect_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    answer_must_contain: list[str] = field(default_factory=list)
    answer_must_contain_any: list[str] = field(default_factory=list)
    use_judge: bool = True


DEFAULT_DATASET: list[EvalCase] = [
    EvalCase(
        name="budget-meeting",
        query="What meetings do I have coming up about the budget?",
        expect_tools=["search_memory"],
        answer_must_contain_any=["october 10", "q4", "budget"],
    ),
    EvalCase(
        name="manager-1on1",
        query="Who is my manager and when is our next 1:1?",
        expect_tools=["search_memory"],
        answer_must_contain_any=["sarah"],
    ),
    EvalCase(
        name="qr-attendance-status",
        query="What's the status of the QR attendance feature?",
        expect_tools=["search_memory"],
        answer_must_contain_any=["staging", "passing", "ready", "tests"],
    ),
    EvalCase(
        name="vendor-selection",
        query="Which vendors are we evaluating for the gate devices?",
        expect_tools=["search_memory"],
        answer_must_contain_any=["securegate", "smartaccess"],
    ),
    EvalCase(
        name="self-knowledge",
        query="What do you know about me?",
        expect_tools=["search_memory"],
        answer_must_contain_any=["safe school", "budget", "sarah", "q4", "kudegowo"],
    ),
    EvalCase(
        name="store-preference",
        query="Remember that I prefer standup meetings before 10am.",
        expect_tools=["add_memory"],
    ),
    EvalCase(
        name="general-knowledge-negative",
        query="What is recursion in programming?",
        forbidden_tools=["search_memory", "add_memory"],
        use_judge=False,
    ),
    EvalCase(
        name="small-talk-negative",
        query="Tell me a joke.",
        forbidden_tools=["search_memory", "add_memory"],
        use_judge=False,
    ),
]
