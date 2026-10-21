"""Run an offline paired plumbing check on the Development fixture.

Both conditions are deterministic local mocks. This example makes no Jev or
LLM request and writes versioned records under ``experiments/comparisons``.
It is a compact entry point for following the comparison runner and artifact
schema; its counts are not provider performance results.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_control_plane.failure_lab.comparison import (  # noqa: E402
    PairedComparisonConfig,
    PairedComparisonRunner,
)
from jev_control_plane.failure_lab.dataset import DatasetStore  # noqa: E402
from jev_control_plane.failure_lab.experiment import ExperimentConfig  # noqa: E402


def main() -> None:
    configs = ROOT / "experiments" / "configs"
    comparison = PairedComparisonConfig.from_dict(
        json.loads((configs / "m4-mock-paired-development.json").read_text(encoding="utf-8"))
    )
    jev_config = ExperimentConfig.from_dict(
        json.loads((configs / comparison.jev_config_file).read_text(encoding="utf-8"))
    )
    jev_config = replace(jev_config, experiment_id=comparison.experiment_id)
    result = PairedComparisonRunner(
        DatasetStore(ROOT / "experiments" / "datasets"),
        ROOT / "experiments" / "comparisons",
        project_root=ROOT,
    ).run(jev_config, comparison)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
