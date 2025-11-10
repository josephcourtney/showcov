from __future__ import annotations

from pathlib import Path
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

    # include a single file
    pf = PathFilter([file_a], [])
    out = pf.filter(sections)
    assert [s.file for s in out] == [file_a]

    # include a whole directory, but exclude via glob
    pf = PathFilter([tmp_path], ["*b.py"])
    out = pf.filter(sections)
    assert [s.file for s in out] == [file_a]

    # explicit path exclude should override a directory include
    pf = PathFilter([tmp_path], [file_a])
    out = pf.filter(sections)
    assert [s.file for s in out] == [file_b]

    # with no includes, everything is included unless excluded
    pf = PathFilter([], ["*a.py"])
    out = pf.filter(sections)
    assert [s.file for s in out] == [file_b]

    # allow() mirrors filter() decisions for individual paths
    pf = PathFilter([tmp_path], ["*b.py"])
    assert pf.allow(file_a)
    assert not pf.allow(file_b)


def test_path_filter_allow_and_normalization(tmp_path: Path) -> None:
    """allow() respects include/exclude and normalizes absolute/relative paths."""
    file_c = tmp_path / "nested" / "c.py"
    file_c.parent.mkdir()
    file_c.write_text("c\n")

    # Include the tmp project root; exclude **/c.py everywhere
    pf = PathFilter([tmp_path], ["**/c.py"])
    assert pf.allow(file_c) is False
    assert pf.allow(tmp_path / "a.py") is True


def test_path_filter_normalizes_and_expands(tmp_path: Path) -> None:
    sub = tmp_path / "pkg"
    sub.mkdir()
    file_a = sub / "a.py"
    file_a.write_text("a\n")
    sections = [UncoveredSection(file_a, [(1, 1)])]

    pf = PathFilter([sub], [], base=tmp_path)
    out = pf.filter(sections)
    assert out == sections
