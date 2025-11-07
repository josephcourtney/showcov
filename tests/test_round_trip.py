import json
from pathlib import Path
from typing import cast

import pytest
from jsonschema import validate

from showcov.core import Report, UncoveredSection, build_sections, get_schema
from showcov.core.types import Format
from showcov.output.base import OutputMeta
from showcov.output.report_render import render_report


def parse_json_output(data: str) -> list[UncoveredSection]:
    """Parse JSON coverage data into :class:`UncoveredSection` instances."""
    obj = json.loads(data)
    validate(obj, get_schema("v2"))
    meta = obj.get("meta", {})
    env = cast("dict[str, object]", meta.get("environment", {}))
    base_path = Path(str(env.get("coverage_xml", "."))).resolve().parent
    sections_obj = cast("dict[str, object]", obj.get("sections", {}))
    lines_section = cast("dict[str, object]", sections_obj.get("lines", {}))
    files = cast("list[dict[str, object]]", lines_section.get("files", []))
    sections = []
    for entry in files:
        item = dict(entry)
        if "file" in item:
            item["file"] = (base_path / str(item["file"])).as_posix()
        sections.append(UncoveredSection.from_dict(item))
    return sections


def test_json_round_trip(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\nb\n")
    sections = build_sections({src: [1, 2]})
    meta = OutputMeta(
        coverage_xml=tmp_path / "cov.xml",
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
    parsed = parse_json_output(json_out)
    assert parsed == sections


def test_to_dict_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.py"
    section = UncoveredSection(missing, [(1, 1)])
    out = section.to_dict(with_code=True, context_lines=1)
    uncovered = cast("list[dict[str, object]]", out["uncovered"])
    first: dict[str, object] = uncovered[0]
    assert "source" not in first


def test_negative_context_lines(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text("a\nb\n")
    section = UncoveredSection(src, [(1, 1)])
    with pytest.raises(ValueError, match="context_lines must be non-negative"):
        section.to_dict(with_code=True, context_lines=-5)


def test_context_lines_exceed_file(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text("a\nb\n")
    section = UncoveredSection(src, [(2, 2)])
    out = section.to_dict(with_code=True, context_lines=10)
    uncovered = cast("list[dict[str, object]]", out["uncovered"])
    source = cast("list[dict[str, object]]", uncovered[0]["source"])
    lines = [cast("int", s["line"]) for s in source]
    assert lines == [1, 2]
