from __future__ import annotations

from pathlib import Path

import pytest

from showcov.adapters.coverage.cobertura import read_root
from showcov.adapters.coverage.discover import resolve_coverage_paths
from showcov.errors import CoverageXMLNotFoundError, InvalidCoverageXMLError


def test_resolve_coverage_paths_explicit_missing(tmp_path: Path) -> None:
    with pytest.raises(CoverageXMLNotFoundError):
        resolve_coverage_paths([tmp_path / "nope.xml"], cwd=tmp_path)


def test_resolve_coverage_paths_default_coverage_xml(tmp_path: Path) -> None:
    p = tmp_path / "coverage.xml"
    p.write_text("<coverage></coverage>\n", encoding="utf-8")

    cwd = Path.cwd()
    try:
        # chdir is fine in a small test; pytest will isolate tmp dirs anyway.
        import os

        os.chdir(tmp_path)
        got = resolve_coverage_paths(None, cwd=tmp_path)
        assert got == (p.resolve(),)
    finally:
        import os

        os.chdir(cwd)


def test_read_root_rejects_non_coverage_root(tmp_path: Path) -> None:
    p = tmp_path / "coverage.xml"
    p.write_text("<notcoverage />\n", encoding="utf-8")
    with pytest.raises(InvalidCoverageXMLError):
        read_root(p)
