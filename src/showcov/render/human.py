from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from showcov.render.table import format_table

if TYPE_CHECKING:
    from collections.abc import Iterable

    from showcov.model.report import (
        BranchesSection,
        DiffSection,
        LinesSection,
        Report,
        SourceLine,
        SummarySection,
        UncoveredFile,
    )
    from showcov.render.render import RenderOptions

_NO_LINES = "No uncovered lines."
_NO_BRANCHES = "No uncovered branches."
_NO_SUMMARY = "No summary data."
_NO_DIFF_NEW = "No new uncovered lines."
_NO_DIFF_RESOLVED = "No resolved uncovered lines."


def _heading(text: str, options: RenderOptions) -> str:
    return f"\x1b[1m{text}\x1b[0m" if (options.color and options.is_tty) else text


def _subheading(text: str, options: RenderOptions) -> str:
    return f"\x1b[1m{text}\x1b[0m" if (options.color and options.is_tty) else text


def _render_rich_table(table: Table, *, color: bool) -> str:
    buf = StringIO()
    console = Console(
        file=buf,
        force_terminal=color,
        color_system="standard" if color else None,
        no_color=not color,
        width=10_000,
    )
    console.print(table)
    return buf.getvalue().rstrip()


def _render_lines_ranges(
    files: Iterable[UncoveredFile],
    *,
    options: RenderOptions,
) -> str:
    # Group into per-file blocks when paths are shown and file labels exist.
    blocks: list[str] = []
    any_files = False

    for f in files:
        if not f.uncovered:
            continue
        any_files = True

        if options.show_paths and f.file:
            blocks.append(f"{f.file}  File")
        # Table of ranges (always)
        t = Table(show_header=True, header_style="bold")
        t.add_column("Start", justify="right")
        t.add_column("End", justify="right")
        t.add_column("# Lines", justify="right")
        for r in f.uncovered:
            t.add_row(str(r.start), str(r.end), str(r.line_count))
        blocks.append(_render_rich_table(t, color=options.color))

    if not any_files:
        return _NO_LINES

    return "\n".join(blocks).rstrip()


def _render_source_line(sl: SourceLine, *, options: RenderOptions) -> str:
    # Human mode: " 123: code" (or "code" if no line numbers requested/available)
    prefix = f"{sl.line:>4}: " if options.show_line_numbers and sl.line is not None else ""
    txt = prefix + sl.code
    if sl.tag:
        txt += f"  [{sl.tag}]"
    return txt


def _render_lines_code_blocks(
    files: Iterable[UncoveredFile],
    *,
    options: RenderOptions,
) -> str:
    # Only render blocks if snippets are present in the model.
    blocks: list[str] = []

    for f in files:
        for r in f.uncovered:
            if not r.source:
                continue
            label = f"{r.start}-{r.end}" if r.start != r.end else f"{r.start}"
            if options.show_paths and f.file:
                blocks.append(f"{f.file}:{label}")
            else:
                blocks.append(label)
            blocks.extend(_render_source_line(sl, options=options) for sl in r.source)
            blocks.append("")  # blank line between ranges

    return "\n".join(blocks).rstrip()


def _render_lines_section(sec: LinesSection, *, options: RenderOptions) -> str:
    body = _render_lines_ranges(sec.files, options=options)

    extra: list[str] = []
    if sec.summary is not None:
        extra.append(f"Total uncovered lines: {sec.summary.uncovered}")

    # Optional per-file stats, if present in the model
    for f in sec.files:
        if f.counts is None:
            continue
        if options.show_paths and f.file:
            uncovered = f.counts.uncovered
            total = f.counts.total
            pct = (uncovered / total * 100.0) if total else 0.0
            extra.append(f"{f.file}: {uncovered} uncovered ({pct:.0f}% of {total})")

    code = _render_lines_code_blocks(sec.files, options=options)

    parts = [body]
    if extra:
        parts.append("\n".join(extra))
    if code:
        parts.append(code)
    return "\n".join([p for p in parts if p]).rstrip()


