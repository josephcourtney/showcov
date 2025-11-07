"""Helpers for rendering grouped Markdown tables."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


def _normalize_headers(headers: Sequence[Sequence[str]]) -> list[tuple[str, ...]]:
    max_depth = max((len(h) for h in headers), default=0)
    return [tuple(("",) * (max_depth - len(h)) + tuple(h)) for h in headers]


def _compute_col_widths(headers: Sequence[Sequence[str]], rows: Sequence[Sequence[Any]]) -> list[int]:
    norm_headers = _normalize_headers(headers)
    ncols = len(headers)
    widths: list[int] = []
    for col in range(ncols):
        col_texts = [str(r[col]) for r in rows]
        col_texts.append(str(norm_headers[col][-1]) if norm_headers else "")
        widths.append(max((len(text) for text in col_texts), default=0))
    return widths


def _adjust_widths_for_grouping(norm_headers: list[tuple[str, ...]], col_widths: list[int]) -> None:
    if not norm_headers:
        return
    max_depth = len(norm_headers[0])
    ncols = len(norm_headers)
    for level in range(max_depth):
        level_values = [norm_headers[col][level] for col in range(ncols)]
        start = 0
        while start < ncols:
            label = str(level_values[start])
            end = start
            while end < ncols and level_values[end] == label:
                end += 1
            span = end - start
            if label.strip() and span > 0:
                span_width = sum(col_widths[start:end]) + (span - 1) * 3
                label_len = len(label)
                if label_len > span_width:
                    extra = label_len - span_width
                    base_add = extra // span
                    rem = extra % span
                    for idx in range(start, end):
                        col_widths[idx] += base_add + (1 if (idx - start) < rem else 0)
            start = end


def _render_header_level(level_values: Sequence[str], col_widths: Sequence[int]) -> str:
    parts: list[str] = []
    idx = 0
    n = len(level_values)
    while idx < n:
        label = str(level_values[idx])
        end = idx
        while end < n and level_values[end] == label:
            end += 1
        span_width = sum(col_widths[idx:end]) + (end - idx - 1) * 3
        cell = " " * span_width if not label.strip() else label.center(span_width)
        parts.append(cell)
        idx = end
    return "| " + " | ".join(parts) + " |"


def format_table(headers: Sequence[Sequence[str]], rows: Sequence[Sequence[Any]]) -> str:
    """Render a Markdown table with grouped headers."""
    if not headers or not rows:
        return ""
    norm_headers = _normalize_headers(headers)
    col_widths = _compute_col_widths(headers, rows)
    _adjust_widths_for_grouping(norm_headers, col_widths)

    header_lines: list[str] = []
    max_depth = len(norm_headers[0]) if norm_headers else 0
    for level in range(max_depth):
        level_values = [norm_headers[col][level] for col in range(len(norm_headers))]
        header_lines.append(_render_header_level(level_values, col_widths))

    sep_parts = ["-" * width for width in col_widths]
    sep_line = "| " + " | ".join(sep_parts) + " |"

    body_lines: list[str] = []
    for row in rows:
        cells = [str(val).rjust(width) for val, width in zip(row, col_widths, strict=False)]
        body_lines.append("| " + " | ".join(cells) + " |")

    return "\n".join([*header_lines, sep_line, *body_lines])
