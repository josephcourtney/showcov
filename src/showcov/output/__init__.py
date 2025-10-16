"""Output formatting utilities for showcov."""

from __future__ import annotations

from showcov.output.base import Format, Formatter
from showcov.output.html import format_html
from showcov.output.human import format_human
from showcov.output.json import format_json
from showcov.output.markdown import format_markdown
from showcov.output.registry import FORMATTERS, resolve_formatter
from showcov.output.render import render_output
from showcov.output.tty import render_coverage_table

__all__ = [
    "FORMATTERS",
    "Format",
    "Formatter",
    "format_html",
    "format_human",
    "format_json",
    "format_markdown",
    "render_coverage_table",
    "render_output",
    "resolve_formatter",
]
