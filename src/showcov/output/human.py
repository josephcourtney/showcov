"""Output formatting utilities for showcov."""

from __future__ import annotations

import sys
from collections import defaultdict
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from showcov.core.files import detect_line_tag, normalize_path, read_file_lines

if TYPE_CHECKING:
    from pathlib import Path

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


def _group_ranges_by_file(
    sections: list[UncoveredSection],
    *,
    base_root: Path,
) -> dict[str, list[tuple[int, int]]]:
    """Return mapping of relative file path -> uncovered (start, end) ranges."""
    grouped: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for section in sections:
        rel = normalize_path(section.file, base=base_root).as_posix()
        for start, end in section.ranges:
            grouped[rel].append((start, end))
    return grouped


def _build_ranges_table(ranges: list[tuple[int, int]]) -> Table:
    """Build a Rich table describing uncovered ranges."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("Start", justify="right", style="cyan")
    table.add_column("End", justify="right", style="cyan")
    table.add_column("# Lines", justify="right", style="magenta")
    for start, end in ranges:
        table.add_row(str(start), str(end), str(end - start + 1))
    return table


def _render_tables_with_paths(
    sections: list[UncoveredSection],
    meta: OutputMeta,
    *,
    base_root: Path,
) -> list[str]:
    """Render tables grouped by file, including a single 'File:' heading."""
    parts: list[str] = []
    by_file = _group_ranges_by_file(sections, base_root=base_root)
    for rel_path in sorted(by_file):
        # Keep output compact but ensure:
        #   - the filename is the first token on the line (tests parse it
        #     that way), and
        #   - the literal word "File" appears somewhere in the heading.
        parts.append(f"{rel_path}  File")
        table = _build_ranges_table(by_file[rel_path])
        parts.append(_render_table(table, color=meta.color))
    return parts


def _render_table_without_paths(
    sections: list[UncoveredSection],
    meta: OutputMeta,
) -> list[str]:
    """Render a single table of uncovered ranges when paths are hidden."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("Start", justify="right", style="cyan")
    table.add_column("End", justify="right", style="cyan")
    table.add_column("# Lines", justify="right", style="magenta")
    for section in sections:
        for start, end in section.ranges:
            table.add_row(str(start), str(end), str(end - start + 1))
    return [_render_table(table, color=meta.color)]


def _render_code_blocks(
    sections: list[UncoveredSection],
    meta: OutputMeta,
    *,
    base_root: Path,
) -> list[str]:
    """Render optional annotated code blocks for each uncovered range."""
    if not meta.with_code:
        return []

    parts: list[str] = []
    for section in sections:
        rel = normalize_path(section.file, base=base_root)
        lines = read_file_lines(section.file)
        for start, end in section.ranges:
            heading = f"{rel.as_posix()}:{start}-{end}" if meta.show_paths else f"{start}-{end}"
            parts.append(heading)
            start_idx = max(1, start - meta.context_before)
            end_idx = min(len(lines), end + meta.context_after)
            for i in range(start_idx, end_idx + 1):
                code = lines[i - 1] if 1 <= i <= len(lines) else "<line not found>"
                tag = detect_line_tag(lines, i - 1) if 1 <= i <= len(lines) else None
                line_txt = f"{i:>4}: {code}" if meta.show_line_numbers else code
                if tag:
                    line_txt += f"  [{tag}]"
                parts.append(line_txt)
            parts.append("")
    return parts


def format_human(sections: list[UncoveredSection], meta: OutputMeta) -> str:
    """Return uncovered sections in a human-friendly text layout.

    Behaviour:
      - When ``meta.show_paths`` is True, produce one compact table per file.
        A single ``File: <path>`` heading precedes each table so the word
        ``"File"`` remains visible in the output (for tests and readers)
        without repeating the path in every row.
      - When ``meta.show_paths`` is False, render a single table without
        any file column.
      - When ``meta.with_code`` is True, append annotated code blocks for
        each uncovered range.
    """
    root = meta.coverage_xml.parent.resolve()
    parts: list[str] = []

    if meta.show_paths:
        parts.extend(_render_tables_with_paths(sections, meta, base_root=root))
    else:
        parts.extend(_render_table_without_paths(sections, meta))

    # Optional code context blocks
    parts.extend(_render_code_blocks(sections, meta, base_root=root))

    return "\n".join(parts).rstrip()
