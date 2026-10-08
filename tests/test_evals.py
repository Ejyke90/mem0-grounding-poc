"""Unit tests for the eval scoring functions and trace extraction.

These are pure-function tests -- no Ollama, no Mem0, no network.
"""

from types import SimpleNamespace

from src.evals.dataset import EvalCase
from src.evals.scoring import extract_trace, score_answer_keywords, score_tool_selection


def _ai(content="", tool_calls=None):
    return SimpleNamespace(type="ai", content=content, tool_calls=tool_calls or [])


def _tool(content):
    return SimpleNamespace(type="tool", content=content)


def test_extract_trace_captures_tool_calls_and_answer():
    messages = [
        _ai(tool_calls=[{"name": "search_memory", "args": {}, "id": "1"}]),
        _tool("[{'memory': 'Q4 budget review Oct 10'}]"),
        _ai(content="You have a Q4 Budget Review on October 10."),
    ]
    trace = extract_trace(messages)
    assert trace["called_tools"] == ["search_memory"]
    assert "Q4 budget review" in trace["tool_outputs"][0]
    assert "October 10" in trace["final_answer"]


def test_extract_trace_handles_dict_tool_messages():
    messages = [
        _ai(tool_calls=[{"name": "add_memory", "args": {}, "id": "1"}]),
        {"role": "tool", "content": "{'status': 'stored'}", "tool_call_id": "1"},
        _ai(content="Done."),
    ]
    trace = extract_trace(messages)
    assert trace["called_tools"] == ["add_memory"]
    assert "stored" in trace["tool_outputs"][0]


def test_extract_trace_no_tools():
    trace = extract_trace([_ai(content="Just an answer.")])
    assert trace["called_tools"] == []
    assert trace["tool_outputs"] == []
    assert trace["final_answer"] == "Just an answer."


def test_tool_selection_passes_when_expected_called():
    case = EvalCase(name="t", query="q", expect_tools=["search_memory"])
    score, problems = score_tool_selection(["search_memory"], case)
    assert score == 1.0
    assert problems == []


def test_tool_selection_fails_on_missing_tool():
    case = EvalCase(name="t", query="q", expect_tools=["search_memory"])
    score, problems = score_tool_selection([], case)
    assert score == 0.0
    assert "search_memory" in str(problems)


def test_tool_selection_fails_on_forbidden_tool():
    case = EvalCase(name="t", query="q", forbidden_tools=["search_memory"])
    score, problems = score_tool_selection(["search_memory"], case)
    assert score == 0.0
    assert "forbidden" in str(problems)


def test_tool_selection_negative_case_passes_with_no_calls():
    case = EvalCase(name="t", query="q", forbidden_tools=["search_memory", "add_memory"])
    score, _ = score_tool_selection([], case)
    assert score == 1.0


def test_answer_keywords_all_required():
    case = EvalCase(name="t", query="q", answer_must_contain=["sarah", "october"])
    score, problems = score_answer_keywords("Your manager Sarah booked it for October 8", case)
    assert score == 1.0

    score, problems = score_answer_keywords("Your manager is Sarah", case)
    assert score == 0.5
    assert "october" in str(problems)


def test_answer_keywords_any():
    case = EvalCase(
        name="t", query="q", answer_must_contain_any=["securegate", "smartaccess"]
    )
    score, _ = score_answer_keywords("You're evaluating SecureGate Pro", case)
    assert score == 1.0

    score, problems = score_answer_keywords("No vendors found", case)
    assert score == 0.0


def test_answer_keywords_none_required():
    case = EvalCase(name="t", query="q")
    score, problems = score_answer_keywords("anything", case)
    assert score == 1.0
    assert problems == []


def test_dataset_structure():
    from src.evals.dataset import DEFAULT_DATASET

    assert len(DEFAULT_DATASET) >= 6
    # every retrieval case expects search_memory
    for case in DEFAULT_DATASET:
        if case.expect_tools == ["search_memory"]:
            assert case.answer_must_contain_any or case.answer_must_contain
    # negative cases forbid tools and skip the judge
    negatives = [c for c in DEFAULT_DATASET if "negative" in c.name]
    assert all(c.forbidden_tools for c in negatives)
    assert all(not c.use_judge for c in negatives)
