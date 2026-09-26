"""End-to-end evaluation benchmark for Samsung PRISM Agent.

Runs a suite of test queries against the real pipeline and measures:
  - MRR@5 (Mean Reciprocal Rank)
  - Recall@5 (fraction of ground-truth chunks found in top-5)
  - Latency (median and p95)
  - Per-query result details with explanations

Usage:
    python evaluation/evaluate_pipeline.py [--repo-dir demo_repo]
"""

import os
import sys
import time
import json
import argparse
from typing import List, Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────
# Ground Truth Test Suite
# ──────────────────────────────────────────────────────────────────

GROUND_TRUTH = [
    {
        "query": "Where is user authentication token validated?",
        "expected_symbols": ["verify_token", "validate_signature"],
        "expected_files": ["auth/service.py", "auth/crypto.py"],
        "category": "symbol_lookup",
    },
    {
        "query": "How are passwords hashed and verified?",
        "expected_symbols": ["hash_password", "verify_password"],
        "expected_files": ["auth/crypto.py"],
        "category": "semantic_search",
    },
    {
        "query": "What happens during checkout?",
        "expected_symbols": ["process_order"],
        "expected_files": ["orders/checkout.py"],
        "category": "semantic_search",
    },
    {
        "query": "Who calls execute_query?",
        "expected_symbols": ["execute_query", "fetch_records", "process_order"],
        "expected_files": ["db/query_executor.py", "orders/checkout.py"],
        "category": "call_chain",
    },
    {
        "query": "Where is input sanitized before database operations?",
        "expected_symbols": ["sanitize_input", "validate_sql"],
        "expected_files": ["auth/crypto.py", "db/query_executor.py"],
        "category": "semantic_search",
    },
    {
        "query": "How does the login flow work?",
        "expected_symbols": ["login", "handle_login"],
        "expected_files": ["auth/service.py", "api/routes.py"],
        "category": "semantic_search",
    },
    {
        "query": "calls sanitize_input before validate_signature",
        "expected_symbols": ["verify_token"],
        "expected_files": ["auth/service.py"],
        "category": "structural",
    },
    {
        "query": "Where are database connections managed?",
        "expected_symbols": ["connect_db", "ConnectionPool"],
        "expected_files": ["db/connection.py"],
        "category": "semantic_search",
    },
    {
        "query": "How are orders cancelled?",
        "expected_symbols": ["cancel_order", "handle_cancel_order"],
        "expected_files": ["orders/checkout.py", "api/routes.py"],
        "category": "semantic_search",
    },
    {
        "query": "What are the API routes?",
        "expected_symbols": [
            "handle_login", "handle_create_order",
            "handle_health_check",
        ],
        "expected_files": ["api/routes.py"],
        "category": "semantic_search",
    },
]


# ──────────────────────────────────────────────────────────────────
# Evaluation Metrics
# ──────────────────────────────────────────────────────────────────

def compute_mrr(
    results: List[Dict[str, Any]],
    expected_symbols: List[str],
    k: int = 5,
) -> float:
    """Compute Mean Reciprocal Rank at k.

    Returns 1/rank of the first result whose symbol matches
    any expected symbol, or 0 if no match in top-k.
    """
    for i, result in enumerate(results[:k]):
        symbol = result.get("symbol", "")
        for exp in expected_symbols:
            if exp.lower() in symbol.lower():
                return 1.0 / (i + 1)
    return 0.0


def compute_recall(
    results: List[Dict[str, Any]],
    expected_symbols: List[str],
    k: int = 5,
) -> float:
    """Compute Recall at k.

    Returns fraction of expected symbols found in top-k results.
    """
    found_symbols = set()
    for result in results[:k]:
        symbol = result.get("symbol", "")
        for exp in expected_symbols:
            if exp.lower() in symbol.lower():
                found_symbols.add(exp)

    if not expected_symbols:
        return 1.0

    return len(found_symbols) / len(expected_symbols)


def compute_file_recall(
    results: List[Dict[str, Any]],
    expected_files: List[str],
    k: int = 5,
) -> float:
    """Compute file-level Recall at k."""
    found_files = set()
    for result in results[:k]:
        result_file = result.get("file", "")
        for exp_file in expected_files:
            if exp_file in result_file or result_file.endswith(exp_file):
                found_files.add(exp_file)

    if not expected_files:
        return 1.0

    return len(found_files) / len(expected_files)


# ──────────────────────────────────────────────────────────────────
# Main Evaluation
# ──────────────────────────────────────────────────────────────────

