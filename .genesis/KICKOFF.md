# Kickoff

- **State:** Milestone 1 core loop is implemented in the previously empty workspace.
- **Evidence:** Ten offline unit tests pass against TypeSafe SDK 0.7.2 question/response models; see `evidence/m1-unit-tests.json`. Current official TypeSafe docs and SDK source were inspected. This workspace did not have Genesis installed, so the project-local harness artifacts were established directly.
- **Blocker:** None for offline core. Live Jev example requires `TYPESAFE_API_KEY` and `typesafe-sdk>=0.7.2`.
- **Next milestone:** Specify the Failure Lab's bounded evaluation data model, split protocol, and experiment runner for individual decisions first. Keep trajectory analysis in research evaluation, not runtime WATCH behavior.
