"""Render unified :class:`~showcov.core.dataset.Report` objects."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from showcov.core.files import normalize_path, read_file_lines
from showcov.core.types import Format
from showcov.output.human import format_human
from showcov.output.json import format_json_v2
from showcov.output.markdown import format_markdown
from showcov.output.table import format_table

if TYPE_CHECKING:
    from collections.abc import Iterable

    from showcov.core import Report, UncoveredSection
    from showcov.core.coverage import BranchCondition, BranchGap
    from showcov.output.base import OutputMeta


def render_report(report: Report, fmt: Format, meta: OutputMeta) -> str:
    """Render *report* using *fmt* and *meta*."""
    if fmt is Format.JSON:
        return format_json_v2(report)
    if fmt is Format.HUMAN:
        return _render_human(report, meta)
    if fmt is Format.MARKDOWN:
        return _render_markdown(report, meta)
    if fmt is Format.HTML:
        return _render_html(report, meta)
    msg = f"Unsupported format: {fmt!r}"
    raise ValueError(msg)


def _render_human(report: Report, meta: OutputMeta) -> str:
    sections: list[str] = []
    for name in report.sections:
        if name == "lines":
            sections.extend((_heading("Lines", meta), _render_lines_human(report, meta)))
        elif name == "branches":
            sections.extend((_heading("Branches", meta), _render_branches_human(report, meta)))
        elif name == "summary":
            sections.extend((_heading("Summary", meta), _render_summary_human(report)))
        elif name == "diff":
            sections.extend((_heading("Diff", meta), _render_diff_human(report, meta)))
    return "\n\n".join(part for part in sections if part)


def _render_markdown(report: Report, meta: OutputMeta) -> str:
    parts: list[str] = []
    for name in report.sections:
        if name == "lines":
            parts.extend(("## Lines", _render_lines_markdown(report, meta) or "_No uncovered lines._"))
        elif name == "branches":
            parts.append("## Branches")
            rendered = _render_branches_markdown(report, meta)
            parts.append(rendered or "_No uncovered branches._")
        elif name == "summary":
            parts.extend(("## Summary", _render_summary_markdown(report)))
        elif name == "diff":
            parts.extend(("## Diff", _render_diff_markdown(report, meta)))
    return "\n\n".join(part for part in parts if part)


def _render_html(report: Report, meta: OutputMeta) -> str:
    sections: list[str] = ["<!DOCTYPE html>", "<html>", "<body>"]
    for name in report.sections:
        if name == "lines":
            sections.append(_render_lines_html(report, meta))
        elif name == "branches":
            sections.append(_render_branches_html(report, meta))
        elif name == "summary":
            sections.append(_render_summary_html(report))
        elif name == "diff":
            sections.append(_render_diff_html(report, meta))
    sections.extend(["</body>", "</html>"])
    return "\n".join(sections)


def _heading(text: str, meta: OutputMeta) -> str:
    if meta.color:
        return f"\x1b[1m{text}\x1b[0m"
    return text


def _render_lines_human(report: Report, meta: OutputMeta) -> str:
    attachments = _as_mapping(report.attachments.get("lines"))
    sections_raw = _as_list(attachments.get("sections"))
    sections = cast("list[UncoveredSection]", sections_raw)
    body = format_human(sections, meta) if sections else "No uncovered lines."
    data = report.sections.get("lines")
    details = _summarize_line_sections(data)
    return "\n".join([part for part in [body, *details] if part])


def _render_branches_human(report: Report, meta: OutputMeta) -> str:
    attachments = _as_mapping(report.attachments.get("branches"))
    gaps_raw = _as_list(attachments.get("gaps"))
    gaps = cast("list[BranchGap]", gaps_raw)
    if not gaps:
        return "No uncovered branches."
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
    table = format_table(headers, rows) if rows else ""
    return table or "No uncovered branches."


def _render_summary_human(report: Report) -> str:  # noqa: PLR0914
    data = report.sections.get("summary")
    if not isinstance(data, Mapping):
        return ""
    summary = cast("Mapping[str, Any]", data)
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
    table = format_table(headers, rows) if rows else ""
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
        parts.append("No new uncovered lines.")
    parts.append(_subheading("Resolved", meta))
    if resolved_sections:
        parts.append(format_human(list(resolved_sections), meta))
    else:
        parts.append("No resolved uncovered lines.")
    return "\n".join(parts)


def _render_lines_markdown(report: Report, meta: OutputMeta) -> str:
    attachments = _as_mapping(report.attachments.get("lines"))
    sections = cast("list[UncoveredSection]", _as_list(attachments.get("sections")))
    if not sections:
        return ""
    return format_markdown(list(sections), meta)


def _render_branches_markdown(report: Report, meta: OutputMeta) -> str:
    attachments = _as_mapping(report.attachments.get("branches"))
    gaps = cast("list[BranchGap]", _as_list(attachments.get("gaps")))
    if not gaps:
        return ""
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
    return format_table(headers, rows)


def _render_summary_markdown(report: Report) -> str:
    data = report.sections.get("summary")
    if not isinstance(data, dict):
        return "_No summary data._"
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
    for entry in data.get("files", []):
        if not isinstance(entry, dict):
            continue
        stmt = entry.get("statements", {})
        br = entry.get("branches", {})
        rows.append([
            str(entry.get("file", "")),
            str(stmt.get("total", 0)),
            str(stmt.get("covered", 0)),
            str(stmt.get("missed", 0)),
            str(br.get("total", 0)),
            str(br.get("covered", 0)),
            str(br.get("missed", 0)),
        ])
    return format_table(headers, rows)


def _render_diff_markdown(report: Report, meta: OutputMeta) -> str:
    diff_data = _as_mapping(report.attachments.get("diff"))
    new_sections = cast("list[UncoveredSection]", _as_list(diff_data.get("new")))
    resolved_sections = cast("list[UncoveredSection]", _as_list(diff_data.get("resolved")))
    parts: list[str] = ["### New"]
    parts.extend([
        format_markdown(list(new_sections), meta) if new_sections else "_No new uncovered lines._",
        "### Resolved",
        format_markdown(list(resolved_sections), meta)
        if resolved_sections
        else "_No resolved uncovered lines._",
    ])
    return "\n\n".join(parts)


def _render_lines_html(report: Report, meta: OutputMeta) -> str:  # noqa: PLR0914
    attachments = _as_mapping(report.attachments.get("lines"))
    sections = cast("list[UncoveredSection]", _as_list(attachments.get("sections")))
    parts: list[str] = ['<section id="lines">', "<h2>Lines</h2>"]
    if not sections:
        parts.append("<p>No uncovered lines.</p>")
    else:
        base = meta.coverage_xml.parent
        for section in sections:
            rel = (
                normalize_path(Path(section.file), base=base).as_posix()
                if meta.show_paths
                else "Uncovered lines"
            )
            anchor = _slugify(rel)
            parts.extend((f'<article id="lines-{escape(anchor)}">', f"<h3>{escape(rel)}</h3>", "<ul>"))
            for start, end in section.ranges:
                label = f"Line {start}" if start == end else f"Lines {start}-{end}"
                parts.append(f"<li>{escape(label)}</li>")
            parts.append("</ul>")
            if meta.with_code:
                lines = read_file_lines(section.file)
                for start, end in section.ranges:
                    before = meta.context_before
                    after = meta.context_after
                    start_idx = max(1, start - before)
                    end_idx = min(len(lines), end + after)
                    snippet: list[str] = []
                    for idx in range(start_idx, end_idx + 1):
                        prefix = f"{idx}: " if meta.show_line_numbers else ""
                        text = lines[idx - 1] if 1 <= idx <= len(lines) else "<line not found>"
                        snippet.append(escape(f"{prefix}{text}"))
                    code = "\n".join(snippet)
                    parts.append(f"<pre><code>{code}</code></pre>")
            parts.append("</article>")
    parts.append("</section>")
    return "\n".join(parts)


def _render_branches_html(report: Report, meta: OutputMeta) -> str:
    attachments = _as_mapping(report.attachments.get("branches"))
    gaps = cast("list[BranchGap]", _as_list(attachments.get("gaps")))
    parts: list[str] = ['<section id="branches">', "<h2>Branches</h2>"]
    if not gaps:
        parts.append("<p>No uncovered branches.</p>")
    else:
        base = meta.coverage_xml.parent
        parts.append("<table>")
        headers = ["Line", "Condition", "Coverage"]
        if meta.show_paths:
            headers.insert(0, "File")
        header_html = "".join(f"<th>{escape(h)}</th>" for h in headers)
        parts.extend((f"<thead><tr>{header_html}</tr></thead>", "<tbody>"))
        for gap in gaps:
            file_label = normalize_path(Path(gap.file), base=base).as_posix() if meta.show_paths else ""
            for cond in gap.conditions:
                coverage = f"{cond.coverage}%" if cond.coverage is not None else "missing"
                cells = []
                if meta.show_paths:
                    cells.append(escape(file_label))
                cells.extend([
                    escape(str(gap.line)),
                    escape(_format_condition(cond)),
                    escape(coverage),
                ])
                parts.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
        parts.extend(("</tbody>", "</table>"))
    parts.append("</section>")
    return "\n".join(parts)


def _render_summary_html(report: Report) -> str:
    data = report.sections.get("summary")
    parts: list[str] = ['<section id="summary">', "<h2>Summary</h2>"]
    if not isinstance(data, Mapping):
        parts.append("<p>No summary data.</p>")
    else:
        summary = cast("Mapping[str, Any]", data)
        files = _as_list(summary.get("files"))
        if not files:
            parts.append("<p>No summary data.</p>")
            return "\n".join(parts)
        parts.append("<table>")
        headers = [
            "File",
            "Statements total",
            "Statements covered",
            "Statements missed",
            "Branches total",
            "Branches covered",
            "Branches missed",
        ]
        parts.extend((
            "<thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in headers) + "</tr></thead>",
            "<tbody>",
        ))
        for entry in files:
            if not isinstance(entry, Mapping):
                continue
            stmt = _as_mapping(entry.get("statements"))
            br = _as_mapping(entry.get("branches"))
            cells = [
                escape(str(entry.get("file", ""))),
                escape(str(stmt.get("total", 0))),
                escape(str(stmt.get("covered", 0))),
                escape(str(stmt.get("missed", 0))),
                escape(str(br.get("total", 0))),
                escape(str(br.get("covered", 0))),
                escape(str(br.get("missed", 0))),
            ]
            parts.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
        parts.extend(("</tbody>", "</table>"))
    parts.append("</section>")
    return "\n".join(parts)


def _render_diff_html(report: Report, meta: OutputMeta) -> str:
    diff_data = _as_mapping(report.attachments.get("diff"))
    new_sections = cast("list[UncoveredSection]", _as_list(diff_data.get("new")))
    resolved_sections = cast("list[UncoveredSection]", _as_list(diff_data.get("resolved")))
    parts: list[str] = ['<section id="diff">', "<h2>Diff</h2>"]
    parts.extend(('<article id="diff-new">', "<h3>New</h3>"))
    if new_sections:
        parts.append(_render_sections_html(new_sections, meta))
    else:
        parts.append("<p>No new uncovered lines.</p>")
    parts.extend(("</article>", '<article id="diff-resolved">', "<h3>Resolved</h3>"))
    if resolved_sections:
        parts.append(_render_sections_html(resolved_sections, meta))
    else:
        parts.append("<p>No resolved uncovered lines.</p>")
    parts.extend(("</article>", "</section>"))
    return "\n".join(parts)


def _render_sections_html(sections: Iterable, meta: OutputMeta) -> str:
    base = meta.coverage_xml.parent
    parts: list[str] = []
    for section in sections:
        rel = (
            normalize_path(Path(section.file), base=base).as_posix() if meta.show_paths else "Uncovered lines"
        )
        parts.extend((f"<h4>{escape(rel)}</h4>", "<ul>"))
        for start, end in section.ranges:
            label = f"Lines {start}-{end}" if start != end else f"Line {start}"
            parts.append(f"<li>{escape(label)}</li>")
        parts.append("</ul>")
        if meta.with_code:
            lines = read_file_lines(section.file)
            for start, end in section.ranges:
                start_idx = max(1, start - meta.context_before)
                end_idx = min(len(lines), end + meta.context_after)
                snippet: list[str] = []
                for idx in range(start_idx, end_idx + 1):
                    prefix = f"{idx}: " if meta.show_line_numbers else ""
                    text = lines[idx - 1] if 1 <= idx <= len(lines) else "<line not found>"
                    snippet.append(escape(f"{prefix}{text}"))
                code = "\n".join(snippet)
                parts.append(f"<pre><code>{code}</code></pre>")
    return "\n".join(parts)


def _subheading(text: str, meta: OutputMeta) -> str:
    if meta.color:
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


def _summarize_line_sections(data: object) -> list[str]:
    mapping = _as_mapping(data)
    if not mapping:
        return []
    extras: list[str] = []
    summary = _as_mapping(mapping.get("summary"))
    if "uncovered" in summary:
        extras.append(f"Total uncovered lines: {summary['uncovered']}")
    for entry in _as_list(mapping.get("files")):
        if not isinstance(entry, Mapping):
            continue
        counts = _as_mapping(entry.get("counts"))
        file_label = entry.get("file")
        if not file_label:
            continue
        total = cast("int", counts.get("total", 0))
        uncovered = cast("int", counts.get("uncovered", 0))
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
