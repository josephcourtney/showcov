"""Output formatting utilities for showcov."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Protocol

from colorama import Fore, Style
from colorama import init as colorama_init
from jsonschema import validate

from . import __version__
from .core import UncoveredSection

colorama_init(autoreset=True)

# Load JSON schema once
SCHEMA = json.loads(resources.files("showcov.data").joinpath("schema.json").read_text(encoding="utf-8"))


class Formatter(Protocol):
    def __call__(
        self,
        sections: list[UncoveredSection],
        *,
        context_lines: int,
        with_code: bool,
        coverage_xml: Path,
        color: bool,
    ) -> str: ...


def _colors(*, enabled: bool) -> dict[str, str]:
    if not enabled:
        return {"RESET": "", "BOLD": "", "YELLOW": "", "CYAN": "", "MAGENTA": "", "GREEN": "", "RED": ""}
    return {
        "RESET": Style.RESET_ALL,
        "BOLD": Style.BRIGHT,
        "YELLOW": Fore.YELLOW,
        "CYAN": Fore.CYAN,
        "MAGENTA": Fore.MAGENTA,
        "GREEN": Fore.GREEN,
        "RED": Fore.RED,
    }


def format_human(
    sections: list[UncoveredSection],
    *,
    context_lines: int,
    with_code: bool,  # noqa: ARG001 - kept for consistent signature
    coverage_xml: Path,  # noqa: ARG001
    color: bool,
) -> str:
    context_lines = max(0, context_lines)
    colors = _colors(enabled=color)
    if not sections:
        return f"{colors['GREEN']}{colors['BOLD']}No uncovered lines found!{colors['RESET']}"

    root = Path.cwd().resolve()
    parts: list[str] = []
    for section in sections:
        try:
            rel = section.file.resolve().relative_to(root)
        except ValueError:
            rel = section.file.resolve()
        parts.append(
            f"\n{colors['BOLD']}{colors['YELLOW']}Uncovered sections in {rel.as_posix()}:{colors['RESET']}"
        )
        try:
            with section.file.open(encoding="utf-8") as f:
                file_lines = [ln.rstrip("\n") for ln in f.readlines()]
        except OSError:
            for start, end in section.ranges:
                text = (
                    f"  {colors['CYAN']}Lines {start}-{end}{colors['RESET']}"
                    if start != end
                    else f"  {colors['CYAN']}Line {start}{colors['RESET']}"
                )
                parts.append(text)
            continue
        for start, end in section.ranges:
            header = (
                f"  {colors['BOLD']}{colors['CYAN']}Lines {start}-{end}:{colors['RESET']}"
                if start != end
                else f"  {colors['BOLD']}{colors['CYAN']}Line {start}:{colors['RESET']}"
            )
            parts.append(header)
            start_idx = max(1, start - context_lines)
            end_idx = min(len(file_lines), end + context_lines)
            for ln in range(start_idx, end_idx + 1):
                content = file_lines[ln - 1] if 1 <= ln <= len(file_lines) else "<line not found>"
                if start <= ln <= end:
                    parts.append(f"    {colors['MAGENTA']}{ln:4d}{colors['RESET']}: {content}")
                else:
                    parts.append(f"    {ln:4d}: {content}")
            parts.append("")
    return "\n".join(parts).lstrip("\n")


def format_json(
    sections: list[UncoveredSection],
    *,
    context_lines: int,
    with_code: bool,
    coverage_xml: Path,
    color: bool,  # noqa: ARG001
) -> str:
    context_lines = max(0, context_lines)
    root = Path.cwd().resolve()
    try:
        xml_path = coverage_xml.resolve().relative_to(root)
    except ValueError:
        xml_path = coverage_xml.resolve()
    data: dict[str, object] = {
        "version": __version__,
        "environment": {
            "coverage_xml": xml_path.as_posix(),
            "context_lines": context_lines,
            "with_code": with_code,
        },
        "files": [sec.to_dict(with_code=with_code, context_lines=context_lines) for sec in sections],
    }
    validate(data, SCHEMA)
    return json.dumps(data, indent=2, sort_keys=True)


def parse_json_output(data: str) -> list[UncoveredSection]:
    """Parse JSON coverage data into :class:`UncoveredSection` instances."""
    obj = json.loads(data)
    validate(obj, SCHEMA)
    files = obj.get("files", [])
    return [UncoveredSection.from_dict(f) for f in files]


FORMATTERS: dict[str, Formatter] = {
    "human": format_human,
    "json": format_json,
}
