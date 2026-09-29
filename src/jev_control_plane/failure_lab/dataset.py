"""Split-scoped JSONL datasets with an explicit Holdout read capability.

Development and Validation operations never scan Holdout. Holdout reads and
its sidecar/digest require a permit issued only after artifact-lock checks.
This protects against accidental access, not deliberate file copying/editing.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from enum import StrEnum
from typing import Iterable

from .benchmark import BenchmarkCase, CaseAnnotation, PerturbationFamily


class DatasetSplit(StrEnum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    HOLDOUT = "holdout"


ALL_DATASET_SPLITS = tuple(split.value for split in DatasetSplit)
_PERMIT_ISSUER = object()


@dataclass(frozen=True, init=False)
class HoldoutReadPermit:
    """Accidental-use capability minted after a persisted lock is verified."""

    lock_id: str
    dataset_id: str
    config_sha256: str

    def __init__(self, lock_id: str, dataset_id: str, config_sha256: str, issuer: object = None) -> None:
        if issuer is not _PERMIT_ISSUER:
            raise TypeError("HoldoutReadPermit can only be issued by a verified experiment lock")
        object.__setattr__(self, "lock_id", lock_id)
        object.__setattr__(self, "dataset_id", dataset_id)
        object.__setattr__(self, "config_sha256", config_sha256)


def _issue_holdout_read_permit(lock_id: str, dataset_id: str, config_sha256: str) -> HoldoutReadPermit:
    return HoldoutReadPermit(lock_id, dataset_id, config_sha256, _PERMIT_ISSUER)


class DatasetStore:
    """Read and append split-scoped cases and secondary annotations."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def add_case(self, case: BenchmarkCase, split: str | DatasetSplit) -> None:
        split = str(split)
        self._validate_split(split)
        # This search intentionally excludes Holdout.
        if case.case_id in self._non_holdout_case_ids():
            raise ValueError(f"duplicate case_id across Development/Validation: {case.case_id}")
        path = self._cases_path(split)
        existing = self._read_cases(split) if path.exists() else ()
        if any(item.case_id == case.case_id for item in existing):
            raise ValueError(f"duplicate case_id within {split}: {case.case_id}")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(case.to_dict(), ensure_ascii=False, allow_nan=False) + "\n")

    def add_annotation(self, annotation: CaseAnnotation, split: str | DatasetSplit) -> None:
        split = str(split)
        self._validate_split(split)
        cases = {case.case_id: case for case in self._read_cases(split)}
        if annotation.case_id not in cases:
            raise ValueError(f"annotation references unknown {split} case: {annotation.case_id}")
        if annotation.base_case_id is not None:
            base = cases.get(annotation.base_case_id)
            if base is None:
                raise ValueError("base_case_id must identify a case in the same split")
            if cases[annotation.case_id].expected_action is not base.expected_action:
                raise ValueError("matched perturbations must preserve the base expected action")
        path = self._annotation_path(split)
        if annotation.case_id in self._read_annotations(split):
            raise ValueError(f"duplicate annotation for case: {annotation.case_id}")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(annotation.to_dict(), ensure_ascii=False, allow_nan=False) + "\n")

    def load_split(self, split: str | DatasetSplit, *, permit: HoldoutReadPermit | None = None,
                   dataset_id: str | None = None) -> tuple[BenchmarkCase, ...]:
        split = str(split)
        self._authorize(split, permit, dataset_id)
        cases = self._read_cases(split)
        if split == DatasetSplit.HOLDOUT:
            protected_ids = self._non_holdout_case_ids()
            collisions = protected_ids.intersection(case.case_id for case in cases)
            if collisions:
                raise ValueError(f"case IDs overlap between Holdout and other splits: {sorted(collisions)}")
        return cases

    def annotations_for(self, case_ids: Iterable[str], split: str | DatasetSplit, *,
                        permit: HoldoutReadPermit | None = None,
                        dataset_id: str | None = None) -> dict[str, CaseAnnotation]:
        split = str(split)
        self._authorize(split, permit, dataset_id)
        wanted = set(case_ids)
        annotations = self._read_annotations(split)
        cases = {case.case_id: case for case in self._read_cases(split)}
        selected = {case_id: annotations[case_id] for case_id in wanted if case_id in annotations}
        for annotation in selected.values():
            if annotation.base_case_id is None:
                continue
            base = cases.get(annotation.base_case_id)
            if base is None or annotation.base_case_id not in annotations:
                raise ValueError("matched perturbation base must exist and be annotated in the same split")
            if annotations[annotation.base_case_id].family is not PerturbationFamily.CLEAN_BASELINE:
                raise ValueError("matched perturbation base must be annotated clean_baseline")
            if cases[annotation.case_id].expected_action is not base.expected_action:
                raise ValueError("matched perturbations must preserve the base expected action")
        return selected

    def split_digest(self, split: str | DatasetSplit, *, permit: HoldoutReadPermit | None = None,
                     dataset_id: str | None = None) -> str:
        split = str(split)
        self._authorize(split, permit, dataset_id)
        return self._digest(self._cases_path(split))

    def annotation_digest(self, split: str | DatasetSplit, *, permit: HoldoutReadPermit | None = None,
                          dataset_id: str | None = None) -> str:
        split = str(split)
        self._authorize(split, permit, dataset_id)
        return self._digest(self._annotation_path(split))

    def case_exists(self, case_id: str) -> bool:
        """Search Development and Validation only; never reveal Holdout IDs."""
        return case_id in self._non_holdout_case_ids()

    def _lock_snapshot(self, dataset_id: str) -> dict[str, str]:
        """Capture the Validation and Holdout digests as part of the LOCK step."""
        validation = self._read_cases(DatasetSplit.VALIDATION)
        holdout = self._read_cases(DatasetSplit.HOLDOUT)
        if not validation:
            raise ValueError("cannot lock without a non-empty Validation dataset")
        if not holdout:
            raise ValueError("cannot lock without a prepared Holdout dataset")
        if {case.case_id for case in validation}.intersection(case.case_id for case in holdout):
            raise ValueError("case IDs must not overlap between Validation and Holdout")
        return {
            "dataset_id": dataset_id,
            "validation_dataset_sha256": self._digest(self._cases_path(DatasetSplit.VALIDATION)),
            "validation_annotation_sha256": self._digest(self._annotation_path(DatasetSplit.VALIDATION)),
            "holdout_dataset_sha256": self._digest(self._cases_path(DatasetSplit.HOLDOUT)),
            "holdout_annotation_sha256": self._digest(self._annotation_path(DatasetSplit.HOLDOUT)),
        }

    def _read_cases(self, split: str | DatasetSplit) -> tuple[BenchmarkCase, ...]:
        path = self._cases_path(str(split))
        if not path.exists():
            return ()
        cases = tuple(BenchmarkCase.from_dict(json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        ids = [case.case_id for case in cases]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate case IDs within {split} split")
        return cases

    def _read_annotations(self, split: str | DatasetSplit) -> dict[str, CaseAnnotation]:
        path = self._annotation_path(str(split))
        if not path.exists():
            return {}
        annotations: dict[str, CaseAnnotation] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            annotation = CaseAnnotation.from_dict(json.loads(line))
            if annotation.case_id in annotations:
                raise ValueError(f"duplicate annotation for case: {annotation.case_id}")
            annotations[annotation.case_id] = annotation
        return annotations

    def _non_holdout_case_ids(self) -> set[str]:
        return {case.case_id for split in (DatasetSplit.DEVELOPMENT, DatasetSplit.VALIDATION)
                for case in self._read_cases(split)}

    def _cases_path(self, split: str | DatasetSplit) -> Path:
        return self.root / str(split) / "cases.jsonl"

    def _annotation_path(self, split: str | DatasetSplit) -> Path:
        return self.root / str(split) / "annotations.jsonl"

    @staticmethod
    def _digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes() if path.exists() else b"").hexdigest()

    @staticmethod
    def _authorize(split: str, permit: HoldoutReadPermit | None, dataset_id: str | None) -> None:
        DatasetStore._validate_split(split)
        if split == DatasetSplit.HOLDOUT:
            if permit is None or not isinstance(permit, HoldoutReadPermit):
                raise PermissionError("Holdout reads require a verified Validation lock permit")
            if dataset_id != permit.dataset_id:
                raise PermissionError("Holdout permit is not valid for this dataset ID")
        elif permit is not None:
            raise ValueError("Holdout permit can only be used for Holdout")

    @staticmethod
    def _validate_split(split: str) -> None:
        if str(split) not in ALL_DATASET_SPLITS:
            raise ValueError(f"split must be one of {ALL_DATASET_SPLITS}")
