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
        if not isinstance(self.source, GroundTruthSource):
            object.__setattr__(self, "source", GroundTruthSource(self.source))
        if not isinstance(self.certainty, GroundTruthCertainty):
            object.__setattr__(self, "certainty", GroundTruthCertainty(self.certainty))
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


@dataclass(frozen=True)
class CaseAnnotation:
    """Secondary case-family and perturbation review metadata.

    The benchmark case stays minimal; these annotations describe construction,
    matched relationships, and review context without encoding Jev answers.
    """

    case_id: str
    family: PerturbationFamily
    description: str
    base_case_id: str | None = None
    case_family_id: str | None = None
    decision_relevant_facts: tuple[str, ...] = ()
    changed_facts: tuple[str, ...] = ()
    unchanged_facts: tuple[str, ...] = ()
    expected_action_unchanged: bool | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("annotation case_id must not be empty")
        if not isinstance(self.family, PerturbationFamily):
            object.__setattr__(self, "family", PerturbationFamily(self.family))
        if not self.description.strip():
            raise ValueError("annotation description must not be empty")
        if self.base_case_id is not None and (not self.base_case_id.strip() or self.base_case_id == self.case_id):
            raise ValueError("base_case_id must identify a different, non-empty base case")
        if self.case_family_id is not None and not self.case_family_id.strip():
            raise ValueError("case_family_id must not be empty")
        for field_name in ("decision_relevant_facts", "changed_facts", "unchanged_facts"):
            values = tuple(str(item).strip() for item in getattr(self, field_name))
            if any(not item for item in values):
                raise ValueError(f"{field_name} entries must not be empty")
            object.__setattr__(self, field_name, values)
        if self.expected_action_unchanged is not None and not isinstance(self.expected_action_unchanged, bool):
            raise ValueError("expected_action_unchanged must be boolean or null")
        if self.base_case_id is None and self.expected_action_unchanged is not None:
            raise ValueError("base annotations cannot declare a matched truth relationship")

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "case_id": self.case_id,
            "family": self.family.value,
            "description": self.description,
            "base_case_id": self.base_case_id,
        }
        if self.case_family_id is not None:
            value.update({
                "case_family_id": self.case_family_id,
                "decision_relevant_facts": list(self.decision_relevant_facts),
                "changed_facts": list(self.changed_facts),
                "unchanged_facts": list(self.unchanged_facts),
                "expected_action_unchanged": self.expected_action_unchanged,
                "notes": self.notes,
            })
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CaseAnnotation":
        required = {"case_id", "family", "description", "base_case_id"}
        extended = {"case_family_id", "decision_relevant_facts", "changed_facts", "unchanged_facts",
                    "expected_action_unchanged", "notes"}
        if not required.issubset(value) or set(value) - required - extended:
            raise ValueError("annotation contains missing or unsupported fields")
        if (set(value) & extended) and not extended.issubset(value):
            raise ValueError("extended review annotations must include every M3 review field")
        return cls(
            str(value["case_id"]), PerturbationFamily(value["family"]),
            str(value["description"]),
            str(value["base_case_id"]) if value["base_case_id"] is not None else None,
            str(value["case_family_id"]) if "case_family_id" in value else None,
            tuple(value.get("decision_relevant_facts", ())),
            tuple(value.get("changed_facts", ())),
            tuple(value.get("unchanged_facts", ())),
            value.get("expected_action_unchanged"),
            str(value.get("notes", "")),
        )


class OutcomeCategory(StrEnum):
    FINAL_ACTION_ERROR = "final_action_error"
    JEV_DECISION_ERROR = "jev_decision_error"
    POLICY_ACTION_ERROR = "policy_action_error"
    FALSE_ALLOW = "false_allow"
    FALSE_DENY = "false_deny"
    UNNECESSARY_ESCALATION = "unnecessary_escalation"
    RUNNER_ERROR = "runner_error"
