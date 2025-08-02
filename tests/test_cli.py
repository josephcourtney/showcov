from pathlib import Path

from click.testing import CliRunner

from showcov.cli import main


def _build_xml(mapping: dict[Path, list[int]]) -> str:
    classes = []
    for file, lines in mapping.items():
        lines_xml = "".join(f'<line number="{ln}" hits="0"/>' for ln in lines)
        classes.append(f'<class filename="{file}"><lines>{lines_xml}</lines></class>')
    inner = "".join(classes)
    return f"<coverage><packages><package><classes>{inner}</classes></package></packages></coverage>"


def test_cli_filters_and_output(tmp_path: Path) -> None:
    file_a = tmp_path / "a.py"
    file_a.write_text("a\n")
    file_b = tmp_path / "b.py"
    file_b.write_text("b\n")
    xml_content = _build_xml({file_a: [1], file_b: [1]})
    xml_file = tmp_path / "cov.xml"
    xml_file.write_text(xml_content)

    runner = CliRunner()
    # include only file_a
    result = runner.invoke(main, ["--xml-file", str(xml_file), str(file_a)])
    assert result.exit_code == 0
    assert str(file_a) in result.output
    assert str(file_b) not in result.output

    # include directory but exclude file_b
    result = runner.invoke(
        main,
        ["--xml-file", str(xml_file), str(tmp_path), "--exclude", "*b.py"],
    )
    assert result.exit_code == 0
    assert str(file_a) in result.output
    assert str(file_b) not in result.output

    # write json output to file
    out_file = tmp_path / "out.json"
    result = runner.invoke(
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
