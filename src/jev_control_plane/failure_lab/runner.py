"""Run one benchmark split through Jev, policy, records, and metrics.

The runner is decision-first and uses only the existing Jev adapter port. In
mock mode it swaps in :class:`DeterministicMockJevAdapter` for local plumbing
checks. To understand one result, follow ``run`` into ``ControlPlane.evaluate``
and then to :func:`calculate_metrics`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from ..aggregator import TransparentEvidenceAggregator
from ..domain import ControlAction, DecisionRequest
from ..jev import JevAdapter, TypeSafeJevAdapter
from ..policy import DeterministicPolicy
from ..runtime import ControlPlane
from ..records import json_safe
from .artifacts import ExperimentArtifactStore
from .benchmark import BenchmarkCase, FailureCategory
from .dataset import DatasetSplit, DatasetStore
from .experiment import ExecutionMode, ExperimentConfig
from .metrics import calculate_metrics
from .mock import DeterministicMockJevAdapter


@dataclass(frozen=True)
class RunOutcome:
    run_id: str
    run_dir: Path
    metrics: dict[str, Any]


class ExperimentRunner:
    """Execute all cases in exactly one configured split and retain every try."""

    def __init__(
        self,
        datasets: DatasetStore,
        artifacts: ExperimentArtifactStore,
        adapter: JevAdapter | None = None,
    ) -> None:
        self.datasets = datasets
        self.artifacts = artifacts
        # Injection is the narrow test seam; production mode still selects only
        # TypeSafe Jev or its deterministic Jev-shaped mock.
        self.adapter_override = adapter

    def run(self, config: ExperimentConfig, lock_id: str | None = None, run_id: str | None = None) -> RunOutcome:
        if config.split == DatasetSplit.HOLDOUT:
            if lock_id is None:
                raise ValueError("Holdout evaluation requires a saved Validation configuration lock")
            lock = self.artifacts.read_lock(lock_id)
            lock.verify(config)
        run_id = run_id or f"{config.experiment_id}-{uuid4().hex[:12]}"
        cases = self.datasets.load_split(config.split)
        annotations = self.datasets.annotations_for(case.case_id for case in cases)
        run_dir = self.artifacts.begin_run(run_id, config, self.datasets.split_digest(config.split), lock_id)
        adapter = self.adapter_override or self._adapter_for(config)
        control = ControlPlane(adapter, TransparentEvidenceAggregator(), DeterministicPolicy(config.policy))
        rows: list[dict[str, Any]] = []
        started = perf_counter()
        try:
            for case in cases:
                row = self._evaluate_case(case, annotations.get(case.case_id), config, run_id, control)
                self.artifacts.append_result(run_dir, row)
                rows.append(row)
            elapsed = perf_counter() - started
            metrics = calculate_metrics(rows, elapsed)
            metrics.update({
                "experiment_id": config.experiment_id,
                "run_id": run_id,
                "dataset_id": config.dataset_id,
                "dataset_split": config.split,
                "execution_mode": config.execution_mode.value,
                "measurement_scope": "mock control-loop timing" if config.execution_mode is ExecutionMode.MOCK else "end-to-end Jev control-loop timing",
            })
            status = "completed_with_case_errors" if metrics["run_errors"] else "complete"
            self.artifacts.finish_run(run_dir, status, metrics)
            return RunOutcome(run_id, run_dir, metrics)
        except Exception:
            # Do not delete a partial run. Its running manifest and prior case
            # rows are evidence that execution stopped before the gate finished.
            raise

    @staticmethod
    def _adapter_for(config: ExperimentConfig) -> JevAdapter:
        if config.execution_mode is ExecutionMode.MOCK:
            return DeterministicMockJevAdapter()
        return TypeSafeJevAdapter(model=config.jev_model)

    @staticmethod
    def _evaluate_case(
        case: BenchmarkCase,
        annotation: Any,
        config: ExperimentConfig,
        run_id: str,
        control: ControlPlane,
    ) -> dict[str, Any]:
        started = perf_counter()
        try:
            request = DecisionRequest(
                agent_state=case.state,
                question=case.decision,
                views=config.views,
                metadata={"experiment_id": config.experiment_id, "case_id": case.case_id,
                          "dataset_split": config.split},
                decision_id=f"{run_id}:{case.case_id}",
            )
            record = control.evaluate(request)
            evidence = record.evidence
            hints = evidence["action_hints"]
            agreement = evidence["agreement"]
            consensus = None
            if agreement is True and hints and len(set(hints.values())) == 1:
                consensus = next(iter(hints.values()))
            expected = case.expected_action.value
            final_action = record.policy["action"]
            jev_error = None if consensus is None else consensus != expected
            correct = final_action == expected
            if agreement is False:
                failure = FailureCategory.CROSS_VIEW_DISAGREEMENT.value
            elif agreement is None:
                failure = FailureCategory.UNMAPPED_EVIDENCE.value
            elif jev_error:
                failure = FailureCategory.JEV_DECISION_ERROR.value
            elif not correct:
                failure = FailureCategory.POLICY_ACTION_ERROR.value
            else:
                failure = None
            return {
                "run_id": run_id,
                "experiment_id": config.experiment_id,
                "dataset_id": config.dataset_id,
                "dataset_split": config.split,
                "execution_mode": config.execution_mode.value,
                "case_id": case.case_id,
                "status": "complete",
                "expected_action": expected,
                "ground_truth": {
                    "source": case.ground_truth.source.value,
                    "reference": case.ground_truth.reference,
                    "certainty": case.ground_truth.certainty.value,
                },
                "perturbation_family": annotation.family.value if annotation else None,
                "jev_view_agreement": agreement,
                "jev_consensus_action": consensus,
                "jev_decision_error": jev_error,
                "final_action": final_action,
                "final_action_correct": correct,
                "policy_action_error": (not correct and jev_error is False),
                "policy_triggered_escalation": final_action == ControlAction.ESCALATE.value,
                "failure_category": failure,
                "latency_ms": (perf_counter() - started) * 1000,
                "decision_record": json_safe(record),
                "error_type": None,
            }
        except Exception as exc:
            # Keep the case ID, truth provenance and exception type, but avoid
            # persisting arbitrary exception text that might include secrets.
            return {
                "run_id": run_id,
                "experiment_id": config.experiment_id,
                "dataset_id": config.dataset_id,
                "dataset_split": config.split,
                "execution_mode": config.execution_mode.value,
                "case_id": case.case_id,
                "status": "error",
                "expected_action": case.expected_action.value,
                "ground_truth": {"source": case.ground_truth.source.value,
                                 "reference": case.ground_truth.reference,
                                 "certainty": case.ground_truth.certainty.value},
                "perturbation_family": annotation.family.value if annotation else None,
                "jev_view_agreement": None,
                "jev_consensus_action": None,
                "jev_decision_error": None,
                "final_action": None,
                "final_action_correct": None,
                "policy_action_error": None,
                "policy_triggered_escalation": False,
                "failure_category": FailureCategory.RUN_ERROR.value,
                "latency_ms": (perf_counter() - started) * 1000,
                "decision_record": None,
                "error_type": type(exc).__name__,
            }
