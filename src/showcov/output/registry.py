"""Formatter registry for showcov output formats."""

from __future__ import annotations

from showcov.output.base import Format, Formatter
from showcov.output.html import format_html
from showcov.output.human import format_human
from showcov.output.json import format_json
from showcov.output.markdown import format_markdown
from showcov.output.sarif import format_sarif

FORMATTERS: dict[Format, Formatter] = {
    Format.HUMAN: format_human,
    Format.HTML: format_html,
    Format.JSON: format_json,
    Format.MARKDOWN: format_markdown,
    Format.SARIF: format_sarif,
}


def resolve_formatter(format_str: str, *, is_tty: bool) -> tuple[Format, Formatter]:
    """Resolve *format_str* to a :class:`Format` and its formatter."""
    try:
        fmt = Format(format_str.lower())
    except ValueError as err:
        choices = ", ".join(f.value for f in Format)
        msg = f"{format_str!r} is not one of {choices}"
        raise ValueError(msg) from err

    if fmt is Format.AUTO:
        fmt = Format.HUMAN if is_tty else Format.JSON

    try:
        formatter = FORMATTERS[fmt]
    except KeyError as err:  # pragma: no cover - defensive
        msg = f"Unsupported format: {fmt!r}"
        raise ValueError(msg) from err

    return fmt, formatter
