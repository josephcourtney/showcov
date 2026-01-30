from __future__ import annotations

import json
import os
import pathlib

from click.testing import CliRunner

from showcov.cli import main


def test_cli_report_default_auto_format_non_tty(project) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]
    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[{"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]}],
    )

    runner = CliRunner()
    result = runner.invoke(main, ["report", str(cov)])
    assert result.exit_code == 0, result.output

    # In non-TTY, auto => rg output
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
        result = runner.invoke(main, ["report"])
    finally:
        os.chdir(cwd)

    assert result.exit_code == 0, result.output
    assert "pkg/mod.py" in result.output


def test_cli_report_sections_summary_only(project) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]
    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[{"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]}],
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["report", str(cov), "--format", "human", "--branches", "off", "--sections", "summary"]
    )
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
    result = runner.invoke(main, ["report", str(cov), "--fail-under-stmt", "90"])
    assert result.exit_code == 2
    assert "Threshold failed" in result.output


def test_cli_report_format_json_schema_valid(project) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]
    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[{"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]}],
    )

    runner = CliRunner()
    result = runner.invoke(main, ["report", str(cov), "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["tool"]["name"] == "showcov"


def test_cli_diff_smoke(project) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]
    base = write_cobertura_xml(
        root, "base.xml", classes=[{"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]}]
    )
    cur = write_cobertura_xml(
        root, "cur.xml", classes=[{"filename": "pkg/mod.py", "lines": [{"number": 4, "hits": 0}]}]
    )

    runner = CliRunner()
    result = runner.invoke(main, ["diff", str(base), str(cur), "--format", "rg"])
    assert result.exit_code == 0, result.output
    assert "New" in result.output
    assert "Resolved" in result.output
