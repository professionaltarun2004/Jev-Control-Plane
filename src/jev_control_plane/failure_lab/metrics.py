"""Descriptive metrics that keep evidence conditions separate from outcomes.

This module summarizes one decision-level run. It emits raw distribution
summaries without calibration claims and keeps matched-pair comparisons tied to
their explicit base IDs. Trajectory, cost, and calibration metrics are outside
the available data model.
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
    correct = sum(row.get("final_action_correct") is True for row in completed)
    incorrect = sum(row.get("final_action_correct") is False for row in completed)
    actions = Counter(row.get("final_action") for row in completed)
    denominator = len(completed)

    agreement_counts = Counter(row.get("view_agreement_status", _legacy_agreement(row)) for row in completed)
    evidence_conditions = Counter()
    for row in completed:
        evidence_conditions["view_disagreement"] += row.get("view_disagreement") is True
        evidence_conditions["unmapped_evidence"] += bool(row.get("unmapped_views"))
        details = row.get("evidence_conditions") or {}
        for key in ("low_confidence_views", "missing_confidence_views", "low_noul_probability_views", "missing_noul_probability_views"):
            evidence_conditions[key] += bool(details.get(key))

    outcome_counts = Counter(category for row in rows for category in row.get("outcome_categories", ()))
    latencies = sorted(float(row["latency_ms"]) for row in rows)
    p95 = latencies[ceil(0.95 * len(latencies)) - 1] if len(latencies) >= 20 else None
    by_family = _group_rows(rows, "perturbation_family", "unannotated")
    family_summary = {family: _outcome_summary(group) for family, group in sorted(by_family.items())}
    by_certainty = _group_rows(completed, "ground_truth", "unknown", nested_key="certainty")
    by_source = _group_rows(completed, "ground_truth", "unknown", nested_key="source")
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
        "escalation_rate": actions.get("ESCALATE", 0) / denominator if denominator else None,
        "evidence_status_counts": {status: agreement_counts.get(status, 0) for status in
                                   ("agreement", "disagreement", "partial", "unmapped", "mixed")},
        "evidence_condition_counts": dict(sorted(evidence_conditions.items())),
        "outcome_category_counts": dict(sorted(outcome_counts.items())),
        "action_confusion": {truth: dict(sorted(predicted.items())) for truth, predicted in sorted(confusion.items())},
        "by_ground_truth_certainty": {key: _outcome_summary(group) for key, group in sorted(by_certainty.items())},
        "by_ground_truth_source": {key: _outcome_summary(group) for key, group in sorted(by_source.items())},
        "latency_observations": len(latencies),
        "median_latency_ms": median(latencies) if latencies else None,
        "p95_latency_ms": p95,
        "throughput_cases_per_second": len(rows) / elapsed_seconds if elapsed_seconds > 0 else None,
        "throughput_denominator": "attempted cases / this run's elapsed time; not a load or capacity claim",
        "per_view_evidence_distributions": _view_distributions(completed),
        "by_perturbation_family": family_summary,
        "matched_perturbation_pairs": _matched_pairs(rows),
    }


def _legacy_agreement(row: Mapping[str, Any]) -> str:
    value = row.get("jev_view_agreement", row.get("view_agreement"))
    return "agreement" if value is True else "disagreement" if value is False else "unmapped"


def _group_rows(rows: Iterable[Mapping[str, Any]], key: str, fallback: str,
                nested_key: str | None = None) -> dict[str, list[Mapping[str, Any]]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(key, fallback)
        if nested_key:
            value = value.get(nested_key, fallback) if isinstance(value, Mapping) else fallback
        groups[str(value or fallback)].append(row)
    return groups


def _outcome_summary(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = tuple(rows)
    completed = tuple(row for row in items if row.get("status") == "complete")
    n = len(completed)
    return {
        "cases": len(items),
        "completed": n,
        "correct": sum(row.get("final_action_correct") is True for row in completed),
        "incorrect": sum(row.get("final_action_correct") is False for row in completed),
        "runner_errors": sum(row.get("status") == "error" for row in items),
        "escalations": sum(row.get("final_action") == "ESCALATE" for row in completed),
        "accuracy": sum(row.get("final_action_correct") is True for row in completed) / n if n else None,
    }


def _view_distributions(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = defaultdict(lambda: {"primitive": None, "confidence": [], "probabilities": defaultdict(list)})
    for row in rows:
        record = row.get("decision_record") or {}
        evidence = record.get("evidence", {})
        for result in evidence.get("results", ()):
            target = values[result["view_id"]]
            target["primitive"] = result.get("primitive")
            if result.get("confidence") is not None:
                target["confidence"].append(float(result["confidence"]))
            for outcome, probability in (result.get("probabilities") or {}).items():
                target["probabilities"][str(outcome)].append(float(probability))
    return {
        view_id: {
            "primitive": item["primitive"],
            "confidence": _distribution(item["confidence"]),
            "probabilities": {key: _distribution(samples) for key, samples in sorted(item["probabilities"].items())},
        }
        for view_id, item in sorted(values.items())
    }


def _distribution(values: list[float]) -> dict[str, Any]:
    return {"observations": len(values), "min": min(values), "median": median(values), "max": max(values)} if values else {"observations": 0, "min": None, "median": None, "max": None}


def _matched_pairs(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = tuple(rows)
    # Metrics can also be computed from small hand-built fixtures; rows without
    # case identity cannot participate in a matched-pair join.
    by_id = {row["case_id"]: row for row in rows if row.get("case_id") is not None}
    pairs = []
    for perturbed in rows:
        base_id = perturbed.get("base_case_id")
        if not base_id or base_id not in by_id:
            continue
        base = by_id[base_id]
        if base.get("status") != "complete" or perturbed.get("status") != "complete":
            pairs.append({"base_case_id": base_id, "perturbed_case_id": perturbed["case_id"], "status": "incomplete"})
            continue
        pairs.append({
            "base_case_id": base_id,
            "perturbed_case_id": perturbed.get("case_id"),
            "family": perturbed.get("perturbation_family"),
            "expected_action_unchanged": base.get("expected_action") == perturbed.get("expected_action"),
            "base_final_action": base.get("final_action"),
            "perturbed_final_action": perturbed.get("final_action"),
            "base_correct": base.get("final_action_correct"),
            "perturbed_correct": perturbed.get("final_action_correct"),
            "base_view_agreement_status": base.get("view_agreement_status"),
            "perturbed_view_agreement_status": perturbed.get("view_agreement_status"),
            "base_latency_ms": base.get("latency_ms"),
            "perturbed_latency_ms": perturbed.get("latency_ms"),
        })
    return pairs
