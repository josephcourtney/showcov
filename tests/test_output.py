import json
from pathlib import Path

from showcov.core import build_sections
from showcov.output import FORMATTERS, format_human, format_markdown, format_sarif


def test_format_human_respects_color(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    colored = format_human(
        sections,
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=True,
    )
    plain = format_human(
        sections,
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
    )
    assert "\x1b" in colored
    assert "\x1b" not in plain


def test_format_registry() -> None:
    assert set(FORMATTERS) == {"human", "json", "markdown", "sarif"}


def test_format_markdown(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    out = format_markdown(
        sections,
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
    )
    assert "<details>" in out
    assert "```" in out


def test_format_sarif(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    out = format_sarif(
        sections,
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
    )
    data = json.loads(out)
    assert data["version"] == "2.1.0"
    assert data["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]["startLine"] == 1
