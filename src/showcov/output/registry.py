"""Formatter registry for showcov output formats."""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

from showcov import logger
from showcov.core.types import Format
from showcov.output.html import format_html
from showcov.output.human import format_human
from showcov.output.json import format_json
from showcov.output.markdown import format_markdown

if TYPE_CHECKING:
    from showcov.output.base import Formatter

FORMATTERS: dict[Format, Formatter] = {
    Format.HUMAN: format_human,
    Format.HTML: format_html,
    Format.JSON: format_json,
    Format.MARKDOWN: format_markdown,
}


def resolve_formatter(format_str: str, *, is_tty: bool) -> tuple[Format, Formatter]:
    """Resolve *format_str* to a :class:`Format` and its formatter."""
    try:
        fmt = Format(format_str.lower())
    except ValueError as err:
        choices = [f.value for f in Format]
        suggestion = difflib.get_close_matches(format_str, choices, n=1)
        hint = f". Did you mean {suggestion[0]!r}?" if suggestion else ""
        msg = f"{format_str!r} is not one of {', '.join(choices)}{hint}"
        raise ValueError(msg) from err

    if fmt is Format.AUTO:
        fmt = Format.HUMAN if is_tty else Format.JSON

    try:
        formatter = FORMATTERS[fmt]
    except KeyError as err:  # pragma: no cover - defensive
        msg = f"Unsupported format: {fmt!r}"
        raise ValueError(msg) from err

    logger.debug("selected formatter %s", fmt.value)
    return fmt, formatter
