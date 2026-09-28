# Bounded implementation plan

## T-1 — Prove the core decision loop

**Outcome:** typed request and views flow through TypeSafe Jev, transparent evidence aggregation, deterministic policy, and structured logging; local tests and one live example explain the result.

**Risk:** medium (decision handling, though this milestone causes no external agent action).

**Requirement trace:** FR-1–FR-6, NFR-1–NFR-4, AC-1–AC-5 in `SPEC.md`.

**Executable gate:** `python -m unittest discover -s tests -v`.

**Evidence expected:** test output plus a JSONL record from the deterministic local flow. Live API execution is separately recorded and not required by offline tests.

**Status:** complete; offline gate passed. Evidence is recorded in `.genesis/evidence/`.

## Explicitly outside T-1

Failure Lab, benchmark datasets, trajectory runtime behavior, WATCH, human review adapter, extra providers, framework adapters, dashboards, distributed services, and performance claims.

## T-2A — Establish minimal benchmark cases and split discipline

**Outcome:** benchmark cases hold only identity, current state, decision, and independent ground truth with provenance/certainty. Split storage is isolated; LOCK freezes a validation configuration before Holdout can be read.

**Risk:** medium (dataset integrity and evaluation leakage).

**Requirement trace:** M2 FR-1–FR-4 and AC-1–AC-3 in `SPEC.md`.

**Executable gate:** `python -m unittest discover -s tests -v`.

## T-2B — Run Jev-only experiments and calculate decision metrics

**Outcome:** one runner executes the existing Jev control loop, supports an explicitly labeled deterministic mock mode for local verification, preserves failed cases and decision records, and calculates metrics supported by the recorded data.

**Risk:** medium (research results and operational evidence).

**Requirement trace:** M2 FR-5–FR-8 and AC-4–AC-7 in `SPEC.md`.

**Executable gate:** `python -m unittest discover -s tests -v` plus `python examples/run_mock_experiment.py`.

## T-2C — Document Failure Lab boundaries and reproducibility

**Outcome:** README, experiment guide, split protocol, perturbation taxonomy, results status, and machine-readable run artifacts explain exactly what was and was not measured.

**Risk:** low.

**Requirement trace:** M2 FR-9, NFR-1–NFR-4 and AC-8–AC-9 in `SPEC.md`.

**Executable gate:** inspect generated manifest, JSONL, summary, and documentation after T-2B.

**Status:** complete; test and mock evidence are recorded in `.genesis/evidence/m2-*.json`.

## Explicitly outside T-2

Live Jev performance, threshold sweeps, calibration, cost accounting, realistic labeled data, trajectory/task evaluation, framework adapters, and external baselines remain unmeasured or future work.
