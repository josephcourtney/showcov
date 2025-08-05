from __future__ import annotations

from typing import TYPE_CHECKING

from showcov.core import PathFilter, UncoveredSection

if TYPE_CHECKING:
    from pathlib import Path


def test_path_filter_include_exclude(tmp_path: Path) -> None:
    file_a = tmp_path / "a.py"
    file_a.write_text("a\n")
    file_b = tmp_path / "b.py"
    file_b.write_text("b\n")
    sections = [
        UncoveredSection(file_a, [(1, 1)]),
        UncoveredSection(file_b, [(1, 1)]),
    ]

    pf = PathFilter([file_a], [])
    out = pf.filter(sections)
    assert [s.file for s in out] == [file_a]

    pf = PathFilter([tmp_path], ["*b.py"])
    out = pf.filter(sections)
    assert [s.file for s in out] == [file_a]


def test_path_filter_resolves_paths(tmp_path: Path) -> None:
    file_a = tmp_path / "a.py"
    file_a.write_text("a\n")
    sections = [UncoveredSection(file_a, [(1, 1)])]

    rel = tmp_path / ".." / tmp_path.name / "a.py"
    pf = PathFilter([str(rel)], [])
    out = pf.filter(sections)
    assert [s.file for s in out] == [file_a]


def test_path_filter_normalizes_and_expands(tmp_path: Path) -> None:
    sub = tmp_path / "pkg"
    sub.mkdir()
    file_a = sub / "a.py"
    file_a.write_text("a\n")
    sections = [UncoveredSection(file_a, [(1, 1)])]

    pf = PathFilter([sub], [], base=tmp_path)
    out = pf.filter(sections)
    assert out == sections
