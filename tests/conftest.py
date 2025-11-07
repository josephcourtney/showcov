from __future__ import annotations

import operator
import re
import xml.etree.ElementTree as ET  # noqa: S405 - coverage XML is locally generated and trusted
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from showcov.output.table import format_table

LinesSpec = Mapping[int, str | int] | Iterable[int]


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a Click CLI runner for invoking the command-line interface."""
    return CliRunner()


@pytest.fixture
def coverage_xml_content() -> Callable[..., str]:
    def build(mapping: Mapping[Path | str, LinesSpec], *, sources: Path | None = None) -> str:
        classes: list[str] = []
        for file, lines in mapping.items():
            items = lines.items() if isinstance(lines, Mapping) else ((ln, 0) for ln in lines)
            lines_xml = "".join(f'<line number="{ln}" hits="{hits}"/>' for ln, hits in items)
            classes.append(f'<class filename="{file}"><lines>{lines_xml}</lines></class>')
        classes_xml = "".join(classes)
        sources_xml = f"<sources><source>{sources}</source></sources>" if sources else ""
        return (
            "<coverage>"
            f"{sources_xml}"
            f"<packages><package><classes>{classes_xml}</classes></package></packages>"
            "</coverage>"
        )

    return build


@pytest.fixture
def coverage_xml_file(
    tmp_path: Path,
    coverage_xml_content: Callable[..., str],
) -> Callable[..., Path]:
    def write(
        mapping: Mapping[Path | str, LinesSpec],
        *,
        sources: Path | None = None,
        filename: str = "coverage.xml",
    ) -> Path:
        xml_content = coverage_xml_content(mapping, sources=sources)
        xml_file = tmp_path / filename
        xml_file.write_text(xml_content)
        return xml_file

    return write
