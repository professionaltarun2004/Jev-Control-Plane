# Experiment lifecycle

This is a lightweight V1 research record layout, not a benchmark engine.

1. `development/` holds synthetic development cases and policy tuning. Never reuse it as the reported holdout.
2. `validation/` records design checks before the final threshold is frozen.
3. `locked-holdout/` is reserved for untouched final evaluation; do not tune policy against it.
4. Each run records dataset/version, source revision, Jev model, view definitions, policy configuration, seed or deterministic case IDs, timestamp, raw decision JSONL, gate/result status, and a summary. Preserve failed runs.

Decision is the primary evaluation unit. Step, trajectory, and task outcomes remain distinct secondary labels. This milestone defines the lifecycle only; it does not implement the Failure Lab or claim benchmark results.
