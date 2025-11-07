"""Output formatting utilities for showcov."""

from __future__ import annotations

from showcov.core.types import Format
from showcov.output.html import format_html
from showcov.output.human import format_human
from showcov.output.json import format_json_v2
from showcov.output.markdown import format_markdown
from showcov.output.report_render import render_report
from showcov.output.tty import render_coverage_table

__all__ = [
    "Format",
    "format_html",
    "format_human",
    "format_json_v2",
    "format_markdown",
    "render_coverage_table",
    "render_report",
]
