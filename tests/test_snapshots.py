import json
from collections.abc import Callable
from pathlib import Path

from click.testing import CliRunner

from showcov.cli import cli
from showcov.core import Report, build_sections
from showcov.core.types import Format
from showcov.output.base import OutputMeta
from showcov.output.report_render import render_report


def _build_sections() -> list:
    src = Path("tests/data/sample.py")
    return build_sections({src: [2, 4, 5]})


def test_json_output_snapshot() -> None:
    sections = _build_sections()
    meta = OutputMeta(
        coverage_xml=Path("coverage.xml"),
        with_code=True,
        color=False,
        show_paths=True,
        show_line_numbers=True,
        context_before=1,
        context_after=1,
    )
    files = [
        sec.to_dict(
            with_code=meta.with_code,
            context_before=meta.context_before,
            context_after=meta.context_after,
            base=meta.coverage_xml.parent,
            show_file=meta.show_paths,
            show_line_numbers=meta.show_line_numbers,
        )
        for sec in sections
    ]
    report = Report(
        meta={
            "environment": {"coverage_xml": meta.coverage_xml.as_posix()},
            "options": {
                "context_lines": meta.context_lines,
                "with_code": meta.with_code,
                "show_paths": meta.show_paths,
                "show_line_numbers": meta.show_line_numbers,
                "aggregate_stats": False,
                "file_stats": False,
            },
        },
        sections={"lines": {"files": files}},
        attachments={"lines": {"sections": sections}},
    )
    json_out = render_report(report, Format.JSON, meta)
    expected_text = Path("tests/snapshots/json_output.json").read_text(encoding="utf-8")
    actual = json.loads(json_out)
    expected = json.loads(expected_text)

    actual["tool"]["version"] = "IGNORED"
    expected["tool"]["version"] = "IGNORED"
    actual["meta"]["environment"]["coverage_xml"] = "coverage.xml"
    expected["meta"]["environment"]["coverage_xml"] = "coverage.xml"

    assert actual == expected


def test_llm_prompt_snapshot() -> None:
    sections = _build_sections()
    meta = OutputMeta(
        coverage_xml=Path("coverage.xml"),
        with_code=True,
        color=False,
        show_paths=True,
        show_line_numbers=True,
        context_before=1,
        context_after=1,
    )
    files = [
        sec.to_dict(
            with_code=meta.with_code,
            context_before=meta.context_before,
            context_after=meta.context_after,
            base=meta.coverage_xml.parent,
            show_file=meta.show_paths,
            show_line_numbers=meta.show_line_numbers,
        )
        for sec in sections
    ]
    report = Report(
        meta={
            "environment": {"coverage_xml": meta.coverage_xml.as_posix()},
            "options": {
                "context_lines": meta.context_lines,
                "with_code": meta.with_code,
                "show_paths": meta.show_paths,
                "show_line_numbers": meta.show_line_numbers,
                "aggregate_stats": False,
                "file_stats": False,
            },
        },
        sections={"lines": {"files": files}},
        attachments={"lines": {"sections": sections}},
    )
    json_out = render_report(report, Format.JSON, meta)
    data = json.loads(json_out)
    data["tool"]["version"] = "IGNORED"
    data["meta"]["environment"]["coverage_xml"] = "coverage.xml"
    prompt = (
        "Please review the following coverage data and suggest tests:\n"
        f"{json.dumps(data, indent=2, sort_keys=True)}\n"
    )

    expected_text = Path("tests/snapshots/llm_prompt.txt").read_text(encoding="utf-8")
    expected_data = json.loads(expected_text.split(":\n", 1)[1])
    expected_data["tool"]["version"] = "IGNORED"
    expected_data["meta"]["environment"]["coverage_xml"] = "coverage.xml"
    expected_prompt = (
        "Please review the following coverage data and suggest tests:\n"
        f"{json.dumps(expected_data, indent=2, sort_keys=True)}\n"
    )

    assert prompt.rstrip("\n") == expected_prompt.rstrip("\n")


def test_cli_json_snapshot(
    cli_runner: CliRunner, coverage_xml_file: Callable[..., Path], tmp_path: Path
) -> None:
    src = tmp_path / "file.py"
    src.write_text("print('hi')\n")
    xml = coverage_xml_file({src: [1]})

    result = cli_runner.invoke(
        cli,
        [
            "--cov",
            str(xml),
            "--sections",
            "lines,summary",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0

    actual = json.loads(result.output)
    expected_path = Path("tests/snapshots/cli_report.json")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))

    actual["tool"]["version"] = "IGNORED"
    expected["tool"]["version"] = "IGNORED"
    actual["meta"]["environment"]["coverage_xml"] = "IGNORED"
    expected["meta"]["environment"]["coverage_xml"] = "IGNORED"

    assert actual == expected
