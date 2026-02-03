from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from showcov.adapters.coverage.records import collect_cobertura_records
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

    records = collect_cobertura_records((cov,))
    opts = BuildOptions(
        coverage_paths=(cov,),
        base_path=root,
        filters=None,
        sections={"lines"},
        branches_mode=BranchMode.PARTIAL,
        summary_sort=SummarySort.FILE,
        want_aggregate_stats=False,
        want_file_stats=True,
        want_snippets=True,
        context_before=1,
        context_after=1,
        records=records,
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


def test_enrich_does_not_crash_when_source_file_missing(tmp_path: Path) -> None:
    from tests.conftest import write_cobertura_xml

    # coverage references a file that does not exist on disk
    cov = write_cobertura_xml(
        tmp_path,
        "coverage.xml",
        classes=[{"filename": "pkg/missing.py", "lines": [{"number": 2, "hits": 0}]}],
    )

    records = collect_cobertura_records((cov,))
    opts = BuildOptions(
        coverage_paths=(cov,),
        base_path=tmp_path,
        filters=None,
        sections={"lines"},
        branches_mode=BranchMode.PARTIAL,
        summary_sort=SummarySort.FILE,
        want_aggregate_stats=False,
        want_file_stats=True,
        want_snippets=True,
        context_before=1,
        context_after=1,
        records=records,
        meta_show_paths=True,
        meta_show_line_numbers=True,
    )

    report = build_report(opts)
    enriched = enrich_report(report, opts)

    sec = enriched.sections.lines
    assert sec is not None
    assert sec.files
    # Must not crash; snippets may be absent due to missing file.
    f = sec.files[0]
    assert f.uncovered
