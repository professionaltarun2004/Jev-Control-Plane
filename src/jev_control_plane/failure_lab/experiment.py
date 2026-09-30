"""Experiment configuration and irreversible LOCK snapshot.

The digest intentionally covers dataset identity, Jev model, views, policy, and
execution mode while leaving the selected data split out. A Validation config
can therefore be replayed on Holdout only when every decision-affecting setting
matches the saved lock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
from typing import Any, Mapping

from ..domain import ControlAction, DecisionView, Primitive
from ..policy import PolicyConfig
from ..records import json_safe
from .dataset import ALL_DATASET_SPLITS, DatasetSplit, HoldoutReadPermit, _issue_holdout_read_permit


class ExecutionMode(StrEnum):
    JEV_LIVE = "jev_live"
    MOCK = "mock"


@dataclass(frozen=True)
class ValidationCriteria:
    """Predeclared pilot interpretation cutoffs; never trained from run outcomes."""

    minimum_final_action_accuracy: float = 0.80
    minimum_correct_autonomous_coverage: float = 0.50
    minimum_correct_escalation_rate: float = 0.80
    maximum_unnecessary_escalation_rate: float = 0.20
    require_zero_false_allow: bool = True
    require_zero_false_deny: bool = True

    def __post_init__(self) -> None:
        for field_name in ("minimum_final_action_accuracy", "minimum_correct_autonomous_coverage",
                           "minimum_correct_escalation_rate", "maximum_unnecessary_escalation_rate"):
            value = getattr(self, field_name)
            if not 0 <= value <= 1:
                raise ValueError(f"{field_name} must be between 0 and 1")


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    dataset_id: str
    split: str
    views: tuple[DecisionView, ...]
    policy: PolicyConfig
    jev_model: str = "jev-latest"
    execution_mode: ExecutionMode = ExecutionMode.JEV_LIVE
    condition_id: str | None = None
    matrix_sha256: str | None = None
    validation_criteria: ValidationCriteria | None = None

    def __post_init__(self) -> None:
        if not self.experiment_id.strip() or not self.dataset_id.strip():
            raise ValueError("experiment_id and dataset_id must not be empty")
        if str(self.split) not in ALL_DATASET_SPLITS:
            raise ValueError(f"experiment split must be one of {ALL_DATASET_SPLITS}")
        if not self.jev_model.strip():
            raise ValueError("jev_model must not be empty")
        if not self.views:
            raise ValueError("experiment requires at least one Jev view")
        ids = [view.view_id for view in self.views]
        if len(ids) != len(set(ids)):
            raise ValueError("experiment view IDs must be unique")
        if self.condition_id is not None and not self.condition_id.strip():
            raise ValueError("condition_id must not be empty")
        if self.matrix_sha256 is not None and len(self.matrix_sha256) != 64:
            raise ValueError("matrix_sha256 must be a SHA-256 hex digest")

    def decision_config(self) -> dict[str, Any]:
        return json_safe({
            "dataset_id": self.dataset_id,
            "jev_model": self.jev_model,
            "execution_mode": self.execution_mode,
            "views": self.views,
            "policy": self.policy,
            "condition_id": self.condition_id,
            "matrix_sha256": self.matrix_sha256,
            "validation_criteria": self.validation_criteria,
        })

    def decision_config_digest(self) -> str:
        canonical = json.dumps(self.decision_config(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "dataset_id": self.dataset_id,
            "split": self.split,
            **self.decision_config(),
            "decision_config_sha256": self.decision_config_digest(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExperimentConfig":
        views = tuple(
            DecisionView(
                view_id=item["view_id"],
                primitive=Primitive(item["primitive"]),
                instructions=item["instructions"],
                criteria=item.get("criteria"),
                action_map={key: ControlAction(action) for key, action in item.get("action_map", {}).items()},
            )
            for item in value["views"]
        )
        return cls(
            experiment_id=value["experiment_id"],
            dataset_id=value["dataset_id"],
            split=value["split"],
            views=views,
            policy=PolicyConfig(**value["policy"]),
            jev_model=value.get("jev_model", "jev-latest"),
            execution_mode=ExecutionMode(value.get("execution_mode", "jev_live")),
            condition_id=value.get("condition_id"),
            matrix_sha256=value.get("matrix_sha256"),
            validation_criteria=ValidationCriteria(**value["validation_criteria"]) if value.get("validation_criteria") else None,
        )


@dataclass(frozen=True)
class ExperimentMatrix:
    """One predeclared A/B condition matrix sharing cases, prompts, and policy."""

    matrix_id: str
    dataset_id: str
    split: str
    jev_model: str
    execution_mode: ExecutionMode
    policy: PolicyConfig
    validation_criteria: ValidationCriteria
    view_definitions: Mapping[str, DecisionView]
    conditions: Mapping[str, tuple[str, ...]]
    matrix_sha256: str

    REQUIRED_CONDITIONS = {
        "A1": ("noul",), "A2": ("choice",), "A3": ("score",),
        "B1": ("choice",), "B2": ("choice", "noul"), "B3": ("choice", "noul", "score"),
    }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExperimentMatrix":
        required = {"matrix_id", "dataset_id", "split", "jev_model", "execution_mode", "policy",
                    "validation_criteria", "view_definitions", "conditions"}
        if set(value) != required:
            raise ValueError(f"matrix fields must be exactly {sorted(required)}")
        views = {}
        for item in value["view_definitions"]:
            view = DecisionView(
                item["view_id"], Primitive(item["primitive"]), item["instructions"],
                item.get("criteria"),
                {key: ControlAction(action) for key, action in item.get("action_map", {}).items()},
            )
            if view.view_id in views:
                raise ValueError(f"duplicate view definition: {view.view_id}")
            views[view.view_id] = view
        conditions = {str(key): tuple(ids) for key, ids in value["conditions"].items()}
        if conditions != cls.REQUIRED_CONDITIONS:
            raise ValueError("matrix must contain the predeclared A1-A3 and B1-B3 conditions")
        for condition_id, view_ids in conditions.items():
            if not set(view_ids).issubset(views):
                raise ValueError(f"condition {condition_id} references an undefined view")
        expected_primitives = {"noul": Primitive.NOUL, "choice": Primitive.CHOICE, "score": Primitive.SCORE}
        for condition_id, view_ids in conditions.items():
            for view_id in view_ids:
                if views[view_id].primitive is not expected_primitives[view_id]:
                    raise ValueError(f"condition {condition_id} uses an invalid primitive for {view_id}")
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return cls(
            str(value["matrix_id"]), str(value["dataset_id"]), str(value["split"]),
            str(value["jev_model"]), ExecutionMode(value["execution_mode"]),
            PolicyConfig(**value["policy"]), ValidationCriteria(**value["validation_criteria"]),
            views, conditions, hashlib.sha256(canonical.encode()).hexdigest(),
        )

    def config_for(self, condition_id: str) -> ExperimentConfig:
        if condition_id not in self.conditions:
            raise ValueError(f"unknown experiment condition: {condition_id}")
        return ExperimentConfig(
            experiment_id=f"{self.matrix_id}-{condition_id}", dataset_id=self.dataset_id,
            split=self.split, views=tuple(self.view_definitions[key] for key in self.conditions[condition_id]),
            policy=self.policy, jev_model=self.jev_model, execution_mode=self.execution_mode,
            condition_id=condition_id, matrix_sha256=self.matrix_sha256,
            validation_criteria=self.validation_criteria,
        )


@dataclass(frozen=True)
class ExperimentLock:
    lock_id: str
    dataset_id: str
    source_validation_run_id: str
    config_sha256: str
    frozen_config: Mapping[str, Any]
    validation_dataset_sha256: str
    validation_annotation_sha256: str
    validation_run_sha256: str
    holdout_dataset_sha256: str
    holdout_annotation_sha256: str
    reproducibility: Mapping[str, Any]
    created_at: str
    lock_sha256: str

    @classmethod
    def from_validation(
        cls,
        config: ExperimentConfig,
        lock_id: str,
        validation_run_id: str,
        snapshot: Mapping[str, str],
        reproducibility: Mapping[str, Any],
        validation_run_sha256: str,
    ) -> "ExperimentLock":
        if config.split != DatasetSplit.VALIDATION:
            raise ValueError("LOCK can only freeze a Validation configuration")
        if not lock_id.strip():
            raise ValueError("lock_id must not be empty")
        if not validation_run_id.strip():
            raise ValueError("LOCK requires a completed Validation run ID")
        body = {
            "lock_id": lock_id,
            "dataset_id": config.dataset_id,
            "source_validation_run_id": validation_run_id,
            "config_sha256": config.decision_config_digest(),
            "frozen_config": config.decision_config(),
            "validation_run_sha256": validation_run_sha256,
            **dict(snapshot),
            "reproducibility": dict(reproducibility),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        lock_digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        return cls(**body, lock_sha256=lock_digest)

    def verify(
        self,
        config: ExperimentConfig,
        reproducibility: Mapping[str, Any],
        validation_dataset_sha256: str,
        validation_annotation_sha256: str,
        validation_run_sha256: str,
    ) -> HoldoutReadPermit:
        if config.split != DatasetSplit.HOLDOUT:
            raise ValueError("a configuration lock is only checked for Holdout runs")
        body = self._body()
        frozen_digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if frozen_digest != self.lock_sha256:
            raise ValueError("saved lock contents do not match their integrity digest")
        config_digest = hashlib.sha256(json.dumps(self.frozen_config, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if config_digest != self.config_sha256:
            raise ValueError("frozen configuration does not match its digest")
        if config.dataset_id != self.dataset_id or config.decision_config_digest() != self.config_sha256:
            raise ValueError("Holdout configuration does not match the frozen Validation configuration")
        if validation_dataset_sha256 != self.validation_dataset_sha256:
            raise ValueError("Validation dataset changed after LOCK")
        if validation_annotation_sha256 != self.validation_annotation_sha256:
            raise ValueError("Validation annotations changed after LOCK")
        if validation_run_sha256 != self.validation_run_sha256:
            raise ValueError("Validation run artifacts changed after LOCK")
        for key in ("python", "typesafe_sdk", "git_revision", "code_tree_sha256", "protocol_sha256", "ground_truth_rules_sha256"):
            if reproducibility.get(key) != self.reproducibility.get(key):
                raise ValueError(f"Holdout runtime/method metadata differs from LOCK: {key}")
        return _issue_holdout_read_permit(self.lock_id, self.dataset_id, self.config_sha256)

    def _body(self) -> dict[str, Any]:
        return {
            "lock_id": self.lock_id,
            "dataset_id": self.dataset_id,
            "source_validation_run_id": self.source_validation_run_id,
            "config_sha256": self.config_sha256,
            "frozen_config": dict(self.frozen_config),
            "validation_dataset_sha256": self.validation_dataset_sha256,
            "validation_annotation_sha256": self.validation_annotation_sha256,
            "validation_run_sha256": self.validation_run_sha256,
            "holdout_dataset_sha256": self.holdout_dataset_sha256,
            "holdout_annotation_sha256": self.holdout_annotation_sha256,
            "reproducibility": dict(self.reproducibility),
            "created_at": self.created_at,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._body(), "lock_sha256": self.lock_sha256}
