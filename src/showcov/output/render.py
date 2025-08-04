"""Utilities for rendering formatted output."""

from __future__ import annotations

from typing import TYPE_CHECKING

from showcov.output import get_formatter
from showcov.output.base import Format, OutputMeta

if TYPE_CHECKING:
    from showcov.core import UncoveredSection


def render_output(
    sections: list[UncoveredSection],
    fmt: Format,
    meta: OutputMeta,
    *,
    aggregate_stats: bool = False,
) -> str:
    """Render ``sections`` according to ``fmt`` and ``meta``.

    Parameters
    ----------
    sections:
        Uncovered code sections to render.
    fmt:
        Desired output format.
    meta:
        Formatting metadata, such as context lines and colour options.
    aggregate_stats:
        When ``True`` and ``fmt`` is :class:`~showcov.output.base.Format.HUMAN`,
        append a footer with aggregate statistics.
    """
    if not sections:
        return "No uncovered lines found (0 files matched input patterns)"

    formatter = get_formatter(fmt)
    output = formatter(sections, meta)

    if aggregate_stats and fmt is Format.HUMAN:
        total_files = len(sections)
        total_regions = sum(len(sec.ranges) for sec in sections)
        total_lines = sum(end - start + 1 for sec in sections for start, end in sec.ranges)
        footer = ", ".join([
            f"{total_files} files with uncovered lines",
            f"{total_regions} uncovered regions",
            f"{total_lines} total lines",
        ])
        output = f"{output}\n{footer}"

    return output
