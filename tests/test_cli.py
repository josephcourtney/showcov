from collections.abc import Callable
from pathlib import Path

from click.testing import CliRunner

from showcov.cli import main


def test_cli_filters_and_output(
    tmp_path: Path, cli_runner: CliRunner, coverage_xml_file: Callable[..., Path]
) -> None:
    file_a = tmp_path / "a.py"
    file_a.write_text("a\n")
    file_b = tmp_path / "b.py"
    file_b.write_text("b\n")
    xml_file = coverage_xml_file({file_a: [1], file_b: [1]})

    # include only file_a
    result = cli_runner.invoke(main, ["--xml-file", str(xml_file), str(file_a), "--format", "human"])
    assert result.exit_code == 0
    assert str(file_a) in result.output
    assert str(file_b) not in result.output

    # include directory but exclude file_b
    result = cli_runner.invoke(
        main,
        ["--xml-file", str(xml_file), str(tmp_path), "--exclude", "*b.py", "--format", "human"],
    )
    assert result.exit_code == 0
    assert str(file_a) in result.output
    assert str(file_b) not in result.output

    # write json output to file
    out_file = tmp_path / "out.json"
    result = cli_runner.invoke(
        main,
        [
            "--xml-file",
            str(xml_file),
            str(tmp_path),
            "--format",
            "json",
            "--output",
            str(out_file),
        ],
    )
    assert result.exit_code == 0
    assert out_file.read_text(encoding="utf-8").strip().startswith("{")


def test_cli_version_flag(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "showcov, version" in result.output


def test_cli_disables_color_flag(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print(1)\n")
    xml = coverage_xml_file({src: [1]})

    result = cli_runner.invoke(
        main,
        ["--xml-file", str(xml), str(src), "--no-color", "--format", "human"],
    )
    assert result.exit_code == 0
    assert "\x1b[" not in result.output  # ANSI escape sequences absent


def test_cli_disables_color_when_not_tty(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print(1)\n")
    xml = coverage_xml_file({src: [1]})

    # Simulate piping by capturing output explicitly
    result = cli_runner.invoke(
        main,
        ["--xml-file", str(xml), str(src), "--format", "human"],
        # colorama disables colors when isatty=False
        # click.testing.CliRunner captures output, which behaves like non-TTY
    )
    assert result.exit_code == 0
    assert "\x1b[" not in result.output


def test_cli_summary_only_and_stats(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    file_a = tmp_path / "a.py"
    file_a.write_text("a\n")
    xml = coverage_xml_file({file_a: [1]})
    result = cli_runner.invoke(
        main,
        ["--xml-file", str(xml), str(tmp_path), "--summary-only", "--stats", "--format", "human"],
    )
    assert result.exit_code == 0
    assert result.output.splitlines()[0] == file_a.as_posix()
    assert "files with uncovered lines" in result.output


def test_cli_format_auto_json(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "f.py"
    src.write_text("a\n")
    xml = coverage_xml_file({src: [1]})
    result = cli_runner.invoke(main, ["--xml-file", str(xml), str(src)])
    assert result.exit_code == 0
    assert result.output.strip().startswith("{")


def test_cli_invalid_format_suggestion(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "f.py"
    src.write_text("a\n")
    xml = coverage_xml_file({src: [1]})
    result = cli_runner.invoke(main, ["--xml-file", str(xml), str(src), "--format", "jsn"])
    assert result.exit_code != 0
    assert "Unsupported format: 'jsn'. Did you mean 'json'?" in result.output


def test_cli_list_files(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "f.py"
    src.write_text("a\n")
    xml = coverage_xml_file({src: [1]})
    result = cli_runner.invoke(main, ["--xml-file", str(xml), str(tmp_path), "--list-files"])
    assert result.exit_code == 0
    assert result.output.strip() == src.as_posix()


def test_cli_no_uncovered_message(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "f.py"
    src.write_text("a\n")
    xml = coverage_xml_file({src: [1]})
    # Pass non-matching path
    result = cli_runner.invoke(main, ["--xml-file", str(xml), "nonexistent", "--format", "human"])
    assert result.exit_code == 0
    assert "No uncovered lines found" in result.output


def test_cli_glob_patterns(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "f.py"
    src.write_text("a\n")
    xml = coverage_xml_file({src: [1]})
    result = cli_runner.invoke(main, ["--xml-file", str(xml), str(tmp_path / "*.py"), "--format", "human"])
    assert result.exit_code == 0
    assert src.as_posix() in result.output


def test_cli_exit_codes(cli_runner: CliRunner, tmp_path: Path) -> None:
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<coverage>", encoding="utf-8")  # malformed
    result = cli_runner.invoke(main, ["--xml-file", str(bad_xml), "--format", "human"])
    assert result.exit_code == 65
