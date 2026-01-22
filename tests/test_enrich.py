from __future__ import annotations

from typing import TYPE_CHECKING

from showcov.engine.build import BuildOptions, build_report
from showcov.engine.enrich import enrich_report
from showcov.model.types import BranchMode, SummarySort

if TYPE_CHECKING:
    from pathlib import Path


def test_enrich_attaches_snippets_and_file_counts(project: dict[str, Path]) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]

    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[
            {
                "filename": "pkg/mod.py",
                "lines": [
                    {"number": 1, "hits": 1},
                    {"number": 2, "hits": 0},
                ],
            }
        ],
    )

    opts = BuildOptions(
        coverage_paths=(cov,),
        base_path=root,
        filters=None,
        sections={"lines"},
        diff_base=None,
        branches_mode=BranchMode.PARTIAL,
        summary_sort=SummarySort.FILE,
        want_aggregate_stats=False,
        want_file_stats=True,
        want_snippets=True,
        context_before=1,
        context_after=1,
        meta_show_paths=True,
        meta_show_line_numbers=True,
    )

    report = build_report(opts)
    assert report.sections.lines is not None

    # Enrich should attach source lines + per-file totals
    enriched = enrich_report(report, opts)
    sec = enriched.sections.lines
    assert sec is not None
    f = sec.files[0]
    assert f.counts is not None
    assert f.counts.total > 0
    assert f.counts.uncovered == 1

    r = f.uncovered[0]
    assert r.source is not None
    # context_before/after=1 => includes 1..3 around uncovered line 2 (bounded by file length)
    assert any(sl.line == 2 for sl in r.source)
    assert any("def f" in sl.code for sl in r.source)
