"""Minimal benchmark case and separate annotations.

This module defines independent ground truth without guessing Jev's per-view
answers. Dataset storage lives in :mod:`dataset`; the experiment runner consumes
these cases only after an explicit split is selected.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from ..domain import AgentState, ControlAction


class GroundTruthSource(StrEnum):
    DETERMINISTIC_RULE = "deterministic_rule"
    HUMAN_LABEL = "human_label"
    LABELED_DATASET = "labeled_dataset"
    ENVIRONMENT_OUTCOME = "environment_outcome"


class GroundTruthCertainty(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class GroundTruthProvenance:
    source: GroundTruthSource
    reference: str
    certainty: GroundTruthCertainty

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValueError("ground-truth reference must not be empty")


@dataclass(frozen=True)
class BenchmarkCase:
    """One decision, its minimal current state, and independently sourced truth."""

    case_id: str
    state: AgentState
    decision: str
    expected_action: ControlAction
    ground_truth: GroundTruthProvenance

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must not be empty")
        if not self.decision.strip():
            raise ValueError("decision must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "state": {
                "user_request": self.state.user_request,
                "previous_action": self.state.previous_action,
                "tool_result": self.state.tool_result,
                "current_action": self.state.current_action,
            },
            "decision": self.decision,
            "ground_truth": {
                "expected_action": self.expected_action.value,
                "source": self.ground_truth.source.value,
                "reference": self.ground_truth.reference,
                "certainty": self.ground_truth.certainty.value,
            },
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BenchmarkCase":
        expected = {"case_id", "state", "decision", "ground_truth"}
        if set(value) != expected:
            raise ValueError(f"benchmark case fields must be exactly {sorted(expected)}")
        state = value["state"]
        state_fields = {"user_request", "previous_action", "tool_result", "current_action"}
        if not isinstance(state, Mapping) or not set(state).issubset(state_fields):
            raise ValueError("benchmark state contains unsupported fields")
        ground_truth = value["ground_truth"]
        truth_fields = {"expected_action", "source", "reference", "certainty"}
        if not isinstance(ground_truth, Mapping) or set(ground_truth) != truth_fields:
            raise ValueError("ground_truth must include action, source, reference, and certainty")
        return cls(
            case_id=str(value["case_id"]),
            state=AgentState(**state),
            decision=str(value["decision"]),
            expected_action=ControlAction(ground_truth["expected_action"]),
            ground_truth=GroundTruthProvenance(
                GroundTruthSource(ground_truth["source"]),
                str(ground_truth["reference"]),
                GroundTruthCertainty(ground_truth["certainty"]),
            ),
        )


class PerturbationFamily(StrEnum):
    CLEAN_BASELINE = "clean_baseline"
    IRRELEVANT_CONTEXT = "irrelevant_context"
    AMBIGUITY = "ambiguity"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    DISTRIBUTION_SHIFT = "distribution_shift"
    ADVERSARIAL_STATE = "adversarial_state"
    CROSS_VIEW_DISAGREEMENT = "cross_view_disagreement"
    THRESHOLD_SENSITIVITY = "threshold_sensitivity"


@dataclass(frozen=True)
class CaseAnnotation:
    """Secondary case-design label kept outside the minimal case record."""

    case_id: str
    family: PerturbationFamily

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("annotation case_id must not be empty")

    def to_dict(self) -> dict[str, str]:
        return {"case_id": self.case_id, "family": self.family.value}


class FailureCategory(StrEnum):
    JEV_DECISION_ERROR = "jev_decision_error"
    POLICY_ACTION_ERROR = "policy_action_error"
    CROSS_VIEW_DISAGREEMENT = "cross_view_disagreement"
    UNMAPPED_EVIDENCE = "unmapped_evidence"
    RUN_ERROR = "run_error"