def _render_branches_section(sec: BranchesSection, *, options: RenderOptions) -> str:
    if not sec.gaps:
        return _NO_BRANCHES

    headers: list[tuple[str, ...]] = []
    if options.show_paths:
        headers.append(("File",))
    headers.extend([("Line",), ("Condition",), ("Coverage",)])

    rows: list[list[str]] = []
    for gap in sec.gaps:
        file_label = gap.file if (options.show_paths and gap.file) else ""
        for cond in gap.conditions:
            cov = "missing" if cond.coverage is None else f"{cond.coverage}%"
            typ = (cond.type or "branch").lower()
            if typ == "line":
                condition_label = str(cond.number) if cond.number >= 0 else "line"
            else:
                suffix = f"#{cond.number}" if cond.number >= 0 else ""
                condition_label = f"{typ}{suffix}"

            row: list[str] = []
            if options.show_paths:
                row.append(file_label)
            row.extend([str(gap.line), condition_label, cov])
            rows.append(row)

    return format_table(headers, rows, color=options.color) or _NO_BRANCHES


def _render_summary_section(sec: SummarySection, *, options: RenderOptions) -> str:
    headers = [
        ("File",),
        ("Statements", "Total"),
        ("Statements", "Covered"),
        ("Statements", "Missed"),
        ("Branches", "Total"),
        ("Branches", "Covered"),
        ("Branches", "Missed"),
    ]

    rows: list[list[str]] = [
        [
            r.file,
            str(r.statements.total),
            str(r.statements.covered),
            str(r.statements.missed),
            str(r.branches.total),
            str(r.branches.covered),
            str(r.branches.missed),
        ]
        for r in sec.files
    ]

    table = format_table(headers, rows, color=options.color) if rows else ""
    if not table:
        return _NO_SUMMARY

    st = sec.totals.statements
    bt = sec.totals.branches
    stmt_pct = (st.covered / st.total * 100.0) if st.total else 100.0
    br_pct = (bt.covered / bt.total * 100.0) if bt.total else 100.0

    footer = "\n".join([
        f"Statements: {st.covered}/{st.total} covered ({stmt_pct:.1f}%)",
        f"Branches: {bt.covered}/{bt.total} covered ({br_pct:.1f}%)",
    ])
    return f"{table}\n{footer}".rstrip()


def _render_diff_section(sec: DiffSection, *, options: RenderOptions) -> str:
    parts: list[str] = []
    parts.append(_subheading("New", options))
    if sec.new:
        parts.append(_render_lines_ranges(sec.new, options=options))
        code = _render_lines_code_blocks(sec.new, options=options)
        if code:
            parts.append(code)
    else:
        parts.append(_NO_DIFF_NEW)

    parts.append(_subheading("Resolved", options))
    if sec.resolved:
        parts.append(_render_lines_ranges(sec.resolved, options=options))
        code = _render_lines_code_blocks(sec.resolved, options=options)
        if code:
            parts.append(code)
    else:
        parts.append(_NO_DIFF_RESOLVED)

    return "\n".join(parts).rstrip()


def render_human(report: Report, options: RenderOptions) -> str:
    """Render report in a sectioned, human-friendly format.

    This renderer performs no filesystem I/O; snippets must already exist in the model.
    """
    parts: list[str] = []

    for name in report.sections.present():
        if name == "lines":
            sec = report.sections.lines
            if sec is None:
                msg = "render_human expected the lines section to be present but it is missing"
                raise ValueError(msg)
            parts.extend((_heading("Uncovered Lines", options), _render_lines_section(sec, options=options)))
        elif name == "branches":
            sec = report.sections.branches
            if sec is None:
                msg = "render_human expected the branches section to be present but it is missing"
                raise ValueError(msg)
            parts.extend((
                _heading("Uncovered Branches", options),
                _render_branches_section(sec, options=options),
            ))
        elif name == "summary":
            sec = report.sections.summary
            if sec is None:
                msg = "render_human expected the summary section to be present but it is missing"
                raise ValueError(msg)
            parts.extend((_heading("Summary", options), _render_summary_section(sec, options=options)))
        elif name == "diff":
            sec = report.sections.diff
            if sec is None:
                msg = "render_human expected the diff section to be present but it is missing"
                raise ValueError(msg)
            parts.extend((_heading("Diff", options), _render_diff_section(sec, options=options)))

    return "\n\n".join([p for p in parts if p]).rstrip()


__all__ = ["render_human"]
