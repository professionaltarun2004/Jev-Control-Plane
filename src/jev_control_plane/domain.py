"""Typed domain objects for one agent decision and its evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping


class Primitive(StrEnum):
    NOUL = "noul"
    CHOICE = "choice"
    SCORE = "score"


class ControlAction(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"


class AgreementStatus(StrEnum):
    """Summary of mapped view actions without hiding mixed evidence states."""

    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"
    PARTIAL = "partial"
    UNMAPPED = "unmapped"
    MIXED = "mixed"


@dataclass(frozen=True)
class AgentState:
    user_request: str
    current_action: str
    previous_action: str | None = None
    tool_result: Any | None = None

    def __post_init__(self) -> None:
        if not self.user_request.strip():
            raise ValueError("user_request must not be empty")
        if not self.current_action.strip():
            raise ValueError("current_action must not be empty")

    def to_jev_state(self) -> dict[str, Any]:
        """Return only the current agent decision state, excluding request metadata."""
        return {
            "user_request": self.user_request,
            "previous_action": self.previous_action,
            "tool_result": self.tool_result,
            "current_action": self.current_action,
        }


@dataclass(frozen=True)
class DecisionView:
    view_id: str
    primitive: Primitive
    instructions: str
    criteria: Mapping[str, Any] | tuple[str, ...] | list[str] | None = None
    # Maps this view's typed answer string (or Noul "true"/"false") to a
    # declared action for the shared underlying decision.
    action_map: Mapping[str, ControlAction] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.view_id.strip():
            raise ValueError("view_id must not be empty")
        if not self.instructions.strip():
            raise ValueError("view instructions must not be empty")
        if self.primitive is Primitive.CHOICE and not self.criteria:
            raise ValueError("Choice views require non-empty criteria")
        if self.primitive is Primitive.SCORE and not self.criteria:
            raise ValueError("Score views require non-empty criteria")


@dataclass(frozen=True)
class DecisionRequest:
    agent_state: AgentState
    question: str
    views: tuple[DecisionView, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    decision_id: str = ""

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("decision question must not be empty")
        if not self.views:
            raise ValueError("at least one decision view is required")
        ids = [view.view_id for view in self.views]
        if len(ids) != len(set(ids)):
            raise ValueError("decision view IDs must be unique")

    def to_jev_state(self) -> dict[str, Any]:
        """Include the decision context and current state, never metadata."""
        return {"decision_question": self.question, **self.agent_state.to_jev_state()}


@dataclass(frozen=True)
class JevResult:
    view_id: str
    primitive: Primitive
    answer: bool | str | float
    probabilities: Mapping[str | int, float] | None
    confidence: float | None
    model: str | None
    latency_ms: float
    raw_answer: Mapping[str, Any]
    request_id: str | None = None
    usage: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class DecisionEvidence:
    decision_id: str
    results: tuple[JevResult, ...]
    action_hints: Mapping[str, ControlAction | None]
    agreement: bool | None
    conflicts: tuple[str, ...]
    unmapped_views: tuple[str, ...] = ()
    disagreeing_views: tuple[str, ...] = ()
    agreement_status: AgreementStatus = AgreementStatus.UNMAPPED

    @property
    def mapped_actions(self) -> Mapping[str, ControlAction]:
        """Expose only interpreted actions while retaining ``action_hints`` raw map."""
        return {view_id: action for view_id, action in self.action_hints.items() if action is not None}


@dataclass(frozen=True)
class PolicyResult:
    action: ControlAction
    reason: str
    policy_version: str


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    timestamp: str
    request: Mapping[str, Any]
    evidence: Mapping[str, Any]
    policy: Mapping[str, Any]
    outcome: Mapping[str, Any] | None = None

    @classmethod
    def now(cls, decision_id: str, request: Mapping[str, Any], evidence: Mapping[str, Any], policy: Mapping[str, Any], outcome: Mapping[str, Any] | None = None) -> "DecisionRecord":
        return cls(decision_id, datetime.now(timezone.utc).isoformat(), request, evidence, policy, outcome)
