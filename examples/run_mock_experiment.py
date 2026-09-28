"""Run the local synthetic Development set through the real control loop.

This is a reproducibility/plumbing example, not a Jev evaluation. It writes a
machine-readable run with ``execution_mode=mock`` and derives its summary from
the emitted records rather than hardcoding result numbers.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_control_plane.failure_lab import (  # noqa: E402
    DatasetStore,
    ExperimentArtifactStore,
    ExperimentConfig,
    ExperimentRunner,
)


def main() -> None:
    experiments = ROOT / "experiments"
    config = ExperimentConfig.from_dict(
        json.loads((experiments / "configs" / "m2-mock-development.json").read_text(encoding="utf-8"))
    )
    run_id = f"{config.experiment_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    outcome = ExperimentRunner(
        DatasetStore(experiments / "datasets"),
        ExperimentArtifactStore(experiments),
    ).run(config, run_id=run_id)
    print(json.dumps({"run_id": outcome.run_id, "run_dir": str(outcome.run_dir), "summary": outcome.metrics}, indent=2))


if __name__ == "__main__":
    main()
