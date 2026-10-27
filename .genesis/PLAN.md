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

## T-2.5 — Experimental protocol and research readiness

**Outcome:** publish an executable decision-level protocol; preserve minimum case schema and truth provenance; harden split/lock plumbing; separate evidence observations from outcome errors; validate Score mappings and matched perturbations; document what is and is not measured.

**Boundaries:** no live Jev call, Holdout run, Validation dataset fabrication, new provider, framework integration, WATCH, dashboard, or benchmark claim.

**Risk:** high (research leakage and interpretation).

**Requirements:** M2.5-FR-1–M2.5-FR-7 and M2.5-AC-1–M2.5-AC-5 in `SPEC.md`.

**Executable gates:** `python -m unittest discover -s tests -v`; `python -m compileall src tests`; `git diff --check`; JSON/JSONL parse validation; `pytest` where available.

**Status:** complete; offline tests, syntax, artifact parsing, mock plumbing run, and diff checks passed. Live Jev and Holdout remain unrun.

**Evidence:** `.genesis/evidence/m2.5-verification.json`.

## T-3A — Reconcile the M3A research contract

**Status:** open. PR #1 was merged in commit ed99056b7665d2311f1568733259eaf10b11f420. T-3A.1 produced the initial proposal; the current review adds a source-linked D1–D12 decision register with explicit status, consequence, and owner question. M3A primitive/action mappings, multi-view aggregation, evidence requirements, and pilot acceptance criteria remain unresolved. See `M3A_DECISION_PROPOSAL.md` and `.genesis/evidence/t3a-finalization-review.json`.

**Boundary:** review and approve research semantics explicitly. Do not infer choices from legacy runtime defaults. No live Jev or Holdout run is part of contract reconciliation.

### T-3A.1 — Research decision proposal

**Status:** proposal prepared; awaiting owner review. T-3A remains open. The proposal distinguishes software invariants, research hypotheses, and approval-required policy choices; no policy choice, Validation configuration, or acceptance criterion is approved by this subtask.

**Boundaries:** no live Jev/LLM request, no Validation or Holdout read/run, no dataset creation, no runtime policy change. A narrow adapter input-integrity check may reject malformed provider probability distributions without normalizing them.

**Evidence:** `.genesis/evidence/t3a1-decision-proposal.json`.

## T-3B — Mock demo and clean-clone experience

**Outcome:** a new contributor can create a Python environment, install the project from the documented dependency declaration, run the existing offline mock example without Jev credentials, locate its machine-readable artifacts, and run the existing tests.

**Boundaries:** use only the existing Development fixtures and mock adapter. Do not change policy behavior, mappings, thresholds, aggregation, ground truth, experiment criteria, or benchmark scope. No live Jev, Holdout, new workflow benchmark, or paired baseline.

**Risk:** low (setup and contributor workflow; no external action is performed).

**Executable gates:** fresh-virtual-environment installation from the current checkout; `python -m unittest discover -s tests -v`; `python examples/run_mock_experiment.py`; inspect generated manifest, summary, and one result row; `git diff --check`.

**Status:** complete. Fresh-clone installation, all 31 unit tests, offline mock execution, artifact inspection, and diff checks passed. Mock results remain plumbing-only.

**Evidence:** `.genesis/evidence/m3b-verification.json`. Live Jev, Validation, Holdout, and real workflow evaluation remain unrun.

## T-4A — Mock-only paired comparison

**Outcome:** run the Jev-shaped deterministic mock control path and deterministic judge mock independently over the same label-free Development decisions; preserve native outputs, normalized actions, execution statuses, evaluator-only outcomes, and paired descriptive artifacts.

**Boundaries:** mock plumbing only. Policy-level equivalence remains disabled because M3A action mappings, thresholds, aggregation, and escalation semantics remain open. No live providers, Validation, or Holdout access.

**Risk:** medium (comparison artifacts can be misread as model-performance evidence).

**Executable gate:** `python -m unittest discover -s tests -v` plus `python examples/run_mock_comparison.py` and inspection of the versioned paired artifacts.

**Status:** implementation is present in commit `52d3afc15d24bd106c08f02bc6c33d18647838eb`; local paired mock execution and artifact inspection were reproduced during T-4A.1. Results are synthetic Development plumbing only.

## T-4A.1 — Comparison CI, artifact validation, and checkpoint

**Outcome:** validate paired run artifacts in CI against the actual Development case IDs, label-isolation boundary, complete two-condition attempt matrix, statuses/actions, evaluator-owned outcomes, and recomputed paired metrics.

**Depends on:** T-4A. The task does not depend on resolving T-3A because policy-level comparison is disabled and no research configuration is selected.

**Boundaries:** verification infrastructure only. CI success is not comparative research evidence. Do not run live Jev/LLM, Validation, or Holdout.

**Risk:** medium (artifact validation must not misstate action outcomes or conceal provider failures).

**Executable gates:** `python -m unittest discover -s tests -v`; `python -m compileall -q src tests examples scripts`; both mock examples; paired artifact validator; `git diff --check`.

**Status:** implementation commit `e291c6a87e60d6c099d8f8c3ac2cff450aade253` is present on `master` and is an ancestor of `origin/master` at `d71104c1198ebec2e102424bdc6e1b9843b4f63d`. Local gates were reproduced; GitHub Actions passed on the descendant commit for Python 3.11 and 3.12. See `.genesis/evidence/m4a1-verification.json` for the evidence source and limits.

## Next research dependency

T-3A remains **open**. M3A aggregation, action mappings, evidence requirements, thresholds, escalation criteria, and acceptance criteria must be explicitly resolved before any live Validation design is executable. M4A.1 does not authorize live provider calls, Validation, or Holdout.
