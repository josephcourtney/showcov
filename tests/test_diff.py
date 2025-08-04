from __future__ import annotations

import json
from typing import TYPE_CHECKING

from showcov.cli import cli
from showcov.core import diff_uncovered_lines

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from click.testing import CliRunner


def test_diff_uncovered_lines(coverage_xml_file: Callable[..., Path], tmp_path: Path) -> None:
    a = tmp_path / "a.py"
    a.write_text("a\n")
    b = tmp_path / "b.py"
    b.write_text("b\n")

    baseline = coverage_xml_file({a: [1], b: [1]}, filename="base.xml")
    current = coverage_xml_file({a: [1, 2]}, filename="curr.xml")

    new_sections, resolved_sections = diff_uncovered_lines(baseline, current)

    assert [(sec.file, sec.ranges) for sec in new_sections] == [(a.resolve(), [(2, 2)])]
    assert [(sec.file, sec.ranges) for sec in resolved_sections] == [(b.resolve(), [(1, 1)])]


def test_cli_diff_json(cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path) -> None:
    a = tmp_path / "a.py"
    a.write_text("a\n")
    b = tmp_path / "b.py"
    b.write_text("b\n")

    baseline = coverage_xml_file({a: [1], b: [1]}, filename="base.xml")
    current = coverage_xml_file({a: [1, 2]}, filename="curr.xml")

    result = cli_runner.invoke(cli, ["diff", str(baseline), str(current), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["new"] == [{"file": a.name, "uncovered": [{"start": 2, "end": 2}]}]
    assert data["resolved"] == [{"file": b.name, "uncovered": [{"start": 1, "end": 1}]}]
