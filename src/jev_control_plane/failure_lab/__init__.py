"""Decision-level Failure Lab around the existing Jev control loop.

Start with :mod:`benchmark` for the intentionally small case contract, then
follow :mod:`runner` for one case's path through control, recording, and metrics.
"""

from .benchmark import (
    BenchmarkCase,
    CaseAnnotation,
    FailureCategory,
    GroundTruthProvenance,
    GroundTruthSource,
    GroundTruthCertainty,
    PerturbationFamily,
)
from .artifacts import ExperimentArtifactStore
from .dataset import DatasetStore, DatasetSplit
from .experiment import ExecutionMode, ExperimentConfig, ExperimentLock
from .runner import ExperimentRunner, RunOutcome
from .mock import DeterministicMockJevAdapter

__all__ = [
    "BenchmarkCase", "CaseAnnotation", "DatasetSplit", "DatasetStore", "ExperimentArtifactStore",
    "ExecutionMode", "ExperimentConfig", "ExperimentLock", "ExperimentRunner",
    "DeterministicMockJevAdapter", "RunOutcome",
    "FailureCategory", "GroundTruthCertainty", "GroundTruthProvenance",
    "GroundTruthSource", "PerturbationFamily", "RunArtifactStore",
]
