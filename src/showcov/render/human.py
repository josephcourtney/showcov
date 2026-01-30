from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from io import StringIO
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from showcov.render.table import format_table

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from showcov.model.report import (
        BranchesSection,
        DiffSection,
        LinesSection,
        Report,
        SourceLine,
        SummaryRow,
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


def _is_fully_covered_summary_row(r: SummaryRow) -> bool:
    stmt_ok = (r.statements.total == 0) or (r.statements.missed == 0)
    br_ok = (r.branches.total == 0) or (r.branches.missed == 0)
    return bool(stmt_ok and br_ok and r.uncovered_lines == 0)


def _summary_visible_files(sec: SummarySection, *, options: RenderOptions) -> list[SummaryRow]:
    files = list(sec.files)
    if not options.show_covered:
        files = [r for r in files if not _is_fully_covered_summary_row(r)]
    return files


def _render_top_offenders(
    files: Sequence[SummaryRow],
    *,
    options: RenderOptions,
) -> str:
    def _top_by(key_fn: Callable[[SummaryRow], tuple[int, int, str]], n: int = 10) -> list[SummaryRow]:
        return sorted(files, key=key_fn)[:n]

    top_stmt = _top_by(lambda r: (-r.statements.missed, -r.uncovered_lines, r.file))
    top_br = _top_by(lambda r: (-r.branches.missed, -r.uncovered_lines, r.file))

    def _render_top(title: str, rows_in: Sequence[SummaryRow]) -> str:
        t = Table(show_header=True, header_style="bold")
        t.add_column(title)
        t.add_column("Miss stmt", justify="right")
        t.add_column("Stmt%", justify="right")
        t.add_column("Miss br", justify="right")
        t.add_column("Br%", justify="right")
        t.add_column("Uncov lines", justify="right")
        for r in rows_in:
            brpct = "—" if r.branch_pct is None else f"{r.branch_pct:.1f}%"
            t.add_row(
                r.file,
                str(r.statements.missed),
                f"{r.statement_pct:.1f}%",
                str(r.branches.missed),
                brpct,
                str(r.uncovered_lines),
            )
        return _render_rich_table(t, color=options.color)

    parts: list[str] = [
        _subheading("Top offenders (statements)", options),
        _render_top("File", top_stmt),
        _subheading("Top offenders (branches)", options),
        _render_top("File", top_br),
    ]
    return "\n".join([p for p in parts if p]).rstrip()


def _render_directory_rollups(
    files: Sequence[SummaryRow],
    *,
    options: RenderOptions,
) -> str:
    if not options.summary_group:
        return ""
    depth = max(1, int(options.summary_group_depth))
    grouped: dict[str, list[SummaryRow]] = defaultdict(list)

    def group_key(path: str) -> str:
        p = PurePosixPath(path)
        parts = p.parts
        if not parts:
            return path
        return "/".join(parts[: min(depth, len(parts))])

    for r in files:
        grouped[group_key(r.file)].append(r)

    roll_rows: list[list[str]] = []
    for g in sorted(grouped):
        rs = grouped[g]
        st_total = sum(x.statements.total for x in rs)
        st_cov = sum(x.statements.covered for x in rs)
        st_miss = sum(x.statements.missed for x in rs)
        br_total = sum(x.branches.total for x in rs)
        br_cov = sum(x.branches.covered for x in rs)
        br_miss = sum(x.branches.missed for x in rs)
        uncov = sum(x.uncovered_lines for x in rs)
        ranges = sum(x.uncovered_ranges for x in rs)

        stmt_pct = 100.0 if st_total == 0 else (st_cov / st_total) * 100.0
        br_pct = None if br_total == 0 else (br_cov / br_total) * 100.0
        br_pct_s = "—" if br_pct is None else f"{br_pct:.1f}%"

        roll_rows.append([
            g,
            f"{stmt_pct:.1f}%",
            str(st_miss),
            br_pct_s,
            str(br_miss),
            str(uncov),
            str(ranges),
        ])

    roll_headers = [
        ("Dir",),
        ("Stmt%",),
        ("Miss stmt",),
        ("Br%",),
        ("Miss br",),
        ("Uncov lines",),
        ("Ranges",),
    ]
    roll_table = format_table(roll_headers, roll_rows, color=options.color) if roll_rows else ""
    if not roll_table:
        return ""
    return "\n".join([_subheading("Directory rollups", options), roll_table]).rstrip()


def _render_files_table(
    files: Sequence[SummaryRow],
    *,
    options: RenderOptions,
) -> str:
    headers = [
        ("File",),
        ("Stmt%",),
        ("Statements", "Total"),
        ("Statements", "Covered"),
        ("Statements", "Missed"),
        ("Br%",),
        ("Branches", "Total"),
        ("Branches", "Covered"),
        ("Branches", "Missed"),
        ("Uncov", "Lines"),
        ("Uncov", "Ranges"),
    ]
    have_deltas = any(r.delta_missed_statements is not None for r in files)
    if have_deltas:
        headers.extend([
            ("Δ miss", "stmt"),
            ("Δ miss", "br"),
            ("Δ uncov", "lines"),
        ])

    def fmt_delta(x: int | None) -> str:
        if x is None:
            return ""
        return f"{x:+d}"

    rows: list[list[str]] = []
    for r in files:
        brpct = "—" if r.branch_pct is None else f"{r.branch_pct:.1f}%"
        row = [
            r.file + ("  [untested]" if r.untested else "") + ("  [tiny]" if r.tiny else ""),
            f"{r.statement_pct:.1f}%",
            str(r.statements.total),
            str(r.statements.covered),
            str(r.statements.missed),
            brpct,
            str(r.branches.total),
            str(r.branches.covered),
            str(r.branches.missed),
            str(r.uncovered_lines),
            str(r.uncovered_ranges),
        ]
        if have_deltas:
            row.extend([
                fmt_delta(r.delta_missed_statements),
                fmt_delta(r.delta_missed_branches),
                fmt_delta(r.delta_uncovered_lines),
            ])
        rows.append(row)

    table = format_table(headers, rows, color=options.color) if rows else ""
    if not table:
        return ""
    return "\n".join([_subheading("Files", options), table]).rstrip()


def _render_summary_footer(sec: SummarySection, *, have_deltas: bool) -> str:
    st = sec.totals.statements
    bt = sec.totals.branches
    stmt_pct = (st.covered / st.total * 100.0) if st.total else 100.0
    br_pct = (bt.covered / bt.total * 100.0) if bt.total else 100.0
    parts = [
        f"Overall (weighted): statements {st.covered}/{st.total} covered ({stmt_pct:.1f}%)",
        f"Overall (weighted): branches {bt.covered}/{bt.total} covered ({br_pct:.1f}%)",
        f"Files with branches: {sec.files_with_branches}/{sec.total_files}",
        ("Note: baseline deltas are (current - baseline)." if have_deltas else ""),
    ]
    return "\n".join([p for p in parts if p]).rstrip()


def _render_summary_section(sec: SummarySection, *, options: RenderOptions) -> str:
    files = _summary_visible_files(sec, options=options)
    if not files:
        return _NO_SUMMARY

    have_deltas = any(r.delta_missed_statements is not None for r in files)

    blocks: list[str] = []
    blocks.append(_render_top_offenders(files, options=options))

    rollups = _render_directory_rollups(files, options=options)
    if rollups:
        blocks.append(rollups)

    file_table = _render_files_table(files, options=options)
    if file_table:
        blocks.append(file_table)

    footer = _render_summary_footer(sec, have_deltas=have_deltas)
    if footer:
        blocks.append(footer)

    return "\n".join([b for b in blocks if b]).rstrip()


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
