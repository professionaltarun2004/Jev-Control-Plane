"""Tests for label-isolated, mock-only paired evaluation plumbing."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from jev_control_plane import AgentState, ControlAction, DecisionView, PolicyConfig, Primitive  # noqa: E402
from jev_control_plane.failure_lab.comparison import (  # noqa: E402
    AttemptStatus,
    DecisionInput,
    DeterministicMockJudge,
    JevMockCondition,
    MockFailure,
    PairedComparisonConfig,
    PairedComparisonRunner,
    ProviderAttempt,
    _copy_provider_input,
)
from jev_control_plane.failure_lab.dataset import DatasetSplit, DatasetStore  # noqa: E402
from jev_control_plane.failure_lab.experiment import ExperimentConfig  # noqa: E402
from jev_control_plane.failure_lab.metrics import calculate_paired_metrics  # noqa: E402
from jev_control_plane.failure_lab.mock import DeterministicMockJevAdapter  # noqa: E402
from validate_comparison_artifacts import validate_artifacts  # noqa: E402


def decision_input(case_id: str = "fixture-1") -> DecisionInput:
    return DecisionInput(case_id, AgentState("Publish the summary", "publish", tool_result={"status": "public"}),
                         "Should the agent publish the summary?")


def view() -> DecisionView:
    return DecisionView(
        "decision", Primitive.CHOICE, "Choose the action for this decision.",
        {"allow": "Proceed", "deny": "Block", "escalate": "Review"},
        {"allow": ControlAction.ALLOW, "deny": ControlAction.DENY,
         "escalate": ControlAction.ESCALATE},
    )


class CapturingJevMock(DeterministicMockJevAdapter):
    def evaluate(self, request):
        self.request_seen = request
        return super().evaluate(request)


class ComparisonInputTests(unittest.TestCase):
    def test_provider_input_has_no_ground_truth_or_annotation_fields(self):
        request = decision_input()
        self.assertEqual(set(request.to_dict()), {"case_id", "state", "decision"})
        adapter = CapturingJevMock()
        JevMockCondition((view(),), PolicyConfig(), adapter).evaluate(request)
        jev_state = adapter.request_seen.to_jev_state()
        self.assertNotIn("expected_action", jev_state)
        self.assertNotIn("ground_truth", jev_state)
        self.assertNotIn("annotation_notes", jev_state)
        self.assertEqual(jev_state["decision_question"], request.decision)

    def test_mock_judge_is_repeatable_and_has_no_confidence_semantics(self):
        adapter = DeterministicMockJudge()
        first = adapter.evaluate(decision_input())
        second = adapter.evaluate(decision_input())
        self.assertEqual(first.native_output, second.native_output)
        self.assertEqual(first.normalized_action, second.normalized_action)
        self.assertEqual(first.provider_version, second.provider_version)
        self.assertEqual(first.status, AttemptStatus.COMPLETED)
        self.assertIn(first.normalized_action, tuple(ControlAction))
        self.assertIsNone(first.policy_result)
        self.assertNotIn("confidence", first.native_output)
        self.assertNotIn("probabilities", first.native_output)

    def test_jev_and_llm_receive_independent_input_objects(self):
        class MutatingJudge(DeterministicMockJudge):
            def evaluate(self, request):
                request.state.tool_result["status"] = "mutated"
                return super().evaluate(request)

        original = decision_input()
        first = _copy_provider_input(original)
        second = _copy_provider_input(original)
        shared_before = first.state.tool_result.copy()
        MutatingJudge().evaluate(second)
        self.assertEqual(first.state.tool_result, shared_before)


class MockJudgeOutputTests(unittest.TestCase):
    def test_malformed_and_schema_invalid_outputs_are_not_actions(self):
        malformed = DeterministicMockJudge({"fixture-1": "{not-json"}).evaluate(decision_input())
        invalid = DeterministicMockJudge({"fixture-1": {"action": "ROUTE"}}).evaluate(decision_input())
        self.assertEqual(malformed.status, AttemptStatus.MALFORMED_OUTPUT)
        self.assertIsNone(malformed.normalized_action)
        self.assertEqual(invalid.status, AttemptStatus.SCHEMA_INVALID_ACTION)
        self.assertIsNone(invalid.normalized_action)

    def test_abstention_timeout_and_provider_failure_are_distinct(self):
        expected = {
            AttemptStatus.ABSTAINED: "provider_abstention",
            AttemptStatus.PROVIDER_TIMEOUT: "provider_timeout",
            AttemptStatus.PROVIDER_FAILURE: "provider_failure",
        }
        for status, category in expected.items():
            with self.subTest(status=status):
                attempt = DeterministicMockJudge({"fixture-1": MockFailure(status)}).evaluate(decision_input())
                self.assertEqual(attempt.status, status)
                self.assertEqual(attempt.error_category, category)
                self.assertIsNone(attempt.normalized_action)

    def test_attempt_invariants_prevent_invalid_status_action_pairs(self):
        with self.assertRaises(ValueError):
            ProviderAttempt("fixture", "1", AttemptStatus.COMPLETED, 1.0)
        with self.assertRaises(ValueError):
            ProviderAttempt("fixture", "1", AttemptStatus.PROVIDER_FAILURE, 1.0,
                            error_category="provider_failure", normalized_action=ControlAction.DENY)
        with self.assertRaisesRegex(ValueError, "typed normalized action"):
            ProviderAttempt("fixture", "1", AttemptStatus.COMPLETED, 1.0, normalized_action="ALLOW")
        with self.assertRaisesRegex(ValueError, "recognized AttemptStatus"):
            ProviderAttempt("fixture", "1", "completed", 1.0, normalized_action=ControlAction.ALLOW)


class PairedMetricTests(unittest.TestCase):
    @staticmethod
    def attempt(case_id, condition, action, status="completed"):
        return {"case_id": case_id, "condition_id": condition, "normalized_action": action,
                "status": status, "latency_ms": 3.0}

    def test_paired_outcome_counts_and_denominators(self):
        expected = {"a": "ALLOW", "b": "DENY", "c": "ESCALATE", "d": "ALLOW"}
        attempts = [
            self.attempt("a", "jev", "ALLOW"), self.attempt("a", "llm", "ALLOW"),
            self.attempt("b", "jev", "DENY"), self.attempt("b", "llm", "ALLOW"),
            self.attempt("c", "jev", "DENY"), self.attempt("c", "llm", "ESCALATE"),
            self.attempt("d", "jev", "DENY"), self.attempt("d", "llm", "DENY"),
        ]
        metrics = calculate_paired_metrics(expected.keys(), expected, attempts, ("jev", "llm"))
        outcomes = metrics["paired_outcomes"]
        self.assertEqual(metrics["both_valid_action_denominator"], 4)
        self.assertEqual(outcomes["both_correct"], {"count": 1, "denominator": 4})
        self.assertEqual(outcomes["jev_only_correct"], {"count": 1, "denominator": 4})
        self.assertEqual(outcomes["llm_mock_only_correct"], {"count": 1, "denominator": 4})
        self.assertEqual(outcomes["neither_correct"], {"count": 1, "denominator": 4})
        self.assertEqual(outcomes["action_disagreement"], {"count": 2, "denominator": 4})

    def test_duplicate_missing_case_ids_and_attempts_are_rejected(self):
        expected = {"a": "ALLOW"}
        one = self.attempt("a", "jev", "ALLOW")
        with self.assertRaisesRegex(ValueError, "unique expected case IDs"):
            calculate_paired_metrics(["a", "a"], expected, [one])
        with self.assertRaisesRegex(ValueError, "missing attempts"):
            calculate_paired_metrics(["a"], expected, [one], ("jev", "llm"))
        duplicate = [one, dict(one), self.attempt("a", "llm", "ALLOW")]
        with self.assertRaisesRegex(ValueError, "duplicate attempt"):
            calculate_paired_metrics(["a"], expected, duplicate, ("jev", "llm"))

    def test_non_decision_statuses_are_counted_separately(self):
        expected = {"a": "ALLOW"}
        attempts = [self.attempt("a", "jev", None, "provider_timeout"),
                    self.attempt("a", "llm", None, "malformed_output")]
        metrics = calculate_paired_metrics(["a"], expected, attempts, ("jev", "llm"))
        self.assertEqual(metrics["pairs_with_both_valid_actions"], 0)
        self.assertEqual(metrics["by_condition"]["jev"]["provider_or_parsing_failures"], 1)
        self.assertEqual(metrics["by_condition"]["llm"]["status_counts"], {"malformed_output": 1})

    def test_one_condition_failure_excludes_only_its_pair_from_action_denominator(self):
        expected = {"a": "ESCALATE", "b": "DENY", "c": "ALLOW"}
        attempts = [
            self.attempt("a", "jev", "ESCALATE"),
            self.attempt("a", "llm", None, "provider_timeout"),
            self.attempt("b", "jev", None, "runner_error"),
            self.attempt("b", "llm", None, "abstained"),
            self.attempt("c", "jev", "ALLOW"),
            self.attempt("c", "llm", "ALLOW"),
        ]
        metrics = calculate_paired_metrics(expected.keys(), expected, attempts, ("jev", "llm"))
        self.assertEqual(metrics["both_valid_action_denominator"], 1)
        self.assertEqual(metrics["pairs_with_one_or_more_non_decision_status"], 2)
        self.assertEqual(metrics["by_condition"]["jev"]["status_counts"],
                         {"completed": 2, "runner_error": 1})

    def test_invalid_completed_action_is_rejected(self):
        attempts = [self.attempt("a", "jev", "ROUTE"), self.attempt("a", "llm", "ALLOW")]
        with self.assertRaisesRegex(ValueError, "valid exactly for completed"):
            calculate_paired_metrics(["a"], {"a": "ALLOW"}, attempts, ("jev", "llm"))


class PairedRunnerTests(unittest.TestCase):
    def config(self, split="development"):
        raw = json.loads((ROOT / "experiments/configs/m2-mock-development.json").read_text(encoding="utf-8"))
        raw["split"] = split
        return ExperimentConfig.from_dict(raw)

    def comparison_config(self, split="development"):
        return PairedComparisonConfig("test-pair", "failure-lab-synthetic-v1", split)

    def test_mock_comparison_writes_versioned_paired_artifacts_without_truth_in_attempts(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = PairedComparisonRunner(
                DatasetStore(ROOT / "experiments/datasets"), Path(temp) / "comparisons", project_root=ROOT,
            )
            with patch("jev_control_plane.jev.TypeSafeJevAdapter._new_client",
                       side_effect=AssertionError("live Jev client must not be created")):
                result = runner.run(self.config(), self.comparison_config(), run_id="pair-test")
            run_dir = Path(result["run_dir"])
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            attempts = [json.loads(line) for line in (run_dir / "attempts.jsonl").read_text().splitlines()]
            pairs = [json.loads(line) for line in (run_dir / "pairs.jsonl").read_text().splitlines()]
            self.assertEqual(manifest["schema_version"], "1.0")
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["execution_status"], "all_attempts_returned_actions")
            self.assertEqual(manifest["purpose"], "synthetic_development_plumbing")
            self.assertFalse(manifest["configuration"]["policy_level_comparison_enabled"])
            self.assertEqual(len(attempts), 16)
            self.assertEqual(len(pairs), 8)
            self.assertTrue(all("expected_action" not in row and "ground_truth" not in row for row in attempts))
            self.assertTrue(all("expected_action" in row and "ground_truth" in row for row in pairs))
            self.assertTrue(all(row["condition_id"] in {"jev_mock", "llm_judge_mock"} for row in attempts))
            self.assertEqual(summary["cases_total"], 8)
            self.assertEqual(summary["attempts_total"], 16)
            self.assertFalse(summary["policy_level_comparison_enabled"])
            output_path = Path(temp) / "stdout.json"
            output_path.write_text(json.dumps(result), encoding="utf-8")
            self.assertEqual(validate_artifacts(output_path, ROOT), {"cases": 8, "attempts": 16, "pairs": 8})

    def test_artifact_validator_rejects_summary_pair_metric_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = PairedComparisonRunner(
                DatasetStore(ROOT / "experiments/datasets"), Path(temp) / "comparisons", project_root=ROOT,
            )
            result = runner.run(self.config(), self.comparison_config(), run_id="tampered-summary")
            run_dir = Path(result["run_dir"])
            summary_path = run_dir / "summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["paired_outcomes"]["action_disagreement"]["count"] += 1
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            output_path = Path(temp) / "stdout.json"
            output_path.write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not reconcile"):
                validate_artifacts(output_path, ROOT)

    def test_failed_artifact_finalization_does_not_mark_manifest_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = PairedComparisonRunner(
                DatasetStore(ROOT / "experiments/datasets"), Path(temp) / "comparisons", project_root=ROOT,
            )
            with patch("jev_control_plane.failure_lab.comparison.calculate_paired_metrics",
                       side_effect=RuntimeError("forced finalization failure")):
                with self.assertRaisesRegex(RuntimeError, "forced finalization failure"):
                    runner.run(self.config(), self.comparison_config(), run_id="interrupted-run")
            manifest_path = Path(temp) / "comparisons" / "runs" / "interrupted-run" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "running")

    def test_holdout_and_validation_are_rejected_before_dataset_access(self):
        class NeverReadDataset:
            def load_split(self, *_args, **_kwargs):
                raise AssertionError("non-Development split must be rejected before data access")

        runner = PairedComparisonRunner(NeverReadDataset(), "unused")
        with tempfile.TemporaryDirectory() as temp:
            runner.output_root = Path(temp)
            with self.assertRaisesRegex(ValueError, "Development-only"):
                runner.run(self.config("holdout"), self.comparison_config("holdout"))
            with self.assertRaisesRegex(ValueError, "Development-only"):
                PairedComparisonConfig("bad", "failure-lab-synthetic-v1", "validation")

    def test_unexpected_condition_exception_is_retained_as_runner_error(self):
        class BrokenJudge:
            condition_id = "llm_judge_mock"

            def evaluate(self, _request):
                raise RuntimeError("fixture implementation failure")

        with tempfile.TemporaryDirectory() as temp:
            result = PairedComparisonRunner(
                DatasetStore(ROOT / "experiments/datasets"), Path(temp) / "comparisons", project_root=ROOT,
            ).run(self.config(), self.comparison_config(), BrokenJudge(), "error-run")
            run_dir = Path(result["run_dir"])
            attempts = [json.loads(line) for line in (run_dir / "attempts.jsonl").read_text().splitlines()]
            failed = [row for row in attempts if row["condition_id"] == "llm_judge_mock"]
            self.assertEqual(len(failed), 8)
            self.assertTrue(all(row["status"] == "runner_error" for row in failed))
            self.assertTrue(all(row["error_category"] == "RuntimeError" for row in failed))
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["execution_status"], "contains_non_decision_attempts")


if __name__ == "__main__":
    unittest.main()
