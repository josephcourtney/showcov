from pathlib import Path

from showcov.core import build_sections
from showcov.output import FORMATTERS, format_human


def test_format_human_respects_color(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text("a\n")
    sections = build_sections({src: [1]})
    colored = format_human(
        sections,
        context_lines=0,
        embed_source=False,
        coverage_xml=tmp_path / "cov.xml",
        color=True,
    )
    plain = format_human(
        sections,
        context_lines=0,
        embed_source=False,
        coverage_xml=tmp_path / "cov.xml",
        color=False,
    )
    assert "\x1b" in colored
    assert "\x1b" not in plain


def test_format_registry() -> None:
    assert set(FORMATTERS) == {"human", "json"}
