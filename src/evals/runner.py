"""Eval runner: seeds Mem0 with the mock corpus, runs each eval case through
the LangGraph agent, scores tool selection + answer keywords + groundedness
(LLM judge), and writes a JSON report.

Usage:
    python -m src.evals.runner                  # full run with judge
    python -m src.evals.runner --no-judge       # deterministic metrics only
    python -m src.evals.runner --case manager-1on1
    python -m src.evals.runner --out evals_report.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

os.environ.setdefault("MEM0_TELEMETRY", "false")

from langchain_core.messages import HumanMessage

from src.agent.orchestrator import create_orchestrator
from src.config import settings
from src.evals.dataset import DEFAULT_DATASET, EvalCase
from src.evals.judge import judge_answer
from src.evals.scoring import extract_trace, score_answer_keywords, score_tool_selection
from src.ingestion.seed import seed_all


def run_case(orchestrator, case: EvalCase, use_judge: bool) -> dict:
    """Run one eval case through the agent and score it."""
    started = time.time()

    result = orchestrator.invoke(
        {
            "messages": [HumanMessage(content=case.query)],
            "session_id": f"eval-{case.name}",
            "user_id": case.user_id,
        }
    )

    trace = extract_trace(result["messages"])
    tool_score, tool_problems = score_tool_selection(trace["called_tools"], case)
    kw_score, kw_problems = score_answer_keywords(trace["final_answer"], case)

    judge_score = None
    judge_raw = ""
    if use_judge and case.use_judge:
        context = "\n".join(trace["tool_outputs"])
        judge_score, judge_raw = judge_answer(
            case.query, context, trace["final_answer"]
        )

    passed = tool_score == 1.0 and kw_score == 1.0
    return {
        "name": case.name,
        "query": case.query,
        "passed": passed,
        "tool_selection": tool_score,
        "answer_keywords": kw_score,
        "judge_score": judge_score,
        "judge_raw": judge_raw,
        "called_tools": trace["called_tools"],
        "answer": trace["final_answer"],
        "problems": tool_problems + kw_problems,
        "elapsed_s": round(time.time() - started, 1),
    }


def run_evals(
    cases: list[EvalCase] | None = None,
    use_judge: bool = True,
    seed: bool = True,
) -> dict:
    """Run the full eval suite and return the report dict."""
    cases = cases or DEFAULT_DATASET

    if seed:
        print("Seeding eval corpus...")
        seed_all()

    orchestrator = create_orchestrator()
    results = []

    for case in cases:
        print(f"  [{case.name}] {case.query[:60]}...")
        try:
            r = run_case(orchestrator, case, use_judge)
        except Exception as exc:  # agent/tool failure = hard fail, still reported
            r = {
                "name": case.name,
                "query": case.query,
                "passed": False,
                "tool_selection": 0.0,
                "answer_keywords": 0.0,
                "judge_score": None,
                "judge_raw": "",
                "called_tools": [],
                "answer": "",
                "problems": [f"exception: {exc}"],
                "elapsed_s": 0.0,
            }
        status = "PASS" if r["passed"] else "FAIL"
        print(f"    {status} ({r['elapsed_s']}s) tools={r['called_tools']}")
        if r["problems"]:
            for p in r["problems"]:
                print(f"      - {p}")
        results.append(r)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    judged = [r["judge_score"] for r in results if r["judge_score"]]

    report = {
        "model": settings.llm_model,
        "judge_model": settings.llm_model if use_judge else None,
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "metrics": {
            "tool_selection": round(
                sum(r["tool_selection"] for r in results) / total, 3
            ),
            "answer_keywords": round(
                sum(r["answer_keywords"] for r in results) / total, 3
            ),
            "judge_avg": round(sum(judged) / len(judged), 2) if judged else None,
        },
        "cases": results,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the personalization agent evals.")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM judge")
    parser.add_argument("--case", type=str, default="", help="run a single case by name")
    parser.add_argument("--no-seed", action="store_true", help="skip corpus seeding")
    parser.add_argument("--out", type=str, default="evals_report.json")
    args = parser.parse_args()

    cases = DEFAULT_DATASET
    if args.case:
        cases = [c for c in DEFAULT_DATASET if c.name == args.case]
        if not cases:
            names = ", ".join(c.name for c in DEFAULT_DATASET)
            print(f"Unknown case '{args.case}'. Available: {names}")
            return 1

    report = run_evals(cases=cases, use_judge=not args.no_judge, seed=not args.no_seed)

    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 60)
    print(f"  {report['passed']}/{report['total']} passed "
          f"({report['pass_rate'] * 100:.0f}%)")
    print(f"  tool_selection:  {report['metrics']['tool_selection']}")
    print(f"  answer_keywords: {report['metrics']['answer_keywords']}")
    if report["metrics"]["judge_avg"] is not None:
        print(f"  judge_avg:       {report['metrics']['judge_avg']} / 5")
    print(f"  Report written to {args.out}")
    print("=" * 60)

    return 0 if report["pass_rate"] == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
