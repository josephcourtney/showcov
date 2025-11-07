from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from showcov.cli import cli

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(slots=True)
class ExampleCoverageData:
    coverage_xml: Path
    logic_file: Path
    expected_ranges: set[tuple[int, int]]
    branch_lines: dict[str, int]


def _make_line_map(source: str, labels: dict[str, str]) -> dict[str, int]:
    lines = source.splitlines()
    mapping: dict[str, int] = {}
    for key, needle in labels.items():
        for idx, line in enumerate(lines, start=1):
            if line.strip() == needle.strip():
                mapping[key] = idx
                break
        else:  # pragma: no cover - defensive
            msg = f"Unable to find line containing: {needle}"
            raise AssertionError(msg)
    return mapping


def _run_pytest_with_coverage(project_root: Path, *, env: dict[str, str]) -> None:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "--cov=examplepkg",
        "--cov-branch",
        "--cov-report=xml",
        "-q",
    ]
    proc = subprocess.run(
        cmd,
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:  # pragma: no cover - debug helper
        msg = f"Example project pytest run failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        raise RuntimeError(msg)


@pytest.fixture(scope="session")
def example_coverage_project(tmp_path_factory: pytest.TempPathFactory) -> ExampleCoverageData:
    project_root = tmp_path_factory.mktemp("example_project")
    src_dir = project_root / "src" / "examplepkg"
    tests_dir = project_root / "tests"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    logic_text = (
        textwrap.dedent(
            """
        from __future__ import annotations

        def compute(value: int) -> str:
            if value > 10:
                return "high"
            elif value == 10:
                return "ten"
            return "low"


        def gate(flag: bool) -> str:
            if flag:
                return "flag"
            return "no-flag"


        def never_called(choice: str) -> str:
            if choice == "x":
                return "x"
            if choice == "y":
                return "y"
            return "other"


        def unreachable(toggle: bool) -> str:
            if toggle:
                return "toggled"
            return "idle"
        """
        ).strip()
        + "\n"
    )
    logic_file = src_dir / "logic.py"
    logic_file.write_text(logic_text, encoding="utf-8")
    (src_dir / "__init__.py").write_text("__all__ = ['compute', 'gate']\n", encoding="utf-8")

    tests_code = (
        textwrap.dedent(
            """
        from examplepkg.logic import compute, gate


        def test_compute_high() -> None:
            assert compute(42) == "high"


        def test_gate_false() -> None:
            assert gate(False) == "no-flag"
        """
        ).strip()
        + "\n"
    )
    (tests_dir / "test_logic.py").write_text(tests_code, encoding="utf-8")

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(project_root / "src") + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )

    _run_pytest_with_coverage(project_root, env=env)

    coverage_xml = project_root / "coverage.xml"
    if not coverage_xml.exists():  # pragma: no cover - defensive
        msg = "coverage.xml was not produced by the example project"
        raise AssertionError(msg)

    line_map = _make_line_map(
        logic_text,
        {
            "compute_if": "if value > 10:",
            "compute_elif": "elif value == 10:",
            "compute_low": 'return "low"',
            "gate_if": "if flag:",
            "gate_return": 'return "flag"',
            "never_if_x": 'if choice == "x":',
            "never_return": 'return "other"',
            "unreachable_if": "if toggle:",
            "unreachable_return": 'return "idle"',
        },
    )

    expected_ranges: set[tuple[int, int]] = {
        (line_map["compute_elif"], line_map["compute_low"]),
        (line_map["gate_return"], line_map["gate_return"]),
        (line_map["never_if_x"], line_map["never_return"]),
        (line_map["unreachable_if"], line_map["unreachable_return"]),
    }

    branch_lines = {
        "compute_if": line_map["compute_if"],
        "compute_elif": line_map["compute_elif"],
        "gate_if": line_map["gate_if"],
        "unreachable_if": line_map["unreachable_if"],
    }

    return ExampleCoverageData(
        coverage_xml=coverage_xml,
        logic_file=logic_file,
        expected_ranges=expected_ranges,
        branch_lines=branch_lines,
    )


def test_e2e_show_reports_expected_ranges(
    cli_runner: Any,
    example_coverage_project: ExampleCoverageData,
) -> None:
    result = cli_runner.invoke(
        cli,
        [
            "--cov",
            str(example_coverage_project.coverage_xml),
            "--sections",
            "lines",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    lines_section = data["sections"]["lines"]
    logic_entry = next(file for file in lines_section["files"] if file.get("file", "").endswith("logic.py"))
    ranges = {(item["start"], item["end"]) for item in logic_entry["uncovered"]}
    assert example_coverage_project.expected_ranges <= ranges


def test_e2e_branches_report_partial_and_missing(
    cli_runner: Any,
    example_coverage_project: ExampleCoverageData,
) -> None:
    result = cli_runner.invoke(
        cli,
        [
            "--cov",
            str(example_coverage_project.coverage_xml),
            "--sections",
            "branches",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    gaps = data["sections"]["branches"]["gaps"]
    logic_lines = {entry["line"]: entry for entry in gaps if entry.get("file", "").endswith("logic.py")}
    for line in example_coverage_project.branch_lines.values():
        assert line in logic_lines
        assert all(
            cond.get("coverage") is None or cond.get("coverage") < 100
            for cond in logic_lines[line]["conditions"]
        )


def test_e2e_summary_matches_example_project(
    cli_runner: Any,
    example_coverage_project: ExampleCoverageData,
) -> None:
    result = cli_runner.invoke(
        cli,
        [
            "--cov",
            str(example_coverage_project.coverage_xml),
            "--sections",
            "summary",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    summary = data["sections"]["summary"]
    logic_entry = next(file for file in summary["files"] if file.get("file", "").endswith("logic.py"))
    totals = summary["totals"]["statements"]
    assert logic_entry["statements"]["missed"] >= 1
    assert totals["missed"] >= logic_entry["statements"]["missed"]
