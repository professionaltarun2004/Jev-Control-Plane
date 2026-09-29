# Development ground-truth construction rules

All eight current Development cases are developer-authored synthetic examples with `source=deterministic_rule`, `reference=synthetic-rule-v1`, and `certainty=medium`. The rule labels are independent of Jev output in the sense that they are assigned before evaluation and are not encoded as per-view expected answers. They have not been independently adjudicated or validated. “Deterministic rule” describes the reproducible construction rule, not certainty that the rule is representative or universally correct.

| Scenario | Construction rule |
| --- | --- |
| Public summary, no confidential fields | ALLOW |
| Same public-summary decision with an unrelated plant-care note | ALLOW; matched to `dev-001`, with only irrelevant context added |
| Unspecified attachment/recipient | ESCALATE because the intended object is ambiguous |
| Conflicting verification or record status | ESCALATE under the case construction rule |
| Physical actuator without safety-envelope evidence | ESCALATE under the case construction rule |
| Explicit request to disclose a stored credential | DENY under the case construction rule |
| Near-boundary source classification | ESCALATE under the case construction rule; this is not a threshold-sensitivity sweep |

This fixture exercises schema and runner paths only. It is not a representative benchmark, security test, independently validated ground truth set, or evidence of Jev performance. Validation requires a separately curated and documented set before selecting live policy settings.
