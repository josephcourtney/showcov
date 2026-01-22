from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from showcov.engine.build import BuildOptions, build_report
from showcov.model.thresholds import Threshold, evaluate, parse_threshold
from showcov.model.types import BranchMode, SummarySort

if TYPE_CHECKING:
    from pathlib import Path


def _build_report_for_thresholds(project_root: Path, cov: Path):
    return build_report(
        BuildOptions(
            coverage_paths=(cov,),
            base_path=project_root,
            filters=None,
            sections={"lines", "summary"},
            diff_base=None,
            branches_mode=BranchMode.PARTIAL,
            summary_sort=SummarySort.FILE,
            want_aggregate_stats=False,
            want_file_stats=False,
            want_snippets=False,
            context_before=0,
            context_after=0,
            meta_show_paths=True,
            meta_show_line_numbers=True,
        )
    )


def test_parse_threshold() -> None:
    t = parse_threshold("statements=90,branches=80,misses=10")
    assert t.statement == 90
    assert t.branch == 80
    assert t.misses == 10

    with pytest.raises(ValueError, match=r"threshold expression must be non-empty"):
        parse_threshold("")


def test_thresholds_pass_and_fail(project: dict[str, Path]) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]

    # statements: line 1 covered, line 2 missed => 50% statement coverage
    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[
            {"filename": "pkg/mod.py", "lines": [{"number": 1, "hits": 1}, {"number": 2, "hits": 0}]},
        ],
    )

    report = _build_report_for_thresholds(root, cov)

    ok = evaluate(report, [Threshold(statement=50)])
    assert ok.passed is True

    bad = evaluate(report, [Threshold(statement=99)])
    assert bad.passed is False
    assert bad.failures
    assert bad.failures[0].metric == "statement"
