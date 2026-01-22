from __future__ import annotations

from typing import TYPE_CHECKING

from showcov.engine.build import BuildOptions, build_report
from showcov.model.path_filter import PathFilter
from showcov.model.types import BranchMode, SummarySort

if TYPE_CHECKING:
    from pathlib import Path


def _opts(
    *,
    coverage_paths: tuple[Path, ...],
    base_path: Path,
    filters: PathFilter | None = None,
    sections: set[str],
    diff_base: Path | None = None,
    branches_mode: BranchMode = BranchMode.PARTIAL,
    want_aggregate_stats: bool = False,
    want_file_stats: bool = False,
    want_snippets: bool = False,
) -> BuildOptions:
    return BuildOptions(
        coverage_paths=coverage_paths,
        base_path=base_path,
        filters=filters,
        sections=sections,
        diff_base=diff_base,
        branches_mode=branches_mode,
        summary_sort=SummarySort.FILE,
        want_aggregate_stats=want_aggregate_stats,
        want_file_stats=want_file_stats,
        want_snippets=want_snippets,
        context_before=0,
        context_after=0,
        meta_show_paths=True,
        meta_show_line_numbers=True,
    )


def test_build_lines_and_summary_with_filters(project: dict[str, Path]) -> None:
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
                    {"number": 3, "hits": 0},
                ],
            },
            {
                "filename": "pkg/other.py",
                "lines": [
                    {"number": 1, "hits": 0},
                ],
            },
        ],
    )

    pf = PathFilter(include=("pkg/mod.py",), exclude=(), base=root)

    report = build_report(
        _opts(
            coverage_paths=(cov,),
            base_path=root,
            filters=pf,
            sections={"lines", "summary"},
            want_aggregate_stats=True,
        )
    )

    assert report.sections.lines is not None
    assert report.sections.summary is not None

    # Only mod.py should remain due to include filter.
    assert len(report.sections.lines.files) == 1
    assert report.sections.lines.files[0].file == "pkg/mod.py"

    # Two uncovered lines -> 2-3
    ranges = report.sections.lines.files[0].uncovered
    assert ranges[0].start == 2
    assert ranges[0].end == 3

    # Aggregate stats reflect filtered content
    assert report.sections.lines.summary is not None
    assert report.sections.lines.summary.uncovered == 2


def test_build_branches_uses_richer_conditions(project: dict[str, Path]) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]

    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[
            {
                "filename": "pkg/mod.py",
                "lines": [
                    {
                        "number": 3,
                        "hits": 1,
                        "branch": True,
                        "condition_coverage": "50% (1/2)",
                        "missing_branches": "1",
                        "conditions": [
                            {"number": 0, "type": "jump", "coverage": "100%"},
                            {"number": 1, "type": "jump", "coverage": "0%"},
                        ],
                    }
                ],
            }
        ],
    )

    report = build_report(
        _opts(
            coverage_paths=(cov,),
            base_path=root,
            sections={"branches"},
            branches_mode=BranchMode.PARTIAL,
        )
    )

    sec = report.sections.branches
    assert sec is not None
    assert sec.gaps

    gap = sec.gaps[0]
    assert gap.file == "pkg/mod.py"
    assert gap.line == 3

    # In PARTIAL mode, we should see:
    # - jump#1 0%
    # - branch#1 missing (coverage None)
    # - line aggregate 50%
    labels = {(c.type, c.number, c.coverage) for c in gap.conditions}
    assert ("jump", 1, 0) in labels
    assert ("branch", 1, None) in labels
    assert ("line", -1, 50) in labels
    assert ("jump", 0, 100) not in labels  # fully covered should be filtered out


def test_build_branches_missing_only(project: dict[str, Path]) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]

    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[
            {
                "filename": "pkg/mod.py",
                "lines": [
                    {
                        "number": 3,
                        "hits": 1,
                        "branch": True,
                        "condition_coverage": "50% (1/2)",
                        "missing_branches": "1",
                        "conditions": [
                            {"number": 0, "type": "jump", "coverage": "100%"},
                            {"number": 1, "type": "jump", "coverage": "0%"},
                        ],
                    }
                ],
            }
        ],
    )

    report = build_report(
        _opts(
            coverage_paths=(cov,),
            base_path=root,
            sections={"branches"},
            branches_mode=BranchMode.MISSING_ONLY,
        )
    )

    sec = report.sections.branches
    assert sec is not None
    gap = sec.gaps[0]
    labels = {(c.type, c.number, c.coverage) for c in gap.conditions}

    # missing-only: coverage None or 0
    assert ("jump", 1, 0) in labels
    assert ("branch", 1, None) in labels
    assert ("line", -1, 50) not in labels


def test_build_summary_prefers_branch_counts_with_larger_denominator(project: dict[str, Path]) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]

    cov1 = write_cobertura_xml(
        root,
        "c1.xml",
        classes=[
            {
                "filename": "pkg/mod.py",
                "lines": [
                    {"number": 1, "hits": 1},
                    {
                        "number": 3,
                        "hits": 1,
                        "branch": True,
                        "condition_coverage": "50% (1/2)",
                    },
                ],
            }
        ],
    )
    cov2 = write_cobertura_xml(
        root,
        "c2.xml",
        classes=[
            {
                "filename": "pkg/mod.py",
                "lines": [
                    {"number": 1, "hits": 1},
                    {
                        "number": 3,
                        "hits": 1,
                        "branch": True,
                        "condition_coverage": "66% (2/3)",
                    },
                ],
            }
        ],
    )

    report = build_report(
        _opts(
            coverage_paths=(cov1, cov2),
            base_path=root,
            sections={"summary"},
        )
    )

    sec = report.sections.summary
    assert sec is not None
    row = next(r for r in sec.files if r.file == "pkg/mod.py")

    # Branch counts should reflect the best-fidelity denominator (3)
    assert row.branches.total == 3
    assert row.branches.covered == 2
    assert row.branches.missed == 1


def test_build_diff_section(project: dict[str, Path]) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]

    base = write_cobertura_xml(
        root,
        "base.xml",
        classes=[
            {"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]},
        ],
    )
    cur = write_cobertura_xml(
        root,
        "cur.xml",
        classes=[
            {"filename": "pkg/mod.py", "lines": [{"number": 4, "hits": 0}]},
        ],
    )

    report = build_report(
        _opts(
            coverage_paths=(cur,),
            base_path=root,
            sections={"diff"},
            diff_base=base,
        )
    )

    diff = report.sections.diff
    assert diff is not None

    assert diff.new
    assert diff.resolved

    new_ranges = diff.new[0].uncovered
    res_ranges = diff.resolved[0].uncovered

    assert (new_ranges[0].start, new_ranges[0].end) == (4, 4)
    assert (res_ranges[0].start, res_ranges[0].end) == (2, 2)


def test_internal_branch_accumulator_prefers_larger_denominator() -> None:
    from showcov.engine import build as build_mod
    from showcov.model.report import BranchCondition

    records = [
        ("pkg/mod.py", 10, 1, (1, 2), (), (BranchCondition(number=-1, type="line", coverage=50),)),
        ("pkg/mod.py", 10, 1, (2, 3), (), (BranchCondition(number=-1, type="line", coverage=67),)),
    ]
    accum = build_mod._aggregate_branch_records(records, files={"pkg/mod.py"})
    assert accum["pkg/mod.py", 10]["bc"] == (2, 3)
