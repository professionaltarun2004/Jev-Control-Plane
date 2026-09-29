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
    score_action_thresholds: Mapping[str, ScoreActionThresholds] | None = None
    version: str = "experimental-default-v1"

    def __post_init__(self) -> None:
        if not isfinite(self.minimum_confidence) or not 0 <= self.minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between 0 and 1")
        if not isfinite(self.minimum_noul_probability) or not 0.5 <= self.minimum_noul_probability <= 1:
            raise ValueError("minimum_noul_probability must be between 0.5 and 1")
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
        if evidence.disagreeing_views or evidence.unmapped_views:
            return PolicyResult(ControlAction.ESCALATE, "views are unmapped or conflicting", self.config.version)
        if any(result.confidence is not None and result.confidence < self.config.minimum_confidence for result in evidence.results):
            return PolicyResult(ControlAction.ESCALATE, "reported confidence is below the configured floor", self.config.version)
        for result in evidence.results:
            if result.primitive in (Primitive.CHOICE, Primitive.SCORE) and result.confidence is None:
                return PolicyResult(ControlAction.ESCALATE, "reported confidence is unavailable", self.config.version)
            if result.primitive is Primitive.NOUL:
                if not result.probabilities:
                    return PolicyResult(ControlAction.ESCALATE, "Noul probability is unavailable", self.config.version)
                support = result.probabilities.get(str(result.answer).lower(), 0.0)
                if support < self.config.minimum_noul_probability:
                    return PolicyResult(ControlAction.ESCALATE, "Noul probability is below the configured floor", self.config.version)
        actions = set(evidence.action_hints.values())
        if len(actions) != 1 or None in actions:
            return PolicyResult(ControlAction.ESCALATE, "no single mapped action is available", self.config.version)
        return PolicyResult(next(iter(actions)), "all mapped views agree", self.config.version)
