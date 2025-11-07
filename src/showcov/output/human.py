"""Output formatting utilities for showcov."""

from __future__ import annotations

import sys
from io import StringIO
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from showcov.core.files import detect_line_tag, normalize_path, read_file_lines

if TYPE_CHECKING:
    from showcov.core import UncoveredSection
    from showcov.output.base import OutputMeta


def _render_table(table: Table, *, color: bool) -> str:
    """Return a string rendering of *table*, preserving ANSI when requested."""
    buffer = StringIO()
    console = Console(
        file=buffer,
        force_terminal=color,
        width=sys.maxsize,
        color_system="standard" if color else None,
        no_color=not color,
    )
    console.print(table)
    return buffer.getvalue()


def format_human(sections: list[UncoveredSection], meta: OutputMeta) -> str:
    """Return uncovered sections in a simple table."""
    root = meta.coverage_xml.parent.resolve()

    table = Table(show_header=True, header_style="bold")
    if meta.show_paths:
        table.add_column("File", style="yellow")
    table.add_column("Start", justify="right", style="cyan")
    table.add_column("End", justify="right", style="cyan")
    table.add_column("# Lines", justify="right", style="magenta")

    for section in sections:
        rel = normalize_path(section.file, base=root)
        for start, end in section.ranges:
            row = []
            if meta.show_paths:
                row.append(rel.as_posix())
            row.extend([str(start), str(end), str(end - start + 1)])
            table.add_row(*row)

    parts: list[str] = [_render_table(table, color=meta.color)]

    if meta.with_code:
        for section in sections:
            rel = normalize_path(section.file, base=root)
            lines = read_file_lines(section.file)
            for start, end in section.ranges:
                heading = f"{rel.as_posix()}:{start}-{end}" if meta.show_paths else f"{start}-{end}"
                parts.append(heading)
                start_idx = max(1, start - meta.context_before)
                end_idx = min(len(lines), end + meta.context_after)
                for i in range(start_idx, end_idx + 1):
                    code = lines[i - 1] if 1 <= i <= len(lines) else "<line not found>"
                    tag = detect_line_tag(lines, i - 1) if 1 <= i <= len(lines) else None
                    line = f"{i:>4}: {code}" if meta.show_line_numbers else code
                    if tag:
                        line += f"  [{tag}]"
                    parts.append(line)
                parts.append("")

    return "\n".join(parts).rstrip()
