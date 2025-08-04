from collections.abc import Callable
from pathlib import Path

from click.testing import CliRunner

from showcov import __version__
from showcov.cli import cli

# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #


def _run(runner: CliRunner, args: list[str]) -> tuple[int, str]:
    """Invoke the CLI and return *(exit_code, output)* for convenience."""
    result = runner.invoke(cli, args)
    return result.exit_code, result.output


# --------------------------------------------------------------------------- #
# tests                                                                       #
# --------------------------------------------------------------------------- #


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
    assert file_a.as_posix() in out
    assert file_b.as_posix() not in out

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
    assert str(file_a) in out
    assert str(file_b) not in out

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
    assert "No uncovered lines found" in out


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
    assert src.as_posix() in out


def test_cli_exit_codes(cli_runner: CliRunner, tmp_path: Path) -> None:
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<coverage>", encoding="utf-8")  # malformed

    code, _ = _run(cli_runner, ["show", "--cov", str(bad_xml), "--format", "human"])
    assert code == 65
