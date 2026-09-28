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
