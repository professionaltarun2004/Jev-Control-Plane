"""Validate the machine-readable output from the offline paired mock run.

This is used by CI and tests to check the serialization boundary between
label-free provider attempts and evaluator-owned outcomes. It verifies
plumbing only; it does not assess either provider's quality.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_control_plane.failure_lab.comparison import AttemptStatus, COMPARISON_SCHEMA_VERSION  # noqa: E402
from jev_control_plane.failure_lab.dataset import DatasetSplit, DatasetStore  # noqa: E402
from jev_control_plane.failure_lab.metrics import calculate_paired_metrics  # noqa: E402

VALID_ACTIONS = {"ALLOW", "DENY", "ESCALATE"}
LABEL_FIELDS = {
    "expected_action", "expected_actions", "ground_truth", "ground_truth_action",
    "annotation", "annotations", "annotation_note", "annotation_notes", "label", "labels",
}
EXPECTED_CONDITIONS = {"jev_mock", "llm_judge_mock"}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path.name}:{line_number} must be a JSON object")
        rows.append(value)
    return rows


def _contains_label_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(str(key).lower() in LABEL_FIELDS or _contains_label_key(item)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_label_key(item) for item in value)
    return False


def validate_artifacts(output_json: str | Path, repo_root: str | Path = ROOT) -> dict[str, int]:
    """Validate all four artifacts against the actual Development case set."""
    root = Path(repo_root)
    output = _read_json(Path(output_json))
    run_dir = Path(output["run_dir"])
    if not run_dir.is_absolute():
        run_dir = root / run_dir
    manifest = _read_json(run_dir / "manifest.json")
    summary = _read_json(run_dir / "summary.json")
    attempts = _read_jsonl(run_dir / "attempts.jsonl")
    pairs = _read_jsonl(run_dir / "pairs.jsonl")

    run_id = output.get("run_id")
    if not run_id or manifest.get("run_id") != run_id or summary.get("run_id") != run_id:
        raise ValueError("stdout, manifest, and summary run IDs must match")
    if manifest.get("status") != "complete" or manifest.get("purpose") != "synthetic_development_plumbing":
        raise ValueError("manifest must identify a completed synthetic Development plumbing run")
    if manifest.get("dataset_split") != DatasetSplit.DEVELOPMENT:
        raise ValueError("comparison artifacts must identify the Development split")
    config = manifest.get("configuration", {})
    comparison = config.get("comparison", {})
    jev = config.get("jev", {})
    jev_experiment = jev.get("experiment_config", {})
    judge = config.get("llm_mock", {})
    if manifest.get("dataset_id") != comparison.get("dataset_id"):
        raise ValueError("manifest dataset ID must match the comparison configuration")
    canonical_config = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)
    config_digest = hashlib.sha256(canonical_config.encode("utf-8")).hexdigest()
    if manifest.get("configuration_sha256") != config_digest:
        raise ValueError("manifest configuration digest does not match its configuration")
    if comparison.get("split") != DatasetSplit.DEVELOPMENT or jev_experiment.get("split") != DatasetSplit.DEVELOPMENT:
        raise ValueError("both conditions must use Development")
    if jev_experiment.get("execution_mode") != "mock" or jev.get("provider_id") != "jev-shaped-deterministic-mock":
        raise ValueError("Jev condition must use the deterministic mock adapter")
    if judge.get("provider_id") != "llm_judge_mock" or judge.get("policy_applied") is not False:
        raise ValueError("judge condition must be the direct offline mock action fixture")
    if config.get("policy_level_comparison_enabled") is not False or summary.get("policy_level_comparison_enabled") is not False:
        raise ValueError("policy-level comparison must remain disabled")
    if summary.get("measurement_scope") != "synthetic Development plumbing; not Jev or LLM performance":
        raise ValueError("summary must label its measurement scope as synthetic plumbing")
    if summary.get("provider_evidence_equivalence_claimed") is not False:
        raise ValueError("provider evidence equivalence must not be claimed")

    cases = DatasetStore(root / "experiments" / "datasets").load_split(
        DatasetSplit.DEVELOPMENT, dataset_id=manifest["dataset_id"]
    )
    case_ids = [case.case_id for case in cases]
    if not case_ids or len(case_ids) != len(set(case_ids)):
        raise ValueError("Development case IDs must be present and unique")
    expected = {case.case_id: case.expected_action.value for case in cases}
    by_id = {case.case_id: case for case in cases}
    expected_conditions = {jev.get("condition_id"), judge.get("condition_id")}
    if expected_conditions != EXPECTED_CONDITIONS:
        raise ValueError("comparison must contain the Jev mock and judge mock conditions")
    if len(attempts) != len(cases) * 2:
        raise ValueError("attempt count must be exactly twice the Development case count")

    attempts_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    valid_statuses = {status.value for status in AttemptStatus}
    for row in attempts:
        if row.get("schema_version") != COMPARISON_SCHEMA_VERSION or row.get("run_id") != run_id:
            raise ValueError("attempt schema or run ID mismatch")
        case_id, condition = row.get("case_id"), row.get("condition_id")
        if case_id not in expected or condition not in EXPECTED_CONDITIONS:
            raise ValueError("attempt references an unexpected case or condition")
        key = (case_id, condition)
        if key in attempts_by_key:
            raise ValueError(f"duplicate attempt for {key}")
        attempts_by_key[key] = row
        status, action = row.get("status"), row.get("normalized_action")
        if status not in valid_statuses:
            raise ValueError(f"unrecognized provider status: {status}")
        if (status == AttemptStatus.COMPLETED.value) != (action in VALID_ACTIONS):
            raise ValueError("normalized action must be valid exactly for completed attempts")
        if status != AttemptStatus.COMPLETED.value and not row.get("error_category"):
            raise ValueError("non-completed attempts require an explicit error category")
        if condition == "jev_mock":
            if row.get("provider_id") != "jev-shaped-deterministic-mock" or not isinstance(row.get("policy_result"), dict):
                raise ValueError("Jev mock attempt must retain its provider identity and policy result")
        elif row.get("provider_id") != "llm_judge_mock" or row.get("policy_result") is not None:
            raise ValueError("judge mock action must remain separate from Jev policy results")
        latency = row.get("latency_ms")
        if not isinstance(latency, (int, float)) or not math.isfinite(latency) or latency < 0:
            raise ValueError("attempt latency must be finite and non-negative")
        if _contains_label_key(row):
            raise ValueError("provider attempts must not contain evaluator-only labels or annotations")
    all_keys = {(case_id, condition) for case_id in case_ids for condition in EXPECTED_CONDITIONS}
    if set(attempts_by_key) != all_keys:
        raise ValueError("attempts must form the complete case-by-condition matrix")
    expected_execution_status = (
        "all_attempts_returned_actions"
        if all(row["status"] == AttemptStatus.COMPLETED.value for row in attempts)
        else "contains_non_decision_attempts"
    )
    if manifest.get("execution_status") != expected_execution_status:
        raise ValueError("manifest execution status does not reflect provider and parsing outcomes")

    if len(pairs) != len(cases) or summary.get("pairs_total") != len(cases):
        raise ValueError("there must be exactly one evaluator pair per Development case")
    pairs_by_id = {}
    for row in pairs:
        case_id = row.get("case_id")
        if case_id not in expected or case_id in pairs_by_id:
            raise ValueError("pairs contain an unexpected or duplicate case ID")
        pairs_by_id[case_id] = row
        if row.get("schema_version") != COMPARISON_SCHEMA_VERSION or row.get("run_id") != run_id:
            raise ValueError("pair schema or run ID mismatch")
        if row.get("expected_action") != expected[case_id]:
            raise ValueError(f"pair ground truth does not match dataset for {case_id}")
        case = by_id[case_id]
        if row.get("ground_truth", {}).get("source") != case.ground_truth.source.value:
            raise ValueError(f"ground-truth provenance mismatch for {case_id}")
        if row.get("ground_truth", {}).get("certainty") != case.ground_truth.certainty.value:
            raise ValueError(f"ground-truth certainty mismatch for {case_id}")
        if row.get("ground_truth", {}).get("reference") != case.ground_truth.reference:
            raise ValueError(f"ground-truth reference mismatch for {case_id}")
        for prefix, condition in (("jev", "jev_mock"), ("llm", "llm_judge_mock")):
            attempt = attempts_by_key[(case_id, condition)]
            if row.get(f"{prefix}_condition_id") != condition:
                raise ValueError("pair condition identity mismatch")
            if row.get(f"{prefix}_status") != attempt["status"] or row.get(f"{prefix}_action") != attempt["normalized_action"]:
                raise ValueError("pair output does not match its provider attempt")
            correct = (attempt["normalized_action"] == expected[case_id]
                       if attempt["status"] == AttemptStatus.COMPLETED.value else None)
            if row.get(f"{prefix}_correct") is not correct:
                raise ValueError("pair correctness does not match action and ground truth")

    metrics = calculate_paired_metrics(case_ids, expected, attempts,
                                      conditions=("jev_mock", "llm_judge_mock"))
    if summary.get("cases_total") != len(cases) or summary.get("attempts_total") != len(attempts):
        raise ValueError("summary case/attempt totals do not match the artifact rows")
    if summary.get("pairs_total") != len(pairs):
        raise ValueError("summary pair total does not match evaluator-owned pair rows")
    for key in ("cases_total", "both_valid_action_denominator",
                "pairs_with_both_valid_actions", "pairs_with_one_or_more_non_decision_status",
                "paired_outcomes", "by_condition"):
        expected_value = metrics.get(key)
        observed_value = summary.get(key)
        if expected_value != observed_value:
            raise ValueError(f"summary metric {key} does not reconcile with attempts and outcomes")
    if set(pairs_by_id) != set(case_ids):
        raise ValueError("pairs are missing Development case IDs")
    if output.get("metrics") != summary:
        raise ValueError("stdout metrics must match the persisted summary")
    return {"cases": len(cases), "attempts": len(attempts), "pairs": len(pairs)}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python scripts/validate_comparison_artifacts.py RUN_OUTPUT.json", file=sys.stderr)
        return 2
    counts = validate_artifacts(args[0])
    print(f"Validated paired mock artifacts: {counts['cases']} cases, "
          f"{counts['attempts']} attempts, {counts['pairs']} pairs (synthetic Development plumbing)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
