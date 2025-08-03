from pathlib import Path
from typing import cast

import pytest

from showcov.core import UncoveredSection, build_sections
from showcov.output import FORMATTERS, parse_json_output


def test_json_round_trip(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\nb\n")
    sections = build_sections({src: [1, 2]})
    json_out = FORMATTERS["json"](
        sections,
        context_lines=1,
        with_code=True,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
    )
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
