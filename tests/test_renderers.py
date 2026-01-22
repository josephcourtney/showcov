from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from showcov.engine.build import BuildOptions, build_report
from showcov.model.types import BranchMode, SummarySort
from showcov.render.render import RenderOptions, render

if TYPE_CHECKING:
    from pathlib import Path


def _report_for_render(project_root: Path, cov: Path):
    opts = BuildOptions(
        coverage_paths=(cov,),
        base_path=project_root,
        filters=None,
        sections={"lines", "branches", "summary"},
        diff_base=None,
        branches_mode=BranchMode.PARTIAL,
        summary_sort=SummarySort.FILE,
        want_aggregate_stats=True,
        want_file_stats=False,
        want_snippets=False,
        context_before=0,
        context_after=0,
        meta_show_paths=True,
        meta_show_line_numbers=True,
    )
    return build_report(opts)


def test_render_json_schema_valid(project: dict[str, Path]) -> None:
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
    out = render(report, fmt="json", options=RenderOptions(color=False))
    payload = json.loads(out)

    assert payload["tool"]["name"] == "showcov"
    assert payload["schema_version"] == 1
    assert "sections" in payload
    assert "lines" in payload["sections"]


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


def test_render_rg_smoke(project: dict[str, Path]) -> None:
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
        fmt="rg",
        options=RenderOptions(color=False, show_paths=True, show_line_numbers=True, is_tty=False),
    )
    assert "pkg/mod.py" in out
    assert "2" in out


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
