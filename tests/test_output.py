import json
from pathlib import Path

import pytest

from showcov.core import build_sections
from showcov.output import (
    FORMATTERS,
    format_human,
    format_markdown,
    format_sarif,
    get_formatter,
)
from showcov.output.base import (
    Format,
    OutputMeta,
)


def test_format_human_respects_color(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    colored_meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=True,
    )
    plain_meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
    )
    colored = format_human(sections, colored_meta)
    plain = format_human(sections, plain_meta)
    assert "\x1b" in colored
    assert "\x1b" not in plain


def test_format_registry() -> None:
    assert set(FORMATTERS) == {
        Format.HUMAN,
        Format.JSON,
        Format.MARKDOWN,
        Format.SARIF,
    }


def test_format_from_str() -> None:
    assert Format.from_str("json") is Format.JSON
    with pytest.raises(ValueError, match="Unsupported format: 'bogus'"):
        Format.from_str("bogus")


def test_get_formatter_enum() -> None:
    assert get_formatter(Format.HUMAN) is FORMATTERS[Format.HUMAN]


def test_format_markdown(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
    )
    out = format_markdown(sections, meta)
    assert "<details>" in out
    assert "```" in out


def test_format_sarif(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
    )
    out = format_sarif(sections, meta)
    data = json.loads(out)
    assert data["version"] == "2.1.0"
    assert data["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]["startLine"] == 1
