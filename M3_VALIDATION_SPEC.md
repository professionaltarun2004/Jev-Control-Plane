# M3 Validation Design Specification

**Status:** design update before implementation of M3 policy behavior or any live Jev Validation run. User-decided principles are distinguished from provisional parameters and open design questions below. No empirical findings are reported.

## Research question

Under what conditions does Jev-based control provide sufficient evidence to make an agent decision autonomously, and under what conditions does it become unreliable or need escalation?

M3 prepares a small decision-level Validation study. It does not establish general reliability, safety, calibration, or comparative performance. The M2.5 minimal benchmark case remains unchanged: case ID, current state, decision, and ground truth. Family and review details live in the split-local annotation sidecar.

## A. User-decided principles

- V1 evaluates only evidence supplied to it. It does not autonomously gather additional evidence. “No more evidence” means no additional source is available within the V1 control-plane boundary. Evidence gathering is a future extension.
- The research goal is to investigate whether multiple Jev perspectives provide sufficient evidence for autonomous decision-making and when unresolved uncertainty should lead to human escalation. Accuracy alone is not the objective.
- Noul, Choice, and Score are distinct views of the **same underlying decision**. A1–A3 characterize each primitive; B1–B3 test whether additional views improve evidence, produce useful disagreement, or add unnecessary complexity/escalation.
- ALLOW and DENY may warrant different evidence requirements because their error costs can differ by domain. Evidence requirements should reflect the cost of being wrong, but hypothetical cost ratios do not directly determine probability thresholds.
- Jev probabilities are quantities to evaluate. Their existence does not establish calibration or reliability.
- Disagreement is an evidence property, not automatically a failure or an automatic reason to ESCALATE. Stronger evidence may outweigh weaker conflicting evidence, but the cross-view aggregation rule is not yet decided.
- Clear, sufficiently supported evidence may permit autonomous action. Uncertainty is evaluated using all supplied evidence. Uncertainty that remains unresolved within the V1 evidence boundary may lead to ESCALATE.
- Keep the architecture deterministic at the policy layer, preserve raw Jev results, and do not add an LLM judge or learned ensemble.

## B. Provisional experimental parameters

- The former ALLOW support value `0.80` and DENY support value `0.70` are **withdrawn as fixed M3 criteria**. Both are **PROVISIONAL / OPEN**; no replacement numbers are specified.
- Any prior confidence or Noul support values are provisional parameters only, not validated requirements. Their applicability by primitive and action remains open until explicitly selected and frozen before a live run.
- The previously written pilot cutoffs (including accuracy, coverage, escalation, and error cutoffs) are not established scientific criteria. They must be reviewed and either explicitly predeclared or removed before live Validation. This revision does not adopt them as fixed acceptance criteria.
- Any numerical values eventually selected are experimental policy choices, not safety constants or empirically justified probability thresholds. Do not derive them directly from hypothetical error costs.

## C. Open design questions — do not infer values

1. What separate evidence requirements, if any, should govern autonomous ALLOW and DENY?
2. How should evidence from Choice, Noul, and Score be aggregated when their views conflict?
3. Should different views receive weights? If so, what justifies those weights and how will they be frozen?
4. How can the relative strength of unlike primitive outputs be compared without falsely treating Noul probability, Choice option probability/confidence, and Score/rubric probability/confidence as equivalent quantities?
5. Which disagreement patterns are resolvable by stronger evidence, and which leave uncertainty unresolved?
6. What exact escalation criteria follow from the selected aggregation rule, primitive-specific missing signals, and action-specific evidence requirements?
7. What Score rubric and explicit score-to-action support mapping will be used? Numeric score must not be treated as a probability.
8. How should Noul’s binary answer map to three actions when a negative answer may mean DENY or unresolved evidence requiring ESCALATE?
9. How will “unnecessary ESCALATE” be defined from predeclared sufficiency criteria? Until then it cannot be inferred from observed outcomes.
10. Which pilot-level summary criteria, if any, are appropriate for this small Validation set, and how will uncertainty and matched-family dependence be reported?

The live Validation matrix must not run a condition whose required aggregation, mapping, threshold, or escalation behavior remains open. Resolve, document, version, and freeze those choices before observing live Jev results.

## Operational meaning of “sufficient evidence”

