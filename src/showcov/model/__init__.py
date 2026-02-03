"""Domain model for showcov (pure types + policy; no IO)."""

from .metrics import pct
from .path_filter import PathFilter
from .report import Report
from .thresholds import Threshold, ThresholdFailure, ThresholdsResult, evaluate, parse_threshold
from .types import BranchMode, SummarySort

__all__ = [
    "BranchMode",
    "PathFilter",
    "Report",
    "SummarySort",
    "Threshold",
    "ThresholdFailure",
    "ThresholdsResult",
    "evaluate",
    "parse_threshold",
    "pct",
]
