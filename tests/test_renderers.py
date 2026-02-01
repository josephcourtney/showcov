from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from showcov.core.build import BuildOptions, build_report
from showcov.core.model.types import BranchMode, SummarySort
from showcov.inputs.records import collect_cobertura_records
from showcov.render.render import RenderOptions, render

if TYPE_CHECKING:
    from pathlib import Path


def _report_for_render(project_root: Path, cov: Path):
    records = collect_cobertura_records((cov,))
    opts = BuildOptions(
        coverage_paths=(cov,),
        base_path=project_root,
        filters=None,
        sections={"lines", "branches", "summary"},
        branches_mode=BranchMode.PARTIAL,
        summary_sort=SummarySort.FILE,
        want_aggregate_stats=True,
        want_file_stats=False,
        want_snippets=False,
        context_before=0,
        context_after=0,
        records=records,
        meta_show_paths=True,
        meta_show_line_numbers=True,
    )
    return build_report(opts)


def test_render_human_smoke(project: dict[str, Path]) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]
    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[
            {"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]},
        ],
    )

    report = _report_for_render(root, cov)
    out = render(
        report,
        fmt="human",
        options=RenderOptions(color=False, show_paths=True, show_line_numbers=True, is_tty=False),
    )
    assert "Uncovered Lines" in out
    assert "pkg/mod.py" in out
    assert "2" in out  # range line number present somewhere


def test_render_invalid_format_raises(project: dict[str, Path]) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]
    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[{"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]}],
    )
    report = _report_for_render(root, cov)

    with pytest.raises(ValueError, match=r"Unsupported format"):
        render(report, fmt="nope", options=RenderOptions(color=False))
