"""Veritrace evaluation harness.

Usage
-----
    python -m evals                          # run against the persisted Chroma store
    python -m evals --verbose                # show per-case details
    MOCK_LLM=true python -m evals --mock     # run in mock mode (no API key needed)

Exit code
---------
    0  all cases pass or warn-only failures
    1  one or more hard failures (blocked/abstain when answer expected, etc.)

Metrics reported
----------------
    - Per-category: pass rate, total, pass count
    - Overall: pass rate, total cases, pass count
    - Hard failures: cases where system behavior contradicts expected_behavior
    - Must-not-contain violations: cases where forbidden text appeared in answer
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Ensure repo root is importable
_REPO = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO))

GOLDEN_FILE = Path(__file__).parent / "golden.jsonl"


def _load_golden() -> list[dict]:
    cases = []
    with open(GOLDEN_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def _run_case(case: dict, store, tenant_id: str = "demo") -> dict:
    """Run one golden case through the full pipeline and score it."""
    from veritrace.safety.guardrails import check_input
    from veritrace.safety.output_gate import check_output
    from veritrace.safety.redaction import redact, restore
    from veritrace.responder.agent import answer
    from veritrace.schemas import TrustReceipt, RefusalInfo

    query = case["query"]
    expected = case["expected_behavior"]
    keywords = case.get("expected_keywords", [])
    must_not = case.get("must_not_contain", [])

    t0 = time.time()

    # 1. Guardrails
    guard = check_input(query)
    if not guard["allowed"]:
        actual_behavior = "blocked"
        answer_text = guard["blocked_reason"] or "Blocked."
        latency_ms = round((time.time() - t0) * 1000, 1)
    else:
        # 2. Redaction
        redacted, rctx = redact(query)
        # 3. Agent
        receipt = answer(redacted, tenant_id, store, start_time=t0)
        # 4. Output gate
        gate = check_output(receipt.answer, redacted, [])
        if not gate["passed"]:
            actual_behavior = "refused"
            answer_text = gate["reason"] or "Output blocked."
        elif receipt.confidence == "abstained":
            actual_behavior = "abstained"
            answer_text = receipt.answer
        else:
            if rctx.applied:
                answer_text = restore(receipt.answer, rctx)
            else:
                answer_text = receipt.answer
            actual_behavior = "answer_with_redaction" if rctx.applied else "answer"
        latency_ms = receipt.latency_ms

    # Score
    answer_lower = answer_text.lower()
    is_blocked = actual_behavior in ("blocked", "refused")

    # Keyword check — only applies when system produced a knowledge answer
    kw_hits = [kw for kw in keywords if kw.lower() in answer_lower]
    kw_pass = True if is_blocked else ((len(kw_hits) == len(keywords)) if keywords else True)

    # Must-not-contain check — only applies to knowledge answers, not block messages
    mnc_violations = [] if is_blocked else [t for t in must_not if t.lower() in answer_lower]
    mnc_pass = len(mnc_violations) == 0

    # Behavior check
    behavior_pass = _behavior_matches(expected, actual_behavior)

    passed = behavior_pass and kw_pass and mnc_pass

    return {
        "id": case["id"],
        "category": case["category"],
        "query": query,
        "expected_behavior": expected,
        "actual_behavior": actual_behavior,
        "answer": answer_text[:200],
        "behavior_pass": behavior_pass,
        "kw_pass": kw_pass,
        "mnc_pass": mnc_pass,
        "passed": passed,
        "latency_ms": latency_ms,
        "kw_hits": kw_hits,
        "mnc_violations": mnc_violations,
        "notes": case.get("notes", ""),
    }


def _behavior_matches(expected: str, actual: str) -> bool:
    """Flexible matching — some expected values accept multiple actual outcomes."""
    # Direct match
    if expected == actual:
        return True
    # Flexible expectations
    if expected == "abstain" and actual in ("abstained", "refused"):
        return True
    if expected == "blocked" and actual in ("blocked", "refused"):
        return True
    if expected == "refused_or_abstained" and actual in ("refused", "abstained", "blocked"):
        return True
    if expected == "blocked_or_redacted" and actual in ("blocked", "answer_with_redaction", "refused"):
        return True
    if expected == "answer_with_redaction" and actual in ("answer_with_redaction", "answer"):
        return True
    if expected == "abstain_or_answer" and actual in ("abstained", "answer", "answer_with_redaction"):
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Veritrace eval harness")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--tenant", default="demo")
    parser.add_argument("--mock", action="store_true", help="Force MOCK_LLM=true")
    args = parser.parse_args()

    if args.mock:
        os.environ["MOCK_LLM"] = "true"

    # Imports after env is set
    from dotenv import load_dotenv
    load_dotenv(_REPO / ".env", override=False)

    import veritrace.llm  # trigger provider print

    from veritrace.config import settings
    from veritrace.index.embeddings import embed_chunks
    from veritrace.index.store import VectorStore
    from veritrace.ingest.chunker import chunk as chunk_doc
    from veritrace.ingest.parsers import parse
    from data.seed import seed, SYNTHETIC_DIR

    # Ensure corpus exists
    if not SYNTHETIC_DIR.exists() or not list(SYNTHETIC_DIR.glob("*.md")):
        print("Seeding synthetic data...")
        seed()

    # Build an eval-specific store
    eval_chroma = _REPO / "chroma_eval"
    store = VectorStore(collection_name="eval", persist_directory=str(eval_chroma))
    if store.count(args.tenant) == 0:
        print("Ingesting corpus for eval store...")
        for f in sorted(SYNTHETIC_DIR.glob("*.md")):
            doc = parse(f)
            doc["metadata"]["tenant_id"] = args.tenant
            chunks = chunk_doc(doc)
            if chunks:
                store.add(chunks, embed_chunks(chunks))

    cases = _load_golden()
    print(f"\nRunning {len(cases)} golden cases (tenant={args.tenant})...\n")

    results = []
    for i, case in enumerate(cases, 1):
        r = _run_case(case, store, args.tenant)
        results.append(r)
        status = "PASS" if r["passed"] else "FAIL"
        if args.verbose or not r["passed"]:
            print(f"  [{status}] {r['id']} ({r['category']}): {r['query'][:60]}")
            if not r["behavior_pass"]:
                print(f"         behavior: expected={r['expected_behavior']} actual={r['actual_behavior']}")
            if not r["kw_pass"]:
                print(f"         missing keywords: {[k for k in case.get('expected_keywords',[]) if k not in r['kw_hits']]}")
            if not r["mnc_pass"]:
                print(f"         must-not-contain violations: {r['mnc_violations']}")
            if args.verbose:
                print(f"         answer: {r['answer'][:120]}")
        else:
            print(f"  [PASS] {r['id']}", end="\r")

    print()
    print("=" * 60)

    # Aggregate by category
    categories: dict[str, list] = {}
    for r in results:
        categories.setdefault(r["category"], []).append(r)

    print(f"{'Category':<25} {'Pass':>5} {'Total':>6} {'Rate':>7}")
    print("-" * 45)
    for cat in sorted(categories):
        cat_results = categories[cat]
        cat_pass = sum(1 for r in cat_results if r["passed"])
        cat_total = len(cat_results)
        rate = cat_pass / cat_total * 100 if cat_total else 0
        print(f"  {cat:<23} {cat_pass:>5} {cat_total:>6}  {rate:>5.1f}%")

    print("-" * 45)
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    rate = passed / total * 100 if total else 0
    avg_latency = sum(r["latency_ms"] for r in results) / total if total else 0
    print(f"  {'TOTAL':<23} {passed:>5} {total:>6}  {rate:>5.1f}%")
    print(f"\n  Avg latency: {avg_latency:.0f} ms")
    print(f"  Hard failures: {total - passed}")

    # Write results JSON
    out_path = _REPO / "evals" / "last_run.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": total, "passed": passed, "rate": round(rate, 1),
            "avg_latency_ms": round(avg_latency, 1),
            "results": results,
        }, f, indent=2)
    print(f"\n  Full results written to evals/last_run.json")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
