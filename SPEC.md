# Project specification

## Objective

Build a small, framework-neutral, decision-level control plane using Jev as V1's decision engine. Jev returns probabilistic structured evidence; a transparent evidence aggregator preserves each view; deterministic policy maps evidence to `ALLOW`, `DENY`, or `ESCALATE`. Research determines where the approach works and fails.

## Functional requirements

- **FR-1** A request carries the current `AgentState`, one decision question, one or more named views of the same decision, and separate metadata.
- **FR-2** The Jev adapter batches supported Noul, Choice, and Score views against one current state and preserves typed answer, reported probabilities/confidence, raw response, model/request metadata, usage when available, and measured latency.
- **FR-3** A transparent aggregator retains every view result and exposes mapped agreement, disagreement, and unmapped views.
- **FR-4** A deterministic configurable policy emits only `ALLOW`, `DENY`, or `ESCALATE`.
- **FR-5** Each decision can be written as a structured JSONL record with timestamp, request identity/state, views, evidence, policy version/action, and optional outcome.
- **FR-6** The first milestone includes a runnable end-to-end example and tests using a local fake adapter.

## Non-functional requirements

- **NFR-1** Framework integrations and alternate decision providers are absent from V1 core; the interfaces permit future providers.
- **NFR-2** Metadata is not passed to Jev by default. Records should avoid secrets and unnecessary personal data.
- **NFR-3** Behavior is deterministic after Jev evidence is returned; policy configuration is separate from inference.
- **NFR-4** Runtime and test setup stays understandable and small; Genesis is an engineering harness, not a runtime dependency.

## Acceptance criteria

- **AC-1** Request validation rejects empty decision context, missing views, and duplicate view IDs.
- **AC-2** Jev result normalization keeps raw answer, probabilities, confidence independently, model/request metadata, usage, and latency. Noul's API absence of separate confidence is represented as `None`.
- **AC-3** Tests show agreeing and disagreeing views; disagreement stays visible and policy escalates it.
- **AC-4** Tests prove all three actions, confidence floor behavior, unmapped evidence handling, and JSONL raw record creation.
- **AC-5** A developer can trace the core flow in source and run an example with a TypeSafe API key.

## Milestone 2: Failure Lab

### Functional requirements

- **M2-FR-1** A benchmark case contains only `case_id`, `AgentState`, decision question, and independent ground truth. It carries no per-view expected answers or Jev-specific labels.
- **M2-FR-2** Ground truth records action, source/provenance, reference, and an explicit certainty level.
- **M2-FR-3** Development, Validation, and Holdout cases are stored separately. LOCK is a configuration checkpoint between Validation and Holdout, not a fourth case file.
- **M2-FR-4** A Holdout run requires a lock created from the same Jev model, views, and policy configuration that was frozen after Validation; Holdout cannot be run in a tuning phase.
- **M2-FR-5** The initial runner executes only the Jev control path; live Jev and deterministic mock execution are explicit and distinguishable modes.
- **M2-FR-6** A result is retained for every attempted case, including run errors, with per-decision control output, independent truth, view agreement, policy escalation, latency, and derived failure labels where evidence allows.
- **M2-FR-7** Metrics include exact-action accuracy/error rate, action rates, run errors, latency summaries, throughput, view agreement/disagreement, policy escalation, and failure-family breakdown when applicable.
- **M2-FR-8** Calibration or cost metrics are emitted only if the result data supports them; this milestone does not claim calibration or compare providers.
- **M2-FR-9** The initial failure taxonomy is explicit; families not yet represented by clean cases or analyses are documented as unimplemented.

### Non-functional requirements

- **M2-NFR-1** No frontier-LLM baseline, WATCH, web UI, framework adapters, or generic model provider abstraction is added.
- **M2-NFR-2** Benchmark cases stay minimal; perturbation family and derived failure classifications are stored separately from expected action.
- **M2-NFR-3** Mock outputs and metrics are labeled as mock and are never represented as Jev performance.
- **M2-NFR-4** Run artifacts are unique, machine-readable, retain case errors, contain no API secrets, and reference privacy-preserving decision records.

### Acceptance criteria

- **M2-AC-1** Case validation rejects missing/extra benchmark labels, malformed state, and incomplete ground-truth provenance.
- **M2-AC-2** Dataset management isolates splits and rejects duplicate case IDs across them.
- **M2-AC-3** Tests prove Holdout is inaccessible without a matching immutable Validation lock and that a changed policy fails the match.
- **M2-AC-4** Runner executes one Jev-path experiment in deterministic mock mode without network access.
- **M2-AC-5** Metrics match hand-computed decision fixtures, including confusion/action counts, escalation, agreement, errors, and latency rules.
- **M2-AC-6** Missing/malformed Jev evidence is preserved as a case-level run error rather than silently removed.
- **M2-AC-7** Run manifest and JSONL records include experiment/dataset/config/mode/provenance/software metadata and preserve every case attempt.
- **M2-AC-8** Perturbation families are annotations, not expected per-view labels; unsupported family analyses are documented.
- **M2-AC-9** README distinguishes implementation facts, the actual mock observation, unmeasured Jev results, hypotheses, and limitations.

## Milestone 2.5: Experimental protocol and research readiness

### Requirements

- **M2.5-FR-1** `EXPERIMENT_PROTOCOL.md` is authoritative for falsifiable questions/hypotheses, primitive and view comparisons, matched perturbations, truth methodology, outcome taxonomy, metrics, and split discipline.
- **M2.5-FR-2** Holdout case and annotation reads/digests require a permit minted only after lock verification. LOCK binds Validation and Holdout case/annotation digests, the Validation run manifest/results/summary digest, decision configuration, software/code/protocol identity, and ground-truth method identity.
- **M2.5-FR-3** A Holdout content snapshot accepts one attempt, including interrupted attempts; altered configuration or inputs cannot silently reuse the saved lock.
- **M2.5-FR-4** Evidence conditions (agreement, unmapped views, probability/confidence observations) remain distinct from outcome errors. Disagreement alone is not an outcome failure.
- **M2.5-FR-5** Per-view Score-to-action thresholds are explicit, range-checked against an ordered rubric, and included in configuration/version digests.
- **M2.5-FR-6** Perturbation annotations are separate from minimal cases; declared matched variants reference a clean same-split base and preserve truth when the intervention is context-only.
- **M2.5-FR-7** Documentation labels synthetic plumbing data, mock runs, unmeasured live findings, and limitations accurately. No Holdout execution or live result is fabricated.

### Acceptance criteria

- **M2.5-AC-1** Tests reject unlocked Holdout data, annotation, and digest access; lock and Validation run artifact tampering, config mismatch, Validation drift, Holdout drift, and repeat attempts.
- **M2.5-AC-2** Tests cover mixed mapped disagreement plus unmapped evidence, Score thresholds, runner errors, outcome/evidence separation, and matched perturbation invariants.
- **M2.5-AC-3** Dataset and protocol document the actual current Development truth process and do not present its labels as independently validated.
- **M2.5-AC-4** Experiments documentation points to the authoritative protocol and makes no unsupported calibration, trajectory, cost, or performance claims.
- **M2.5-AC-5** Unit, syntax, artifact, and diff checks pass; live Jev and Holdout remain unrun unless explicitly authorized by the research protocol.
