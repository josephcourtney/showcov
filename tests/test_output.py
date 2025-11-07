import json
from pathlib import Path

import pytest
from jsonschema import validate

from showcov import __version__
from showcov.core import Report, build_sections, get_schema
from showcov.core.coverage import gather_uncovered_branches_from_xml
from showcov.core.types import Format
from showcov.output import (
    FORMATTERS,
    format_html,
    format_human,
    format_json,
    format_markdown,
    render_output,
    resolve_formatter,
)
from showcov.output.base import OutputMeta
from showcov.output.json import format_json_v2


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


def test_render_output_human_deterministic(tmp_path: Path) -> None:
    src = tmp_path / "y.py"
    src.write_text("line1\nline2\nline3\nline4\n")
    sections = build_sections({src: [1, 2, 4]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
        show_paths=True,
        show_line_numbers=False,
    )
    first = render_output(sections, Format.HUMAN, FORMATTERS[Format.HUMAN], meta)
    second = render_output(sections, Format.HUMAN, FORMATTERS[Format.HUMAN], meta)
    assert first == second
    assert "y.py" in first
    assert "# Lines" in first


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
    lines = data["sections"]["lines"]
    assert lines["summary"]["uncovered"] == 1
    assert lines["files"][0]["counts"]["uncovered"] == 1
    assert data["schema_version"] == 2


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
    files = data["sections"]["lines"]["files"]
    assert "file" not in files[0]


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
    files = data["sections"]["lines"]["files"]
    assert files[0]["uncovered"][0]["source"][0]["tag"] == "no-cover"


def test_format_json_v2_schema(tmp_path: Path) -> None:
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
    files = [
        sec.to_dict(
            with_code=meta.with_code,
            context_lines=meta.context_lines,
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
    )
    out = format_json_v2(report)
    data = json.loads(out)
    validate(data, get_schema("v2"))
    assert data["tool"] == {"name": "showcov", "version": __version__}


def test_gather_uncovered_branches_from_xml(tmp_path: Path) -> None:
    # Build a minimal coverage XML with a branchy line having one 0% condition
    src = tmp_path / "f.py"
    src.write_text("if x:\n    pass\n")
    xml = tmp_path / "cov.xml"
    xml.write_text(
        (
            "<coverage>"
            "<packages><package><classes>"
            f'<class filename="{src}"><lines>'
            '<line number="1" hits="1" branch="true" condition-coverage="50% (1/2)">'
            "<conditions>"
            '<condition number="0" type="jump" coverage="0%"/>'
            '<condition number="1" type="jump" coverage="100%"/>'
            "</conditions>"
            "</line>"
            "</lines></class>"
            "</classes></package></packages>"
            "</coverage>"
        ),
        encoding="utf-8",
    )
    gaps = gather_uncovered_branches_from_xml(xml)
    assert len(gaps) == 1
    g = gaps[0]
    assert g.file.resolve() == src.resolve()
    assert g.line == 1
    assert [(c.number, c.coverage) for c in g.conditions] == [(0, 0)]


def test_gather_uncovered_branches_from_xml_missing_branches_attr(tmp_path: Path) -> None:
    # Some coverage.py versions omit <conditions> but include missing-branches metadata.
    src = tmp_path / "f.py"
    src.write_text("if x:\n    pass\n")
    xml = tmp_path / "cov.xml"
    xml.write_text(
        (
            "<coverage>"
            "<packages><package><classes>"
            f'<class filename="{src}"><lines>'
            '<line number="1" hits="1" branch="true" '
            'condition-coverage="50% (1/2)" missing-branches="99, 123"/>'
            "</lines></class>"
            "</classes></package></packages>"
            "</coverage>"
        ),
        encoding="utf-8",
    )
    gaps = gather_uncovered_branches_from_xml(xml)
    assert len(gaps) == 1
    g = gaps[0]
    assert g.file.resolve() == src.resolve()
    assert g.line == 1
    assert [(c.number, c.type, c.coverage) for c in g.conditions] == [(99, "line", None), (123, "line", None)]


def test_gather_uncovered_branches_from_xml_partial_condition(tmp_path: Path) -> None:
    src = tmp_path / "f.py"
    src.write_text("if x:\n    pass\n")
    xml = tmp_path / "cov.xml"
    xml.write_text(
        (
            "<coverage>"
            "<packages><package><classes>"
            f'<class filename="{src}"><lines>'
            '<line number="1" hits="1" branch="true" condition-coverage="75% (3/4)">'
            "<conditions>"
            '<condition number="0" type="jump" coverage="75%"/>'
            '<condition number="1" type="jump" coverage="100%"/>'
            "</conditions>"
            "</line>"
            "</lines></class>"
            "</classes></package></packages>"
            "</coverage>"
        ),
        encoding="utf-8",
    )
    gaps = gather_uncovered_branches_from_xml(xml)
    assert len(gaps) == 1
    conds = gaps[0].conditions
    assert [(c.number, c.type, c.coverage) for c in conds] == [(0, "jump", 75)]
