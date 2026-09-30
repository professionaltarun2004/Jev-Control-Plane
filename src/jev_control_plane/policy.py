"""Small deterministic policy, independent of inference configuration."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .domain import ControlAction, DecisionEvidence, PolicyResult, Primitive


@dataclass(frozen=True)
class ScoreActionThresholds:
    """Policy boundaries for one Score rubric ordered from low to high risk."""

    allow_at_or_below: float
    deny_at_or_above: float

    def __post_init__(self) -> None:
        values = (self.allow_at_or_below, self.deny_at_or_above)
        if any(not isfinite(float(value)) for value in values):
            raise ValueError("Score thresholds must be finite")
        if self.allow_at_or_below >= self.deny_at_or_above:
            raise ValueError("Score ALLOW threshold must be below its DENY threshold")


@dataclass(frozen=True)
class PolicyConfig:
    minimum_confidence: float = 0.70
    minimum_noul_probability: float = 0.80
    # Zero keeps the M1/M2 policy behavior unchanged unless an experiment
    # explicitly predeclares Choice/Score action-support floors.
    minimum_allow_probability: float = 0.0
    minimum_deny_probability: float = 0.0
    minimum_escalate_probability: float = 0.0
    score_action_thresholds: Mapping[str, ScoreActionThresholds] | None = None
    version: str = "experimental-default-v1"

    def __post_init__(self) -> None:
        if not isfinite(self.minimum_confidence) or not 0 <= self.minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between 0 and 1")
        if not isfinite(self.minimum_noul_probability) or not 0.5 <= self.minimum_noul_probability <= 1:
            raise ValueError("minimum_noul_probability must be between 0.5 and 1")
        for name in ("minimum_allow_probability", "minimum_deny_probability", "minimum_escalate_probability"):
            value = getattr(self, name)
            if not isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        normalized: dict[str, ScoreActionThresholds] = {}
        for view_id, thresholds in (self.score_action_thresholds or {}).items():
            if not str(view_id).strip():
                raise ValueError("Score threshold view IDs must not be empty")
            if isinstance(thresholds, Mapping):
                thresholds = ScoreActionThresholds(**thresholds)
            if not isinstance(thresholds, ScoreActionThresholds):
                raise TypeError("score_action_thresholds values must be ScoreActionThresholds")
            normalized[str(view_id)] = thresholds
        object.__setattr__(self, "score_action_thresholds", normalized)


class DeterministicPolicy:
    def __init__(self, config: PolicyConfig = PolicyConfig()) -> None:
        self.config = config

    def decide(self, evidence: DecisionEvidence) -> PolicyResult:
        actions = set(evidence.action_hints.values())
        candidate = next(iter(actions)) if len(actions) == 1 and None not in actions else None
        reasons: list[str] = []
        if evidence.disagreeing_views or evidence.unmapped_views:
            reasons.append("views are unmapped or conflicting")
        for result in evidence.results:
            if result.primitive in (Primitive.CHOICE, Primitive.SCORE) and result.confidence is None:
                reasons.append(f"reported confidence is unavailable for {result.view_id}")
            elif result.confidence is not None and result.confidence < self.config.minimum_confidence:
                reasons.append(f"reported confidence is below the configured floor for {result.view_id}")
            action = evidence.action_hints.get(result.view_id)
            support = evidence.action_support.get(result.view_id)
            if result.primitive is Primitive.NOUL:
                minimum = self.config.minimum_noul_probability
            elif action is ControlAction.ALLOW:
                minimum = self.config.minimum_allow_probability
            elif action is ControlAction.DENY:
                minimum = self.config.minimum_deny_probability
            elif action is ControlAction.ESCALATE:
                minimum = self.config.minimum_escalate_probability
            else:
                minimum = 0.0
            if support is None:
                if result.primitive is Primitive.NOUL or result.primitive is Primitive.SCORE or minimum > 0:
                    reasons.append(f"action support is unavailable for {result.view_id}")
            elif support < minimum:
                reasons.append(f"action support is below its configured floor for {result.view_id}")
        if candidate is None:
            reasons.append("no single mapped action is available")
        if reasons:
            return PolicyResult(
                ControlAction.ESCALATE, "; ".join(dict.fromkeys(reasons)), self.config.version,
                candidate_action=candidate, evidence_sufficient=False,
                sufficiency_reasons=tuple(dict.fromkeys(reasons)),
            )
        return PolicyResult(
            candidate, "all views agree and meet configured evidence floors", self.config.version,
            candidate_action=candidate, evidence_sufficient=True, sufficiency_reasons=(),
        )
