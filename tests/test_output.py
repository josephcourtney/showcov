import json
from pathlib import Path

from jsonschema import validate

from showcov import __version__
from showcov.core import Report, build_sections, get_schema
from showcov.core.core import UncoveredSection
from showcov.core.coverage import gather_uncovered_branches_from_xml
from showcov.core.types import Format
from showcov.output.base import OutputMeta
from showcov.output.human import format_human
from showcov.output.json import format_json_v2
from showcov.output.report_render import render_report


def _make_meta(
    tmp_path: Path, *, with_code: bool = False, show_paths: bool = True, color: bool = False
) -> OutputMeta:
    return OutputMeta(
        coverage_xml=tmp_path / "cov.xml",
        with_code=with_code,
        color=color,
        show_paths=show_paths,
        show_line_numbers=False,
        context_before=0,
        context_after=0,
    )


def _make_report(meta: OutputMeta, sections: list[UncoveredSection]) -> Report:
    files_payload = [
        section.to_dict(
            with_code=meta.with_code,
            context_before=meta.context_before,
            context_after=meta.context_after,
            base=meta.coverage_xml.parent,
            show_file=meta.show_paths,
            show_line_numbers=meta.show_line_numbers,
        )
        for section in sections
    ]
    sections_data = {"lines": {"files": files_payload, "summary": {"uncovered": 1}}}
    attachments = {"lines": {"sections": sections}}
    report_meta = {
        "environment": {"coverage_xml": meta.coverage_xml.as_posix()},
        "options": {
            "context_lines": meta.context_lines,
            "with_code": meta.with_code,
            "show_paths": meta.show_paths,
            "show_line_numbers": meta.show_line_numbers,
            "aggregate_stats": True,
            "file_stats": True,
        },
    }
    return Report(meta=report_meta, sections=sections_data, attachments=attachments)


def test_format_human_respects_color(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    colored_meta = _make_meta(tmp_path, color=True)
    plain_meta = _make_meta(tmp_path, color=False)
    colored = format_human(sections, colored_meta)
    plain = format_human(sections, plain_meta)
    assert "\x1b" in colored
    assert "\x1b" not in plain


def test_render_report_human_sections(tmp_path: Path) -> None:
    src = tmp_path / "f.py"
    src.write_text("print(1)\n")
    sections = build_sections({src: [1]})
    meta = _make_meta(tmp_path)
    report = _make_report(meta, sections)
    output = render_report(report, Format.HUMAN, meta)
    assert "Lines" in output
    assert "Total uncovered lines: 1" in output


def test_render_report_json_schema(tmp_path: Path) -> None:
    src = tmp_path / "f.py"
    src.write_text("print(1)\n")
    sections = build_sections({src: [1]})
    meta = _make_meta(tmp_path)
    report = _make_report(meta, sections)
    rendered = render_report(report, Format.JSON, meta)
    data = json.loads(rendered)
    validate(data, get_schema("v2"))
    assert data["tool"] == {"name": "showcov", "version": __version__}


def test_format_json_v2_schema(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    meta = _make_meta(tmp_path)
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
    out = format_json_v2(report)
    data = json.loads(out)
    validate(data, get_schema("v2"))
    assert data["tool"] == {"name": "showcov", "version": __version__}


def test_gather_uncovered_branches_from_xml(tmp_path: Path) -> None:
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
