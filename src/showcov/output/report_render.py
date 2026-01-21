"""Render unified :class:`~showcov.core.dataset.Report` objects."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from showcov.core.files import normalize_path
from showcov.core.types import Format
from showcov.output.human import format_human
from showcov.output.json import format_json_v2
from showcov.output.rg import format_rg
from showcov.output.table import format_table

_NO_LINES = "No uncovered lines."
_NO_BRANCHES = "No uncovered branches."
_NO_SUMMARY = "No summary data."
_NO_DIFF_NEW = "No new uncovered lines."
_NO_DIFF_RESOLVED = "No resolved uncovered lines."

if TYPE_CHECKING:
    from showcov.core import Report, UncoveredSection
    from showcov.core.coverage import BranchCondition, BranchGap
    from showcov.output.base import OutputMeta


def render_report(report: Report, fmt: Format, meta: OutputMeta) -> str:
    """Render *report* using *fmt* and *meta*."""
    if fmt is Format.JSON:
        return format_json_v2(report)
    if fmt is Format.RG:
        return format_rg(report, meta)
    if fmt is Format.HUMAN:
        return _render_human(report, meta)
    msg = f"Unsupported format: {fmt!r}"
    raise ValueError(msg)


def _render_human(report: Report, meta: OutputMeta) -> str:
    registry: dict[str, tuple[str, Callable]] = {
        "lines": ("Uncovered Lines", lambda: _render_lines_human(report, meta)),
        "branches": ("Uncovered Branches", lambda: _render_branches_human(report, meta)),
        "summary": ("Summary", lambda: _render_summary_human(report, meta)),
        "diff": ("Diff", lambda: _render_diff_human(report, meta)),
    }
    parts: list[str] = []
    for name in report.sections:
        entry = registry.get(name)
        if not entry:
            continue
        title, render = entry
        body = render()
        if body:
            parts.extend((_heading(title, meta), body))
    return "\n\n".join(parts)


def _heading(text: str, meta: OutputMeta) -> str:
    if meta.color and meta.is_tty:
        return f"\x1b[1m{text}\x1b[0m"
    return text


def _render_lines_human(report: Report, meta: OutputMeta) -> str:
    attachments = cast("dict[str, Any]", report.attachments.get("lines"))
    sections = cast("list[UncoveredSection]", attachments.get("sections", []))
    body = format_human(sections, meta) if sections else _NO_LINES
    data = cast("dict[str, Any]", report.sections.get("lines"))
    options = cast("dict[str, Any]", cast("dict[str, Any]", report.meta)["options"])
    details = _summarize_line_sections(data, options)
    return "\n".join([part for part in [body, *details] if part])


def _render_branches_human(report: Report, meta: OutputMeta) -> str:
    attachments = cast("dict[str, Any]", report.attachments.get("branches"))
    gaps = cast("list[BranchGap]", attachments.get("gaps", []))
    if not gaps:
        return _NO_BRANCHES
    base = meta.coverage_xml.parent
    headers: list[tuple[str, ...]] = []
    if meta.show_paths:
        headers.append(("File",))
    headers.extend([("Line",), ("Condition",), ("Coverage",)])
    rows: list[list[str]] = []
    for gap in gaps:
        file_label = normalize_path(Path(gap.file), base=base).as_posix() if meta.show_paths else ""
        for cond in gap.conditions:
            coverage = f"{cond.coverage}%" if cond.coverage is not None else "missing"
            condition_label = _format_condition(cond)
            row: list[str] = []
            if meta.show_paths:
                row.append(file_label)
            row.extend([str(gap.line), condition_label, coverage])
            rows.append(row)
    table = format_table(headers, rows, color=meta.color) if rows else ""
    return table or _NO_BRANCHES


def _render_summary_human(report: Report, meta: OutputMeta) -> str:  # noqa: PLR0914
    summary = cast("dict[str, Any]", report.sections.get("summary"))
    headers = [
        ("File",),
        ("Statements", "Total"),
        ("Statements", "Covered"),
        ("Statements", "Missed"),
        ("Branches", "Total"),
        ("Branches", "Covered"),
        ("Branches", "Missed"),
    ]
    rows: list[list[str]] = []
    for entry in _as_list(summary.get("files")):
        if not isinstance(entry, Mapping):
            continue
        stmt = _as_mapping(entry.get("statements"))
        br = _as_mapping(entry.get("branches"))
        rows.append([
            str(entry.get("file", "")),
            str(stmt.get("total", 0)),
            str(stmt.get("covered", 0)),
            str(stmt.get("missed", 0)),
            str(br.get("total", 0)),
            str(br.get("covered", 0)),
            str(br.get("missed", 0)),
        ])
    # Summary rendering doesn't currently receive `meta`; default to colored table.
    table = format_table(headers, rows, color=meta.color) if rows else ""
    totals = _as_mapping(summary.get("totals"))
    stmt_tot = _as_mapping(totals.get("statements"))
    br_tot = _as_mapping(totals.get("branches"))
    footer_parts = []
    if stmt_tot:
        stmt_total = stmt_tot.get("total", 0)
        stmt_missed = stmt_tot.get("missed", 0)
        stmt_pct = (1 - (stmt_missed / stmt_total)) * 100 if stmt_total else 100
        footer_parts.append(f"Statements: {stmt_total - stmt_missed}/{stmt_total} covered ({stmt_pct:.1f}%)")
    if br_tot:
        br_total = br_tot.get("total", 0)
        br_missed = br_tot.get("missed", 0)
        br_pct = (1 - (br_missed / br_total)) * 100 if br_total else 100
        footer_parts.append(f"Branches: {br_total - br_missed}/{br_total} covered ({br_pct:.1f}%)")
    return "\n".join([part for part in [table, "\n".join(footer_parts)] if part])


def _render_diff_human(report: Report, meta: OutputMeta) -> str:
    parts: list[str] = []
    diff_data = _as_mapping(report.attachments.get("diff"))
    new_sections_raw = _as_list(diff_data.get("new"))
    resolved_sections_raw = _as_list(diff_data.get("resolved"))
    new_sections = cast("list[UncoveredSection]", new_sections_raw)
    resolved_sections = cast("list[UncoveredSection]", resolved_sections_raw)
    parts.append(_subheading("New", meta))
    if new_sections:
        parts.append(format_human(list(new_sections), meta))
    else:
        parts.append(_NO_DIFF_NEW)
    parts.append(_subheading("Resolved", meta))
    if resolved_sections:
        parts.append(format_human(list(resolved_sections), meta))
    else:
        parts.append(_NO_DIFF_RESOLVED)
    return "\n".join(parts)


def _subheading(text: str, meta: OutputMeta) -> str:
    if meta.color and meta.is_tty:
        return f"\x1b[1m{text}\x1b[0m"
    return text


def _format_condition(cond: BranchCondition) -> str:
    number = cond.number if cond.number >= 0 else None
    typ = (cond.type or "branch").lower()
    if typ == "line" and number is not None:
        label = str(number)
    elif typ == "line":
        label = "line"
    else:
        suffix = f"#{number}" if number is not None else ""
        label = f"{typ}{suffix}"
    return label


def _slugify(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text)


def _summarize_line_sections(data: object, options: Mapping[str, Any]) -> list[str]:
    """Render optional line stats, guarded by flags from report.meta['options'].

    Rules:
      - Only show aggregate total if options['aggregate_stats'] is True and a
        valid 'summary.uncovered' value exists.
      - Only show per-file stats if options['file_stats'] is True and a 'counts'
        object exists for that file. Do not fabricate zeros.
    """
    mapping = _as_mapping(data)
    if not mapping:
        return []
    extras: list[str] = []

    # Aggregate uncovered lines
    if bool(options.get("aggregate_stats")):
        summary = _as_mapping(mapping.get("summary"))
        if "uncovered" in summary:
            extras.append(f"Total uncovered lines: {summary['uncovered']}")

    # Per-file counts
    if bool(options.get("file_stats")):
        for entry in _as_list(mapping.get("files")):
            if not isinstance(entry, Mapping):
                continue
            counts = _as_mapping(entry.get("counts"))
            # Only render when counts are present; no defaulting to zeros.
            if not counts:
                continue
            file_label = entry.get("file")
            if not file_label:
                continue
            total = counts.get("total")
            uncovered = counts.get("uncovered")
            # Both numbers must exist to compute a percentage.
            if isinstance(total, int) and isinstance(uncovered, int) and total >= 0 and uncovered >= 0:
                pct = (uncovered / total * 100) if total else 0
                extras.append(f"{file_label}: {uncovered} uncovered ({pct:.0f}% of {total})")
    return extras


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return cast("Mapping[str, Any]", value)
    return cast("Mapping[str, Any]", {})


def _as_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


__all__ = ["render_report"]
