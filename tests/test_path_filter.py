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
