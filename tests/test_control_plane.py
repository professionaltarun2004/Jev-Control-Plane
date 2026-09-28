from __future__ import annotations

import json
import tempfile
import types
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_control_plane import (
    AgentState,
    ControlAction,
    ControlPlane,
    DecisionRequest,
    DecisionView,
    DeterministicPolicy,
    JevResult,
    PolicyConfig,
    Primitive,
    TransparentEvidenceAggregator,
    TypeSafeJevAdapter,
)
from jev_control_plane.records import JsonlDecisionLogger


def view(view_id: str, primitive: Primitive = Primitive.CHOICE, mapping=None) -> DecisionView:
    return DecisionView(
        view_id=view_id,
        primitive=primitive,
        instructions=f"Evaluate the {view_id} view for the same action.",
        criteria={"allow": None, "deny": None} if primitive is Primitive.CHOICE else None,
        action_map=(mapping if mapping is not None else {"allow": ControlAction.ALLOW, "deny": ControlAction.DENY}),
    )


def request(views=None) -> DecisionRequest:
    return DecisionRequest(
        agent_state=AgentState("Read the report", "send_report", previous_action="draft_report"),
        question="Should the agent send the report?",
        views=tuple(views or (view("safety"), view("intent"))),
        metadata={"task_id": "task-1", "framework": "custom"},
        decision_id="decision-1",
    )


def result(view_id: str, answer: str, confidence: float | None = 0.9) -> JevResult:
    return JevResult(
        view_id=view_id, primitive=Primitive.CHOICE, answer=answer,
        probabilities={"allow": 0.8 if answer == "allow" else 0.1,
                       "deny": 0.1 if answer == "allow" else 0.8},
        confidence=confidence, model="jev-test", latency_ms=12.5,
        raw_answer={"type": "choice", "choice": answer,
                    "probabilities": {"allow": 0.8, "deny": 0.2}, "confidence": confidence},
        request_id="req-1", usage={"input_tokens": 20, "output_tokens": 3},
    )


class FakeAdapter:
    def __init__(self, results):
        self.results = results
        self.seen_request = None

    def evaluate(self, req):
        self.seen_request = req
        return self.results


class DomainTests(unittest.TestCase):
    def test_request_validation(self):
        with self.assertRaises(ValueError):
            AgentState(" ", "send")
        with self.assertRaises(ValueError):
            DecisionRequest(AgentState("request", "send"), " ", (view("v"),))
        with self.assertRaises(ValueError):
            DecisionRequest(AgentState("request", "send"), "question", ())
        with self.assertRaises(ValueError):
            DecisionRequest(AgentState("request", "send"), "question", (view("v"), view("v")))

    def test_jev_state_excludes_metadata_and_contains_decision_context(self):
        jev_state = request().to_jev_state()
        self.assertEqual(jev_state["decision_question"], "Should the agent send the report?")
        self.assertNotIn("task_id", jev_state)
        self.assertNotIn("framework", jev_state)


class AggregationAndPolicyTests(unittest.TestCase):
    def test_agreeing_views_are_preserved_and_allow(self):
        req = request()
        evidence = TransparentEvidenceAggregator().aggregate(req, (result("safety", "allow"), result("intent", "allow")))
        self.assertTrue(evidence.agreement)
        self.assertEqual(len(evidence.results), 2)
        policy = DeterministicPolicy(PolicyConfig(minimum_confidence=0.7)).decide(evidence)
        self.assertEqual(policy.action, ControlAction.ALLOW)

    def test_disagreement_remains_visible_and_escalates(self):
        req = request()
        evidence = TransparentEvidenceAggregator().aggregate(req, (result("safety", "allow"), result("intent", "deny")))
        self.assertFalse(evidence.agreement)
        self.assertEqual(set(evidence.conflicts), {"safety", "intent"})
        self.assertEqual(len(evidence.results), 2)
        self.assertEqual(DeterministicPolicy().decide(evidence).action, ControlAction.ESCALATE)

    def test_all_control_actions_and_confidence_floor(self):
        req = request()
        aggregate = TransparentEvidenceAggregator()
        policy = DeterministicPolicy(PolicyConfig(minimum_confidence=0.7))
        deny = aggregate.aggregate(req, (result("safety", "deny"), result("intent", "deny")))
        self.assertEqual(policy.decide(deny).action, ControlAction.DENY)
        low = aggregate.aggregate(req, (result("safety", "allow", 0.2), result("intent", "allow")))
        self.assertEqual(policy.decide(low).action, ControlAction.ESCALATE)

    def test_unmapped_view_escalates(self):
        req = request((view("safety", mapping={}),))
        evidence = TransparentEvidenceAggregator().aggregate(req, (result("safety", "allow"),))
        self.assertIsNone(evidence.agreement)
        self.assertEqual(evidence.conflicts, ("safety",))
        self.assertEqual(DeterministicPolicy().decide(evidence).action, ControlAction.ESCALATE)

    def test_ambiguous_noul_probability_escalates_without_becoming_confidence(self):
        req = request((view("safety", Primitive.NOUL,
                            {"true": ControlAction.ALLOW, "false": ControlAction.DENY}),))
        noul = JevResult(
            view_id="safety", primitive=Primitive.NOUL, answer=True,
            probabilities={"true": 0.55, "false": 0.45}, confidence=None,
            model="jev-test", latency_ms=1.0, raw_answer={"noul": 0.55},
        )
        evidence = TransparentEvidenceAggregator().aggregate(req, (noul,))
        result_policy = DeterministicPolicy().decide(evidence)
        self.assertIsNone(evidence.results[0].confidence)
        self.assertEqual(result_policy.action, ControlAction.ESCALATE)
        self.assertIn("probability", result_policy.reason)

    def test_missing_noul_probability_and_missing_choice_confidence_escalate(self):
        req = request()
        aggregate = TransparentEvidenceAggregator()
        policy = DeterministicPolicy()
        missing_noul = JevResult("safety", Primitive.NOUL, True, None, None, "jev-test", 1.0, {"noul": 0.9})
        noul_req = request((view("safety", Primitive.NOUL,
                                 {"true": ControlAction.ALLOW, "false": ControlAction.DENY}),))
        evidence = aggregate.aggregate(noul_req, (missing_noul,))
        self.assertEqual(policy.decide(evidence).action, ControlAction.ESCALATE)
        no_confidence = aggregate.aggregate(req, (result("safety", "allow", None), result("intent", "allow", None)))
        self.assertEqual(policy.decide(no_confidence).action, ControlAction.ESCALATE)


