import json
from pathlib import Path

import pytest

from showcov.core import build_sections
from showcov.output import (
    FORMATTERS,
    format_html,
    format_human,
    format_json,
    format_markdown,
    format_sarif,
    render_output,
    resolve_formatter,
)
from showcov.output.base import Format, OutputMeta


def test_format_human_respects_color(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    colored_meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=True,
        show_paths=True,
        show_line_numbers=False,
    )
    plain_meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
        show_paths=True,
        show_line_numbers=False,
    )
    colored = format_human(sections, colored_meta)
    plain = format_human(sections, plain_meta)
    assert "\x1b" in colored
    assert "\x1b" not in plain


def test_format_human_outputs_table(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n" * 3)
    sections = build_sections({src: [2, 3]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
        show_paths=True,
        show_line_numbers=False,
    )
    out = format_human(sections, meta)
    assert "File" in out
    assert "Start" in out
    assert "End" in out
    assert "# Lines" in out
    assert "x.py" in out


def test_format_human_no_paths(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
        show_paths=False,
        show_line_numbers=False,
    )
    out = format_human(sections, meta)
    assert "File" not in out
    assert "x.py" not in out


def test_format_human_no_line_numbers(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    meta = OutputMeta(
        context_lines=0,
        with_code=True,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
        show_paths=True,
        show_line_numbers=False,
    )
    out = format_human(sections, meta)
    assert "1:" not in out


def test_format_registry() -> None:
    assert set(FORMATTERS) == {
        Format.HUMAN,
        Format.HTML,
        Format.JSON,
        Format.MARKDOWN,
        Format.SARIF,
    }


def test_resolve_formatter() -> None:
    fmt, formatter = resolve_formatter("json", is_tty=False)
    assert fmt is Format.JSON
    assert formatter is FORMATTERS[Format.JSON]


def test_format_suggestion() -> None:
    with pytest.raises(ValueError, match="Did you mean 'json'"):
        resolve_formatter("jsn", is_tty=False)


def test_format_markdown(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    meta = OutputMeta(
        context_lines=0,
        with_code=True,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
        show_paths=True,
        show_line_numbers=True,
    )
    out = format_markdown(sections, meta)
    assert "<details>" in out
    assert "```" in out


def test_format_html(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
        show_paths=True,
        show_line_numbers=False,
    )
    out = format_html(sections, meta)
    assert "<html>" in out
    assert "x.py" in out


def test_markdown_no_code(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
        show_paths=True,
        show_line_numbers=True,
    )
    out = format_markdown(sections, meta)
    assert "```" not in out


def test_file_stats_summary(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
        show_paths=True,
        show_line_numbers=False,
    )
    out = render_output(
        sections,
        Format.HUMAN,
        FORMATTERS[Format.HUMAN],
        meta,
        file_stats=True,
    )
    assert "x.py: 1 uncovered (100%)" in out


def test_json_stats(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
        show_paths=True,
        show_line_numbers=True,
    )
    out = render_output(
        sections,
        Format.JSON,
        FORMATTERS[Format.JSON],
        meta,
        aggregate_stats=True,
        file_stats=True,
    )
    data = json.loads(out)
    assert data["summary"]["uncovered"] == 1
    assert data["files"][0]["counts"]["uncovered"] == 1


def test_json_no_paths(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
        show_paths=False,
        show_line_numbers=True,
    )
    out = format_json(sections, meta)
    data = json.loads(out)
    assert "file" not in data["files"][0]


def test_format_sarif(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
        show_paths=True,
        show_line_numbers=False,
    )
    out = format_sarif(sections, meta)
    data = json.loads(out)
    assert data["version"] == "2.1.0"
    assert data["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]["startLine"] == 1


def test_json_includes_tags(tmp_path: Path) -> None:
    src = tmp_path / "f.py"
    src.write_text("def g():\n    return 1  # pragma: no cover\n")
    sections = build_sections({src: [2]})
    meta = OutputMeta(
        context_lines=0,
        with_code=True,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
        show_paths=True,
        show_line_numbers=True,
    )
    out = format_json(sections, meta)
    data = json.loads(out)
    assert data["files"][0]["uncovered"][0]["source"][0]["tag"] == "no-cover"
