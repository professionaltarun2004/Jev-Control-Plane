"""Immutable configuration locks and append-only experiment artifacts.

Run directories are unique and never overwritten. The manifest is marked
``running`` before the first case so an interrupted experiment remains visible
with all case records written up to that point.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import subprocess
from typing import Any, Mapping

from ..records import json_safe
from .experiment import ExperimentConfig, ExperimentLock
from .dataset import DatasetSplit, DatasetStore


class ExperimentArtifactStore:
    def __init__(self, root: str | Path, project_root: str | Path | None = None) -> None:
        self.root = Path(root)
        self.runs_dir = self.root / "runs"
        self.locks_dir = self.root / "locks"
        self.project_root = Path(project_root) if project_root else Path(__file__).resolve().parents[3]

    def write_lock(
        self,
        config: ExperimentConfig,
        lock_id: str,
        validation_run_id: str,
        datasets: DatasetStore,
    ) -> ExperimentLock:
        """Freeze a completed Validation run and both split/annotation snapshots."""
        if config.split != DatasetSplit.VALIDATION:
            raise ValueError("LOCK can only be created from a Validation configuration")
        run_dir = self.runs_dir / self._safe_id(validation_run_id)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        if manifest.get("dataset_split") != DatasetSplit.VALIDATION or manifest.get("status") != "complete":
            raise ValueError("LOCK requires a complete, error-free Validation run")
        if manifest.get("decision_config_sha256") != config.decision_config_digest():
            raise ValueError("Validation run configuration does not match the requested LOCK config")
        if summary.get("run_errors", 0) != 0:
            raise ValueError("LOCK requires zero Validation runner errors")
        validation_dataset = datasets.split_digest(DatasetSplit.VALIDATION)
        validation_annotations = datasets.annotation_digest(DatasetSplit.VALIDATION)
        if manifest.get("dataset_split_sha256") != validation_dataset:
            raise ValueError("Validation dataset changed since its completed run")
        if manifest.get("annotation_sha256") != validation_annotations:
            raise ValueError("Validation annotations changed since their completed run")
        snapshot = datasets._lock_snapshot(config.dataset_id)
        if (snapshot["validation_dataset_sha256"] != validation_dataset or
                snapshot["validation_annotation_sha256"] != validation_annotations):
            raise ValueError("Validation snapshot changed while creating LOCK")
        software = self.reproducibility_metadata()
        validation_software = manifest.get("software", {})
        for key in ("python", "typesafe_sdk", "git_revision", "code_tree_sha256", "protocol_sha256", "ground_truth_rules_sha256"):
            if validation_software.get(key) != software.get(key):
                raise ValueError(f"Validation run {key} differs from current LOCK environment")
        lock = ExperimentLock.from_validation(config, lock_id, validation_run_id, snapshot, software)
        self.assert_holdout_unclaimed(lock)
        path = self.locks_dir / f"{self._safe_id(lock_id)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(lock.to_dict(), stream, indent=2)
            stream.write("\n")
        return lock

    def read_lock(self, lock_id: str) -> ExperimentLock:
        path = self.locks_dir / f"{self._safe_id(lock_id)}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        lock = ExperimentLock(**value)
        body_digest = hashlib.sha256(json.dumps(lock._body(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if body_digest != lock.lock_sha256:
            raise ValueError("saved lock contents do not match their integrity digest")
        return lock

    def claim_holdout(self, lock: ExperimentLock, run_id: str) -> Path:
        """Atomically claim one evaluation attempt for this Holdout snapshot."""
        claims = self.locks_dir / "holdout-claims"
        claims.mkdir(parents=True, exist_ok=True)
        claim_key = hashlib.sha256(
            f"{lock.holdout_dataset_sha256}:{lock.holdout_annotation_sha256}".encode()
        ).hexdigest()
        path = claims / f"{claim_key}.json"
        claim = {
            "dataset_id": lock.dataset_id,
            "holdout_dataset_sha256": lock.holdout_dataset_sha256,
            "holdout_annotation_sha256": lock.holdout_annotation_sha256,
            "lock_id": lock.lock_id,
            "config_sha256": lock.config_sha256,
            "run_id": run_id,
            "claimed_at": datetime.now(timezone.utc).isoformat(),
            "policy": "one attempt per exact Holdout case+annotation digest, even after interruption",
        }
        with path.open("x", encoding="utf-8") as stream:
            json.dump(claim, stream, indent=2)
            stream.write("\n")
        return path

    def assert_holdout_unclaimed(self, lock: ExperimentLock) -> None:
        """Reject a second attempt before opening Holdout case contents."""
        claim_key = hashlib.sha256(
            f"{lock.holdout_dataset_sha256}:{lock.holdout_annotation_sha256}".encode()
        ).hexdigest()
        path = self.locks_dir / "holdout-claims" / f"{claim_key}.json"
        if path.exists():
            raise ValueError("this exact Holdout content has already been claimed; preserve the prior attempt")

    def reproducibility_metadata(self) -> dict[str, Any]:
        """Capture local versions and content digests needed to explain a run."""
        try:
            sdk_version = importlib.metadata.version("typesafe-sdk")
        except importlib.metadata.PackageNotFoundError:
            sdk_version = None
        try:
            revision = subprocess.run(
                ["git", "-c", f"safe.directory={self.project_root.as_posix()}", "-C",
                 str(self.project_root), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            revision = None
        return {
            "python": platform.python_version(),
            "typesafe_sdk": sdk_version,
            "git_revision": revision,
            "code_tree_sha256": self._source_tree_digest(),
            "protocol_sha256": self._file_digest(self.project_root / "EXPERIMENT_PROTOCOL.md"),
            "ground_truth_rules_sha256": self._file_digest(
                self.project_root / "experiments" / "datasets" / "ground_truth_rules.md"
            ),
        }

    def begin_run(
        self,
        run_id: str,
        config: ExperimentConfig,
        dataset_digest: str,
        annotation_digest: str,
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
            "annotation_sha256": annotation_digest,
            "execution_mode": config.execution_mode.value,
            "jev_model": config.jev_model,
            "views": json_safe(config.views),
            "policy": json_safe(config.policy),
            "decision_config": config.decision_config(),
            "policy_version": config.policy.version,
            "decision_config_sha256": config.decision_config_digest(),
            "lock_id": lock_id,
            "software": {**self.reproducibility_metadata(), "control_plane": "0.1.0"},
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

    def _source_tree_digest(self) -> str:
        digest = hashlib.sha256()
        tracked_roots = (self.project_root / "src", self.project_root / "tests")
        files = [path for root in tracked_roots if root.exists() for path in root.rglob("*.py")]
        files.append(self.project_root / "pyproject.toml")
        for path in sorted((path for path in files if path.is_file()), key=lambda item: item.relative_to(self.project_root).as_posix()):
            relative = path.relative_to(self.project_root).as_posix().encode()
            digest.update(len(relative).to_bytes(4, "big"))
            digest.update(relative)
            payload = path.read_bytes()
            digest.update(len(payload).to_bytes(8, "big"))
            digest.update(payload)
        return digest.hexdigest()

    @staticmethod
    def _file_digest(path: Path) -> str | None:
        if not path.exists():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _write_json(path: Path, value: Mapping[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as stream:
            json.dump(json_safe(dict(value)), stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
