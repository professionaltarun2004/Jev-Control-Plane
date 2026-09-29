"""Decision-level orchestration; agent lifecycle remains outside the core."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from uuid import uuid4

from .aggregator import TransparentEvidenceAggregator
from .domain import DecisionRecord, DecisionRequest
from .jev import JevAdapter
from .policy import DeterministicPolicy
from .records import JsonlDecisionLogger, json_safe


@dataclass
class ControlPlane:
    jev: JevAdapter
    aggregator: TransparentEvidenceAggregator
    policy: DeterministicPolicy
    logger: JsonlDecisionLogger | None = None

    def evaluate(self, request: DecisionRequest) -> DecisionRecord:
        decision_id = request.decision_id or str(uuid4())
        if decision_id != request.decision_id:
            request = DecisionRequest(request.agent_state, request.question, request.views, request.metadata, decision_id)
        results = self.jev.evaluate(request)
        evidence = self.aggregator.aggregate(request, results, self.policy.config)
        policy_result = self.policy.decide(evidence)
        fingerprint_source = json.dumps(
            json_safe({"agent_state": request.agent_state, "question": request.question}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        input_fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
        record = DecisionRecord.now(
            decision_id,
            {"input_fingerprint_sha256": input_fingerprint,
             "views": json_safe(request.views), "metadata": json_safe(dict(request.metadata))},
            json_safe(evidence),
            json_safe(policy_result),
        )
        if self.logger:
            self.logger.write(record)
        return record
