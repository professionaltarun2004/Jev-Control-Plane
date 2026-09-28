# Dataset layout

Each case file belongs to one split and contains only `case_id`, `state`, `decision`, and `ground_truth` (`expected_action` plus provenance). It has no Jev-view labels. `annotations.jsonl` is a separate, optional join from case ID to perturbation family.

- `development/cases.jsonl`: synthetic plumbing and case-development set.
- `validation/cases.jsonl`: reserved for policy and threshold choices.
- `holdout/cases.jsonl`: reserved, currently empty. Add cases only before the configuration is locked and keep them inaccessible to tuning.
- `ground_truth_rules.md`: construction rules and provenance for the included synthetic cases.

LOCK is stored under `experiments/locks/` as a configuration digest created from Validation. It is a phase transition, not a fourth case split. The runner checks this lock before it asks the dataset store to read Holdout.

Folders alone do not make a benchmark statistically valid. The included cases are small, synthetic, and authored alongside the implementation; they are not representative samples. No confidence intervals, population claims, or generalization claims follow from this structure.
