"""Experiment configuration and irreversible LOCK snapshot.

The digest intentionally covers dataset identity, Jev model, views, policy, and
execution mode while leaving the selected data split out. A Validation config
can therefore be replayed on Holdout only when every decision-affecting setting
matches the saved lock.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
from typing import Any, Mapping

from ..domain import ControlAction, DecisionView, Primitive
from ..policy import PolicyConfig
from ..records import json_safe
from .dataset import ALL_DATASET_SPLITS, DatasetSplit


class ExecutionMode(StrEnum):
    JEV_LIVE = "jev_live"
    MOCK = "mock"


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    dataset_id: str
    split: str
    views: tuple[DecisionView, ...]
    policy: PolicyConfig
    jev_model: str = "jev-latest"
    execution_mode: ExecutionMode = ExecutionMode.JEV_LIVE

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

    def decision_config(self) -> dict[str, Any]:
        return json_safe({
            "dataset_id": self.dataset_id,
            "jev_model": self.jev_model,
            "execution_mode": self.execution_mode,
            "views": self.views,
            "policy": self.policy,
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
        )


@dataclass(frozen=True)
class ExperimentLock:
    lock_id: str
    dataset_id: str
    source_experiment_id: str
    config_sha256: str
    frozen_config: Mapping[str, Any]
    created_at: str

    @classmethod
    def from_validation(cls, config: ExperimentConfig, lock_id: str) -> "ExperimentLock":
        if config.split != DatasetSplit.VALIDATION:
            raise ValueError("LOCK can only freeze a Validation configuration")
        if not lock_id.strip():
            raise ValueError("lock_id must not be empty")
        return cls(
            lock_id=lock_id,
            dataset_id=config.dataset_id,
            source_experiment_id=config.experiment_id,
            config_sha256=config.decision_config_digest(),
            frozen_config=config.decision_config(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def verify(self, config: ExperimentConfig) -> None:
        if config.split != DatasetSplit.HOLDOUT:
            raise ValueError("a configuration lock is only checked for Holdout runs")
        frozen_json = json.dumps(self.frozen_config, sort_keys=True, separators=(",", ":"), allow_nan=False)
        frozen_digest = hashlib.sha256(frozen_json.encode("utf-8")).hexdigest()
        if frozen_digest != self.config_sha256:
            raise ValueError("saved configuration lock digest does not match its frozen configuration")
        if config.dataset_id != self.dataset_id or config.decision_config_digest() != self.config_sha256:
            raise ValueError("Holdout configuration does not match the frozen Validation configuration")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)
