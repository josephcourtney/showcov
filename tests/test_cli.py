from __future__ import annotations

import os
import pathlib

from click.testing import CliRunner

from showcov.entrypoints.cli import cli


def test_cli_report_default_human_output(project) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]
    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[{"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]}],
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["report", str(cov)])
    assert result.exit_code == 0, result.output

    # Default human output contains the uncovered file and line number.
    assert "pkg/mod.py" in result.output
    assert "2" in result.output


def test_cli_report_discovers_coverage_xml_when_omitted(project) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]
    write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[{"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]}],
    )

    runner = CliRunner()
    cwd = pathlib.Path.cwd()
    try:
        os.chdir(root)
        result = runner.invoke(cli, ["report"])
    finally:
        os.chdir(cwd)

    assert result.exit_code == 0, result.output
    assert "pkg/mod.py" in result.output


def test_cli_report_summary_only(project) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]
    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[{"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]}],
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["report", str(cov), "--no-lines", "--no-branches"])
    assert result.exit_code == 0, result.output
    assert "Summary" in result.output
    assert "Uncovered Lines" not in result.output


def test_cli_threshold_failure_exit_code_2(project) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]
    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[{"filename": "pkg/mod.py", "lines": [{"number": 1, "hits": 1}, {"number": 2, "hits": 0}]}],
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["report", str(cov), "--fail-under-stmt", "90"])
    assert result.exit_code == 2
    assert "Threshold failed" in result.output
