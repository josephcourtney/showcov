"""Output formatting utilities for showcov."""

from __future__ import annotations

from showcov.output.base import Format, Formatter
from showcov.output.human import format_human
from showcov.output.json import format_json
from showcov.output.markdown import format_markdown
from showcov.output.registry import FORMATTERS, get_formatter
from showcov.output.sarif import format_sarif

__all__ = [
    "FORMATTERS",
    "Format",
    "Formatter",
    "format_human",
    "format_json",
    "format_markdown",
    "format_sarif",
    "get_formatter",
]