“Sufficient evidence” is intended to be a deterministic, predeclared policy concept that considers final-action correctness, action-specific error risk, evidence quality, and escalation behavior. It is not synonymous with accuracy, a probability, confidence, view agreement, or any one metric. The exact thresholds and aggregation semantics remain **OPEN** as listed above. This document therefore does not define a runnable sufficiency predicate or authorize any implied default.

Primitive-specific semantics must remain distinct: preserve the typed answer and probabilities; preserve confidence only where the API returns it; do not synthesize Noul confidence; and do not claim probabilities are calibrated. V1 evaluates only the evidence included in the DecisionRequest and does not call tools or acquire more evidence. If the frozen deterministic rule cannot support an autonomous action from the supplied evidence, ESCALATE may be selected.

## Action-specific outcomes

- **False ALLOW:** final action is ALLOW while expected action is DENY or ESCALATE. Count and rate denominator: all completed cases whose expected action is not ALLOW. Report separately; no numeric pass/fail consequence is set here.
- **False DENY:** final action is DENY while expected action is ALLOW or ESCALATE. Denominator: all completed cases whose expected action is not DENY. It is an action error with availability cost. Report separately from false ALLOW; no numeric pass/fail consequence is set here.
- **Unnecessary ESCALATION:** **OPEN / not currently computable.** Its definition depends on the unresolved sufficiency and aggregation rules. Do not label an escalation necessary or unnecessary from view agreement or observed Jev outputs alone.
- **Correct escalation:** expected and final action are both ESCALATE. Report independently from unnecessary escalation.
- **Evidence disagreement, low confidence, or low support:** descriptive evidence properties only. They do not become outcome failures without comparison to ground truth and the criteria above.

A final-action error is always retained. Once a view-to-action mapping and aggregation rule are predeclared, `jev_decision_error` may describe an aggregated Jev action that differs from ground truth. `policy_action_error` may describe a final policy output that differs from an otherwise ground-truth-correct aggregated Jev action. Attribution remains unknown where the selected aggregation cannot produce a mapped action. These are reporting definitions, not a decision to use consensus aggregation.

## Pilot interpretation and small-sample uncertainty

No numeric pilot pass/fail criteria are adopted by this revision. Before live Validation, decide whether pilot criteria are needed, state them as **PREDECLARED EXPERIMENTAL CRITERIA**, and freeze them before viewing outcomes. Do not use accuracy alone to define sufficiency. Report action counts and denominators separately, distinguish false ALLOW from false DENY, and do not count every ESCALATE or disagreement as a failure.

The dataset is small by design. Do not report a percentage without `k/n`. If intervals are reported, state the method and limitations. Exact binomial intervals do not remedy synthetic sampling, annotation bias, dependence within matched families, or lack of external validity. Because cases within a family are paired, do not treat all case rows as independent observations for population claims. Calibration, Brier score, and ECE are not established by this protocol update.

## Validation dataset and ground truth

The Validation fixture is planned to target **12 underlying case families** and **16 case rows** after matched variants. Rules should be written independently of Jev output. A human second review is pending; do not claim human validation or consensus. Ambiguity cases should use a documented rule for underspecification rather than subjective normative judgment.

Annotations document family ID, perturbation, decision-relevant facts, what changed and stayed fixed, whether the expected action should remain unchanged, and reviewer notes. Context-only variants must preserve ground truth; relevant changes must name the changed fact and may change the expected action. The dataset validator checks all declared relationships and split-local base links.

## Experiment matrix

The planned six Jev-only configurations share the same Validation cases and compare:

| Layer | Condition | Views |
| --- | --- | --- |
| Primitive | A1 | Noul |
| Primitive | A2 | Choice |
| Primitive | A3 | Score |
| View ablation | B1 | Choice |
| View ablation | B2 | Choice + Noul |
| View ablation | B3 | Choice + Noul + Score |

Every view must ask about the same underlying decision. No live condition has been run. Each configuration should be run separately; preserve every run and do not tune policy after inspecting outcomes. Failure-boundary families should be matched where possible; paired outputs can compare expected action, final action, per-view evidence, and correctness transition. The exact aggregation and policy configuration remains an explicit prerequisite, not an assumed part of this matrix.

## Results and limits

The existing deterministic mock run remains plumbing evidence. It is not included in Validation metrics. M3 creates no Holdout results, no LLM baseline, and no safety certification. Calibration, Brier score, ECE, SAC, risk-coverage, cost, and trajectory metrics remain out of scope.
