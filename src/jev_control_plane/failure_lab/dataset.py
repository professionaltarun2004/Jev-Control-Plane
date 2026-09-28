"""Split-isolated JSONL benchmark storage.

Cases, perturbation annotations, and splits have separate files so expected
actions cannot quietly grow Jev-specific labels. :mod:`runner` selects exactly
one split and applies the LOCK check before asking this store for Holdout data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from enum import StrEnum
from typing import Iterable

from .benchmark import BenchmarkCase, CaseAnnotation


class DatasetSplit(StrEnum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    HOLDOUT = "holdout"


ALL_DATASET_SPLITS = tuple(split.value for split in DatasetSplit)


class DatasetStore:
    """Stores cases by split and keeps perturbation labels in a sidecar."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def add_case(self, case: BenchmarkCase, split: str | DatasetSplit) -> None:
        split = str(split)
        self._validate_split(split)
        if self.case_exists(case.case_id):
            raise ValueError(f"duplicate case_id across dataset splits: {case.case_id}")
        path = self._cases_path(split)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(case.to_dict(), ensure_ascii=False, allow_nan=False) + "\n")

    def add_annotation(self, annotation: CaseAnnotation) -> None:
        if not self.case_exists(annotation.case_id):
            raise ValueError(f"annotation references unknown case: {annotation.case_id}")
        annotations = self.root / "annotations.jsonl"
        if annotations.exists():
            for line in annotations.read_text(encoding="utf-8").splitlines():
                if line.strip() and json.loads(line)["case_id"] == annotation.case_id:
                    raise ValueError(f"duplicate annotation for case: {annotation.case_id}")
        annotations.parent.mkdir(parents=True, exist_ok=True)
        with annotations.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(annotation.to_dict(), ensure_ascii=False) + "\n")

    def load_split(self, split: str | DatasetSplit) -> tuple[BenchmarkCase, ...]:
        split = str(split)
        self._validate_split(split)
        path = self._cases_path(split)
        if not path.exists():
            return ()
        cases = tuple(
            BenchmarkCase.from_dict(json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        ids = [case.case_id for case in cases]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate case IDs within {split} split")
        return cases

    def annotations_for(self, case_ids: Iterable[str]) -> dict[str, CaseAnnotation]:
        wanted = set(case_ids)
        path = self.root / "annotations.jsonl"
        if not path.exists():
            return {}
        annotations: dict[str, CaseAnnotation] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            case_id = str(item["case_id"])
            if case_id in wanted:
                if case_id in annotations:
                    raise ValueError(f"duplicate annotation for case: {case_id}")
                from .benchmark import PerturbationFamily
                annotations[case_id] = CaseAnnotation(case_id, PerturbationFamily(item["family"]))
        return annotations

    def split_digest(self, split: str | DatasetSplit) -> str:
        split = str(split)
        self._validate_split(split)
        path = self._cases_path(split)
        payload = path.read_bytes() if path.exists() else b""
        return hashlib.sha256(payload).hexdigest()

    def case_exists(self, case_id: str) -> bool:
        return any(case.case_id == case_id for split in ALL_DATASET_SPLITS for case in self.load_split(split))

    def _cases_path(self, split: str) -> Path:
        return self.root / str(split) / "cases.jsonl"

    @staticmethod
    def _validate_split(split: str) -> None:
        if str(split) not in ALL_DATASET_SPLITS:
            raise ValueError(f"split must be one of {ALL_DATASET_SPLITS}")
