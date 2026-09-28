"""Transparent evidence aggregation; raw per-view Jev results stay available."""

from __future__ import annotations

from .domain import ControlAction, DecisionEvidence, DecisionRequest, JevResult, Primitive


class TransparentEvidenceAggregator:
    def aggregate(self, request: DecisionRequest, results: tuple[JevResult, ...]) -> DecisionEvidence:
        by_id = {view.view_id: view for view in request.views}
        if len(results) != len(request.views) or {r.view_id for r in results} != set(by_id):
            raise ValueError("Jev results must contain exactly one result for every requested view")
        hints: dict[str, ControlAction | None] = {}
        for result in results:
            view = by_id[result.view_id]
            key = str(result.answer).lower() if result.primitive is Primitive.NOUL else str(result.answer)
            hints[result.view_id] = view.action_map.get(key)
        known = [action for action in hints.values() if action is not None]
        agreement = len(set(known)) <= 1 if len(known) == len(hints) else None
        conflicts = tuple(view_id for view_id, action in hints.items() if action is None)
        if len(set(known)) > 1:
            conflicts += tuple(view_id for view_id, action in hints.items() if action is not None)
        return DecisionEvidence(request.decision_id, results, hints, agreement, conflicts)
