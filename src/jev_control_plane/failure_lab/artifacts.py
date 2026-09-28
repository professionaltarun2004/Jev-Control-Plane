"""Immutable configuration locks and append-only experiment artifacts.

Run directories are unique and never overwritten. The manifest is marked
``running`` before the first case so an interrupted experiment remains visible
with all case records written up to that point.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
from typing import Any, Mapping
from uuid import uuid4

from ..records import json_safe
from .experiment import ExperimentConfig, ExperimentLock


class ExperimentArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.runs_dir = self.root / "runs"
        self.locks_dir = self.root / "locks"

    def write_lock(self, config: ExperimentConfig, lock_id: str) -> ExperimentLock:
        lock = ExperimentLock.from_validation(config, lock_id)
        path = self.locks_dir / f"{self._safe_id(lock_id)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(lock.to_dict(), stream, indent=2)
            stream.write("\n")
        return lock

    def read_lock(self, lock_id: str) -> ExperimentLock:
        path = self.locks_dir / f"{self._safe_id(lock_id)}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        return ExperimentLock(**value)

    def begin_run(
        self,
        run_id: str,
        config: ExperimentConfig,
        dataset_digest: str,
        lock_id: str | None,
    ) -> Path:
        run_dir = self.runs_dir / self._safe_id(run_id)
        run_dir.mkdir(parents=True, exist_ok=False)
        manifest = {
            "run_id": run_id,
            "experiment_id": config.experiment_id,
            "method": "jev_control",
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "dataset_id": config.dataset_id,
            "dataset_split": config.split,
            "dataset_split_sha256": dataset_digest,
            "execution_mode": config.execution_mode.value,
            "jev_model": config.jev_model,
            "views": json_safe(config.views),
            "policy": json_safe(config.policy),
            "policy_version": config.policy.version,
            "decision_config_sha256": config.decision_config_digest(),
            "lock_id": lock_id,
            "software": {"python": platform.python_version(), "control_plane": "0.1.0"},
            "note": "mock mode outputs are synthetic and are not Jev performance",
        }
        self._write_json(run_dir / "manifest.json", manifest)
        (run_dir / "results.jsonl").touch(exist_ok=False)
        return run_dir

    def append_result(self, run_dir: Path, result: Mapping[str, Any]) -> None:
        with (run_dir / "results.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(json_safe(dict(result)), ensure_ascii=False, allow_nan=False) + "\n")

    def finish_run(self, run_dir: Path, status: str, metrics: Mapping[str, Any]) -> None:
        manifest_path = run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["status"] = status
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        self._write_json(manifest_path, manifest)
        self._write_json(run_dir / "summary.json", dict(metrics))

    @staticmethod
    def _safe_id(value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
            raise ValueError("run and lock IDs may contain letters, numbers, dot, underscore, and hyphen")
        return value

    @staticmethod
    def _write_json(path: Path, value: Mapping[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as stream:
            json.dump(json_safe(dict(value)), stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
