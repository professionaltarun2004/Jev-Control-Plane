"""JSON-safe structured decision records and append-only JSONL logging."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .domain import DecisionRecord


def json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


class JsonlDecisionLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, record: DecisionRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(json_safe(record), ensure_ascii=False, allow_nan=False) + "\n")
