# M3A Research Decision Proposal

**Status:** Proposal for review; not an approved policy or experiment configuration.
**Scope:** Resolve the design questions needed to make an M3A synthetic authorization study executable.
**Authority:** Until approved decisions are incorporated into `M3_VALIDATION_SPEC.md`, that specification and the existing user-approved synthetic authorization rules remain authoritative. This proposal does not authorize live Jev, Validation, Holdout, or enforcement.

## Research question

> Under what conditions does Jev-based control provide sufficient evidence to make an agent decision autonomously, and under what conditions does it become unreliable or need escalation?

The study should characterize decision evidence and the boundary between autonomous action and escalation. It should not optimize classification accuracy alone, declare a Jev primitive a winner, or infer practical value for an unexamined developer workflow.

## Decision labels used here

- **Software invariant:** a property that implementation and artifacts should enforce regardless of research outcomes.
- **Research hypothesis:** a claim whose direction or practical consequence must be evaluated on appropriate cases.
- **Approval-required policy choice:** a consequential rule that must be explicitly approved before it becomes an M3A configuration.

Recommendations below are proposals. None changes runtime semantics or closes an approval-required decision.

## Verified current state

- The Jev adapter retains primitive-specific `JevResult` fields. Noul is normalized to a boolean using the adapter's configured `noul_yes_threshold` (default `0.5`) while retaining the reported yes probability and deriving the complementary false probability. The adapter does not create a separate Noul confidence.
- Choice retains its selected option, probability mapping, and confidence where returned. Score retains its numeric score, probability mapping, and confidence where returned. The aggregator maps Choice/Noul answers through `DecisionView.action_map`; Score needs explicit per-view `PolicyConfig.score_action_thresholds`.
- The legacy deterministic policy proposes an action only when mapped views agree. It escalates on disagreement or unmapped evidence, missing Choice/Score confidence, confidence below its default `0.70`, or Noul support below its default `0.80`. Action support floors for Choice/Score default to zero. These are current code defaults, not approved M3A semantics.
- `ValidationCriteria` still has constructor defaults: accuracy `0.80`, correct autonomous coverage `0.50`, correct escalation rate `0.80`, maximum unnecessary escalation `0.20`, and zero false ALLOW/DENY. A sufficiency assessment is emitted only when criteria are supplied. No M3A criteria are approved. These values must not be mistaken for validated thresholds.
- The current paired runner is Development-only and mock-only. It executes a Jev-shaped deterministic mock through the legacy aggregator/policy and a separate deterministic action fixture directly. Policy-level equivalence is disabled. It keeps expected outcomes in evaluator-owned pair rows, not provider attempts; providers receive case ID, state, and decision, while annotations are kept out.
- The synthetic deterministic rule baseline is not an implemented condition in the paired runner. It is a reference for labels/policy conformance, not an actual developer workflow comparator.
- Development has eight developer-authored synthetic cases with medium-certainty deterministic-rule labels. The 36-row/12-family Validation plan is still a target; no Validation dataset or Holdout run exists.

The official TypeSafe documentation currently describes Noul as a yes-probability, Choice as a selected option plus an option distribution and confidence, and Score as a position on ordered levels plus a level distribution and confidence. The documentation says Choice/Score confidence is computed from the returned probability distribution. Thus confidence and the distribution should be preserved as distinct native fields, but must not be counted as independent pieces of evidence within the same view. The documentation's primitive definitions do not establish action mappings, acceptable thresholds, calibration for this project, or suitability for authorization decisions. See [Noul](https://docs.typesafe.ai/primitives/noul), [Choice](https://docs.typesafe.ai/primitives/choice), [Score](https://docs.typesafe.ai/primitives/score), and [Confidence](https://docs.typesafe.ai/confidence) (reviewed 2026-10-27).

## Decision matrix

### Approved task boundary

The approved design target for the first Validation task is a **controlled synthetic authorization decision**: decide whether a proposed agent tool action is `ALLOW`, `DENY`, or `ESCALATE` under the approved synthetic manifest rules. The proposed action is not executed. This boundary and the fixture-specific coverage, authority/version, half-open currency, prohibition precedence, and closed-world rules are recorded in [M3_VALIDATION_SPEC.md](M3_VALIDATION_SPEC.md). This design approval does not authorize dataset creation or a live run, and it does not choose a Jev primitive, a Jev-to-action mapping, or an actual developer workflow.

### Decision register

