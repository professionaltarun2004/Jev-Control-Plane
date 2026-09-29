"""Run one benchmark split through Jev, policy, records, and metrics.

The runner is decision-first and uses only the existing Jev adapter port. In
mock mode it swaps in :class:`DeterministicMockJevAdapter` for local plumbing
checks. To understand one result, follow ``run`` into ``ControlPlane.evaluate``
and then to :func:`calculate_metrics`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from ..aggregator import TransparentEvidenceAggregator
from ..domain import ControlAction, DecisionRequest, Primitive
from ..jev import JevAdapter, TypeSafeJevAdapter
from ..policy import DeterministicPolicy
from ..runtime import ControlPlane
from ..records import json_safe
from .artifacts import ExperimentArtifactStore
from .benchmark import BenchmarkCase, OutcomeCategory
from .dataset import DatasetSplit, DatasetStore, HoldoutReadPermit
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
        run_id = run_id or f"{config.experiment_id}-{uuid4().hex[:12]}"
        permit: HoldoutReadPermit | None = None
        if config.split == DatasetSplit.HOLDOUT:
            if config.execution_mode is not ExecutionMode.JEV_LIVE or self.adapter_override is not None:
                raise ValueError("Holdout requires the locked live TypeSafe Jev execution path")
            if lock_id is None:
                raise ValueError("Holdout evaluation requires a saved Validation configuration lock")
            lock = self.artifacts.read_lock(lock_id)
            runtime = self.artifacts.reproducibility_metadata()
            validation_case_digest = self.datasets.split_digest(DatasetSplit.VALIDATION)
            validation_annotation_digest = self.datasets.annotation_digest(DatasetSplit.VALIDATION)
            validation_run_digest = self.artifacts.validation_run_digest(lock.source_validation_run_id)
            permit = lock.verify(
                config, runtime, validation_case_digest, validation_annotation_digest,
                validation_run_digest,
            )
            self.artifacts.assert_holdout_unclaimed(lock)
            case_digest = self.datasets.split_digest(DatasetSplit.HOLDOUT, permit=permit, dataset_id=config.dataset_id)
            annotation_digest = self.datasets.annotation_digest(DatasetSplit.HOLDOUT, permit=permit, dataset_id=config.dataset_id)
            if case_digest != lock.holdout_dataset_sha256 or annotation_digest != lock.holdout_annotation_sha256:
                raise ValueError("Holdout data or annotations changed after LOCK")
            # Claim before loading labels or calling Jev. Interrupted runs stay consumed.
            self.artifacts.claim_holdout(lock, run_id)
        else:
            case_digest = self.datasets.split_digest(config.split)
            annotation_digest = self.datasets.annotation_digest(config.split)
        cases = self.datasets.load_split(config.split, permit=permit, dataset_id=config.dataset_id if permit else None)
        if not cases:
            raise ValueError(f"cannot run an experiment on an empty {config.split} split")
        annotations = self.datasets.annotations_for(
            (case.case_id for case in cases), config.split,
            permit=permit, dataset_id=config.dataset_id if permit else None,
        )
        if (case_digest != self.datasets.split_digest(config.split, permit=permit, dataset_id=config.dataset_id if permit else None)
                or annotation_digest != self.datasets.annotation_digest(config.split, permit=permit, dataset_id=config.dataset_id if permit else None)):
            raise ValueError("dataset changed while the run inputs were being loaded")
        adapter = self.adapter_override or self._adapter_for(config)
        run_dir = self.artifacts.begin_run(
            run_id, config, case_digest, annotation_digest, lock_id,
            adapter_implementation=f"{type(adapter).__module__}.{type(adapter).__qualname__}",
            adapter_injected_for_test=self.adapter_override is not None,
        )
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
            consensus = None
            if evidence["agreement_status"] == "agreement" and hints and len(set(hints.values())) == 1:
                consensus = next(iter(hints.values()))
            expected = case.expected_action.value
            final_action = record.policy["action"]
            jev_error = None if consensus is None else consensus != expected
            correct = final_action == expected
            policy_error = None if consensus is None else (not correct and jev_error is False)
            outcome_categories = []
            if not correct:
                outcome_categories.append(OutcomeCategory.FINAL_ACTION_ERROR.value)
            if jev_error is True:
                outcome_categories.append(OutcomeCategory.JEV_DECISION_ERROR.value)
            if policy_error is True:
                outcome_categories.append(OutcomeCategory.POLICY_ACTION_ERROR.value)
            evidence_conditions = ExperimentRunner._evidence_conditions(record, config)
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
                "perturbation_description": annotation.description if annotation else None,
                "base_case_id": annotation.base_case_id if annotation else None,
                "jev_view_agreement": evidence["agreement"],
                "view_agreement_status": evidence["agreement_status"],
                "view_disagreement": bool(evidence["disagreeing_views"]),
                "disagreeing_views": evidence["disagreeing_views"],
                "unmapped_views": evidence["unmapped_views"],
                "evidence_conditions": evidence_conditions,
                "jev_consensus_action": consensus,
                "jev_decision_error": jev_error,
                "final_action": final_action,
                "final_action_correct": correct,
                "final_action_error": not correct,
                "policy_action_error": policy_error,
                "runner_error": False,
                "policy_triggered_escalation": final_action == ControlAction.ESCALATE.value,
                "outcome_categories": outcome_categories,
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
                "perturbation_description": annotation.description if annotation else None,
                "base_case_id": annotation.base_case_id if annotation else None,
                "jev_view_agreement": None,
                "view_agreement_status": None,
                "view_disagreement": None,
                "disagreeing_views": [],
                "unmapped_views": [],
                "evidence_conditions": None,
                "jev_consensus_action": None,
                "jev_decision_error": None,
                "final_action": None,
                "final_action_correct": None,
                "final_action_error": None,
                "policy_action_error": None,
                "runner_error": True,
                "policy_triggered_escalation": False,
                "outcome_categories": [OutcomeCategory.RUNNER_ERROR.value],
                "latency_ms": (perf_counter() - started) * 1000,
                "decision_record": None,
                "error_type": type(exc).__name__,
            }

    @staticmethod
    def _evidence_conditions(record: Any, config: ExperimentConfig) -> dict[str, list[str]]:
        results = record.evidence["results"]
        low_confidence: list[str] = []
        missing_confidence: list[str] = []
        low_noul_probability: list[str] = []
        missing_noul_probability: list[str] = []
        for result in results:
            primitive = result["primitive"]
            view_id = result["view_id"]
            confidence = result["confidence"]
            if primitive in ("choice", "score") and confidence is None:
                missing_confidence.append(view_id)
            elif confidence is not None and confidence < config.policy.minimum_confidence:
                low_confidence.append(view_id)
            if primitive == "noul":
                probabilities = result["probabilities"] or {}
                support = probabilities.get(str(result["answer"]).lower())
                if support is None:
                    missing_noul_probability.append(view_id)
                elif support < config.policy.minimum_noul_probability:
                    low_noul_probability.append(view_id)
        return {
            "low_confidence_views": low_confidence,
            "missing_confidence_views": missing_confidence,
            "low_noul_probability_views": low_noul_probability,
            "missing_noul_probability_views": missing_noul_probability,
        }
