# Kickoff

- **State:** Milestone 1 core loop is complete; Milestone 2 task T-2A is active.
- **Evidence:** The pre-M2 gate passed 11/11 tests against TypeSafe SDK 0.7.2; details are in `evidence/m1-unit-tests.json`. The requested source-of-truth files were inspected before planning.
- **Blocker:** None for local implementation. Live Jev calls still require `TYPESAFE_API_KEY`. Genesis CLI is not installed; project-local harness records continue to be maintained without a runtime dependency.
- **Next action:** Finish minimal case/provenance types and split/lock enforcement, then implement and run the Jev-only mockable experiment path.
