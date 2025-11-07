from pathlib import Path

import pytest

from showcov.core.core import UncoveredSection
from showcov.core.thresholds import (
    Threshold,
    ThresholdFailure,
    ThresholdsResult,
    evaluate_thresholds,
    parse_threshold,
)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("stmt=80", Threshold(statement=80.0)),
        ("br=75% miss=10", Threshold(branch=75.0, misses=10)),
        ("stmt=90, br=80, miss=5", Threshold(statement=90.0, branch=80.0, misses=5)),
        ("STATEMENTS=100 BRANCHES=0", Threshold(statement=100.0, branch=0.0)),
    ],
)
def test_parse_threshold(expression: str, expected: Threshold) -> None:
    assert parse_threshold(expression) == expected


@pytest.mark.parametrize(
    ("expression", "pattern"),
    [
        ("", "non-empty"),
        (" ", "non-empty"),
        ("stmt", "invalid threshold token"),
        ("foo=10", "unknown threshold metric"),
        ("stmt=-1", "percentage out of range"),
        ("stmt=101", "percentage out of range"),
        ("miss=-5", "must be non-negative"),
        ("stmt=80 stmt=90", "duplicate percentage constraint"),
    ],
)
def test_parse_threshold_rejects_invalid_input(expression: str, pattern: str) -> None:
    with pytest.raises(ValueError, match=pattern):
        parse_threshold(expression)


def test_evaluate_thresholds_passes_at_boundaries() -> None:
    sections = [UncoveredSection(Path("file.py"), [(5, 5)])]
    totals = (10, 8, 4, 3)
    thresholds = [parse_threshold("stmt=80 br=75 miss=1")]
    result = evaluate_thresholds(thresholds, totals=totals, sections=sections)
    assert result == ThresholdsResult(passed=True, failures=[])


def test_evaluate_thresholds_reports_failures() -> None:
    sections = [UncoveredSection(Path("file.py"), [(1, 3)])]
    totals = (20, 10, 0, 0)
    thresholds = [parse_threshold("stmt=60 br=50 miss=2")]
    result = evaluate_thresholds(thresholds, totals=totals, sections=sections)
    assert not result.passed
    assert result.failures == [
        ThresholdFailure(metric="statement", required=60.0, actual=50.0, comparison=">="),
        ThresholdFailure(metric="misses", required=2, actual=3, comparison="<="),
    ]


def test_evaluate_thresholds_combines_multiple_specs() -> None:
    sections = [UncoveredSection(Path("file.py"), [(10, 12)])]
    totals = (12, 9, 6, 6)
    thresholds = [parse_threshold("stmt=80"), parse_threshold("miss=2")]
    result = evaluate_thresholds(thresholds, totals=totals, sections=sections)
    assert not result.passed
    assert result.failures == [
        ThresholdFailure(metric="statement", required=80.0, actual=75.0, comparison=">="),
        ThresholdFailure(metric="misses", required=2, actual=3, comparison="<="),
    ]


def test_evaluate_thresholds_branch_failure() -> None:
    sections: list[UncoveredSection] = []
    totals = (5, 5, 4, 2)
    thresholds = [parse_threshold("br=60")]
    result = evaluate_thresholds(thresholds, totals=totals, sections=sections)
    assert not result.passed
    assert result.failures == [
        ThresholdFailure(metric="branch", required=60.0, actual=50.0, comparison=">="),
    ]
