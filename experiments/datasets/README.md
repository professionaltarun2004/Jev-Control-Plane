# Dataset layout

The authoritative benchmark, split, annotation, and ground-truth methodology is in [EXPERIMENT_PROTOCOL.md](../../EXPERIMENT_PROTOCOL.md).

Each case file has only `case_id`, `state`, `decision`, and `ground_truth`. Ground truth carries expected final action, source, reference, and certainty. It contains no expected Jev primitive/view answers. Optional split-local `annotations.jsonl` records describe perturbation family and, for matched perturbations, a base case ID.

| Path | Purpose | Current status |
| --- | --- | --- |
| `development/cases.jsonl` | Plumbing and iteration | Eight developer-authored synthetic cases |
| `development/annotations.jsonl` | Secondary perturbation metadata | Includes one matched irrelevant-context case |
| `validation/` | Protocol/policy selection | Not populated; no claims of validated configuration |
| `holdout/` | Locked final evaluation | Not populated and not evaluated |
| `ground_truth_rules.md` | Provenance and labeling limits | Synthetic deterministic rules only |

The Holdout read API requires a permit produced after a matching Validation lock. Lock digests detect accidental drift through this application; they cannot prevent operators from copying or editing files outside it. Split existence alone does not establish representative sampling, independent annotation, statistical power, blinding, or external validity.
