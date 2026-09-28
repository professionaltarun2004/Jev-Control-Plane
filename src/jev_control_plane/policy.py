"""Small deterministic policy, independent of inference configuration."""

from __future__ import annotations

from dataclasses import dataclass

from .domain import ControlAction, DecisionEvidence, PolicyResult, Primitive


@dataclass(frozen=True)
class PolicyConfig:
    minimum_confidence: float = 0.70
    minimum_noul_probability: float = 0.80
    version: str = "experimental-default-v1"

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between 0 and 1")
        if not 0.5 <= self.minimum_noul_probability <= 1:
            raise ValueError("minimum_noul_probability must be between 0.5 and 1")


class DeterministicPolicy:
    def __init__(self, config: PolicyConfig = PolicyConfig()) -> None:
        self.config = config

    def decide(self, evidence: DecisionEvidence) -> PolicyResult:
        if evidence.agreement is not True or evidence.conflicts:
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
