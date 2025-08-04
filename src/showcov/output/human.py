"""Output formatting utilities for showcov."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from showcov.core.files import detect_line_tag, normalize_path, read_file_lines

if TYPE_CHECKING:
    from showcov.core import UncoveredSection
    from showcov.output.base import OutputMeta


def format_human(sections: list[UncoveredSection], meta: OutputMeta) -> str:
    """Return uncovered sections in a simple table."""
    root = meta.coverage_xml.parent.resolve()
    console = Console(force_terminal=meta.color, width=sys.maxsize)

    table = Table(show_header=True, header_style="bold")
    table.add_column("File", style="yellow")
    table.add_column("Start", justify="right", style="cyan")
    table.add_column("End", justify="right", style="cyan")
    table.add_column("# Lines", justify="right", style="magenta")

    for section in sections:
        rel = normalize_path(section.file, base=root)
        for start, end in section.ranges:
            table.add_row(
                rel.as_posix(),
                str(start),
                str(end),
                str(end - start + 1),
            )

    parts: list[str] = []
    with console.capture() as capture:
        console.print(table)
    parts.append(capture.get())

    if meta.with_code:
        for section in sections:
            rel = normalize_path(section.file, base=root)
            lines = read_file_lines(section.file)
            for start, end in section.ranges:
                parts.append(f"{rel.as_posix()}:{start}-{end}")
                start_idx = max(1, start - meta.context_lines)
                end_idx = min(len(lines), end + meta.context_lines)
                for i in range(start_idx, end_idx + 1):
                    code = lines[i - 1] if 1 <= i <= len(lines) else "<line not found>"
                    tag = detect_line_tag(lines, i - 1) if 1 <= i <= len(lines) else None
                    line = f"{i:>4}: {code}"
                    if tag:
                        line += f"  [{tag}]"
                    parts.append(line)
                parts.append("")

    return "\n".join(parts).rstrip()
