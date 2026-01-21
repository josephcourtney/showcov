from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from showcov.model.report import (
    BranchesSection,
    BranchGap,
    DiffSection,
    LinesSection,
    Report,
    SourceLine,
    SummarySection,
    UncoveredFile,
    UncoveredRange,
)

if TYPE_CHECKING:
    from showcov.render.render import RenderOptions

_NO_LINES = "No uncovered lines."
_NO_BRANCHES = "No uncovered branches."
_NO_SUMMARY = "No summary data."
_NO_DIFF_NEW = "No new uncovered lines."
_NO_DIFF_RESOLVED = "No resolved uncovered lines."


def _range_label(r: UncoveredRange) -> str:
    return f"{r.start}" if r.start == r.end else f"{r.start}-{r.end}"


def _format_code_line_rg(
    *,
    file_label: str | None,
    sl: SourceLine,
    r: UncoveredRange,
    options: RenderOptions,
) -> str:
    # Determine match vs context based on line number (if present).
    lineno = sl.line
    is_match = lineno is None or (r.start <= lineno <= r.end)
    sep = ":" if is_match else "-"

    parts: list[str] = []
    if not options.is_tty and options.show_paths and file_label:
        parts.append(file_label)

    # rg always shows line numbers when available; if unavailable, omit but keep sep for matches.
    if lineno is not None:
        parts.extend([str(lineno), sep])
        prefix = ":".join(parts[:-1]) + parts[-1]  # "path:line:" or "line:"
        return f"{prefix}{sl.code}"

    # No line number: in tty heading mode, just emit ":code"; in grep mode, "path::code" is ugly.
    if parts:
        prefix = ":".join(parts) + (sep or ":")
        return f"{prefix}{sl.code}"
    return f"{sep}{sl.code}" if is_match else f"-{sl.code}"


def _render_lines_file_rg(f: UncoveredFile, *, options: RenderOptions) -> str:
    file_label = f.file if (options.show_paths and f.file) else None
    heading_label = file_label if (options.is_tty and file_label) else None
    use_heading = heading_label is not None
    out: list[str] = []

    if heading_label is not None:
        out.append(heading_label)

    for idx, r in enumerate(f.uncovered):
        if idx > 0:
            out.append("--")

        if r.source:
            out.extend(
                _format_code_line_rg(file_label=file_label, sl=sl, r=r, options=options) for sl in r.source
            )
            continue

        # No snippets: emit range labels only
        label = _range_label(r)
        if use_heading:
            out.append(label)
        else:
            prefix = f"{file_label}:" if (options.show_paths and file_label) else ""
            out.append(f"{prefix}{label}")

    return "\n".join(out).rstrip()


def _render_lines_section_rg(sec: LinesSection, *, options: RenderOptions) -> str:
    if not sec.files:
        return _NO_LINES
    blocks = [b for b in (_render_lines_file_rg(f, options=options) for f in sec.files) if b]
    return "\n".join(blocks).rstrip() if blocks else _NO_LINES


def _render_branches_section_rg(sec: BranchesSection, *, options: RenderOptions) -> str:
    if not sec.gaps:
        return _NO_BRANCHES

    grouped = _group_rg_branch_entries(sec.gaps)
    use_heading = options.is_tty and options.show_paths
    return _format_rg_branch_entries(grouped, options=options, use_heading=use_heading)


def _group_rg_branch_entries(
    gaps: tuple[BranchGap, ...],
) -> dict[str, list[tuple[int, str, str]]]:
    by_file: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for gap in gaps:
        file_label = gap.file or ""
        for cond in gap.conditions:
            cov = "missing" if cond.coverage is None else f"{cond.coverage}%"
            typ = (cond.type or "branch").lower()
            if typ == "line":
                label = str(cond.number) if cond.number >= 0 else "line"
            else:
                suffix = f"#{cond.number}" if cond.number >= 0 else ""
                label = f"{typ}{suffix}"
            by_file[file_label].append((gap.line, label, cov))
    return by_file


def _format_rg_branch_entries(
    grouped: dict[str, list[tuple[int, str, str]]],
    *,
    options: RenderOptions,
    use_heading: bool,
) -> str:
    out: list[str] = []
    for file_label in sorted(grouped):
        entries = sorted(grouped[file_label])
        if use_heading:
            if file_label:
                out.append(file_label)
            for line, label, cov in entries:
                out.append(f"{line}:{label} {cov}")
        else:
            for line, label, cov in entries:
                prefix = f"{file_label}:" if (options.show_paths and file_label) else ""
                out.append(f"{prefix}{line}:{label} {cov}")
    return "\n".join(out).rstrip()


def _render_summary_section_rg(sec: SummarySection) -> str:
    if not sec.files:
        return _NO_SUMMARY

    out: list[str] = []
    for r in sec.files:
        st = r.statements
        bt = r.branches
        stmt_pct = (st.covered / st.total * 100.0) if st.total else 100.0
        br_pct = (bt.covered / bt.total * 100.0) if bt.total else 100.0
        out.append(
            f"{r.file}: statements {st.covered}/{st.total} ({stmt_pct:.1f}%) "
            f"branches {bt.covered}/{bt.total} ({br_pct:.1f}%)"
        )

    stt = sec.totals.statements
    btt = sec.totals.branches
    stmt_pct = (stt.covered / stt.total * 100.0) if stt.total else 100.0
    br_pct = (btt.covered / btt.total * 100.0) if btt.total else 100.0
    out.append(
        f"Overall: statements {stt.covered}/{stt.total} ({stmt_pct:.1f}%) "
        f"branches {btt.covered}/{btt.total} ({br_pct:.1f}%)"
    )
    return "\n".join(out).rstrip()


def _render_diff_section_rg(sec: DiffSection, *, options: RenderOptions) -> str:
    out: list[str] = []
    out.append("New")
    if sec.new:
        tmp = LinesSection(files=sec.new, summary=None)
        out.append(_render_lines_section_rg(tmp, options=options))
    else:
        out.append(_NO_DIFF_NEW)

    out.append("Resolved")
    if sec.resolved:
        tmp = LinesSection(files=sec.resolved, summary=None)
        out.append(_render_lines_section_rg(tmp, options=options))
    else:
        out.append(_NO_DIFF_RESOLVED)

    return "\n".join(out).rstrip()


def render_rg(report: Report, options: RenderOptions) -> str:
    """Ripgrep-like output. No filesystem I/O; uses snippets if present."""
    parts: list[str] = []

    if report.sections.lines is not None:
        parts.append(_render_lines_section_rg(report.sections.lines, options=options))
    if report.sections.branches is not None:
        parts.append(_render_branches_section_rg(report.sections.branches, options=options))
    if report.sections.summary is not None:
        parts.append(_render_summary_section_rg(report.sections.summary))
    if report.sections.diff is not None:
        parts.append(_render_diff_section_rg(report.sections.diff, options=options))

    return "\n\n".join([p for p in parts if p]).rstrip()


__all__ = ["render_rg"]
