"""Ripgrep-style human output for showcov.

Conventions implemented (subset aligned with rg "human" mode):
  - Heading mode (default on a TTY): a file path heading precedes a block
    of lines; lines omit the file path.
  - Grep-like mode (default when not a TTY): each line is prefixed by
    "path:line:...".
  - Context lines (when --code and context are active) use '-' after the
    line number; match lines use ':'.
  - Non-contiguous uncovered groups are separated by a lone '--' line.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from showcov.core.files import normalize_path, read_file_lines

if TYPE_CHECKING:
    from collections.abc import Mapping

    from showcov.core import Report, UncoveredSection
    from showcov.core.coverage import BranchGap
    from showcov.output.base import OutputMeta

_NO_LINES = "No uncovered lines."
_NO_BRANCHES = "No uncovered branches."


def format_rg(report: Report, meta: OutputMeta) -> str:
    """Render the unified report using ripgrep-like text output."""
    parts: list[str] = []
    for name in report.sections:
        if name == "lines":
            parts.append(_render_lines_rg(report, meta))
        elif name == "branches":
            parts.append(_render_branches_rg(report, meta))
        elif name == "summary":
            # fall back to the existing human summary table for now
            from .report_render import _render_summary_human  # noqa: PLC0415 # local import to avoid cycle

            parts.append(_render_summary_human(report, meta))
        elif name == "diff":
            # diff uses the lines renderer for each side, preserve existing human diff structure
            from .report_render import _subheading  # noqa: PLC0415 # local import to avoid cycle

            attachments = _as_mapping(report.attachments.get("diff"))
            newer = cast("list[UncoveredSection]", _as_list(attachments.get("new")))
            resolved = cast("list[UncoveredSection]", _as_list(attachments.get("resolved")))
            parts.extend((
                _subheading("New", meta),
                _render_lines_rg_from_sections(newer, report, meta),
                _subheading("Resolved", meta),
                _render_lines_rg_from_sections(resolved, report, meta),
            ))
    return "\n\n".join([p for p in parts if p])


def _heading(text: str, meta: OutputMeta) -> str:
    if meta.color and meta.is_tty:
        return f"\x1b[1m{text}\x1b[0m"
    return text


# ---------------------------- Lines ------------------------------------------
def _render_lines_rg(report: Report, meta: OutputMeta) -> str:
    attach = _as_mapping(report.attachments.get("lines"))
    sections = cast("list[UncoveredSection]", _as_list(attach.get("sections")))
    return _render_lines_rg_from_sections(sections, report, meta)


def _render_lines_rg_from_sections(sections: list[UncoveredSection], report: Report, meta: OutputMeta) -> str:
    if not sections:
        return _NO_LINES
    base = report.meta.get("environment", {}).get("coverage_xml")
    base_dir = Path(str(base)).parent if isinstance(base, str) else meta.coverage_xml.parent
    blocks: list[str] = [_render_file_block(sec, base_dir, meta) for sec in sections]
    return "\n".join(blocks)


def _render_file_block(sec: UncoveredSection, base_dir: Path, meta: OutputMeta) -> str:
    """Render one file's uncovered lines."""
    use_heading = meta.is_tty  # heading on a TTY by default
    show_path = meta.show_paths
    # rg-style output always includes line numbers on match lines
    show_lineno = True

    # Always show match lines (line:code). Only include context lines when the user
    # explicitly enabled code/context via CLI flags.
    want_context = meta.with_code
    ctx_before = meta.context_before if want_context else 0
    ctx_after = meta.context_after if want_context else 0

    rel = normalize_path(Path(sec.file), base=base_dir).as_posix()
    lines = read_file_lines(Path(sec.file))

    # Always render with the code-path so we emit match lines like "N:code".
    # With ctx_before/after == 0 this prints only the uncovered lines (no context).
    return _render_file_block_with_code(
        sec,
        rel,
        lines,
        use_heading=use_heading,
        show_path=show_path,
        show_lineno=show_lineno,
        ctx_before=ctx_before,
        ctx_after=ctx_after,
    )


