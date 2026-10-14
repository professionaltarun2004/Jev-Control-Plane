# Contributing

Thanks for considering a contribution. This repository is a small Jev-first control plane and research harness; contributions should keep its behavior inspectable and its evidence honest.

## Set up and verify

Use Python 3.11 or newer. Follow the offline setup in the [README](README.md#path-a-offline-mock-no-api-key), then run:

```sh
python -m unittest discover -s tests -v
python examples/run_mock_experiment.py
```

The mock command creates a new run directory under `experiments/runs/`. Inspect its manifest, summary, and JSONL results. The output is mock plumbing evidence, not a Jev evaluation. Do not run `examples/decision_flow.py` in tests or CI; it makes a live request. A live run requires a separately authorized experiment and the user's own credentials.

## Pull requests

- Keep changes focused and explain the problem, the change, and the checks you ran.
- Add or update tests for behavior changes. Do not weaken a failing test to make a check pass.
- Do not include `.env`, API keys, private user data, or unnecessary raw decision state.
- Do not rewrite or discard failed experiment runs. Label mock and live runs distinctly and preserve their configuration and provenance.
- Do not change M3A policy semantics, Jev mappings, aggregation, thresholds, benchmark membership, labels, or acceptance criteria without an explicit, recorded research decision.
- Keep Development, Validation, LOCK, and Holdout boundaries intact. No Holdout access or live Jev experiment is authorized by a code contribution.
- Update the relevant specification and reproducibility evidence when an approved change affects them.

The project currently has no selected license. Contributions do not imply that the repository is licensed for general reuse; the maintainer must choose and add a license separately.
