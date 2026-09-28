"""Metrics computable from decision records in one experiment run.

This module reports exact final-action outcomes, rates, latency, throughput,
agreement, escalation, and failure labels. It deliberately omits calibration
and cost metrics because this run schema does not yet establish their validity.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from math import ceil
from statistics import median
from typing import Any, Iterable, Mapping


def calculate_metrics(results: Iterable[Mapping[str, Any]], elapsed_seconds: float) -> dict[str, Any]:
    rows = tuple(results)
    completed = tuple(row for row in rows if row["status"] == "complete")
    errors = tuple(row for row in rows if row["status"] == "error")
    correct = sum(row["final_action_correct"] is True for row in completed)
    incorrect = len(completed) - correct
    actions = Counter(row["final_action"] for row in completed)
    denominator = len(completed)
    agreement_counts = Counter(
        "agree" if row.get("jev_view_agreement", row.get("view_agreement")) is True else
        "disagree" if row.get("jev_view_agreement", row.get("view_agreement")) is False else "unmapped"
        for row in completed
    )
    failure_counts = Counter(row["failure_category"] for row in rows if row["failure_category"])
    latencies = sorted(float(row["latency_ms"]) for row in rows)
    p95 = latencies[ceil(0.95 * len(latencies)) - 1] if len(latencies) >= 20 else None

    by_family: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        family = row.get("perturbation_family") or "unannotated"
        by_family[family].append(row)
    family_summary = {
        family: {
            "cases": len(family_rows),
            "completed": sum(row["status"] == "complete" for row in family_rows),
            "correct": sum(row.get("final_action_correct") is True for row in family_rows),
            "errors": sum(row.get("status") == "error" or row.get("final_action_correct") is False for row in family_rows),
            "escalations": sum(row.get("final_action") == "ESCALATE" for row in family_rows),
        }
        for family, family_rows in sorted(by_family.items())
    }
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in completed:
        confusion[row["expected_action"]][row["final_action"]] += 1

    return {
        "cases_total": len(rows),
        "completed_decisions": denominator,
        "run_errors": len(errors),
        "run_error_rate": len(errors) / len(rows) if rows else None,
        "correct_final_actions": correct,
        "incorrect_final_actions": incorrect,
        "accuracy": correct / denominator if denominator else None,
        "error_rate": incorrect / denominator if denominator else None,
        "action_counts": {action: actions.get(action, 0) for action in ("ALLOW", "DENY", "ESCALATE")},
        "action_rates": {action: actions.get(action, 0) / denominator if denominator else None
                         for action in ("ALLOW", "DENY", "ESCALATE")},
        "policy_triggered_escalations": actions.get("ESCALATE", 0),
        "view_agreement_counts": {key: agreement_counts.get(key, 0) for key in ("agree", "disagree", "unmapped")},
        "failure_categories": dict(sorted(failure_counts.items())),
        "action_confusion": {truth: dict(sorted(predicted.items())) for truth, predicted in sorted(confusion.items())},
        "latency_observations": len(latencies),
        "median_latency_ms": median(latencies) if latencies else None,
        "p95_latency_ms": p95,
        "throughput_cases_per_second": len(rows) / elapsed_seconds if elapsed_seconds > 0 else None,
        "throughput_denominator": "all attempted cases; mock throughput is harness throughput, not Jev throughput",
        "by_perturbation_family": family_summary,
    }
