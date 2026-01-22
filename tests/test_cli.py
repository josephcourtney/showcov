from __future__ import annotations

import json
from typing import TYPE_CHECKING

from click.testing import CliRunner

from showcov.cli import main

if TYPE_CHECKING:
    from pathlib import Path


def test_cli_json_output(project: dict[str, Path]) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]
    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[{"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]}],
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--cov",
            str(cov),
            "--sections",
            "lines,summary",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["tool"]["name"] == "showcov"
    assert "lines" in payload["sections"]
    assert "summary" in payload["sections"]


def test_cli_threshold_failure_exit_code_2(project: dict[str, Path]) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]
    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[{"filename": "pkg/mod.py", "lines": [{"number": 1, "hits": 1}, {"number": 2, "hits": 0}]}],
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--cov",
            str(cov),
            "--sections",
            "lines,summary",
            "--format",
            "json",
            "--threshold",
            "statements=90",
        ],
    )
    assert result.exit_code == 2
    assert "Threshold failed" in result.output


def test_cli_include_exclude_filters(project: dict[str, Path]) -> None:
    from tests.conftest import write_cobertura_xml

    root = project["root"]
    cov = write_cobertura_xml(
        root,
        "coverage.xml",
        classes=[
            {"filename": "pkg/mod.py", "lines": [{"number": 2, "hits": 0}]},
            {"filename": "pkg/other.py", "lines": [{"number": 1, "hits": 0}]},
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--cov",
            str(cov),
            "--sections",
            "lines",
            "--format",
            "json",
            "--include",
            "pkg/mod.py",
        ],
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    files = payload["sections"]["lines"]["files"]
    assert len(files) == 1
    assert files[0]["file"] == "pkg/mod.py"


def test_cli_include_existing_source_file_is_not_treated_as_pattern_file() -> None:
    from pathlib import Path

    from tests.conftest import write_cobertura_xml, write_source_file

    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()

        # Create real source files on disk.
        write_source_file(root, "pkg/mod.py", "def f():\n    return 1\n")
        write_source_file(root, "pkg/other.py", "def g():\n    return 2\n")

        cov = write_cobertura_xml(
            root,
            "coverage.xml",
            classes=[
                {"filename": "pkg/mod.py", "lines": [{"number": 1, "hits": 0}]},
                {"filename": "pkg/other.py", "lines": [{"number": 1, "hits": 0}]},
            ],
        )

        result = runner.invoke(
            main,
            [
                "--cov",
                str(cov),
                "--sections",
                "lines",
                "--format",
                "json",
                "--include",
                "pkg/mod.py",
            ],
        )
        assert result.exit_code == 0, result.output

        payload = json.loads(result.output)
        files = payload["sections"]["lines"]["files"]
        assert len(files) == 1
        assert files[0]["file"] == "pkg/mod.py"
