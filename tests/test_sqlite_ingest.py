from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from showcov.adapters.coverage.input_kind import CoverageInputBackend
from showcov.errors import CoverageInputDataError
from showcov.model.types import BranchMode, SummarySort
from showcov.usecases.inputs import resolve_coverage_inputs
from showcov.usecases.pipeline import build_report_from_coverage

if TYPE_CHECKING:
    from types import TracebackType


def _make_coverage_db(tmp_path: Path) -> Path:
    # Create a tiny package with a simple branch and an uncovered line.
    from tests.conftest import write_source_file

    write_source_file(tmp_path, "pkg/__init__.py", "")
    write_source_file(
        tmp_path,
        "pkg/mod.py",
        "def f(x):\n    if x:\n        return 1\n    return 0\n",
    )

    db = tmp_path / ".coverage"

    import importlib.util

    from coverage import Coverage

    cov = Coverage(
        data_file=str(db),
        data_suffix=False,
        config_file=False,
        branch=True,
        source=[str(tmp_path)],
    )
    cov.start()
    spec = importlib.util.spec_from_file_location("test_pkg_mod", tmp_path / "pkg/mod.py")
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.f(x=True)
    cov.stop()
    cov.save()

    assert db.exists()
    return db


class _Cwd:
    def __init__(self, p: Path) -> None:
        self.p = p
        self._orig: Path | None = None

    def __enter__(self) -> None:
        import os

        self._orig = Path.cwd()
        os.chdir(self.p)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        import os

        if self._orig is not None:
            os.chdir(self._orig)


def test_resolve_coverage_inputs_discovers_coverage_db(tmp_path: Path) -> None:
    db = _make_coverage_db(tmp_path)
    with _Cwd(tmp_path):
        got = resolve_coverage_inputs(None, cwd=tmp_path)
    assert got == (db.resolve(),)


def test_resolve_coverage_inputs_respects_backend(tmp_path: Path) -> None:
    db = _make_coverage_db(tmp_path)
    with _Cwd(tmp_path):
        got = resolve_coverage_inputs(
            None,
            cwd=tmp_path,
            backend=CoverageInputBackend.SQLITE,
        )
    assert got == (db.resolve(),)


def test_resolve_coverage_inputs_explicit_mismatch_raises(tmp_path: Path) -> None:
    db = _make_coverage_db(tmp_path)
    with pytest.raises(CoverageInputDataError):
        resolve_coverage_inputs(
            (db,),
            cwd=tmp_path,
            backend=CoverageInputBackend.XML,
        )


def test_build_report_from_coverage_db(tmp_path: Path) -> None:
    db = _make_coverage_db(tmp_path)

    with _Cwd(tmp_path):
        report = build_report_from_coverage(
            coverage_paths=(db,),
            base_path=tmp_path,
            filters=None,
            sections={"lines", "branches", "summary"},
            branches_mode=BranchMode.PARTIAL,
            summary_sort=SummarySort.MISSED_STATEMENTS,
            want_stats=True,
            want_file_stats=False,
            want_snippets=False,
            context_before=0,
            context_after=0,
            show_paths=True,
            show_line_numbers=True,
            drop_empty_branches=False,
        )

    assert report.sections.lines is not None
    assert report.sections.branches is not None

    # The missing `return 0` is line 4 in pkg/mod.py.
    lines_files = {f.file: f for f in report.sections.lines.files}
    mod_lines = lines_files.get("pkg/mod.py")
    assert mod_lines is not None
    assert any(r.start == 4 and r.end == 4 for r in mod_lines.uncovered)

    # The `if x:` at line 2 should have partial branch coverage.
    gaps = [g for g in report.sections.branches.gaps if g.file == "pkg/mod.py" and g.line == 2]
    assert gaps
    conds = gaps[0].conditions
    assert any(c.type == "line" and c.coverage == 50 for c in conds)
    assert any((c.type or "").lower() == "jump" and c.coverage in {0, 100} for c in conds)
