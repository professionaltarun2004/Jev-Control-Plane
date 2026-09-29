"""Transparent evidence aggregation; raw per-view Jev results stay available."""

from __future__ import annotations

from .domain import AgreementStatus, ControlAction, DecisionEvidence, DecisionRequest, JevResult, Primitive
from .policy import PolicyConfig


class TransparentEvidenceAggregator:
    def aggregate(
        self,
        request: DecisionRequest,
        results: tuple[JevResult, ...],
        policy_config: PolicyConfig | None = None,
    ) -> DecisionEvidence:
        policy_config = policy_config or PolicyConfig()
        by_id = {view.view_id: view for view in request.views}
        if len(results) != len(request.views) or {r.view_id for r in results} != set(by_id):
            raise ValueError("Jev results must contain exactly one result for every requested view")
        hints: dict[str, ControlAction | None] = {}
        for result in results:
            view = by_id[result.view_id]
            if result.primitive is not view.primitive:
                raise ValueError(f"Jev primitive does not match requested view {view.view_id}")
            key = str(result.answer).lower() if result.primitive is Primitive.NOUL else str(result.answer)
            if result.primitive is Primitive.SCORE:
                thresholds = policy_config.score_action_thresholds.get(view.view_id)
                if thresholds is None:
                    hints[result.view_id] = None
                    continue
                maximum = len(view.criteria or ()) - 1
                if thresholds.allow_at_or_below < 0 or thresholds.deny_at_or_above > maximum:
                    raise ValueError(f"Score policy thresholds exceed rubric range for {view.view_id}")
                score = float(result.answer)
                if score <= thresholds.allow_at_or_below:
                    hints[result.view_id] = ControlAction.ALLOW
                elif score >= thresholds.deny_at_or_above:
                    hints[result.view_id] = ControlAction.DENY
                else:
                    hints[result.view_id] = ControlAction.ESCALATE
            else:
                hints[result.view_id] = view.action_map.get(key)
        known = [action for action in hints.values() if action is not None]
        unmapped = tuple(view_id for view_id, action in hints.items() if action is None)
        disagreeing = tuple(view_id for view_id, action in hints.items() if action is not None) if len(set(known)) > 1 else ()
        if disagreeing and unmapped:
            status = AgreementStatus.MIXED
        elif disagreeing:
            status = AgreementStatus.DISAGREEMENT
        elif unmapped and known:
            status = AgreementStatus.PARTIAL
        elif unmapped:
            status = AgreementStatus.UNMAPPED
        else:
            status = AgreementStatus.AGREEMENT
        agreement = False if disagreeing else None if unmapped else True
        conflicts = tuple(dict.fromkeys((*unmapped, *disagreeing)))
        return DecisionEvidence(
            request.decision_id, results, hints, agreement, conflicts,
            unmapped_views=unmapped, disagreeing_views=disagreeing, agreement_status=status,
        )
