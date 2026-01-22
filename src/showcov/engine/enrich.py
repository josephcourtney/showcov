from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from showcov.model.report import FileCounts, Report, SourceLine, UncoveredFile, UncoveredRange

if TYPE_CHECKING:
    from collections.abc import Iterable

    from showcov.engine.build import BuildOptions


def read_file_lines_uncached(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        # Coverage XML often references paths that don't exist in the current workspace.
        return []


def detect_line_tag(code: str) -> str | None:
    """Lightweight tag heuristic for human/rg snippets."""
    s = code.strip()
    if not s:
        return "blank"
    if s.startswith("#"):
        return "comment"
    if s.startswith(("def ", "class ")):
        return "def"
    if s.startswith(("if ", "elif ", "else:", "for ", "while ", "try:", "except", "with ")):
        return "control"
    return None


def _determine_context_offsets(
    *,
    start: int,
    end: int,
    before: int,
    after: int,
    max_line: int,
) -> tuple[int, int]:
    a = max(1, start - max(0, before))
    b = min(max_line, end + max(0, after))
    return a, b


def _resolve_source_path(file_label: str, *, base: Path) -> Path:
    p = Path(file_label)
    if p.is_absolute():
        return p
    return (base / p).resolve()


def _enrich_range(
    r: UncoveredRange,
    *,
    file_lines: list[str],
    before: int,
    after: int,
    include_line_numbers: bool,
) -> UncoveredRange:
    max_line = len(file_lines)
    a, b = _determine_context_offsets(
        start=r.start,
        end=r.end,
        before=before,
        after=after,
        max_line=max_line,
    )
    src: list[SourceLine] = []
    for lineno in range(a, b + 1):
        code = file_lines[lineno - 1] if 1 <= lineno <= max_line else ""
        tag = detect_line_tag(code)
        src.append(SourceLine(code=code, line=(lineno if include_line_numbers else None), tag=tag))
    return replace(r, source=tuple(src))


def _enrich_file(
    f: UncoveredFile,
    *,
    base: Path,
    before: int,
    after: int,
    include_line_numbers: bool,
    want_snippets: bool,
    want_file_stats: bool,
) -> UncoveredFile:
    if not f.file:
        return f

    src_path = _resolve_source_path(f.file, base=base)
    lines = read_file_lines_uncached(src_path)

    ranges = f.uncovered
    if want_snippets:
        ranges = tuple(
            _enrich_range(
                r,
                file_lines=lines,
                before=before,
                after=after,
                include_line_numbers=include_line_numbers,
            )
            for r in f.uncovered
        )

    counts = f.counts
    if want_file_stats:
        uncovered = sum(r.line_count for r in ranges)
        counts = FileCounts(uncovered=uncovered, total=len(lines))

    return replace(f, uncovered=ranges, counts=counts)


def enrich_report(report: Report, opts: BuildOptions) -> Report:
    """Attach filesystem-derived data (snippets, file totals) to an already-built Report."""
    sec = report.sections
    if sec.lines is None and sec.diff is None:
        return report

    include_line_numbers = bool(opts.meta_show_line_numbers)

    def enrich_files(files: Iterable[UncoveredFile]) -> tuple[UncoveredFile, ...]:
        out: list[UncoveredFile] = [
            _enrich_file(
                f,
                base=opts.base_path,
                before=opts.context_before,
                after=opts.context_after,
                include_line_numbers=include_line_numbers,
                want_snippets=bool(opts.want_snippets),
                want_file_stats=bool(opts.want_file_stats),
            )
            for f in files
        ]
        return tuple(out)

    new_lines = sec.lines
    if new_lines is not None:
        new_lines = replace(new_lines, files=enrich_files(new_lines.files))

    new_diff = sec.diff
    if new_diff is not None:
        new_diff = replace(
            new_diff,
            new=enrich_files(new_diff.new),
            resolved=enrich_files(new_diff.resolved),
        )

    return replace(report, sections=replace(sec, lines=new_lines, diff=new_diff))


__all__ = ["enrich_report"]
