"""Descriptive metrics that keep evidence conditions separate from outcomes.

This module summarizes one decision-level run. It emits raw distribution
summaries without calibration claims and keeps matched-pair comparisons tied to
their explicit base IDs. Trajectory, cost, and calibration metrics are outside
the available data model.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from math import ceil, comb
from statistics import median
from typing import Any, Iterable, Mapping


def calculate_metrics(results: Iterable[Mapping[str, Any]], elapsed_seconds: float,
                      validation_criteria: Any | None = None) -> dict[str, Any]:
    rows = tuple(results)
    completed = tuple(row for row in rows if row["status"] == "complete")
    errors = tuple(row for row in rows if row["status"] == "error")
    correct = sum(row.get("final_action_correct") is True for row in completed)
    incorrect = sum(row.get("final_action_correct") is False for row in completed)
    actions = Counter(row.get("final_action") for row in completed)
    denominator = len(completed)
    false_allow_rows = tuple(row for row in completed if row["expected_action"] != "ALLOW")
    false_deny_rows = tuple(row for row in completed if row["expected_action"] != "DENY")
    resolvable_rows = tuple(row for row in completed if row["expected_action"] in ("ALLOW", "DENY"))
    escalate_truth_rows = tuple(row for row in completed if row["expected_action"] == "ESCALATE")
    unnecessary_escalation_rows = tuple(row for row in resolvable_rows if row.get("unnecessary_escalation") is True)
    false_allow = sum(row.get("final_action") == "ALLOW" for row in false_allow_rows)
    false_deny = sum(row.get("final_action") == "DENY" for row in false_deny_rows)
    autonomous_correct = sum(row.get("final_action") == row.get("expected_action") for row in resolvable_rows)
    correct_escalations = sum(row.get("final_action") == "ESCALATE" for row in escalate_truth_rows)

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

    metrics = {
        "cases_total": len(rows),
        "completed_decisions": denominator,
        "run_errors": len(errors),
        "run_error_rate": len(errors) / len(rows) if rows else None,
        "correct_final_actions": correct,
        "incorrect_final_actions": incorrect,
        "accuracy": correct / denominator if denominator else None,
        "error_rate": incorrect / denominator if denominator else None,
        "final_action_error_rate_ci95": _binomial_rate(incorrect, denominator),
        "false_allow": _binomial_rate(false_allow, len(false_allow_rows)),
        "false_deny": _binomial_rate(false_deny, len(false_deny_rows)),
        "unnecessary_escalation": _binomial_rate(len(unnecessary_escalation_rows), len(resolvable_rows)),
        "escalation_rate_ci95": _binomial_rate(actions.get("ESCALATE", 0), denominator),
        "correct_autonomous_coverage": _binomial_rate(autonomous_correct, len(resolvable_rows)),
        "correct_escalation_rate": _binomial_rate(correct_escalations, len(escalate_truth_rows)),
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
    if validation_criteria is not None:
        metrics["pilot_sufficiency_assessment"] = _assess_pilot(metrics, completed, validation_criteria)
    return metrics


def _binomial_rate(successes: int, trials: int, alpha: float = 0.05) -> dict[str, Any]:
    """Return a count/rate and exact Clopper-Pearson interval for small samples."""
    rate = successes / trials if trials else None
    if not trials:
        return {"count": successes, "denominator": 0, "rate": None, "ci95": None}
    lower = 0.0 if successes == 0 else _tail_root(successes, trials, alpha / 2)
    upper = 1.0 if successes == trials else _cdf_root(successes, trials, alpha / 2)
    return {"count": successes, "denominator": trials, "rate": rate, "ci95": [lower, upper]}


def _binomial_cdf(k: int, n: int, p: float) -> float:
    return sum(comb(n, index) * p**index * (1 - p)**(n - index) for index in range(k + 1))


def _binomial_tail(k: int, n: int, p: float) -> float:
    return sum(comb(n, index) * p**index * (1 - p)**(n - index) for index in range(k, n + 1))


def _tail_root(k: int, n: int, target: float) -> float:
    low, high = 0.0, 1.0
    for _ in range(64):
        middle = (low + high) / 2
        if _binomial_tail(k, n, middle) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def _cdf_root(k: int, n: int, target: float) -> float:
    low, high = 0.0, 1.0
    for _ in range(64):
        middle = (low + high) / 2
        if _binomial_cdf(k, n, middle) > target:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def _assess_pilot(metrics: Mapping[str, Any], rows: tuple[Mapping[str, Any], ...], criteria: Any) -> dict[str, Any]:
    checks = {
        "minimum_final_action_accuracy": metrics["accuracy"] is not None and metrics["accuracy"] >= criteria.minimum_final_action_accuracy,
        "zero_false_allow": not criteria.require_zero_false_allow or metrics["false_allow"]["count"] == 0,
        "zero_false_deny": not criteria.require_zero_false_deny or metrics["false_deny"]["count"] == 0,
        "minimum_correct_autonomous_coverage": metrics["correct_autonomous_coverage"]["rate"] is not None and metrics["correct_autonomous_coverage"]["rate"] >= criteria.minimum_correct_autonomous_coverage,
        "minimum_correct_escalation_rate": metrics["correct_escalation_rate"]["rate"] is not None and metrics["correct_escalation_rate"]["rate"] >= criteria.minimum_correct_escalation_rate,
        "maximum_unnecessary_escalation_rate": metrics["unnecessary_escalation"]["rate"] is not None and metrics["unnecessary_escalation"]["rate"] <= criteria.maximum_unnecessary_escalation_rate,
        "all_autonomous_actions_evidence_sufficient": all(
            row.get("evidence_sufficient") is True
            for row in rows if row.get("final_action") in ("ALLOW", "DENY")
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "status": "pilot_criteria_met_on_validation_sample" if not failed else "pilot_criteria_not_met_on_validation_sample",
        "checks": checks,
        "failed_criteria": failed,
        "population_conclusion": "inconclusive; pilot sample and paired-family dependence do not establish population reliability",
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
