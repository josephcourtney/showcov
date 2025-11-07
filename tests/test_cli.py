import json
from collections.abc import Callable
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from showcov import __version__
from showcov.cli import EXIT_DATAERR, EXIT_GENERIC, _resolve_context_option, cli

# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #


def _run(runner: CliRunner, args: list[str]) -> tuple[int, str]:
    """Invoke the CLI and return *(exit_code, output)* for convenience."""
    result = runner.invoke(cli, args)
    return result.exit_code, result.output


def _write_summary_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    src_a = tmp_path / "a.py"
    src_b = tmp_path / "b.py"
    for path in (src_a, src_b):
        path.write_text("x = 1\n")
    xml = tmp_path / "cov.xml"
    xml.write_text(
        (
            "<coverage>"
            "<packages><package><classes>"
            f'<class filename="{src_a}"><lines>'
            '<line number="1" hits="1" branch="true" condition-coverage="100% (2/2)"/>'
            "</lines></class>"
            f'<class filename="{src_b}"><lines>'
            '<line number="1" hits="0" branch="true" condition-coverage="50% (1/2)"/>'
            "</lines></class>"
            "</classes></package></packages>"
            "</coverage>"
        ),
        encoding="utf-8",
    )
    return xml, src_a, src_b


# --------------------------------------------------------------------------- #
# tests                                                                       #
# --------------------------------------------------------------------------- #


def test_cli_no_options(cli_runner: CliRunner) -> None:
    code, _out = _run(cli_runner, [])
    assert code == 66


def test_cli_filters_and_output(
    tmp_path: Path,
    cli_runner: CliRunner,
    coverage_xml_file: Callable[..., Path],
) -> None:
    file_a = tmp_path / "a.py"
    file_a.write_text("a\n")
    file_b = tmp_path / "b.py"
    file_b.write_text("b\n")
    xml_file = coverage_xml_file({file_a: [1], file_b: [1]})

    # include only file_a
    code, out = _run(
        cli_runner,
        ["show", "--cov", str(xml_file), str(file_a), "--format", "human"],
    )
    assert code == 0
    assert file_a.name in out
    assert file_b.name not in out

    # include directory but exclude file_b
    code, out = _run(
        cli_runner,
        [
            "show",
            "--cov",
            str(xml_file),
            str(tmp_path),
            "--exclude",
            "*b.py",
            "--format",
            "human",
        ],
    )
    assert code == 0
    assert file_a.name in out
    assert file_b.name not in out

    # write json output to file
    out_file = tmp_path / "out.json"
    code, _ = _run(
        cli_runner,
        [
            "show",
            "--cov",
            str(xml_file),
            str(tmp_path),
            "--format",
            "json",
            "--output",
            str(out_file),
        ],
    )
    assert code == 0
    assert out_file.read_text(encoding="utf-8").lstrip().startswith("{")


def test_cli_version_flag(cli_runner: CliRunner) -> None:
    code, out = _run(cli_runner, ["--version"])
    assert code == 0
    assert out.strip() == __version__


