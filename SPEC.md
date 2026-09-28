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
