"""Helpers for rendering grouped tables."""

from __future__ import annotations

import sys
from io import StringIO
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

from rich.console import Console
from rich.table import Table


def _header_text(parts: Sequence[str]) -> str:
    r"""Convert a grouped header tuple like ('Statements','Covered') to 'Statements\\nCovered'."""
    items = [str(p) for p in parts if str(p).strip()]
    return "\n".join(items) if items else ""


def _render_rich_table(
    headers: Sequence[Sequence[str]], rows: Sequence[Sequence[Any]], *, color: bool
) -> str:
    r"""Render a Rich table captured to a string.

    Notes
    -----
    Rich doesn't support true column-spanning grouped headers in a single
    header row; we encode grouping as multi-line column headers:
      ('Statements','Total') -> "Statements\\nTotal"
    """
    table = Table(show_header=True, header_style="bold")
    for h in headers:
        table.add_column(_header_text(h), justify="right")

    # Heuristic: left-align first column (usually file path / label)
    if table.columns:
        table.columns[0].justify = "left"

    for r in rows:
        table.add_row(*[str(v) for v in r])

    buf = StringIO()
    console = Console(
        file=buf,
        force_terminal=color,
        width=sys.maxsize,
        color_system="standard" if color else None,
        no_color=not color,
    )
    console.print(table)
    return buf.getvalue().rstrip()


def format_table(
    headers: Sequence[Sequence[str]], rows: Sequence[Sequence[Any]], *, color: bool = True
) -> str:
    """Render a Rich table captured to text.

    Kept as `format_table(...)` to preserve the existing call sites in
    `report_render.py`.
    """
    if not headers or not rows:
        return ""
    return _render_rich_table(headers, rows, color=color)
