"""Utilities for rendering formatted output."""

from __future__ import annotations

from typing import TYPE_CHECKING

from showcov import logger
from showcov.core.files import normalize_path, read_file_lines
from showcov.output.base import Format, Formatter, OutputMeta

if TYPE_CHECKING:
    from showcov.core import UncoveredSection


def render_output(
    sections: list[UncoveredSection],
    fmt: Format,
    formatter: Formatter,
    meta: OutputMeta,
    *,
    aggregate_stats: bool = False,
    file_stats: bool = False,
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
    file_stats:
        When ``True`` and ``fmt`` is :class:`~showcov.output.base.Format.HUMAN`,
        append a per-file summary with uncovered counts and percentages.
    """
    if not sections:
        return "No uncovered lines found (0 files matched input patterns)"

    if fmt is Format.JSON:
        from showcov.output.json import format_json  # noqa: PLC0415

        output = format_json(
            sections,
            meta,
            aggregate_stats=aggregate_stats,
            file_stats=file_stats,
        )
    else:
        output = formatter(sections, meta)

    if file_stats and fmt is Format.HUMAN:
        logger.debug("computing per-file statistics")
        base = meta.coverage_xml.parent.resolve()
        summary_lines = []
        for sec in sections:
            uncovered = sum(end - start + 1 for start, end in sec.ranges)
            total_lines = len(read_file_lines(sec.file))
            pct = (uncovered / total_lines * 100) if total_lines else 0
            rel = normalize_path(sec.file, base=base)
            summary_lines.append(f"{rel.as_posix()}: {uncovered} uncovered ({pct:.0f}%)")
        output = f"{output}\n" + "\n".join(summary_lines)

    if aggregate_stats and fmt is Format.HUMAN:
        logger.debug("computing aggregate statistics")
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
