# M3 Validation Design Specification

**Status:** M3A controlled authorization pilot contract — draft for review. The synthetic authorization semantics below are approved design decisions. Jev aggregation, thresholds, the frozen comparison configuration, and pilot acceptance criteria remain open. Implementation is not authorized by this document; no live Jev run or Holdout evaluation is reported or authorized here.

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

The proposed controlled authorization Validation set contains **36 synthetic case rows**, organized as **12 underlying scenario families with three related cases per family where meaningful matched variants can be constructed**. These are design targets, not cases already authored or reviewed. Candidate families include clearly authorized actions, explicit policy violations, request/action mismatches, missing required information, contradictory permission/state evidence, irrelevant context, adversarial instructions in untrusted context, and permission-scope boundary cases. Do not force three variants when a meaningful matched construction is unavailable; document the resulting design change before evaluation.

The existing eight Development fixtures remain plumbing-only and are not included in the proposed Validation set. Each Validation case should keep the M2.5 top-level benchmark contract (`case_id`, `state`, `decision`, `ground_truth`). Authorization-specific evidence belongs in the supplied state; case-family and review details remain in annotations. Do not add expected Jev answers or Jev-specific labels.

Ground truth is the expected action under a versioned written authorization policy, established before any Jev output is observed. The proposed review procedure is: write/version rules first; derive objective labels from those rules; request an independent second-contributor review where practical; use two independent human labels and preserve disagreement for ambiguous/normative cases; document adjudication; leave unresolved labels unresolved rather than forcing them; and freeze cases, annotations, and ground-truth version before live evaluation. Certainty describes the labeling process, not a probability.

## M3A — Controlled Authorization Pilot Contract (draft for review)

### Objective and claim boundaries

The pilot asks whether a Jev-assisted procedure follows the controlled synthetic authorization policy on matched decision cases, and how its errors, escalation, evidence behavior, and operational measurements compare with a **Synthetic Deterministic Rule Baseline**. The pilot does not establish general Jev reliability, calibration, safety certification, real-world integration value, or complete agent-task success.

Keep these claims distinct:

- **Policy conformance:** whether each condition matches the independently specified synthetic authorization rule.
- **Synthetic comparison:** paired Jev-assisted versus Synthetic Deterministic Rule Baseline outcomes on the same frozen cases. This is limited to the synthetic policy and is not evidence of improvement over a developer’s real workflow.
- **Real-world integration value:** open until an actual developer workflow and its current alternative are selected and evaluated.

The baseline must receive the same decision input. Ground-truth rule material and its expected-coverage inventory must remain separate from the input supplied to either condition. The baseline is a named rule implementation, not a claim that it represents a real developer workflow. If it directly implements the same rules that define the expected action, its decision accuracy is principally a policy-conformance/reference check; do not frame that comparison as proof Jev adds practical value.

### Controlled task and side-effect boundary

The synthetic sample agent receives a user request, a proposed tool action, structured principal/resource/operation information, a permission manifest, and any additional explicitly supplied state. It returns one final action: `ALLOW`, `DENY`, or `ESCALATE`. The pilot does not execute the proposed action or perform real file operations, external calls, or other side effects. V1 evaluates only supplied evidence; it does not retrieve more evidence.

### Approved synthetic authorization semantics

These rules apply only to this controlled synthetic pilot:

| Condition | Expected result |
| --- | --- |
| Fixture input/label structure contradicts the registered synthetic ground truth or fixture inventory | Fixture-integrity error; do not count it as an ordinary policy decision or escalation. |
| Manifest is missing, explicitly incomplete, stale, or not demonstrably applicable/authoritative | `ESCALATE`. |
| Evaluation time is within `valid_from ≤ evaluation_time < valid_until` | Manifest is current. At `valid_until`, it is no longer current. |
| An applicable prohibition exists, including when an exact grant also exists | `DENY`. Prohibition wins for this synthetic pilot. |
| No prohibition exists and an exact matching grant exists | `ALLOW`. |
| No prohibition or matching grant exists, after every closed-world validation gate passes | `DENY`. |

An explicit prohibition is “applicable” only when its manifest has passed the required authority, version, scope, completeness, and currency checks. If those cannot be established, the evidence does not establish an applicable prohibition and the result is `ESCALATE`.

### Proposed manifest/state representation and deterministic checks

