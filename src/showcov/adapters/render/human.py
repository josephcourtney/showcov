from __future__ import annotations

import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from rich.table import Table

from showcov.adapters.render.table import format_table, render_table
from showcov.model.metrics import pct  # <-- you also hit NameError earlier
from showcov.model.report import (
    SummaryCounts,
    SummaryRow,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from showcov.adapters.render.render import RenderOptions
    from showcov.model.report import (
        BranchesSection,
        LinesSection,
        Report,
        SourceLine,
        SummarySection,
        UncoveredFile,
    )

_NO_LINES = "No uncovered lines."
_NO_BRANCHES = "No uncovered branches."
_NO_SUMMARY = "No summary data."


def _limit_display_path(path: str, *, max_depth: int | None) -> str:
    """Truncate a posix-ish relative path to at most max_depth components.

    Examples (max_depth=1):
      pkg/mod.py      -> pkg/
      pkg/sub/a.py    -> pkg/
      mod.py          -> mod.py
    """
    if max_depth is None:
        return path
    p = PurePosixPath(path)
    parts = list(p.parts)
    if len(parts) <= 1:
        return path
    # keep first max_depth components; display as a directory rollup label
    kept = parts[:max_depth]
    return "/".join(kept) + "/"


def _heading(text: str, options: RenderOptions) -> str:
    return f"\x1b[1m{text}\x1b[0m" if (options.color and options.is_tty) else text


def _subheading(text: str, options: RenderOptions) -> str:
    return f"\x1b[1m{text}\x1b[0m" if (options.color and options.is_tty) else text


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
            label = _limit_display_path(f.file, max_depth=options.summary_max_depth)
            blocks.append(f"{label}  File")
        # Table of ranges (always)
        t = Table(show_header=True, header_style="bold")
        t.add_column("Start", justify="right")
        t.add_column("End", justify="right")
        t.add_column("# Lines", justify="right")
        for r in f.uncovered:
            t.add_row(str(r.start), str(r.end), str(r.line_count))
        blocks.append(render_table(t, color=options.color))

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
                fname = _limit_display_path(f.file, max_depth=options.summary_max_depth)
                blocks.append(f"{fname}:{label}")
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
        if options.show_paths and gap.file:
            file_label = _limit_display_path(gap.file, max_depth=options.summary_max_depth)
        else:
            file_label = ""

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
        return render_table(t, color=options.color)

    parts: list[str] = [
        _subheading("Top offenders (statements)", options),
        _render_top("File", top_stmt),
        _subheading("Top offenders (branches)", options),
        _render_top("File", top_br),
    ]
    return "\n".join([p for p in parts if p]).rstrip()


def _directory_rollup_row(group: str, rows: Sequence[SummaryRow]) -> list[str]:
    st_total = sum(r.statements.total for r in rows)
    st_cov = sum(r.statements.covered for r in rows)
    st_miss = sum(r.statements.missed for r in rows)
    br_total = sum(r.branches.total for r in rows)
    br_cov = sum(r.branches.covered for r in rows)
    br_miss = sum(r.branches.missed for r in rows)
    uncov = sum(r.uncovered_lines for r in rows)
    ranges = sum(r.uncovered_ranges for r in rows)

    stmt_pct = 100.0 if st_total == 0 else (st_cov / st_total) * 100.0
    br_pct = None if br_total == 0 else (br_cov / br_total) * 100.0
    br_pct_s = "—" if br_pct is None else f"{br_pct:.1f}%"

    return [
        group,
        f"{stmt_pct:.1f}%",
        str(st_miss),
        br_pct_s,
        str(br_miss),
        str(uncov),
        str(ranges),
    ]


@dataclass
class _DirNode:
    name: str  # single path component, e.g. "adapters"
    path: str  # full path from root, e.g. "src/showcov/adapters"
    children: dict[str, _DirNode] = field(default_factory=dict)
    files: list[SummaryRow] = field(default_factory=list)


def _insert_file(root: _DirNode, row: SummaryRow) -> None:
    p = PurePosixPath(row.file)
    parts = list(p.parts)

    if len(parts) <= 1:
        root.files.append(row)
        return

    dir_parts = parts[:-1]

    cur = root
    accum: list[str] = []
    for part in dir_parts:
        accum.append(part)
        full = "/".join(accum)
        nxt = cur.children.get(part)
        if nxt is None:
            nxt = _DirNode(name=part, path=full)
            cur.children[part] = nxt
        cur = nxt

    cur.files.append(row)


def _aggregate_dir(node: _DirNode) -> SummaryRow:
    # Aggregate across *all descendant files*
    all_files: list[SummaryRow] = []

    def collect(n: _DirNode) -> None:
        all_files.extend(n.files)
        for child in n.children.values():
            collect(child)

    collect(node)

    st_total = sum(r.statements.total for r in all_files)
    st_cov = sum(r.statements.covered for r in all_files)
    st_miss = sum(r.statements.missed for r in all_files)

    br_total = sum(r.branches.total for r in all_files)
    br_cov = sum(r.branches.covered for r in all_files)
    br_miss = sum(r.branches.missed for r in all_files)

    uncov_lines = sum(r.uncovered_lines for r in all_files)
    uncov_ranges = sum(r.uncovered_ranges for r in all_files)

    stmt_pct = pct(st_cov, st_total)
    br_pct = None if br_total == 0 else pct(br_cov, br_total)

    return SummaryRow(
        file=node.path + "/",
        statements=SummaryCounts(total=st_total, covered=st_cov, missed=st_miss),
        branches=SummaryCounts(total=br_total, covered=br_cov, missed=br_miss),
        statement_pct=float(stmt_pct),
        branch_pct=(None if br_pct is None else float(br_pct)),
        uncovered_lines=int(uncov_lines),
        uncovered_ranges=int(uncov_ranges),
        untested=False,
        tiny=False,
    )


def _tree_order_rows(root: _DirNode, *, max_depth: int | None) -> list[SummaryRow]:
    """
    Walk the _DirNode tree in directory-tree order and emit:
      - a rollup row for each directory (node.path + "/"), displayed with tree glyphs
      - then files in that directory (basename), displayed with tree glyphs.

    Returns SummaryRow objects where `.file` is already the display label (tree-style).
    """
    out: list[SummaryRow] = []

    def walk_dir(
        node: _DirNode,
        *,
        ancestor_last: list[bool],
        is_last: bool,
        is_root: bool,
        depth: int,  # depth in directory components; root synthetic node is depth=0
    ) -> None:
        if not is_root:
            name = node.name + "/"
            prefix = _tree_prefix(ancestor_last, is_last=is_last)
            out.append(_with_display_file(_aggregate_dir(node), prefix + name))

        # If we've reached max_depth, do not expand this directory's contents.
        # depth counts real directories from the top; root is depth 0.
        if not is_root and (max_depth is not None and depth >= max_depth):
            return

        dir_items = sorted(node.children.items(), key=operator.itemgetter(0))
        file_items = sorted(node.files, key=lambda r: PurePosixPath(r.file).name)

        total_children = len(dir_items) + len(file_items)
        next_ancestor_last = ancestor_last.copy() if is_root else [*ancestor_last, is_last]

        idx = 0
        for _dirname, child in dir_items:
            idx += 1
            child_is_last = idx == total_children
            walk_dir(
                child,
                ancestor_last=next_ancestor_last,
                is_last=child_is_last,
                is_root=False,
                depth=depth + 1,
            )

        for r in file_items:
            idx += 1
            file_is_last = idx == total_children
            prefix = _tree_prefix(next_ancestor_last, is_last=file_is_last)
            fname = PurePosixPath(r.file).name
            out.append(_with_display_file(r, prefix + fname))

    walk_dir(root, ancestor_last=[], is_last=True, is_root=True, depth=0)
    return out


def _tree_prefix(ancestor_last: list[bool], *, is_last: bool) -> str:
    """
    Build a tree(1)-style prefix.

    ancestor_last: for each ancestor level, True if that ancestor was the last child.
    is_last: whether the current node is the last among its siblings.
    """
    if not ancestor_last:
        return ""
    # For each ancestor: draw a vertical continuation if ancestor wasn't last.
    parts = [("    " if last else "│   ") for last in ancestor_last]
    parts.append("└── " if is_last else "├── ")
    return "".join(parts)


def _with_display_file(row: SummaryRow, display: str) -> SummaryRow:
    """Copy a SummaryRow but replace its .file label with a display string."""
    # SummaryRow is a dataclass (frozen=True), so use dataclasses.replace
    from dataclasses import replace

    return replace(row, file=display)


def _render_summary_tree_table(
    files: Sequence[SummaryRow],
    *,
    options: RenderOptions,
) -> str:
    # Build tree
    root = _DirNode(name="", path="")

    for r in files:
        _insert_file(root, r)

    rows_in_order = _tree_order_rows(
        root,
        max_depth=options.summary_max_depth,
    )

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

    rows: list[list[str]] = []
    for r in rows_in_order:
        brpct = "—" if r.branch_pct is None else f"{r.branch_pct:.1f}%"

        # Preserve your existing file tags for *files only*
        label = r.file
        if not label.rstrip().endswith("/"):
            label = label + ("  [untested]" if r.untested else "") + ("  [tiny]" if r.tiny else "")

        rows.append([
            label,
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
        ])

    table = format_table(headers, rows, color=options.color) if rows else ""
    if not table:
        return ""
    return "\n".join([_subheading("Summary", options), table]).rstrip()


def _render_summary_footer(sec: SummarySection) -> str:
    st = sec.totals.statements
    bt = sec.totals.branches
    stmt_pct = (st.covered / st.total * 100.0) if st.total else 100.0
    br_pct = (bt.covered / bt.total * 100.0) if bt.total else 100.0
    parts = [
        f"Overall (weighted): statements {st.covered}/{st.total} covered ({stmt_pct:.1f}%)",
        f"Overall (weighted): branches {bt.covered}/{bt.total} covered ({br_pct:.1f}%)",
        f"Files with branches: {sec.files_with_branches}/{sec.total_files}",
    ]
    return "\n".join([p for p in parts if p]).rstrip()


def _render_summary_section(sec: SummarySection, *, options: RenderOptions) -> str:
    files = _summary_visible_files(sec, options=options)
    if not files:
        return _NO_SUMMARY

    blocks: list[str] = []

    tree_table = _render_summary_tree_table(files, options=options)
    if tree_table:
        blocks.append(tree_table)

    footer = _render_summary_footer(sec)
    if footer:
        blocks.append(footer)

    return "\n".join([b for b in blocks if b]).rstrip()


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
    return "\n\n".join([p for p in parts if p]).rstrip()


__all__ = ["render_human"]