class AdapterTests(unittest.TestCase):
    def test_official_adapter_normalizes_noul_and_preserves_raw_answer(self):
        class Question:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class Noul(Question):
            pass

        class Choice(Question):
            pass

        class Score(Question):
            pass

        response = types.SimpleNamespace(
            nouls={"safe": types.SimpleNamespace(noul=0.82, model_dump=lambda **_: {"type": "noul", "noul": 0.82})},
            choices={}, scores={}, model="jev-latest", request_id="req-live-shape",
            usage=types.SimpleNamespace(model_dump=lambda **_: {"input_tokens": 7, "output_tokens": 1}),
        )

        class Client:
            def system_one(self, **kwargs):
                self.kwargs = kwargs
                return response

        sdk = types.SimpleNamespace(Noul=Noul, Choice=Choice, Score=Score)
        req = request((view("safe", Primitive.NOUL, {"true": ControlAction.ALLOW, "false": ControlAction.DENY}),))
        client = Client()
        with patch.dict("sys.modules", {"typesafe_sdk": sdk}):
            normalized = TypeSafeJevAdapter(client=client).evaluate(req)[0]
        self.assertTrue(normalized.answer)
        self.assertAlmostEqual(normalized.probabilities["true"], 0.82)
        self.assertAlmostEqual(normalized.probabilities["false"], 0.18)
        self.assertIsNone(normalized.confidence)
        self.assertEqual(normalized.raw_answer, {"type": "noul", "noul": 0.82})
        self.assertEqual(normalized.model, "jev-latest")
        self.assertEqual(normalized.request_id, "req-live-shape")
        self.assertEqual(client.kwargs["state"]["decision_question"], req.question)
        self.assertNotIn("task_id", client.kwargs["state"])
        self.assertEqual(tuple(client.kwargs["questions"]), ("safe",))

    def test_installed_official_sdk_question_and_response_models(self):
        try:
            from typesafe_sdk import SystemOneResponse
        except ImportError:
            self.skipTest("official SDK is not installed in this Python environment")

        response = SystemOneResponse(
            model="jev-latest",
            answers={
                "safe": {"type": "noul", "noul": 0.91},
                "choice": {"type": "choice", "choice": "allow", "confidence": 0.88,
                           "probabilities": {"allow": 0.9, "deny": 0.1}},
                "risk": {"type": "score", "score": 0.2, "confidence": 0.86,
                         "legend": {0: "low", 1: "high"},
                         "probabilities": {0: 0.8, 1: 0.2}},
            },
            usage={"input_tokens": 30, "output_tokens": 9},
        )

        class Client:
            def system_one(self, **kwargs):
                self.kwargs = kwargs
                return response

        views = (
            view("safe", Primitive.NOUL, {"true": ControlAction.ALLOW, "false": ControlAction.DENY}),
            view("choice"),
            DecisionView("risk", Primitive.SCORE, "Rate the risk", ("low", "high")),
        )
        req = request(views)
        client = Client()
        normalized = TypeSafeJevAdapter(client=client).evaluate(req)
        self.assertEqual([item.answer for item in normalized], [True, "allow", 0.2])
        self.assertIsNone(normalized[0].confidence)
        self.assertEqual(normalized[1].confidence, 0.88)
        self.assertEqual(normalized[1].probabilities, {"allow": 0.9, "deny": 0.1})
        self.assertEqual(normalized[2].probabilities, {0: 0.8, 1: 0.2})
        self.assertEqual(client.kwargs["questions"]["safe"].type, "noul")
        self.assertEqual(client.kwargs["questions"]["choice"].type, "choice")
        self.assertEqual(client.kwargs["questions"]["risk"].type, "score")


class EndToEndTests(unittest.TestCase):
    def test_raw_decision_record_and_jsonl_creation(self):
        fake = FakeAdapter((result("safety", "allow"), result("intent", "allow")))
        with tempfile.TemporaryDirectory() as temp:
            log_path = Path(temp) / "logs" / "decisions.jsonl"
            plane = ControlPlane(fake, TransparentEvidenceAggregator(), DeterministicPolicy(), JsonlDecisionLogger(log_path))
            record = plane.evaluate(request())
            self.assertEqual(record.decision_id, "decision-1")
            self.assertEqual(record.evidence["results"][0]["raw_answer"]["choice"], "allow")
            self.assertEqual(record.policy["action"], "ALLOW")
            self.assertEqual(len(record.request["input_fingerprint_sha256"]), 64)
            self.assertNotIn("Read the report", json.dumps(record.request))
            loaded = json.loads(log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(loaded["evidence"]["results"][1]["raw_answer"]["choice"], "allow")
            self.assertEqual(fake.seen_request.to_jev_state()["current_action"], "send_report")


if __name__ == "__main__":
    unittest.main()
