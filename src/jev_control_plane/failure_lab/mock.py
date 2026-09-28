"""Deterministic mock Jev adapter for runner verification only.

Outputs depend on the decision state and view definition, never on benchmark
ground truth. This makes repeated plumbing tests stable without implying
anything about live Jev behavior, accuracy, or latency.
"""

from __future__ import annotations

import hashlib
import json

from ..domain import DecisionRequest, JevResult, Primitive


class DeterministicMockJevAdapter:
    """Create stable, explicitly synthetic answers with Jev-shaped fields."""

    def evaluate(self, request: DecisionRequest) -> tuple[JevResult, ...]:
        state_json = json.dumps(request.to_jev_state(), sort_keys=True, separators=(",", ":"), default=str)
        results: list[JevResult] = []
        for view in request.views:
            digest = hashlib.sha256(f"{state_json}|{view.view_id}|{view.instructions}".encode()).digest()
            confidence = 0.55 + (int.from_bytes(digest[0:4], "big") / 0xFFFFFFFF) * 0.4
            if view.primitive is Primitive.NOUL:
                probability = 0.2 + (int.from_bytes(digest[4:8], "big") / 0xFFFFFFFF) * 0.6
                answer = probability >= 0.5
                probabilities = {"true": probability, "false": 1 - probability}
                raw = {"type": "noul", "noul": probability, "mock": True}
            elif view.primitive is Primitive.CHOICE:
                labels = tuple((view.criteria or {}).keys())
                if not labels:
                    raise ValueError(f"mock Choice view has no criteria: {view.view_id}")
                answer = labels[int.from_bytes(digest[4:8], "big") % len(labels)]
                selected_probability = 0.6 + (int.from_bytes(digest[8:12], "big") / 0xFFFFFFFF) * 0.2
                remainder = (1 - selected_probability) / max(1, len(labels) - 1)
                probabilities = {label: selected_probability if label == answer else remainder for label in labels}
                raw = {"type": "choice", "choice": answer, "confidence": confidence,
                       "probabilities": probabilities, "mock": True}
            else:
                criteria = tuple(view.criteria or ())
                if not criteria:
                    raise ValueError(f"mock Score view has no criteria: {view.view_id}")
                selected = int.from_bytes(digest[4:8], "big") % len(criteria)
                selected_probability = 0.6 + (int.from_bytes(digest[8:12], "big") / 0xFFFFFFFF) * 0.2
                remainder = (1 - selected_probability) / max(1, len(criteria) - 1)
                probabilities = {i: selected_probability if i == selected else remainder for i in range(len(criteria))}
                answer = sum(level * probability for level, probability in probabilities.items())
                raw = {"type": "score", "score": answer, "confidence": confidence,
                       "legend": {i: str(label) for i, label in enumerate(criteria)},
                       "probabilities": probabilities, "mock": True}
            results.append(JevResult(
                view_id=view.view_id,
                primitive=view.primitive,
                answer=answer,
                probabilities=probabilities,
                confidence=None if view.primitive is Primitive.NOUL else confidence,
                model="deterministic-mock",
                latency_ms=0.0,
                raw_answer=raw,
                request_id=hashlib.sha256(digest).hexdigest()[:16],
                usage=None,
            ))
        return tuple(results)
