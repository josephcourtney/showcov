"""Output formatting utilities for showcov."""

from __future__ import annotations

from showcov.core.types import Format
from showcov.output.human import format_human
from showcov.output.json import format_json
from showcov.output.report_render import render_report
from showcov.output.rg import format_rg
from showcov.output.tty import render_coverage_table

__all__ = [
    "Format",
    "format_human",
    "format_json",
    "format_rg",
    "render_coverage_table",
    "render_report",
]
