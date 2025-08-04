"""Output formatting utilities for showcov."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from showcov.core import UncoveredSection
    from showcov.output.base import OutputMeta


def format_human(sections: list[UncoveredSection], meta: OutputMeta) -> str:
    """Return uncovered sections in a simple table."""
    root = Path.cwd().resolve()
    console = Console(force_terminal=meta.color, width=sys.maxsize)

    table = Table(show_header=True, header_style="bold")
    table.add_column("File", style="yellow")
    table.add_column("Start", justify="right", style="cyan")
    table.add_column("End", justify="right", style="cyan")
    table.add_column("# Lines", justify="right", style="magenta")

    for section in sections:
        try:
            rel = section.file.resolve().relative_to(root)
        except ValueError:
            rel = section.file.resolve()
        for start, end in section.ranges:
            table.add_row(
                rel.as_posix(),
                str(start),
                str(end),
                str(end - start + 1),
            )

    with console.capture() as capture:
        console.print(table)
    return capture.get()
