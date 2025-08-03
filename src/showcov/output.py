"""Output formatting utilities for showcov."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from colorama import Fore, Style
from jsonschema import validate

from showcov import __version__
from showcov.config import get_schema
from showcov.core import UncoveredSection


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
    validate(data, get_schema())
    return json.dumps(data, indent=2, sort_keys=True)


def parse_json_output(data: str) -> list[UncoveredSection]:
    """Parse JSON coverage data into :class:`UncoveredSection` instances."""
    obj = json.loads(data)
    validate(obj, get_schema())
    files = obj.get("files", [])
    return [UncoveredSection.from_dict(f) for f in files]


def format_markdown(
    sections: list[UncoveredSection],
    *,
    context_lines: int,
    with_code: bool,  # noqa: ARG001 - kept for signature consistency
    coverage_xml: Path,  # noqa: ARG001
    color: bool,  # noqa: ARG001
) -> str:
    context_lines = max(0, context_lines)
    parts: list[str] = []
    root = Path.cwd().resolve()
    for section in sections:
        try:
            rel = section.file.resolve().relative_to(root)
        except ValueError:
            rel = section.file.resolve()
        code_blocks: list[str] = []
        try:
            with section.file.open(encoding="utf-8") as f:
                file_lines = [ln.rstrip("\n") for ln in f.readlines()]
        except OSError:
            file_lines = []
        for start, end in section.ranges:
            start_idx = max(1, start - context_lines)
            end_idx = min(len(file_lines), end + context_lines)
            snippet = "\n".join(
                f"{i:4d}: {file_lines[i - 1] if 1 <= i <= len(file_lines) else '<line not found>'}"
                for i in range(start_idx, end_idx + 1)
            )
            code_blocks.append(f"```python\n{snippet}\n```")
        details = "\n\n".join(code_blocks)
        parts.append(
            f"<details>\n<summary>Uncovered sections in {rel.as_posix()}</summary>\n\n{details}\n</details>"
        )
    return "\n\n".join(parts)


def format_sarif(
    sections: list[UncoveredSection],
    *,
    context_lines: int,  # noqa: ARG001
    with_code: bool,  # noqa: ARG001
    coverage_xml: Path,  # noqa: ARG001
    color: bool,  # noqa: ARG001
) -> str:
    results: list[dict[str, object]] = []
    for section in sections:
        for start, end in section.ranges:
            results.append({
                "ruleId": "uncovered-code",
                "level": "note",
                "message": {"text": "Uncovered code"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": section.file.as_posix()},
                            "region": {"startLine": start, "endLine": end},
                        }
                    }
                ],
            })
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "showcov",
                        "semanticVersion": __version__,
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, indent=2, sort_keys=True)


FORMATTERS: dict[str, Formatter] = {
    "human": format_human,
    "json": format_json,
    "markdown": format_markdown,
    "sarif": format_sarif,
}


def get_formatter(format_name: str) -> Formatter:
    """Return a formatter callable for the given format name."""
    try:
        return FORMATTERS[format_name]
    except KeyError as e:
        msg = f"Unsupported format: {format_name!r}"
        raise ValueError(msg) from e
