"""Paired, offline comparison plumbing for independent decision procedures.

This module runs the existing Jev mock control path beside a deterministic
LLM-shaped response fixture. It sits beside (rather than inside) the Jev
runtime so provider-native evidence stays distinct. Start with
``run_mock_comparison.py`` and the paired-metrics tests; this is plumbing, not
a provider-quality benchmark.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Protocol
from uuid import uuid4

from ..aggregator import TransparentEvidenceAggregator
from ..domain import AgentState, ControlAction, DecisionRequest, DecisionView
from ..jev import JevAdapter
from ..policy import DeterministicPolicy, PolicyConfig
from ..records import json_safe
from ..runtime import ControlPlane
from .artifacts import ExperimentArtifactStore
from .dataset import DatasetSplit, DatasetStore
from .experiment import ExecutionMode, ExperimentConfig
from .metrics import calculate_paired_metrics
from .mock import DeterministicMockJevAdapter


COMPARISON_SCHEMA_VERSION = "1.0"
LLM_RESPONSE_SCHEMA_VERSION = "1.0"


class AttemptStatus(StrEnum):
    COMPLETED = "completed"
    ABSTAINED = "abstained"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_FAILURE = "provider_failure"
    MALFORMED_OUTPUT = "malformed_output"
    SCHEMA_INVALID_ACTION = "schema_invalid_action"
    RUNNER_ERROR = "runner_error"


@dataclass(frozen=True)
class DecisionInput:
    """The label-free projection passed to a condition; annotations stay out."""

    case_id: str
    state: AgentState
    decision: str

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.decision.strip():
            raise ValueError("case_id and decision must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return json_safe({"case_id": self.case_id, "state": self.state, "decision": self.decision})


def _copy_provider_input(request: DecisionInput) -> DecisionInput:
    """Give each condition a separate state copy, including nested tool data."""
    return DecisionInput(request.case_id, deepcopy(request.state), request.decision)


@dataclass(frozen=True)
class PairedComparisonConfig:
    """Versioned controls for the first offline paired plumbing run."""

    experiment_id: str
    dataset_id: str
    split: str
    jev_config_file: str = "m2-mock-development.json"
    schema_version: str = COMPARISON_SCHEMA_VERSION
    llm_condition_id: str = "llm_judge_mock"
    llm_response_schema_version: str = LLM_RESPONSE_SCHEMA_VERSION
    policy_level_comparison_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.experiment_id.strip() or not self.dataset_id.strip():
            raise ValueError("experiment_id and dataset_id must not be empty")
        if self.split != DatasetSplit.DEVELOPMENT:
            raise ValueError("mock comparison configuration is Development-only")
        if Path(self.jev_config_file).name != self.jev_config_file:
            raise ValueError("jev_config_file must name a file in experiments/configs")
        if self.schema_version != COMPARISON_SCHEMA_VERSION:
            raise ValueError(f"unsupported comparison schema version: {self.schema_version}")
        if self.llm_response_schema_version != LLM_RESPONSE_SCHEMA_VERSION:
            raise ValueError(f"unsupported LLM response schema version: {self.llm_response_schema_version}")
        if self.policy_level_comparison_enabled:
            raise ValueError("policy-level comparison is disabled until M3A semantics are resolved")
        if not self.llm_condition_id.strip() or self.llm_condition_id == "jev_mock":
            raise ValueError("LLM mock condition ID must be non-empty and distinct from Jev")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PairedComparisonConfig":
        allowed = {"experiment_id", "dataset_id", "split", "jev_config_file", "schema_version", "llm_condition_id",
                   "llm_response_schema_version", "policy_level_comparison_enabled"}
        if set(value) - allowed or not {"experiment_id", "dataset_id", "split"}.issubset(value):
            raise ValueError("comparison config has missing or unknown fields")
        return cls(**value)

    def to_dict(self) -> dict[str, Any]:
        return json_safe(self)


@dataclass(frozen=True)
class ProviderAttempt:
    """One provider-native attempt plus its optional common action proposal.

    ``native_output`` preserves provider-specific semantics. ``policy_result``
    is present only when a deterministic policy actually ran; this prevents a
    direct LLM action from masquerading as a Jev policy result.
    """

    provider_id: str
    provider_version: str
    status: AttemptStatus
    latency_ms: float
    native_output: Any = None
    normalized_action: ControlAction | None = None
    error_category: str | None = None
    policy_result: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.provider_id.strip() or not self.provider_version.strip():
            raise ValueError("provider identity and version are required")
        if not isfinite(self.latency_ms) or self.latency_ms < 0:
            raise ValueError("latency_ms must be finite and non-negative")
        if self.status is AttemptStatus.COMPLETED and self.normalized_action is None:
            raise ValueError("completed attempts require a normalized action")
        if self.status is not AttemptStatus.COMPLETED and self.normalized_action is not None:
            raise ValueError("non-completed attempts cannot claim a normalized action")
        if self.status is AttemptStatus.COMPLETED and self.error_category is not None:
            raise ValueError("completed attempts cannot have an error category")


class DecisionProvider(Protocol):
    """Small Failure Lab contract; this does not replace the Jev runtime API."""

    condition_id: str

    def evaluate(self, request: DecisionInput) -> ProviderAttempt: ...


@dataclass(frozen=True)
class MockFailure:
    """A deterministic failure fixture used only to verify error retention."""

    status: AttemptStatus

    def __post_init__(self) -> None:
        if self.status not in (AttemptStatus.ABSTAINED, AttemptStatus.PROVIDER_TIMEOUT,
                               AttemptStatus.PROVIDER_FAILURE):
            raise ValueError("mock failure fixture must be abstention, timeout, or provider failure")


class JevMockCondition:
    """Run the existing Jev-shaped mock through its real aggregator and policy."""

    condition_id = "jev_mock"

    def __init__(self, views: tuple[DecisionView, ...], policy: PolicyConfig,
                 adapter: JevAdapter | None = None) -> None:
        self.views = views
        self.policy_config = policy
        self.adapter = adapter or DeterministicMockJevAdapter()

    def evaluate(self, request: DecisionInput) -> ProviderAttempt:
        started = perf_counter()
        decision_request = DecisionRequest(
            agent_state=request.state,
            question=request.decision,
            views=self.views,
            metadata={"case_id": request.case_id, "condition_id": self.condition_id},
            decision_id=request.case_id,
        )
        record = ControlPlane(
            self.adapter,
            TransparentEvidenceAggregator(),
            DeterministicPolicy(self.policy_config),
        ).evaluate(decision_request)
        policy_result = json_safe(record.policy)
        action = ControlAction(policy_result["action"])
        return ProviderAttempt(
            provider_id="jev-shaped-deterministic-mock",
            provider_version="1",
            status=AttemptStatus.COMPLETED,
            latency_ms=(perf_counter() - started) * 1000,
            native_output=json_safe(record.evidence),
            normalized_action=action,
            policy_result=policy_result,
        )


class DeterministicMockJudge:
    """Return strict structured actions from deterministic, label-free fixtures.

    An optional case-ID fixture mapping makes parser/failure tests explicit.
    The default fixture hashes only the provider input and never receives truth.
    It is not a language model and its rationale is not evidence.
    """

    condition_id = "llm_judge_mock"
    _actions = (ControlAction.ALLOW, ControlAction.DENY, ControlAction.ESCALATE)

    def __init__(self, fixtures: Mapping[str, Any] | None = None,
                 condition_id: str = "llm_judge_mock") -> None:
        if not condition_id.strip() or condition_id == "jev_mock":
            raise ValueError("LLM mock condition ID must be non-empty and distinct from Jev")
        self.condition_id = condition_id
        self.fixtures = dict(fixtures or {})
        canonical = json.dumps(json_safe(self.fixtures), sort_keys=True, separators=(",", ":"))
        self.fixture_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def evaluate(self, request: DecisionInput) -> ProviderAttempt:
        started = perf_counter()
        fixture = self.fixtures.get(request.case_id)
        if isinstance(fixture, MockFailure):
            status = fixture.status
            error = {
                AttemptStatus.ABSTAINED: "provider_abstention",
                AttemptStatus.PROVIDER_TIMEOUT: "provider_timeout",
                AttemptStatus.PROVIDER_FAILURE: "provider_failure",
            }[status]
            return ProviderAttempt(
                self.condition_id, f"fixture-v1:{self.fixture_sha256[:12]}", status,
                (perf_counter() - started) * 1000,
                native_output={"fixture_status": status.value}, error_category=error,
            )
        if fixture is None:
            fixture = self._deterministic_response(request)
        return self._parse_fixture(fixture, started)

    def _deterministic_response(self, request: DecisionInput) -> dict[str, str]:
        seed = json.dumps(request.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(("m4-llm-judge-mock-v1:" + seed).encode("utf-8")).digest()
        action = self._actions[digest[0] % len(self._actions)]
        return {
            "action": action.value,
            "rationale": "Deterministic mock fixture; not generated by a language model.",
        }

    def _parse_fixture(self, fixture: Any, started: float) -> ProviderAttempt:
        raw = fixture
        if isinstance(fixture, str):
            try:
                fixture = json.loads(fixture)
            except (json.JSONDecodeError, TypeError):
                return self._invalid(AttemptStatus.MALFORMED_OUTPUT, "malformed_output", raw, started)
        if not isinstance(fixture, Mapping):
            return self._invalid(AttemptStatus.MALFORMED_OUTPUT, "malformed_output", raw, started)
        if set(fixture) - {"action", "rationale"} or not isinstance(fixture.get("rationale", ""), str):
            return self._invalid(AttemptStatus.MALFORMED_OUTPUT, "malformed_output", raw, started)
        try:
            action = ControlAction(fixture["action"])
        except (KeyError, ValueError, TypeError):
            return self._invalid(AttemptStatus.SCHEMA_INVALID_ACTION, "schema_invalid_action", raw, started)
        return ProviderAttempt(
            provider_id=self.condition_id,
            provider_version=f"fixture-v{LLM_RESPONSE_SCHEMA_VERSION}:{self.fixture_sha256[:12]}",
            status=AttemptStatus.COMPLETED,
            latency_ms=(perf_counter() - started) * 1000,
            native_output=json_safe(dict(fixture)),
            normalized_action=action,
        )

    def _invalid(self, status: AttemptStatus, error: str, raw: Any, started: float) -> ProviderAttempt:
        return ProviderAttempt(
            provider_id=self.condition_id,
            provider_version=f"fixture-v{LLM_RESPONSE_SCHEMA_VERSION}:{self.fixture_sha256[:12]}",
            status=status,
            latency_ms=(perf_counter() - started) * 1000,
            native_output=json_safe(raw) if isinstance(raw, (dict, list, str, int, float, bool, type(None))) else repr(type(raw).__name__),
            error_category=error,
        )


class PairedComparisonRunner:
    """Run two offline conditions on Development and write paired artifacts.

    This runner rejects Validation and Holdout before opening their dataset
    files. Expected outcomes remain evaluator-owned and are written only to
    ``pairs.jsonl`` after both providers have returned.
    """

    def __init__(self, datasets: DatasetStore, output_root: str | Path,
                 project_root: str | Path | None = None) -> None:
        self.datasets = datasets
        self.output_root = Path(output_root)
        self.artifacts = ExperimentArtifactStore(self.output_root, project_root=project_root)

    def run(self, jev_config: ExperimentConfig, comparison_config: PairedComparisonConfig,
            llm_condition: DecisionProvider | None = None, run_id: str | None = None) -> dict[str, Any]:
        if jev_config.dataset_id != comparison_config.dataset_id or jev_config.split != comparison_config.split:
            raise ValueError("Jev and comparison configs must identify the same dataset and split")
        if str(jev_config.split) != DatasetSplit.DEVELOPMENT:
            raise ValueError("mock paired comparison is Development-only; it cannot read Validation or Holdout")
        if jev_config.execution_mode is not ExecutionMode.MOCK:
            raise ValueError("paired plumbing requires the deterministic Jev mock mode")
        llm_condition = llm_condition or DeterministicMockJudge(condition_id=comparison_config.llm_condition_id)
        if llm_condition.condition_id != comparison_config.llm_condition_id:
            raise ValueError("LLM condition ID differs from the comparison configuration")
        if llm_condition.condition_id == JevMockCondition.condition_id:
            raise ValueError("comparison condition IDs must be distinct")
        conditions: tuple[DecisionProvider, ...] = (
            JevMockCondition(jev_config.views, jev_config.policy), llm_condition,
        )
        cases = self.datasets.load_split(DatasetSplit.DEVELOPMENT, dataset_id=jev_config.dataset_id)
        if not cases:
            raise ValueError("cannot compare an empty Development split")
        case_ids = [case.case_id for case in cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("comparison input contains duplicate case IDs")
        annotations = self.datasets.annotations_for(case_ids, DatasetSplit.DEVELOPMENT,
                                                    dataset_id=jev_config.dataset_id)
        case_digest = self.datasets.split_digest(DatasetSplit.DEVELOPMENT)
        annotation_digest = self.datasets.annotation_digest(DatasetSplit.DEVELOPMENT)
        run_id = run_id or f"{comparison_config.experiment_id}-{uuid4().hex[:12]}"
        run_dir = self.output_root / "runs" / self.artifacts._safe_id(run_id)
        run_dir.mkdir(parents=True, exist_ok=False)

        provider_config = {
            "comparison": comparison_config.to_dict(),
            "jev": {
                "condition_id": conditions[0].condition_id,
                "provider_id": "jev-shaped-deterministic-mock",
                "provider_version": "1",
                "experiment_config": jev_config.to_dict(),
            },
            "llm_mock": {
                "condition_id": conditions[1].condition_id,
                "provider_id": conditions[1].condition_id,
                "provider_version": "1",
                "fixture_sha256": getattr(conditions[1], "fixture_sha256", None),
                "fixture_algorithm": (
                    "sha256-label-free-input-v1" if isinstance(conditions[1], DeterministicMockJudge)
                    else "injected-provider-fixture"
                ),
                "response_schema_version": LLM_RESPONSE_SCHEMA_VERSION,
                "policy_applied": False,
            },
            "policy_level_comparison_enabled": False,
            "comparison_note": (
                "Synthetic Development plumbing only. Jev's legacy deterministic policy and the direct mock action "
                "are not policy-normalized or evidence-equivalent; no provider superiority claim is supported."
            ),
            "latency_scope": "local mock adapter overhead; not model or provider inference latency",
            "retry_policy": "no retries in offline mock conditions",
            "timeout_policy": "not applicable to deterministic local fixtures",
        }
        config_sha = self._digest(provider_config)
        metadata = self.artifacts.reproducibility_metadata()
        self._write_json(run_dir / "manifest.json", {
            "schema_version": COMPARISON_SCHEMA_VERSION,
            "run_id": run_id,
            "experiment_id": jev_config.experiment_id,
            "status": "running",
            "purpose": "synthetic_development_plumbing",
            "dataset_id": jev_config.dataset_id,
            "dataset_split": DatasetSplit.DEVELOPMENT,
            "case_set_sha256": case_digest,
            "annotation_sha256": annotation_digest,
            "configuration": provider_config,
            "configuration_sha256": config_sha,
            "software": metadata,
            "started_at": self._timestamp(),
            "note": "No live provider calls; no Validation or Holdout data read.",
        })
        attempts_path = run_dir / "attempts.jsonl"
        pairs_path = run_dir / "pairs.jsonl"
        attempts_path.touch(exist_ok=False)
        pairs_path.touch(exist_ok=False)
        attempts: list[dict[str, Any]] = []
        pairs: list[dict[str, Any]] = []
        started = perf_counter()
        for case in cases:
            pair_attempts: dict[str, dict[str, Any]] = {}
            for condition in conditions:
                try:
                    # Deep-copy nested state for each provider so one condition
                    # cannot mutate the input observed by the other.
                    request = _copy_provider_input(DecisionInput(case.case_id, case.state, case.decision))
                    attempt = condition.evaluate(request)
                    if not isinstance(attempt, ProviderAttempt):
                        raise TypeError("provider did not return ProviderAttempt")
                except Exception as exc:  # retain unexpected implementation errors as runner errors
                    attempt = ProviderAttempt(
                        provider_id=condition.condition_id,
                        provider_version="unknown",
                        status=AttemptStatus.RUNNER_ERROR,
                        latency_ms=0.0,
                        error_category=type(exc).__name__,
                    )
                row = self._attempt_row(run_id, case.case_id, condition.condition_id, attempt)
                attempts.append(row)
                self._append_jsonl(attempts_path, row)
                pair_attempts[condition.condition_id] = row
            annotation = annotations.get(case.case_id)
            pair_row = {
                "schema_version": COMPARISON_SCHEMA_VERSION,
                "run_id": run_id,
                "case_id": case.case_id,
                "case_family_id": annotation.case_family_id if annotation else None,
                "perturbation_family": annotation.family.value if annotation else None,
                "expected_action": case.expected_action.value,
                "ground_truth": {
                    "source": case.ground_truth.source.value,
                    "reference": case.ground_truth.reference,
                    "certainty": case.ground_truth.certainty.value,
                },
                "jev_condition_id": conditions[0].condition_id,
                "jev_status": pair_attempts[conditions[0].condition_id]["status"],
                "jev_action": pair_attempts[conditions[0].condition_id]["normalized_action"],
                "jev_correct": self._is_correct(pair_attempts[conditions[0].condition_id], case.expected_action.value),
                "llm_condition_id": conditions[1].condition_id,
                "llm_status": pair_attempts[conditions[1].condition_id]["status"],
                "llm_action": pair_attempts[conditions[1].condition_id]["normalized_action"],
                "llm_correct": self._is_correct(pair_attempts[conditions[1].condition_id], case.expected_action.value),
            }
            pairs.append(pair_row)
            self._append_jsonl(pairs_path, pair_row)

        metrics = calculate_paired_metrics(
            case_ids,
            {case.case_id: case.expected_action.value for case in cases},
            attempts,
            conditions=(c.condition_id for c in conditions),
        )
        metrics.update({
            "schema_version": COMPARISON_SCHEMA_VERSION,
            "run_id": run_id,
            "cases_total": len(cases),
            "attempts_total": len(attempts),
            "pairs_total": len(pairs),
            "elapsed_seconds": perf_counter() - started,
            "measurement_scope": "synthetic Development plumbing; not Jev or LLM performance",
            "policy_level_comparison_enabled": False,
            "provider_evidence_equivalence_claimed": False,
            "latency_scope": "local mock adapter overhead; not model or provider inference latency",
        })
        self._write_json(run_dir / "summary.json", metrics)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["status"] = "complete"
        manifest["finished_at"] = self._timestamp()
        self._write_json(run_dir / "manifest.json", manifest)
        return {"run_id": run_id, "run_dir": str(run_dir), "metrics": metrics}

    @staticmethod
    def _attempt_row(run_id: str, case_id: str, condition_id: str,
                     attempt: ProviderAttempt) -> dict[str, Any]:
        return {
            "schema_version": COMPARISON_SCHEMA_VERSION,
            "run_id": run_id,
            "case_id": case_id,
            "condition_id": condition_id,
            "provider_id": attempt.provider_id,
            "provider_version": attempt.provider_version,
            "status": attempt.status.value,
            "normalized_action": attempt.normalized_action.value if attempt.normalized_action else None,
            "error_category": attempt.error_category,
            "latency_ms": attempt.latency_ms,
            "native_output": json_safe(attempt.native_output),
            "policy_result": json_safe(attempt.policy_result) if attempt.policy_result is not None else None,
        }

    @staticmethod
    def _is_correct(attempt: Mapping[str, Any], expected: str) -> bool | None:
        if attempt["status"] != AttemptStatus.COMPLETED.value:
            return None
        return attempt["normalized_action"] == expected

    @staticmethod
    def _digest(value: Any) -> str:
        canonical = json.dumps(json_safe(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _timestamp() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.write_text(json.dumps(json_safe(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                        encoding="utf-8")

    @staticmethod
    def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(json_safe(dict(row)), ensure_ascii=False, allow_nan=False) + "\n")
