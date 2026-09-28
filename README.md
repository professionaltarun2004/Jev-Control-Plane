# Jev Control Plane

A framework-neutral, decision-level control plane. Jev produces structured evidence; a transparent aggregator preserves view agreement and conflict; deterministic policy maps evidence to `ALLOW`, `DENY`, or `ESCALATE`.

## First flow

```text
AgentState → DecisionRequest → Jev adapter → JevResult(s)
           → DecisionEvidence → PolicyEngine → PolicyResult
           → structured DecisionRecord
```

Each named view describes the same underlying decision. The Jev adapter batches all views in one official TypeSafe `system_one` call and passes only `AgentState` to Jev. Control-plane metadata is retained for records and is not sent as Jev state.

## Install and run

Python 3.11+ is required. Install the package and its official TypeSafe SDK dependency, then set `TYPESAFE_API_KEY` before using the live adapter.

```powershell
python -m pip install -e .
python examples/decision_flow.py
```

Run the local deterministic tests with `python -m unittest discover -s tests -v`. Tests use a fake Jev adapter and do not call the service.

## Jev output shape

Choice and Score carry answer, probabilities, and confidence. Noul carries a probability for “yes” and has no separate confidence or probability map in the current API; the adapter preserves its probability and derives a typed boolean using a configurable midpoint. No confidence is synthesized. Request latency is measured around the SDK call, and model, usage, and request ID are retained when available.

## Policy defaults

The starter policy requires every view to map its answer to an action. Missing mappings, disagreement, reported confidence below its configured floor, or Noul support below its separate probability floor produce `ESCALATE`. Consistent mapped actions produce that action. The confidence floor (0.70) and Noul probability floor (0.80) are experimental defaults, not validated safety thresholds. Policy does not infer confidence from probabilities.

JSONL records store a SHA-256 fingerprint of the decision question and `AgentState`, rather than copying potentially sensitive input text. Keep reproducible synthetic/real evaluation inputs in the corresponding controlled dataset and use metadata such as `task_id` to join records to that source.

See [SPEC.md](SPEC.md), [Genesis harness](.genesis/PLAN.md), and [experiment lifecycle](experiments/README.md).