`Approved` below means the cited contract or upstream schema establishes that item at the stated scope. It does not imply owner approval of any adjacent policy choice. The detailed options, evidence needed, and contract tests remain in the matching D-section below.

| ID | Status | Repository evidence | Still unknown / exact owner decision | Consequence if left open |
| --- | --- | --- | --- | --- |
| D1 | unresolved | [M3 validation spec](M3_VALIDATION_SPEC.md) §C; [SPEC](SPEC.md) FR-2; [`domain.py`](src/jev_control_plane/domain.py), [`aggregator.py`](src/jev_control_plane/aggregator.py), [`policy.py`](src/jev_control_plane/policy.py); [TypeSafe primitive docs](https://docs.typesafe.ai/primitives) | Decide whether each used primitive may propose a final action and approve the exact Noul/Choice/Score interpretation. In particular, does a negative Noul answer mean DENY, ESCALATE, or only a predicate result? | No live condition using that primitive can be mapped to a final action without silently choosing semantics. |
| D2 | unresolved | [M3 validation spec](M3_VALIDATION_SPEC.md) §§A,C; [protocol](EXPERIMENT_PROTOCOL.md) §5; [`aggregator.py`](src/jev_control_plane/aggregator.py), [`policy.py`](src/jev_control_plane/policy.py) | Choose whether multi-view results use unanimity, a specified deterministic precedence/weight rule, or descriptive-only reporting; state how disagreement, missing views, and unmapped results affect action. | B2/B3 cannot validly produce a comparable M3A final action; legacy unanimity cannot stand in for approval. |
| D3 | approved — upstream response-schema invariant | [TypeSafe Choice](https://docs.typesafe.ai/primitives/choice), [Score](https://docs.typesafe.ai/primitives/score), [confidence](https://docs.typesafe.ai/confidence); [`jev.py`](src/jev_control_plane/jev.py), [`test_control_plane.py`](tests/test_control_plane.py) | No M3A policy approval is required for preserving native fields and rejecting malformed distributions. Task-specific meaning, calibration, or evidentiary sufficiency remains unapproved and out of scope for this invariant. | No decision blocker; without the invariant, malformed probability data could pass normalization as a provider result. |
| D4 | unresolved | [M3 validation spec](M3_VALIDATION_SPEC.md) §§A,C and “Operational meaning”; [`policy.py`](src/jev_control_plane/policy.py) | Define what evidence is required for autonomous ALLOW versus DENY, and what is insufficient. Do not translate hypothetical error-cost ratios directly into probability cutoffs. | No defensible sufficiency predicate; autonomous-action requirements cannot be frozen. |
| D5 | unresolved | [M3 validation spec](M3_VALIDATION_SPEC.md) §B; [`policy.py`](src/jev_control_plane/policy.py); [`experiment.py`](src/jev_control_plane/failure_lab/experiment.py); [legacy config](experiments/configs/m1-policy-default.json) | Confirm which explicit M3A values, if any, will replace/isolate legacy defaults and how candidate thresholds may be selected on Development/Validation. No replacement numbers are approved. | A run can accidentally inherit legacy floors or criteria and present them as M3A policy. |
| D6 | unresolved | [protocol](EXPERIMENT_PROTOCOL.md) §§5–6; [`jev.py`](src/jev_control_plane/jev.py), [`runner.py`](src/jev_control_plane/failure_lab/runner.py), [`comparison.py`](src/jev_control_plane/failure_lab/comparison.py) | Decide the live timeout/retry limits, fatal-run versus per-case error handling, and caller-visible behavior when Jev is unavailable. Confirm that technical failure remains distinct from a valid ESCALATE decision. | Live operational behavior and its latency/error denominators are not reproducible; no caller failure contract is established. |
| D7 | unresolved | [M3 validation spec](M3_VALIDATION_SPEC.md) “Action-specific outcomes”; [protocol](EXPERIMENT_PROTOCOL.md) §5; [`runner.py`](src/jev_control_plane/failure_lab/runner.py), [`metrics.py`](src/jev_control_plane/failure_lab/metrics.py) | Define the sufficiency predicate that makes an escalation “unnecessary,” and approve its denominator. Until then, report escalation and correct escalation only. | The current legacy-derived unnecessary-escalation metric cannot be interpreted as an M3A outcome. |
| D8 | unresolved | [M3 validation spec](M3_VALIDATION_SPEC.md) “Experiment matrix”; [protocol](EXPERIMENT_PROTOCOL.md) §§3,6–7; [`experiment.py`](src/jev_control_plane/failure_lab/experiment.py) | Select the primary Jev condition and any secondary conditions; approve the exact questions/views, model/SDK, mappings, aggregator, policy, retries, and config fields to freeze. Choice-only remains a proposal, not a selection. | No M3A configuration can be frozen or run; matrix rows remain design candidates. |
| D9 | proposed (synthetic authorization rule approved) | [M3 validation spec](M3_VALIDATION_SPEC.md) “Approved synthetic authorization semantics” and “Ground truth”; [ground-truth rules](experiments/datasets/ground_truth_rules.md); [benchmark model](src/jev_control_plane/failure_lab/benchmark.py) | Approve the Validation case-review/adjudication procedure, reviewer roles, certainty assignment, and handling of unresolved labels. The approved synthetic policy does not mean any Validation label has been reviewed. | A future dataset could be reproducible but still lack the review strength needed for its intended claims. |
| D10 | proposed | [M3 validation spec](M3_VALIDATION_SPEC.md) “Validation dataset”; [protocol](EXPERIMENT_PROTOCOL.md) §4 and “M3A dataset and fixture gates”; [`dataset.py`](src/jev_control_plane/failure_lab/dataset.py) | Confirm the family inventory, case IDs, matched variants, and final size after reviewing whether meaningful variants can be authored. The 36-row/12-family count remains a target. | Sampling, matched-pair denominators, and family-level conclusions cannot be frozen. |
| D11 | unresolved | [M3 validation spec](M3_VALIDATION_SPEC.md) “Pilot interpretation and small-sample uncertainty”; [protocol](EXPERIMENT_PROTOCOL.md) §8; [`metrics.py`](src/jev_control_plane/failure_lab/metrics.py) | Approve pilot-level success/failure/inconclusive criteria, minimum evidence/sample expectations, and how matched-family dependence is handled. No numeric acceptance cutoff is approved. | Only descriptive results can be reported; no decision rule for further integration can be applied. |
| D12 | proposed | [M3 validation spec](M3_VALIDATION_SPEC.md) “Controlled task and side-effect boundary”; [SPEC](SPEC.md); [`runtime.py`](src/jev_control_plane/runtime.py) | The synthetic pilot is already scoped offline with no action execution. Before any later real-workflow study, approve read-only/shadow boundaries, who can review outcomes, and a separate enforcement gate. | The synthetic decision study cannot establish deployment or enforcement readiness; no real action may be inferred from it. |

No approval record was found that closes D1, D2, D4–D8, D10–D12. This register records current repository evidence and the decisions needed; it is not an approval record. The synthetic authorization rule itself remains the approved scope at D9.

### D1 — Primitive-to-action mappings

**Classification:** Approval-required policy choice; primitive behavior is also a research hypothesis.

**Current behavior and evidence:** `DecisionView` permits configurable answer-to-action maps. Noul has two answer states; Choice has a declared finite set of options; Score has an ordered rubric and may map intervals to actions. The official API documentation defines answer shapes, not Jev Control Plane action semantics.

**Options:** (a) map every primitive directly to all three final actions; (b) ask binary Noul predicates and keep `false` distinct from both proven denial and insufficient evidence; (c) use Choice as the direct three-action view and treat Noul/Score as additional evidence; or (d) characterize primitive outputs without producing a final action until a separately approved policy maps them.

**Provisional recommendation:** Use Choice-only as a possible reference condition because its answer can name one of the three actions, provided the option text and mapping are approved. Do not assume `Noul false → DENY`; a negative answer can be compatible with missing evidence, which the approved synthetic task labels `ESCALATE`. Keep Score action mapping open until a rubric and meaning for each level are approved. This recommendation is a design convenience, not evidence that Choice is more reliable.

**Evidence needed:** Actual live primitive outputs on independently labeled, predeclared cases; analysis of errors and escalation by action and family.
**Contract tests:** Reject unknown Choice answers, wrong primitive/view associations, invalid Noul probabilities, out-of-range Score values, absent required mappings, and malformed probability distributions.
**Approval:** Required for questions, options/rubric, mappings, and whether each primitive is allowed to produce a final action.

### D2 — Cross-view aggregation and dependence

**Classification:** Research hypothesis plus approval-required policy choice.

**Current behavior and evidence:** The transparent aggregator preserves raw results and reports agreement, disagreement, and unmapped views. The legacy policy escalates on any disagreement or unmapped view. It does not weight views. TypeSafe says questions in one request see the same state and are evaluated independently, but this API behavior does not establish statistical independence of their errors. Choice/Score confidence is derived from that view's probability distribution, not an independent extra vote.

**Options:** (a) unanimity; (b) a fixed precedence hierarchy; (c) a primitive-specific rule that permits stronger evidence to outweigh weaker conflict; or (d) a single primary view with other views reported descriptively. Any weighting or precedence would be a policy choice; raw confidence values from unlike primitives cannot be treated as comparable weights without evidence.

**Provisional recommendation:** Do not enable a multi-view final-action condition until its exact rule is frozen. Preserve per-view outputs and analyze disagreement as evidence. A Choice-only reference plus separately predeclared view-ablation conditions is the smallest design that can compare added views without pretending the current unanimity policy is approved. The aggregation rule for each multi-view condition still requires your approval.

**Evidence needed:** Paired per-case and per-family behavior under A1–A3 and B1–B3, including correctness, false ALLOW/DENY, escalation, disagreement, missing evidence, and latency. Correlation or dependence must be measured; multiple questions alone do not prove independent evidence.
**Contract tests:** Each raw view remains present; mapped/unmapped/disagreement summaries reconcile with raw outputs; any selected rule is deterministic and versioned; both disagreement and unmapped evidence can coexist.
**Approval:** Required before a multi-view condition may emit an M3A final action.

### D3 — Evidence representation and normalization

**Classification:** Software invariant.

**Current behavior and evidence:** Raw typed answers and provider metadata are retained. Confidence is optional and primitive-specific. The adapter validates probability values individually but previously did not verify that Choice/Score probability distributions sum to one; that small validation gap is corrected in this task using a `1e-9` absolute tolerance for floating-point serialization, with a regression test. It rejects rather than silently normalizing malformed distributions.

**Recommended invariant:** Keep native output, normalized interpretation, policy result, expected action, and execution status as separate fields. Never manufacture confidence, overwrite raw results, compare confidence between unlike primitives as equivalent, or treat co-derived confidence and probabilities as independent views. A malformed distribution is a normalization/runner error, not a valid `ESCALATE` prediction.

**Evidence needed:** No empirical evidence is required to enforce schema validity; empirical work is required to assess predictive value, calibration, or thresholds.
**Contract tests:** Existing adapter shape tests plus normalized-sum tolerance, invalid sum rejection, range/finiteness, and preservation of original native values.
**Approval:** No approval needed for data-integrity checks; any action mapping remains subject to D1.

### D4 — Action-specific evidence requirements and risk

**Classification:** Approval-required policy choice; relative error costs are domain hypotheses.

**Current behavior and evidence:** The policy applies one confidence floor regardless of action. This is not a justified action-specific risk model. The synthetic authorization pilot has independent deterministic ground truth, but no Jev evidence requirement is approved.

**Options:** one shared floor; different floors for ALLOW and DENY; or action-specific rules using primitive-specific evidence requirements. No hypothetical cost ratio mathematically supplies a probability threshold without a validated decision model and loss assumptions.

**Provisional recommendation:** First predeclare the consequence of false ALLOW versus false DENY for the synthetic authorization task and the evidence considered admissible for each action. Do not choose numbers until the Validation protocol states how they will be explored and frozen. Report false ALLOW and false DENY separately.

**Evidence needed:** Independent labels, action-specific outcome counts, confidence/probability behavior, and domain cost assumptions. Small synthetic counts can identify observed failure cases but cannot establish general risk rates.
**Contract tests:** Configuration bounds and action-specific rules are deterministic, serialized, versioned, and do not access expected labels.
**Approval:** Required for any autonomous-action floor or action-specific evidence rule.

### D5 — Thresholds and legacy defaults

**Classification:** Approval-required policy choice; thresholds are experimental parameters, not established facts.

**Current behavior and evidence:** `PolicyConfig` has legacy defaults (`minimum_confidence=0.70`, `minimum_noul_probability=0.80`, Choice/Score action-support floors `0.0`, and no Score thresholds). `ValidationCriteria` has defaults described in D1. Existing Development config uses the legacy confidence/Noul values. The M3 spec withdrew the former `0.80` ALLOW / `0.70` DENY support values as fixed M3 criteria and supplied no replacements.

**Options:** retain defaults for legacy M1/M2 examples only; create a separate explicit M3A configuration after approval; or omit numeric thresholds from an initial descriptive primitive characterization. Do not tune final criteria on Holdout.

**Provisional recommendation:** Keep the existing defaults for backward compatibility and mark them legacy; require a complete explicit M3A policy configuration before live Validation. Do not make a config appear approved merely because it serializes old defaults. The 36-row target does not validate any threshold by itself.

**Evidence needed:** Development may debug the runner; Validation may compare predeclared candidate settings under a declared selection method. Holdout remains untouched until a separate lock process and authorization.
**Contract tests:** Missing M3A policy configuration prevents an M3A run; config digest changes for any policy/mapping/threshold change; the M3A path cannot silently fall back to legacy defaults.
**Approval:** Required for final settings and threshold-selection procedure.

### D6 — Missing, malformed, unsupported, and failed results

**Classification:** Software invariant for representation and label isolation; approval-required choice for retry and action-on-error behavior.

**Current behavior and evidence:** The single-provider runner records case errors without a decision action when adapter/normalization fails. The paired mock schema distinguishes abstention, timeout, provider failure, malformed output, schema-invalid action, and runner error. No live comparison adapter or live retry/timeout configuration exists. A thrown Jev call is not a policy-generated `ESCALATE` action.

**Options:** retain one attempt and report failure; use a fixed predeclared retry policy; or abort the whole run on a fatal environment failure while preserving partial artifacts. Any conversion of a technical failure to a returned action belongs at the future integration boundary and must never silently become ALLOW.

**Provisional recommendation:** In research artifacts, keep provider/execution failures separate from valid `ESCALATE`. Preserve every attempted case and reason category. For the first live smoke, prefer no hidden retries; if retries are approved, record every attempt, retry limit, and elapsed/cost effect. The caller's fail-closed integration contract needs a separate explicit decision before enforcement.

**Evidence needed:** SDK timeout/error behavior, provider reliability, and actual retry/cost/latency observations.
**Contract tests:** Invalid outputs and thrown adapter errors yield non-decision status; no error path emits ALLOW; attempts are retained; pair denominators are explicit.
**Approval:** Required for timeouts, retries, fatal-run semantics, and any caller-visible action on failure.

### D7 — Escalation and “unnecessary escalation”

**Classification:** Approval-required policy choice; escalation trade-off is a research outcome.

**Current behavior and evidence:** Current policy escalates under its legacy agreement/confidence/support rules. The runner currently calculates “unnecessary escalation” using `candidate_action`, `expected_action`, and legacy `evidence_sufficient`; the M3 contract correctly says this is not meaningful for M3A until sufficiency and aggregation are approved.

**Options:** report only exact-action errors and escalation counts; define unnecessary escalation as avoidable under a frozen sufficiency predicate; or use a separate human-review outcome in a later study. A correct ground-truth `ALLOW` or `DENY` alone does not demonstrate that the supplied evidence should have allowed autonomous resolution.

**Provisional recommendation:** In M3A reports, show escalation rate and correct escalation (`expected=ESCALATE, final=ESCALATE`). Keep unnecessary escalation unavailable until a predeclared sufficiency predicate exists. Never count disagreement by itself as failure.

**Evidence needed:** Approved action-specific sufficiency rule; if workload is claimed, actual human-review outcomes and time/cost data.
**Contract tests:** Metric remains unavailable absent the rule; disagreement does not increment an outcome error; all counts state denominators.
**Approval:** Required to define sufficiency and unnecessary escalation.

### D8 — Primary condition and frozen comparison configuration

**Classification:** Approval-required experiment choice.

**Current behavior and evidence:** The protocol lists A1 Noul, A2 Choice, A3 Score and B1 Choice, B2 Choice+Noul, B3 Choice+Noul+Score. Those rows are proposals, not authorization to run. The paired harness is mock-only and policy equivalence is disabled.

**Options:** one Choice-only primary condition with others secondary; a predeclared multi-view primary; or primitive characterization without cross-condition final-action comparisons. The first option limits unresolved aggregation, but cannot be used until Choice output/ESCALATE mapping and action evidence requirements are approved.

**Provisional recommendation:** Approve one primary configuration and label additional conditions secondary before live calls. Freeze model/version, SDK, questions/instructions, view set/order, output/action mapping, aggregator, policy thresholds, retry/timeout settings, dataset and annotation digests, code revision, and metrics before observing Validation outcomes. Any change after outcome inspection starts a new development/configuration cycle.

**Evidence needed:** No performance evidence is required to define the configuration; it must be frozen before outcome access.
**Contract tests:** Canonical config digest covers every decision-affecting field; run manifest records revisions and artifacts; Holdout requires a matching Validation lock and is not accessed in this pilot.
**Approval:** Required for primary/secondary status, exact configuration, and run authorization.

### D9 — Ground truth and adjudication

**Classification:** Software invariant for separation; approval-required dataset methodology.

**Current behavior and evidence:** Benchmark cases carry expected final action and provenance/certainty; annotations are separate. The eight Development rules are synthetic, developer-authored, medium certainty, and not independently reviewed. The approved synthetic authorization design uses a fixture-defined finite tuple coverage inventory and deterministic fixture validation. That inventory is evaluator/ground-truth material, not Jev input.

**Provisional recommendation:** Author rules and labels before provider results. For objective synthetic authorization cases, retain the rule ID/rationale and request second review where practical. For normative labels, obtain independent labels under one rubric, preserve disagreements and adjudication, and retain unresolved labels rather than forcing them. Keep expected labels, oracle inventory, rationales, and annotation notes out of provider-visible input.

**Evidence needed:** Case-by-case rule review and reproducibility of the ground-truth derivation. Synthetic truth supports conformance to the declared synthetic policy only.
**Contract tests:** Duplicate IDs, invalid provenance/action, registry mismatch, coverage mismatch, invalid timestamps, and malformed matched pairs fail as fixture-integrity errors before provider evaluation.
**Approval:** Required for label rubric, reviewer procedure, case admissions, and any unresolved-label handling for primary metrics.

### D10 — Proposed 36-row / 12-family design

**Classification:** Approval-required sampling/design choice; perturbation effects are hypotheses.

**Current behavior and evidence:** The plan proposes 36 synthetic rows across 12 scenario families, with three related cases per family where meaningful. No such Validation rows or family allocations currently exist. The eight Development cases are plumbing fixtures. A useful pair keeps ground truth fixed when only irrelevant context changes; genuinely changed relevant facts require an independently derived label.

**Options:** target 36 rows and accept documented shortfalls when meaningful matching is not possible; revise the target before authoring; or start with fewer cases as protocol rehearsal only. No statistical power or population validity follows from the row/family count.

**Provisional recommendation:** Keep 36/12 as a planning target. Freeze family names, base IDs, perturbation definition, changed/unchanged facts, and expected-action invariance before live output. If a matched variant changes relevant evidence, label it independently and do not call it an unchanged-truth perturbation.

**Evidence needed:** Independent review of each case, rule provenance, and family-level coverage. Report counts by family/provenance and matched transitions; avoid treating related rows as independent population samples.
**Contract tests:** Every perturbation points to a valid base in the split; same expected action is required only when the declared intervention preserves decision-relevant facts; label/registry contradictions fail fixture validation.
**Approval:** Required before the dataset plan is frozen; no cases are created by this proposal.

### D11 — Metrics and acceptance criteria

**Classification:** Software invariant for honest denominators; approval-required choice for pass/fail criteria; comparative effects are research hypotheses.

**Current behavior and evidence:** Existing single-run metrics report exact-action accuracy/error, false ALLOW/DENY, escalation, agreement/unmapped counts, latency, runner errors, and family breakdown. Exact binomial intervals are computed for some rates, but do not account for matched-family dependence. The paired mock reports both-correct/Jev-only/LLM-mock-only/neither, action disagreement, and failures, using only pairs where both conditions return valid actions for the paired accuracy denominator.

**Provisional recommendation:** Report all attempted cases and execution failures; action metrics with `k/n`; false ALLOW/DENY separately; correct escalation and escalation rate; evidence properties separately; paired wins/losses/ties and disagreement; by-family results; and latency observations/method. Show excluded/non-decision pairs as counts. Do not report ECE/Brier/calibration, SAC, risk-coverage, trajectory success, cost, or human workload absent an appropriate data/protocol. Do not use one composite score.

**Hypotheses:** View additions may improve, worsen, or leave action outcomes unchanged while affecting escalation/latency. Perturbations may or may not alter evidence/action. Any direction is empirical.
**Support/contradiction/inconclusive:** A direction can be assessed only against predeclared margins/criteria and reviewed ground truth. If thresholds/margins are not approved or denominators are too small/family-dependent, report descriptive counts and call the result inconclusive for population claims. No numeric acceptance cutoff is adopted here.
**Contract tests:** Hand-computed metric fixtures; denominator reconciliation; errors excluded only from action denominators but retained in attempt counts; no hidden dropping of failed cases.
**Approval:** Required for any pilot-level success/failure gate or minimum evidence/sample standard.

### D12 — Shadow mode and enforcement

**Classification:** Approval-required operational policy choice.

**Current behavior and evidence:** The control plane returns a decision-level action; it does not own an agent lifecycle, execute the proposed action, implement a human-review service, or provide an existing-agent shadow integration. M3A's synthetic authorization task has no external side effects.

**Provisional recommendation:** Keep the initial pilot as offline replay over frozen synthetic cases. Do not claim shadow-mode behavior or enforcement readiness. Any future actual workflow evaluation should begin with a developer-selected, read-only/shadow condition where Jev cannot change actions, followed by a separately approved enforcement gate only if the evidence and domain owner justify it.

**Evidence needed:** A representative existing workflow, safe interception point, human-review process, recovery/rollback behavior, and measured outcome impact.
**Contract tests:** Future integration tests must prove observation-only mode has no side effects and enforcement is off by default. These tests are not part of current M3A.
**Approval:** Required before inspecting/connecting a real project, shadow evaluation, or enforcement.

## Proposed experiment protocol (not executed)

1. **Unit and domain:** one proposed synthetic authorization decision, with exact principal/resource/operation, explicit finite manifest coverage, manifest status/authority/version, half-open validity bounds, grants/prohibitions, and the proposed action. Do not execute the action.
2. **Conditions:** Synthetic Deterministic Rule Baseline for conformance; one approved Jev primary condition; any additional A1–A3/B1–B3 conditions only after their mapping and aggregation rules are frozen. The baseline is not an actual developer workflow.
3. **Label-free provider inputs:** provider-visible state and decision only. Keep expected action, rule rationale, coverage oracle, family annotations, and adjudication notes evaluator-side. Case identity is retained in the run envelope; an eventual live adapter should avoid putting outcome-encoding IDs in model content.
4. **Ground truth:** versioned rules and fixture registry first; derive expected actions before any Jev result; independent second review of objective cases where practical; multiple independent human labels for normative cases; preserve unresolved labels and disagreements.
5. **Matched cases:** group by family and pair by base-case identity. Irrelevant-context changes preserve ground truth. Relevant-fact changes require a new independent label and are analyzed as a changed decision, not as a same-label perturbation. Do not cherry-pick after outputs.
6. **Outputs:** provider-native response, normalized view evidence, policy result, expected outcome, and execution status in separate fields. Preserve per-attempt latency and errors. No expected label or other condition output enters a provider request.
7. **Missing/ambiguous truth:** retain the row and reason. Do not force a label. Exclude unresolved truth only from metrics that require a definite reference, with the excluded denominator disclosed; do not silently remove it.
8. **Paired analysis:** same cases and config across conditions. Report paired action outcomes over both-valid-action pairs and separately show all attempted pairs, failures, abstentions, and missing actions. Report false autonomous ALLOW and DENY against independent expected actions, escalation rates, valid escalation outcomes, view disagreement, and family-level transitions. No composite winner score.
9. **Operations:** separate inference latency from runner/serialization overhead; record provider/model/SDK, prompt/config, timestamps, usage, retries, timeouts, and failure categories where available. Monetary cost only from actual usage and applicable price source; do not invent it. At small n, show counts and method; p95 and inferential intervals do not overcome family dependence or sampling bias.
10. **Lifecycle:** Development for plumbing/design, Validation for frozen-case selection under an approved method, LOCK only after the complete configuration and Validation artifacts are frozen, Holdout only after separate authorization. No Validation or Holdout execution is authorized by this proposal.

## Hypothesis interpretation

| Hypothesis | Evidence that could support it | Evidence that could contradict it | Inconclusive when |
| --- | --- | --- | --- |
| A single primitive can support autonomous action for some structured cases. | A predeclared class/config meets the approved action-specific evidence and outcome criteria on reviewed cases. | It repeatedly produces false autonomous actions or fails the predeclared criteria for the tested class. | Criteria are not fixed, truth is weak, or sample/family dependence cannot support a conclusion. |
| Additional views can improve evidence in some conditions, with possible costs. | Paired view conditions show a predeclared benefit on action outcomes or error trade-offs, while costs are measured. | Added views fail a predeclared benefit criterion or worsen errors/escalation/latency for the tested class. | No approved aggregation rule, insufficient matched cases, or no predeclared definition of a meaningful trade-off. |
| Perturbations change decision evidence or actions under some conditions. | Within-family evidence/action transitions occur in the intended direction under the specified intervention and labels. | Adequately reviewed matched cases show no relevant transition for the tested intervention. | Too few matched families, the intervention changes more than intended, or labels are uncertain. |
| Escalation is preferable in some cases. | Cases independently labeled `ESCALATE` are escalated without unsafe autonomous actions under approved criteria. | The selected rule autonomously acts on unresolved cases or escalates cases contrary to approved sufficiency criteria. | No approved sufficiency/cost/workload criteria or no actual review outcome data. |

These are hypotheses, not conclusions. No numeric acceptance criteria, statistical power, or universal reliability claim is introduced.

## Current comparison-harness readiness

| Capability | Verified state | Needed before live comparison |
| --- | --- | --- |
| Provider contract | `DecisionProvider` / `ProviderAttempt` can retain native output, action, policy result, status, and error category. | Add actual providers only after explicit configuration/credentials path and contract approval. |
| Provider isolation | Mock runner deep-copies state and excludes annotations/labels from attempts. | Keep case IDs only as opaque run metadata; verify model request payloads do not contain ground truth or annotation data. |
| Pairing | Same Development case IDs; duplicate/missing pairs rejected; evaluator labels live in `pairs.jsonl`. | Extend only after approved Validation split and provider configuration exist. |
| Failure handling | Mock status enum distinguishes abstention, timeout, provider failure, parse/schema error, runner error. | Define real timeout/retry semantics; preserve every attempt and never convert operational error to a valid action. |
| Policy normalization | Jev-shaped mock returns legacy policy output; LLM-shaped mock returns a direct action; comparison explicitly disables policy equivalence. | M3A mapping/aggregation/action criteria must be approved before comparable final-action policy results are claimed. |
| Reproducibility | Paired manifest records config/dataset digests and software metadata; validator checks artifacts; CI is offline. | Live model/SDK/prompt version, request usage, retries/timeouts, timestamp, source revision and cost source must be captured and validated. |
| Results | Paired descriptive metrics retain denominators and error counts. | Use real labels and actual live providers before making comparative claims; current mocks are not providers. |

## Approval register

| Decision needing approval | Why it matters | Recommended next move |
| --- | --- | --- |
| Primary Jev condition and action/view mappings | Determines what an action means for each primitive and whether an output can resolve ALLOW/DENY/ESCALATE. | Review D1 and D8; tentatively consider Choice-only as a reference, with explicit mapping. |
| Multi-view aggregation, disagreement, and missing-evidence behavior | Determines whether conflicting views can support autonomous action or require escalation. | Keep open; select a deterministic, versioned rule before any B2/B3 run. |
| Action-specific evidence criteria and thresholds | Determines false ALLOW/DENY trade-off and what “sufficient” means. | Define decision stakes and evidence first; select any numeric values only as predeclared experimental criteria. |
| Failure, timeout, retry, and caller action semantics | Separates an explicit escalation decision from a failed provider call and affects latency/cost. | Report operational errors separately; approve retries/failure handling before live provider use. |
| Dataset plan and acceptance criteria | Determines case inclusion, interpretation, and what conclusions can be drawn. | Keep 36/12 as a target; freeze case families/labels and denominators before live outcomes. |
| Shadow/enforcement gate | A decision-level result does not itself authorize executing an agent action. | Keep the pilot offline and side-effect-free; treat a real workflow as a separately approved study. |

## Not resolved by this proposal

- Whether Jev probabilities or confidence are reliable for the selected task; this requires live observations against independent labels. The official API field definitions do not establish project-specific calibration or action sufficiency.
- Whether multiple views add useful evidence or instead add correlated error, latency, or escalation.
- Which aggregation, action-specific thresholds, or acceptance criteria are appropriate; these require explicit owner approval and a predeclared Validation method.
- Whether Jev improves an actual developer workflow; the synthetic rule baseline is only policy conformance, and no real workflow has been selected.
- Whether live SDK timeout/retry behavior, operational cost, human-review workload, or agent-task outcomes justify integration.

## Recommended next action

Review and decide the first three approval items in the register: (1) primary condition and primitive mappings, (2) multi-view disagreement/missing-evidence rule, and (3) action-specific sufficiency criteria and how thresholds may be selected on Validation. Keep T‑3A open until those decisions are recorded in `M3_VALIDATION_SPEC.md`. Then implement the approved configuration boundary and its tests before any live Validation authorization.
