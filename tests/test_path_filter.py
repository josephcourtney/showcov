from __future__ import annotations

from typing import TYPE_CHECKING

from showcov.core.model.path_filter import PathFilter

if TYPE_CHECKING:
    from pathlib import Path


def test_path_filter_include_exclude_basic(project: dict[str, Path], tmp_path: Path) -> None:
    base = project["root"]
    pf = PathFilter(include=("pkg/*.py",), exclude=("*/other.py",), base=base)

    assert pf.allow("pkg/mod.py") is True
    assert pf.allow("pkg/other.py") is False
    assert pf.allow("README.md") is False


def test_path_filter_patterns_from_file(tmp_path: Path) -> None:
    base = tmp_path
    patterns = tmp_path / "patterns.txt"
    patterns.write_text(
        "# comment\n\npkg/*.py\n",
        encoding="utf-8",
    )

    pf = PathFilter(include=(patterns,), exclude=(), base=base)
    assert pf.allow("pkg/mod.py") is True
    assert pf.allow("nope.txt") is False


def test_path_filter_filter_files_keeps_payloads(tmp_path: Path) -> None:
    pf = PathFilter(include=("a*",), exclude=(), base=tmp_path)
    items = [("abc.py", 1), ("zzz.py", 2)]
    kept = pf.filter_files(items)
    assert kept == [("abc.py", 1)]