def _render_file_block_without_code(
    sec: UncoveredSection,
    rel: str,
    *,
    use_heading: bool,
    show_path: bool,
) -> str:
    """Compact per-range summary for a file when code snippets are disabled."""
    if use_heading and show_path:
        header = rel
        body = [f"{_range_label(start, end)}" for (start, end) in sec.ranges]
        return "\n".join([header, *body])
    # grep-like path:range form
    prefix = f"{rel}:" if (show_path and not use_heading) else ""
    return "\n".join([f"{prefix}{_range_label(s, e)}" for (s, e) in sec.ranges])


def _render_file_block_with_code(
    sec: UncoveredSection,
    rel: str,
    lines: list[str],
    *,
    use_heading: bool,
    show_path: bool,
    show_lineno: bool,
    ctx_before: int,
    ctx_after: int,
) -> str:
    """Full ripgrep-style block with context and match lines."""
    out: list[str] = []
    if use_heading and show_path:
        out.append(rel)

    # Render each non-contiguous group; insert '--' between groups.
    for idx, (start, end) in enumerate(sec.ranges):
        if idx > 0:
            out.append("--")
        start_idx = max(1, start - ctx_before)
        end_idx = min(len(lines), end + ctx_after)
        for i in range(start_idx, end_idx + 1):
            code = lines[i - 1] if 1 <= i <= len(lines) else ""
            is_match = start <= i <= end
            sep = ":" if is_match else "-"
            out.append(
                _format_code_line(
                    rel=rel,
                    code=code,
                    lineno=i,
                    separator=sep,
                    is_match=is_match,
                    use_heading=use_heading,
                    show_path=show_path,
                    show_lineno=show_lineno,
                )
            )
    return "\n".join(out)


def _range_label(start: int, end: int) -> str:
    return f"{start}" if start == end else f"{start}-{end}"


# ---------------------------- Branches ---------------------------------------
def _render_branches_rg(report: Report, meta: OutputMeta) -> str:
    attach = _as_mapping(report.attachments.get("branches"))
    gaps = cast("list[BranchGap]", _as_list(attach.get("gaps")))
    if not gaps:
        return _NO_BRANCHES
    base_dir = meta.coverage_xml.parent
    use_heading = meta.is_tty
    show_path = meta.show_paths

    # Group by file for heading mode
    by_file: dict[str, list[tuple[int, str, str]]] = {}
    for gap in gaps:
        rel = normalize_path(Path(gap.file), base=base_dir).as_posix()
        for cond in gap.conditions:
            cov = "missing" if (cond.coverage is None or cond.coverage == 0) else f"{cond.coverage}%"
            label = _format_condition(cond.number, cond.type)
            by_file.setdefault(rel, []).append((gap.line, label, cov))

    out: list[str] = []
    if use_heading and show_path:
        for path in sorted(by_file):
            out.append(path)
            for line, label, cov in sorted(by_file[path]):
                # match-like lines: line: condition  (cov)
                out.append(f"{line}:{label} {cov}")
    else:
        # grep-like, always include path prefix
        for path in sorted(by_file):
            for line, label, cov in sorted(by_file[path]):
                prefix = f"{path}:" if show_path else ""
                out.append(f"{prefix}{line}:{label} {cov}")
    return "\n".join(out)


def _format_condition(number: int, typ: str | None) -> str:
    typ = (typ or "branch").lower()
    if typ == "line":
        return str(number) if number >= 0 else "line"
    suffix = f"#{number}" if number >= 0 else ""
    return f"{typ}{suffix}"


# ---------------------------- helpers ----------------------------------------
def _format_code_line(
    *,
    rel: str,
    code: str,
    lineno: int,
    separator: str,
    is_match: bool,
    use_heading: bool,
    show_path: bool,
    show_lineno: bool,
) -> str:
    """Format a single code line prefix + text, mirroring ripgrep behaviour."""
    parts: list[str] = []
    if not use_heading and show_path:
        parts.append(rel)
    if show_lineno:
        parts.extend((str(lineno), separator))
    # When no line numbers, still include the separator for match lines to mirror rg feel.
    elif is_match:
        parts.append(separator)
    prefix = ":".join(parts) if parts and parts[-1] != separator else "".join(parts)
    if parts and parts[-1] == separator:
        return f"{prefix}{code}"
    # either "path:line:code" or "line:code" or ":code"
    delimiter = "" if (prefix.endswith((":", "-")) or not prefix) else ":"
    return f"{prefix}{delimiter}{code}"


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, dict):
        return cast("Mapping[str, Any]", value)
    return cast("Mapping[str, Any]", {})


def _as_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    return []
