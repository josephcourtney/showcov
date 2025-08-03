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
    result = cli_runner.invoke(main, ["--xml-file", str(xml_file), str(file_a)])
    assert result.exit_code == 0
    assert str(file_a) in result.output
    assert str(file_b) not in result.output

    # include directory but exclude file_b
    result = cli_runner.invoke(
        main,
        ["--xml-file", str(xml_file), str(tmp_path), "--exclude", "*b.py"],
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
