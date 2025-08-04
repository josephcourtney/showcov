"""Output formatting utilities for showcov."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.text import Text

if TYPE_CHECKING:
    from showcov.core import UncoveredSection
    from showcov.output.base import OutputMeta


def format_human(sections: list[UncoveredSection], meta: OutputMeta) -> str:
    context_lines = max(0, meta.context_lines)

    root = Path.cwd().resolve()
    console = Console(force_terminal=meta.color, width=sys.maxsize)

    with console.capture() as capture:
        for section in sections:
            try:
                rel = section.file.resolve().relative_to(root)
            except ValueError:
                rel = section.file.resolve()
            console.print(Text(f"Uncovered sections in {rel.as_posix()}:", style="bold yellow"))
            try:
                with section.file.open(encoding="utf-8") as f:
                    file_lines = [ln.rstrip("\n") for ln in f.readlines()]
            except OSError:
                for start, end in section.ranges:
                    line_str = f"Lines {start}-{end}" if start != end else f"Line {start}"
                    console.print(Text(f"  {line_str}", style="cyan"))
                continue
            for start, end in section.ranges:
                header = f"Lines {start}-{end}" if start != end else f"Line {start}"
                console.print(Text(f"  {header}:", style="bold cyan"))
                start_idx = max(1, start - context_lines)
                end_idx = min(len(file_lines), end + context_lines)
                for ln in range(start_idx, end_idx + 1):
                    line_text = file_lines[ln - 1] if 1 <= ln <= len(file_lines) else "<line not found>"
                    style = "magenta" if start <= ln <= end else ""
                    console.print(f"    {ln:4d}: {line_text}", style=style)
                console.print()
    return capture.get()