def test_cli_disables_color_flag(
    cli_runner: CliRunner,
    coverage_xml_file: Callable[..., Path],
    tmp_path: Path,
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print(1)\n")
    xml = coverage_xml_file({src: [1]})

    code, out = _run(
        cli_runner,
        ["show", "--cov", str(xml), str(src), "--no-color", "--format", "human"],
    )
    assert code == 0
    assert "\x1b[" not in out  # ANSI sequences absent


def test_cli_disables_color_when_not_tty(
    cli_runner: CliRunner,
    coverage_xml_file: Callable[..., Path],
    tmp_path: Path,
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print(1)\n")
    xml = coverage_xml_file({src: [1]})

    code, out = _run(cli_runner, ["show", "--cov", str(xml), str(src), "--format", "human"])
    assert code == 0
    assert "\x1b[" not in out  # colorama disables colours when output captured


def test_cli_forces_color_flag(
    cli_runner: CliRunner,
    coverage_xml_file: Callable[..., Path],
    tmp_path: Path,
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print(1)\n")
    xml = coverage_xml_file({src: [1]})

    result = cli_runner.invoke(
        cli,
        ["show", "--cov", str(xml), str(src), "--format", "human", "--color"],
        color=True,
    )
    assert result.exit_code == 0
    assert "\x1b[" in result.output


def test_cli_human_shows_code(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "f.py"
    src.write_text("a = 1\nb = 2\n")
    xml = coverage_xml_file({src: [2]})
    code, out = _run(cli_runner, ["show", "--cov", str(xml), str(src), "--code", "--format", "human"])
    assert code == 0
    assert "b = 2" in out


def test_cli_line_tags(cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path) -> None:
    src = tmp_path / "f.py"
    src.write_text("def g():\n    return 1  # pragma: no cover\n")
    xml = coverage_xml_file({src: [2]})
    code, out = _run(cli_runner, ["show", "--cov", str(xml), str(src), "--code", "--format", "human"])
    assert code == 0
    assert "[no-cover]" in out


def test_cli_line_tag_abstractmethod(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "f.py"
    src.write_text(
        "from abc import ABC, abstractmethod\n"
        "class A(ABC):\n"
        "    @abstractmethod\n"
        "    def f(self):\n"
        "        pass\n"
    )
    xml = coverage_xml_file({src: [4, 5]})
    code, out = _run(cli_runner, ["show", "--cov", str(xml), str(src), "--code", "--format", "human"])
    assert code == 0
    assert "[abstractmethod]" in out


def test_context_option_error() -> None:
    with pytest.raises(click.BadParameter):
        _resolve_context_option("bad,value")


def test_output_path_error(
    tmp_path: Path, cli_runner: CliRunner, coverage_xml_file: Callable[..., Path]
) -> None:
    src = tmp_path / "f.py"
    src.write_text("a\n")
    xml = coverage_xml_file({src: [1]})
    bad = tmp_path / "missing" / "out.txt"
    code, out = _run(
        cli_runner,
        ["show", "--cov", str(xml), str(src), "--format", "human", "--output", str(bad)],
    )
    assert code != 0
    assert "directory does not exist" in out


def test_auto_format_with_output(
    tmp_path: Path, cli_runner: CliRunner, coverage_xml_file: Callable[..., Path]
) -> None:
    src = tmp_path / "f.py"
    src.write_text("a\n")
    xml = coverage_xml_file({src: [1]})
    out_file = tmp_path / "out.txt"
    code, out = _run(
        cli_runner,
        [
            "show",
            "--cov",
            str(xml),
            str(src),
            "--output",
            str(out_file),
        ],
    )
    assert code != 0
    assert "Cannot use --format=auto" in out


def test_cli_format_auto_json(
    cli_runner: CliRunner,
    coverage_xml_file: Callable[..., Path],
    tmp_path: Path,
) -> None:
    src = tmp_path / "f.py"
    src.write_text("a\n")
    xml = coverage_xml_file({src: [1]})

    code, out = _run(cli_runner, ["show", "--cov", str(xml), str(src)])
    assert code == 0
    assert out.lstrip().startswith("{")


def test_cli_format_html(
    cli_runner: CliRunner,
    coverage_xml_file: Callable[..., Path],
    tmp_path: Path,
) -> None:
    src = tmp_path / "f.py"
    src.write_text("a\n")
    xml = coverage_xml_file({src: [1]})

    code, out = _run(
        cli_runner,
        ["show", "--cov", str(xml), str(src), "--format", "html"],
    )
    assert code == 0
    assert out.lstrip().startswith("<html>")


def test_cli_invalid_format_suggestion(
    cli_runner: CliRunner,
    coverage_xml_file: Callable[..., Path],
    tmp_path: Path,
) -> None:
    src = tmp_path / "f.py"
    src.write_text("a\n")
    xml = coverage_xml_file({src: [1]})

    code, out = _run(cli_runner, ["show", "--cov", str(xml), str(src), "--format", "jsn"])
    assert code != 0
    assert "'jsn' is not one of" in out


def test_cli_no_uncovered_message(
    cli_runner: CliRunner,
    coverage_xml_file: Callable[..., Path],
    tmp_path: Path,
) -> None:
    src = tmp_path / "f.py"
    src.write_text("a\n")
    xml = coverage_xml_file({src: [1]})

    # Pass non-matching path
    code, out = _run(cli_runner, ["show", "--cov", str(xml), "nonexistent", "--format", "human"])
    assert code == 0
    assert "No uncovered lines found (all matched files fully covered)" in out


def test_cli_glob_patterns(
    cli_runner: CliRunner,
    coverage_xml_file: Callable[..., Path],
    tmp_path: Path,
) -> None:
    src = tmp_path / "f.py"
    src.write_text("a\n")
    xml = coverage_xml_file({src: [1]})
    pattern = str(tmp_path / "*.py")

    code, out = _run(cli_runner, ["show", "--cov", str(xml), pattern, "--format", "human"])
    assert code == 0
    assert src.name in out


def test_cli_exit_codes(cli_runner: CliRunner, tmp_path: Path) -> None:
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<coverage>", encoding="utf-8")  # malformed

    code, _ = _run(cli_runner, ["show", "--cov", str(bad_xml), "--format", "human"])
    assert code == 65


def test_show_with_malformed_xml_reports_data_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.xml"
    bad.write_text("<not-coverage></not-coverage>", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, ["show", "--cov", str(bad)])
    assert result.exit_code == EXIT_DATAERR
    assert "ERROR: failed to read coverage XML" in result.output


def test_diff_with_malformed_xml_reports_data_error(tmp_path: Path) -> None:
    base = tmp_path / "base.xml"
    cur = tmp_path / "cur.xml"
    base.write_text("<coverage></coverage>", encoding="utf-8")
    cur.write_text("<not-coverage/>", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(base), str(cur)])
    # defused or stdlib parse error or invalid root -> DATAERR
    assert result.exit_code in {EXIT_DATAERR, EXIT_GENERIC}
    assert "ERROR: failed to read coverage XML" in result.output


def test_cli_branches_human(cli_runner: CliRunner, tmp_path: Path) -> None:
    src = tmp_path / "b.py"
    src.write_text("if x:\n    pass\n")
    xml = tmp_path / "cov.xml"
    xml.write_text(
        (
            "<coverage>"
            "<packages><package><classes>"
            f'<class filename="{src}"><lines>'
            '<line number="1" hits="1" branch="true" condition-coverage="50% (1/2)">'
            '<conditions><condition number="0" type="jump" coverage="0%"/></conditions>'
            "</line>"
            "</lines></class>"
            "</classes></package></packages>"
            "</coverage>"
        ),
        encoding="utf-8",
    )
    result = cli_runner.invoke(cli, ["branches", "--cov", str(xml), "--format", "human"])
    assert result.exit_code == 0
    assert "Uncovered Branches" in result.output
    assert "jump#0 (0%)" in result.output


def test_cli_branches_json(cli_runner: CliRunner, tmp_path: Path) -> None:
    src = tmp_path / "b.py"
    src.write_text("if x:\n    pass\n")
    xml = tmp_path / "cov.xml"
    xml.write_text(
        (
            "<coverage>"
            "<packages><package><classes>"
            f'<class filename="{src}"><lines>'
            '<line number="1" hits="1" branch="true" condition-coverage="50% (1/2)">'
            '<conditions><condition number="0" type="jump" coverage="0%"/></conditions>'
            "</line>"
            "</lines></class>"
            "</classes></package></packages>"
            "</coverage>"
        ),
        encoding="utf-8",
    )
    result = cli_runner.invoke(cli, ["branches", "--cov", str(xml), "--format", "json"])
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("[")


def test_cli_branches_handles_missing_branches_attr(cli_runner: CliRunner, tmp_path: Path) -> None:
    src = tmp_path / "b.py"
    src.write_text("if x:\n    pass\n")
    xml = tmp_path / "cov.xml"
    xml.write_text(
        (
            "<coverage>"
            "<packages><package><classes>"
            f'<class filename="{src}"><lines>'
            '<line number="1" hits="1" branch="true" condition-coverage="50% (1/2)" missing-branches="5, 7"/>'
            "</lines></class>"
            "</classes></package></packages>"
            "</coverage>"
        ),
        encoding="utf-8",
    )
    result = cli_runner.invoke(cli, ["branches", "--cov", str(xml)])
    assert result.exit_code == 0
    assert "5, 7" in result.output
    assert "line->" not in result.output


def test_cli_branches_json_handles_missing_branches_attr(cli_runner: CliRunner, tmp_path: Path) -> None:
    src = tmp_path / "b.py"
    src.write_text("if x:\n    pass\n")
    xml = tmp_path / "cov.xml"
    xml.write_text(
        (
            "<coverage>"
            "<packages><package><classes>"
            f'<class filename="{src}"><lines>'
            '<line number="1" hits="1" branch="true" condition-coverage="50% (1/2)" missing-branches="5"/>'
            "</lines></class>"
            "</classes></package></packages>"
            "</coverage>"
        ),
        encoding="utf-8",
    )
    result = cli_runner.invoke(cli, ["branches", "--cov", str(xml), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["conditions"][0] == {"number": 5, "type": "line", "coverage": None}


def test_cli_branches_code_option(cli_runner: CliRunner, tmp_path: Path) -> None:
    src = tmp_path / "b.py"
    src.write_text("if x:\n    pass\n")
    xml = tmp_path / "cov.xml"
    xml.write_text(
        (
            "<coverage>"
            "<packages><package><classes>"
            f'<class filename="{src}"><lines>'
            '<line number="1" hits="1" branch="true" condition-coverage="50% (1/2)" missing-branches="2"/>'
            "</lines></class>"
            "</classes></package></packages>"
            "</coverage>"
        ),
        encoding="utf-8",
    )
    result = cli_runner.invoke(
        cli,
        [
            "branches",
            "--cov",
            str(xml),
            "--code",
            "--line-numbers",
            "--context",
            "1",
        ],
    )
    assert result.exit_code == 0
    assert "line->" not in result.output
    assert ">    1: if x:" in result.output
    assert "     2:     pass" in result.output


def test_cli_summary_outputs_table(cli_runner: CliRunner, tmp_path: Path) -> None:
    xml, _src_a, _src_b = _write_summary_fixture(tmp_path)
    result = cli_runner.invoke(cli, ["summary", "--cov", str(xml)])
    assert result.exit_code == 0
    out = result.output
    assert "Coverage Report" in out
    assert "a.py" in out
    assert "b.py" in out
    assert "Overall" in out


def test_cli_summary_supports_json_output(cli_runner: CliRunner, tmp_path: Path) -> None:
    xml, src_a, src_b = _write_summary_fixture(tmp_path)
    result = cli_runner.invoke(cli, ["summary", "--cov", str(xml), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert {entry["file"] for entry in data["files"]} == {src_a.name, src_b.name}
    assert data["metadata"]["show_paths"] is True
    assert data["totals"]["statements"]["total"] == 2
    assert data["totals"]["branches"]["miss"] == 1


def test_cli_summary_auto_format_defaults_to_json_when_not_tty(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    xml, _src_a, _src_b = _write_summary_fixture(tmp_path)
    result = cli_runner.invoke(cli, ["summary", "--cov", str(xml), "--format", "auto"])
    assert result.exit_code == 0
    assert json.loads(result.output)["files"]


def test_cli_completions_use_showcov(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli, ["completions", "--shell", "bash"])
    assert result.exit_code == 0
    assert "_SHOWCOV_COMPLETE" in result.output
    assert "showcov" in result.output