def run_evaluation(repo_dir: str) -> Dict[str, Any]:
    """Run full evaluation suite against the real pipeline."""

    from pipeline_wiring import build_pipeline_from_directory

    print("=" * 60)
    print("SAMSUNG PRISM PIPELINE EVALUATION")
    print("=" * 60)
    print(f"Repository: {repo_dir}")
    print(f"Test queries: {len(GROUND_TRUTH)}")
    print()

    # Build pipeline
    print("[INFO] Building pipeline...")
    agent, graph, dna_store = build_pipeline_from_directory(repo_dir)
    print(f"[INFO] Indexed {len(dna_store)} chunks.")
    print()

    # Run queries
    all_mrr = []
    all_recall = []
    all_file_recall = []
    all_latencies = []
    per_query_results = []

    for idx, test_case in enumerate(GROUND_TRUTH, 1):
        query = test_case["query"]
        expected_symbols = test_case["expected_symbols"]
        expected_files = test_case["expected_files"]
        category = test_case["category"]

        print(f"[{idx}/{len(GROUND_TRUTH)}] {query}")

        start_time = time.time()
        response = agent.run(query)
        elapsed_ms = (time.time() - start_time) * 1000

        results = response.get("results", [])
        trace = response.get("agent_trace", [])

        # Compute metrics
        mrr = compute_mrr(results, expected_symbols)
        recall = compute_recall(results, expected_symbols)
        file_rec = compute_file_recall(results, expected_files)

        all_mrr.append(mrr)
        all_recall.append(recall)
        all_file_recall.append(file_rec)
        all_latencies.append(elapsed_ms)

        # Determine pass/fail
        passed = mrr > 0 and recall > 0

        status = "[PASS]" if passed else "[FAIL]"
        print(
            f"  {status}  MRR={mrr:.2f}  Recall={recall:.2f}  "
            f"FileRecall={file_rec:.2f}  Latency={elapsed_ms:.0f}ms"
        )

        if results:
            top = results[0]
            print(
                f"  Top: {top.get('symbol', '?')} in "
                f"{top.get('file', '?')} (score={top.get('final_score', 0):.3f})"
            )
        else:
            print("  Top: (no results)")

        per_query_results.append({
            "query": query,
            "category": category,
            "status": "PASS" if passed else "FAIL",
            "mrr": round(mrr, 3),
            "recall": round(recall, 3),
            "file_recall": round(file_rec, 3),
            "latency_ms": round(elapsed_ms, 1),
            "top_result": (
                results[0].get("symbol", "?") if results else "none"
            ),
            "trace_steps": len(trace),
        })

    # Aggregate
    print()
    print("=" * 60)
    print("AGGREGATE RESULTS")
    print("=" * 60)

    avg_mrr = sum(all_mrr) / len(all_mrr) if all_mrr else 0
    avg_recall = sum(all_recall) / len(all_recall) if all_recall else 0
    avg_file_recall = sum(all_file_recall) / len(all_file_recall) if all_file_recall else 0
    sorted_latencies = sorted(all_latencies)
    median_latency = sorted_latencies[len(sorted_latencies) // 2] if sorted_latencies else 0
    p95_latency = sorted_latencies[int(len(sorted_latencies) * 0.95)] if sorted_latencies else 0

    pass_count = sum(1 for r in per_query_results if r["status"] == "PASS")
    total = len(per_query_results)

    summary = {
        "total_queries": total,
        "passed": pass_count,
        "failed": total - pass_count,
        "pass_rate": round(pass_count / total * 100, 1) if total else 0,
        "avg_mrr_at_5": round(avg_mrr, 3),
        "avg_recall_at_5": round(avg_recall, 3),
        "avg_file_recall_at_5": round(avg_file_recall, 3),
        "median_latency_ms": round(median_latency, 1),
        "p95_latency_ms": round(p95_latency, 1),
        "per_query": per_query_results,
    }

    print(f"Pass Rate:      {pass_count}/{total} ({summary['pass_rate']}%)")
    print(f"Avg MRR@5:      {avg_mrr:.3f}")
    print(f"Avg Recall@5:   {avg_recall:.3f}")
    print(f"Avg FileRec@5:  {avg_file_recall:.3f}")
    print(f"Median Latency: {median_latency:.0f}ms")
    print(f"P95 Latency:    {p95_latency:.0f}ms")
    print()

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Samsung PRISM Agent Pipeline"
    )
    parser.add_argument(
        "--repo-dir",
        default=os.path.join(
            os.path.dirname(__file__), "..", "demo_repo"
        ),
        help="Path to the repository to index and evaluate.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to save JSON results.",
    )
    args = parser.parse_args()

    repo_dir = os.path.abspath(args.repo_dir)
    summary = run_evaluation(repo_dir)

    # Save results
    output_path = args.output or os.path.join(
        os.path.dirname(__file__), "eval_results.json"
    )
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"[INFO] Results saved to {output_path}")


if __name__ == "__main__":
    main()
