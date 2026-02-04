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

    # Default output is summary-only now (tree view), so file is basename under its dir.
    assert "pkg/" in result.output
    assert "mod.py" in result.output
    # Summary-only output reports counts, not specific line numbers.
    assert "Uncov" in result.output
    assert "1" in result.output  # uncovered lines/ranges count appears


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
    assert "pkg/" in result.output
    assert "mod.py" in result.output


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


def test_cli_report_max_depth_optional_unlimited(project) -> None:
    from tests.conftest import write_cobertura_xml, write_source_file

    root = project["root"]
    write_source_file(root, "pkg/sub/a.py", "def g():\n    return 1\n")

    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[
            {"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]},
            {"filename": "pkg/sub/a.py", "lines": [{"number": 1, "hits": 0}]},
        ],
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["report", str(cov), "--no-lines", "--no-branches"])  # summary only
    assert result.exit_code == 0, result.output

    # With no --max-depth, we should expand into pkg/sub/ somewhere.
    # Depending on your tree labels, either "sub/" rollup or "a.py" appears under it.
    assert "sub/" in result.output or "a.py" in result.output


def test_cli_report_max_depth_1_top_level_only(project) -> None:
    from tests.conftest import write_cobertura_xml, write_source_file

    root = project["root"]
    write_source_file(root, "pkg/sub/a.py", "def g():\n    return 1\n")

    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[
            {"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]},
            {"filename": "pkg/sub/a.py", "lines": [{"number": 1, "hits": 0}]},
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["report", str(cov), "--no-lines", "--no-branches", "--max-depth", "1"],
    )
    assert result.exit_code == 0, result.output

    # Top-level rollup "pkg/" should be visible (or at least present as a directory row)
    assert "pkg/" in result.output

    # But deeper "sub/" should NOT be expanded at depth=1
    assert "sub/" not in result.output
    # and the file under it should not show
    assert "a.py" not in result.output
