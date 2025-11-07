from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from defusedxml import ElementTree

from showcov.core.dataset import (
    CoverageDataset,
    build_branches,
    build_dataset,
    build_diff,
    build_lines,
    build_summary,
)
from showcov.core.exceptions import InvalidCoverageXMLError
from showcov.core.types import BranchMode

if TYPE_CHECKING:
    from pathlib import Path


def _build_root(xml: str):
    return ElementTree.fromstring(xml)


def test_build_dataset_and_lines(tmp_path: Path) -> None:
    src = tmp_path / "pkg" / "sample.py"
    src.parent.mkdir()
    src.write_text("""line1\n\nline3\n""")

    xml = f"""
    <coverage>
      <packages><package><classes>
        <class filename="{src}">
          <lines>
            <line number="1" hits="0" />
            <line number="2" hits="1" />
            <line number="3" hits="0" branch="true" condition-coverage="50% (1/2)">
              <conditions>
                <condition number="0" type="jump" coverage="0%" />
                <condition number="1" type="jump" coverage="100%" />
              </conditions>
            </line>
          </lines>
        </class>
      </classes></package></packages>
    </coverage>
    """

    root = _build_root(xml)
    dataset = CoverageDataset.from_roots([root], base_path=tmp_path)

    files = list(dataset.iter_files())
    assert len(files) == 1
    file_cov = files[0]
    assert file_cov.path == src.resolve()
    assert file_cov.uncovered_lines() == [1, 3]

    sections = build_lines(dataset)
    assert len(sections) == 1
    assert sections[0].file == src.resolve()
    assert sections[0].ranges == [(1, 3)]

    rows, totals = build_summary(dataset)
    expected_path = dataset.display_path(src.resolve())
    assert rows == [(expected_path, 3, 1, 2, 2, 1, 1)]
    assert totals == (3, 1, 2, 1)


@pytest.mark.parametrize(
    ("mode", "expected_counts"),
    [
        (BranchMode.MISSING_ONLY, [0]),
        (BranchMode.PARTIAL, [0]),
        (BranchMode.ALL, [0, 100]),
    ],
)
def test_build_branches_modes(tmp_path: Path, mode: BranchMode, expected_counts: list[int]) -> None:
    src = tmp_path / "sample.py"
    src.write_text("""def f(x):\n    if x:\n        return 1\n    return 0\n""")

    xml = f"""
    <coverage>
      <packages><package><classes>
        <class filename="{src}">
          <lines>
            <line number="2" hits="1" branch="true" condition-coverage="50% (1/2)">
              <conditions>
                <condition number="0" type="jump" coverage="0%" />
                <condition number="1" type="jump" coverage="100%" />
              </conditions>
            </line>
          </lines>
        </class>
      </classes></package></packages>
    </coverage>
    """

    dataset = CoverageDataset.from_roots([_build_root(xml)], base_path=tmp_path)
    gaps = build_branches(dataset, mode=mode)
    assert len(gaps) == 1
    cov = [cond.coverage for cond in gaps[0].conditions]
    assert cov == expected_counts


def test_build_branches_invalid_mode(tmp_path: Path) -> None:
    src = tmp_path / "sample.py"
    src.write_text("pass\n")
    xml = f"""
    <coverage><packages><package><classes>
      <class filename="{src}"><lines><line number="1" hits="0" /></lines></class>
    </classes></package></packages></coverage>
    """
    dataset = CoverageDataset.from_roots([_build_root(xml)], base_path=tmp_path)
    with pytest.raises(ValueError, match="mode must be one of"):
        build_branches(dataset, mode="oops")


def test_build_diff_sections(tmp_path: Path) -> None:
    src = tmp_path / "sample.py"
    src.write_text("print('hi')\n")

    xml_base = f"""
    <coverage><packages><package><classes>
      <class filename="{src}">
        <lines>
          <line number="1" hits="0" />
          <line number="2" hits="1" />
        </lines>
      </class>
    </classes></package></packages></coverage>
    """
    xml_cur = f"""
    <coverage><packages><package><classes>
      <class filename="{src}">
        <lines>
          <line number="1" hits="1" />
          <line number="2" hits="0" />
        </lines>
      </class>
    </classes></package></packages></coverage>
    """

    base = CoverageDataset.from_roots([_build_root(xml_base)], base_path=tmp_path)
    cur = CoverageDataset.from_roots([_build_root(xml_cur)], base_path=tmp_path)

    diff = build_diff(base, cur)
    assert [sec.ranges for sec in diff["new"]] == [[(2, 2)]]
    assert [sec.ranges for sec in diff["resolved"]] == [[(1, 1)]]


def test_build_dataset_rejects_invalid_root() -> None:
    root = ElementTree.fromstring("<invalid/>")
    dataset = CoverageDataset()
    with pytest.raises(InvalidCoverageXMLError, match="Invalid root element"):
        dataset.add_root(root)


def test_build_dataset_helper(tmp_path: Path) -> None:
    src = tmp_path / "sample.py"
    src.write_text("print('hi')\n")
    xml = f"""
    <coverage><packages><package><classes>
      <class filename="{src}"><lines><line number="1" hits="0" /></lines></class>
    </classes></package></packages></coverage>
    """
    dataset = build_dataset(_build_root(xml), base_path=tmp_path)
    sections = build_lines(dataset)
    assert len(sections) == 1
    assert sections[0].ranges == [(1, 1)]