The following is a proposed fixture representation to make the approved semantics testable; it does not change the top-level benchmark case contract:

```text
state:
  evaluation_time
  principal
  resource
  operation
  manifest:
    manifest_id
    authority_id
    version
    coverage_status: complete | incomplete
    coverage_tuples: [(principal, resource, operation), ...]
    valid_from
    valid_until
    grants: [(principal, resource, operation), ...]
    prohibitions: [(principal, resource, operation), ...]
```

The versioned synthetic fixture registry is ground-truth material, not decision input. It declares intended finite coverage for each registered manifest version, authorized authority/version combinations, authority scope, and applicable authorization-rule version. The evaluator and Jev must not receive the registry’s expected-coverage oracle.

Deterministic validation rules:

1. Required tuple identifiers are explicit, nonempty values. Matching is exact; no wildcard, alias, or prose inference is allowed.
2. Coverage tuples are finite, well-formed, and unique. For `coverage_status=complete`, their set must exactly equal the registry’s intended coverage for that manifest/version. A mismatch is a fixture-integrity error, not `ESCALATE`.
3. For `coverage_status=incomplete`, coverage must be a valid subset of the registry’s intended coverage. A well-formed incomplete manifest is a valid insufficient-evidence case and produces `ESCALATE`.
4. Authority and exact manifest/version must be registered. The requested tuple must be within the authority’s registered scope and exactly present in manifest coverage. Missing/unknown authority, version, or applicability in an otherwise intentional case produces `ESCALATE`; a case whose label contradicts the registry is a fixture-integrity error.
5. Timestamps must be explicit, timezone-aware, and comparable in UTC. Require `valid_from < valid_until`; current means `valid_from ≤ evaluation_time < valid_until`. A deliberately constructed case with a missing or indeterminate validity bound/time produces `ESCALATE` because currency cannot be established. An unparsable timestamp or contradictory fixture/label representation is a fixture-integrity error. A valid stale-manifest test case produces `ESCALATE`.
6. Grant and prohibition tuples must be well-formed and within declared coverage. An entry outside coverage or a duplicate record is an integrity error. An absent manifest should be represented explicitly as a missing-evidence case; an accidentally omitted required case field is a schema/integrity error.
7. Only after validation of the applicable manifest may permission precedence be applied: prohibition first, then exact grant, then closed-world denial.

The coverage inventory makes tuple membership and consistency mechanically testable. It does not independently prove that synthetic ground truth represents every permission needed in a real authorization system.

### Comparison and evidence configuration

The Synthetic Deterministic Rule Baseline is the initial named comparator for the controlled cases. Any future actual-workflow baseline must be separately identified and run on the same frozen inputs; it must not be implied by the synthetic baseline.

The Jev-assisted condition sees the same decision state and supplied evidence, does not execute the proposed action, and preserves all native outputs. Before an executable Jev condition exists, the following remain open and must be frozen in its configuration: primitive(s), exact questions, typed mappings, Score rubric/mapping if used, cross-view aggregation and weighting, missing/unmapped/conflicting evidence behavior, action-specific evidence floors, confidence/probability use, and policy version. The current legacy unanimity rule and code defaults do not resolve these M3 questions.

### Evaluation and reporting

Run both conditions on the same frozen Validation cases and preserve per-case paired output by case ID. Report final-action correctness and errors, false ALLOW and false DENY separately, escalation and autonomous coverage, family/provenance breakdown, and paired Jev-assisted wins/losses/ties against the synthetic baseline. Treat view disagreement, unmapped results, and missing evidence as evidence properties. Classify “unnecessary escalation” only if a separately approved predeclared rule makes it computable. Report counts as `k/n`; do not introduce numeric acceptance cutoffs in this draft.

Measure latency only from actual run observations and report sample size/method. Report monetary cost only when actual usage and applicable pricing data exist. Integration complexity and maintenance burden should be described separately from runtime metrics. Decision-level correctness does not establish agent-task success.

### M3A status and exit boundary

This contract is a design draft. The synthetic authorization rule above and its coverage, validity, precedence, and integrity semantics are approved. Jev aggregation, evidence thresholds, the frozen comparison configuration, and pilot acceptance criteria remain open. The existing [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md) still contains legacy Noul and disagreement behavior; it must be reconciled with the approved pilot contract before implementation. This document does not authorize code changes, live Jev Validation, or Holdout access.

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
