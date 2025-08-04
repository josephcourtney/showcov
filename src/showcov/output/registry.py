"""Formatter registry for showcov output formats."""

from __future__ import annotations

from showcov.output.base import Format, Formatter
from showcov.output.human import format_human
from showcov.output.json import format_json
from showcov.output.markdown import format_markdown
from showcov.output.sarif import format_sarif

FORMATTERS: dict[Format, Formatter] = {
    Format.HUMAN: format_human,
    Format.JSON: format_json,
    Format.MARKDOWN: format_markdown,
    Format.SARIF: format_sarif,
}


def get_formatter(fmt: Format) -> Formatter:
    """Return the formatter callable registered for the given format."""
    try:
        return FORMATTERS[fmt]
    except KeyError as e:  # defensive fallback
        msg = f"Unsupported format: {fmt!r}"
        raise ValueError(msg) from e
