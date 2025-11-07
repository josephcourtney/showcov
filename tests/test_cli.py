import json
from collections.abc import Callable
from pathlib import Path
from xml.etree.ElementTree import Element  # noqa: S405

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner

from showcov import __version__
from showcov.cli import EXIT_NOINPUT, EXIT_THRESHOLD, cli
from showcov.core import dataset


def _run(runner: CliRunner, args: list[str]) -> tuple[int, str]:
    result = runner.invoke(cli, args)
    return result.exit_code, result.output


def test_cli_reports_lines_by_default(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print('hi')\n")
    xml = coverage_xml_file({src: [1]})

    code, output = _run(cli_runner, ["--cov", str(xml), "--format", "human"])
    assert code == 0
    assert "Lines" in output
    assert src.name in output


def test_cli_supports_report_alias(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print('hi')\n")
    xml = coverage_xml_file({src: [1]})

    code, output = _run(cli_runner, ["report", "--cov", str(xml), "--format", "json"])
    assert code == 0
    assert output.strip().startswith("{")


def test_cli_requires_diff_base(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print('hi')\n")
    xml = coverage_xml_file({src: [1]})

    result = cli_runner.invoke(cli, ["--cov", str(xml), "--sections", "diff"])
    assert result.exit_code != 0
    assert "--diff-base" in result.output


def test_cli_threshold_failure(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print('hi')\n")
    xml = coverage_xml_file({src: [1]})

    code, output = _run(cli_runner, ["--cov", str(xml), "--threshold", "stmt=100"])
    assert code == EXIT_THRESHOLD
    assert "Threshold failed" in output


def test_cli_writes_json_output(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print('hi')\n")
    xml = coverage_xml_file({src: [1]})
    out_file = tmp_path / "out.json"

    code, output = _run(
        cli_runner,
        ["--cov", str(xml), "--format", "json", "--output", str(out_file)],
    )
    assert code == 0
    assert out_file.read_text(encoding="utf-8").lstrip().startswith("{")
    assert not output


def test_cli_color_flag(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print('hi')\n")
    xml = coverage_xml_file({src: [1]})

    result = cli_runner.invoke(
        cli,
        ["--cov", str(xml), "--format", "human", "--color"],
        color=True,
    )
    assert result.exit_code == 0
    assert "\x1b" in result.output


def test_cli_no_color_flag(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print('hi')\n")
    xml = coverage_xml_file({src: [1]})

    result = cli_runner.invoke(
        cli,
        ["--cov", str(xml), "--format", "human", "--no-color"],
        color=True,
    )
    assert result.exit_code == 0
    assert "\x1b" not in result.output


def test_cli_auto_color_when_tty(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print('hi')\n")
    xml = coverage_xml_file({src: [1]})

    result = cli_runner.invoke(cli, ["--cov", str(xml)], color=True)
    assert result.exit_code == 0
    assert "\x1b" in result.output


def test_cli_sections_json_combo(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print('hi')\n")
    xml = tmp_path / "cov.xml"
    xml.write_text(
        (
            "<coverage>"
            "<packages><package><classes>"
            f'<class filename="{src}"><lines>'
            '<line number="1" hits="0"/>'
            '<line number="2" hits="0" branch="true" condition-coverage="0% (0/2)">'
            '<conditions><condition number="0" type="jump" coverage="0%"/></conditions>'
            "</line>"
            "</lines></class>"
            "</classes></package></packages>"
            "</coverage>"
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(
        cli,
        [
            "--cov",
            str(xml),
            "--sections",
            "lines,branches,summary",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    sections = data["sections"]
    assert set(sections) >= {"lines", "branches", "summary"}


def test_cli_parses_xml_once(
    cli_runner: CliRunner,
    coverage_xml_file: Callable[..., Path],
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print('hi')\n")
    xml = coverage_xml_file({src: [1]})

    calls = 0
    original = dataset.read_coverage_xml_file

    def tracker(path: Path) -> Element | None:
        nonlocal calls
        calls += 1
        return original(path)

    monkeypatch.setattr("showcov.core.dataset.read_coverage_xml_file", tracker)

    code, _ = _run(
        cli_runner,
        [
            "--cov",
            str(xml),
            "--sections",
            "lines,branches,summary",
        ],
    )
    assert code == 0
    assert calls == 1


def test_cli_version_flag(cli_runner: CliRunner) -> None:
    code, output = _run(cli_runner, ["--version"])
    assert code == 0
    assert output.strip().endswith(__version__)


def test_cli_missing_coverage_file(cli_runner: CliRunner, tmp_path: Path) -> None:
    missing = tmp_path / "missing.xml"
    code, output = _run(cli_runner, ["--cov", str(missing)])
    assert code == EXIT_NOINPUT
    assert "ERROR" in output
