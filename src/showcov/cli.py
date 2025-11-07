"""Unified command line interface for ``showcov``."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
import click.utils as click_utils
from defusedxml import ElementTree

from showcov import __version__, logger
from showcov.core import (
    BranchMode,
    CoverageDataset,
    PathFilter,
    Report,
    SummarySort,
    build_branches,
    build_diff,
    build_lines,
    determine_xml_file,
    evaluate_thresholds,
    parse_threshold,
)
from showcov.core.exceptions import CoverageXMLNotFoundError, InvalidCoverageXMLError
from showcov.core.files import normalize_path, read_file_lines
from showcov.core.types import Format
from showcov.output.base import OutputMeta
from showcov.output.report_render import render_report

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from showcov.core.dataset import FileCoverage
    from showcov.core.thresholds import Threshold

CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "auto_envvar_prefix": "SHOWCOV",
}

SECTIONS = ("lines", "branches", "summary", "diff")
CONTEXT_PAIR_SIZE = 2

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_DATAERR = 65
EXIT_NOINPUT = 66
EXIT_CONFIG = 78
EXIT_THRESHOLD = 2


def _configure_logging(*, quiet: bool, verbose: bool, debug: bool) -> None:
    level = (
        logging.ERROR if quiet else (logging.DEBUG if debug else (logging.DEBUG if verbose else logging.INFO))
    )
    logging.basicConfig(level=level, format="%(message)s")
    if debug:
        logger.debug("debug logging enabled")


def _resolve_context(value: str | None) -> tuple[int, int]:
    if not value:
        return 0, 0
    parts = [token.strip() for token in value.replace(",", " ").split() if token.strip()]
    if len(parts) == 1:
        try:
            amount = int(parts[0])
        except ValueError as exc:  # pragma: no cover - defensive
            msg = "context must be an integer"
            raise click.BadParameter(msg) from exc
        return amount, amount
    if len(parts) == CONTEXT_PAIR_SIZE:
        try:
            before, after = (int(parts[0]), int(parts[1]))
        except ValueError as exc:
            msg = "context values must be integers"
            raise click.BadParameter(msg) from exc
        return before, after
    msg = "--context expects N or N,M"
    raise click.BadParameter(msg)


def _resolve_sections(value: str | None) -> tuple[str, ...]:
    if not value:
        return ("lines",)
    parts = [item.strip().lower() for item in value.split(",") if item.strip()]
    invalid = [item for item in parts if item not in SECTIONS]
    if invalid:
        choices = ", ".join(SECTIONS)
        msg = f"unknown section(s): {', '.join(invalid)} (choose from {choices})"
        raise click.BadParameter(msg)
    seen: list[str] = []
    for item in parts:
        if item not in seen:
            seen.append(item)
    return tuple(seen)


def _resolve_format(value: str, *, is_tty: bool) -> Format:
    try:
        fmt = Format(value.lower())
    except ValueError as exc:
        choices = ", ".join(fmt.value for fmt in Format)
        msg = f"unsupported format: {value!r}; choose from {choices}"
        raise click.BadParameter(msg) from exc
    if fmt is Format.AUTO:
        return Format.HUMAN if is_tty else Format.JSON
    return fmt


def _parse_threshold_options(values: Sequence[str]) -> tuple[Threshold, ...]:
    parsed: list[Threshold] = []
    for expr in values:
        try:
            parsed.append(parse_threshold(expr))
        except ValueError as exc:
            raise click.BadParameter(str(exc)) from exc
    return tuple(parsed)


def _resolve_filters(
    includes: Sequence[str],
    excludes: Sequence[str],
    *,
    base: Path,
) -> PathFilter | None:
    if not includes and not excludes:
        return None
    include_patterns: list[str | Path] = [Path(item) if Path(item).exists() else item for item in includes]
    exclude_patterns: list[str | Path] = [Path(item) if Path(item).exists() else item for item in excludes]
    return PathFilter(include_patterns, exclude_patterns, base=base)


def _resolve_coverage_paths(cov: Sequence[Path]) -> tuple[Path, ...]:
    if cov:
        return tuple(path.resolve() for path in cov)
    resolved = determine_xml_file()
    return (resolved.resolve(),)


def _build_lines_section(
    sections: Sequence,
    *,
    meta: OutputMeta,
    base_path: Path,
    file_stats: bool,
    aggregate_stats: bool,
    attachments: dict[str, Any],
) -> Mapping[str, object]:
    files_payload: list[dict[str, object]] = []
    total_uncovered = 0
    for section in sections:
        section_dict = section.to_dict(
            with_code=meta.with_code,
            context_before=meta.context_before,
            context_after=meta.context_after,
            base=base_path,
            show_file=meta.show_paths,
            show_line_numbers=meta.show_line_numbers,
        )
        if file_stats:
            uncovered = sum(end - start + 1 for start, end in section.ranges)
            total = len(read_file_lines(section.file))
            section_dict["counts"] = {"uncovered": uncovered, "total": total}
            total_uncovered += uncovered
        else:
            total_uncovered += sum(end - start + 1 for start, end in section.ranges)
        files_payload.append(section_dict)
    payload: dict[str, object] = {"files": files_payload}
    if aggregate_stats:
        payload["summary"] = {"uncovered": total_uncovered}
    attachments["lines"] = {"sections": list(sections)}
    return payload


def _build_branches_section(
    gaps: Sequence,
    *,
    meta: OutputMeta,
    base_path: Path,
    attachments: dict[str, Any],
) -> Mapping[str, object]:
    rendered: list[dict[str, object]] = []
    for gap in gaps:
        conditions: list[dict[str, object]] = []
        entry: dict[str, object] = {"line": gap.line, "conditions": conditions}
        if meta.show_paths:
            entry["file"] = normalize_path(gap.file, base=base_path).as_posix()
        conditions.extend(
            {
                "number": cond.number,
                "type": cond.type,
                "coverage": cond.coverage,
            }
            for cond in gap.conditions
        )
        rendered.append(entry)
    attachments["branches"] = {"gaps": list(gaps)}
    return {"gaps": rendered}


def _build_summary_section(
    dataset: CoverageDataset,
    *,
    filters: PathFilter | None,
    sort: SummarySort,
    attachments: dict[str, Any],
) -> tuple[Mapping[str, object], tuple[int, int, int, int]]:
    rows: list[dict[str, object]] = []
    stmt_total = stmt_hit = br_total = br_hit = 0
    files: list[FileCoverage] = []
    for file_cov in dataset.iter_files():
        if filters is not None and not filters.allow(file_cov.path):
            continue
        files.append(file_cov)
    # Apply ordering after filtering
    if sort is SummarySort.FILE:
        files.sort(key=lambda fc: dataset.display_path(fc.path))
    elif sort is SummarySort.STATEMENT_COVERAGE:
        files.sort(
            key=lambda fc: (
                -((sum(1 for cov in fc.lines.values() if cov.hits > 0) / len(fc.lines)) * 100)
                if fc.lines
                else float("inf"),
                dataset.display_path(fc.path),
            )
        )
    elif sort is SummarySort.BRANCH_COVERAGE:

        def branch_key(fc: FileCoverage) -> tuple[float, str]:
            total = sum(cov.branches_total for cov in fc.lines.values())
            hit = sum(cov.branches_covered for cov in fc.lines.values())
            pct = (hit / total * 100) if total else float("inf")
            return (-pct, dataset.display_path(fc.path))

        files.sort(key=branch_key)
    else:  # SummarySort.MISSES
        files.sort(
            key=lambda fc: (
                -(
                    sum(1 for cov in fc.lines.values() if cov.hits == 0)
                    + sum(cov.branches_total - cov.branches_covered for cov in fc.lines.values())
                ),
                dataset.display_path(fc.path),
            )
        )

    for file_cov in files:
        stmt_tot = len(file_cov.lines)
        stmt_cov = sum(1 for cov in file_cov.lines.values() if cov.hits > 0)
        br_tot = sum(cov.branches_total for cov in file_cov.lines.values())
        br_cov = sum(cov.branches_covered for cov in file_cov.lines.values())
        rows.append({
            "file": dataset.display_path(file_cov.path),
            "statements": {
                "total": stmt_tot,
                "covered": stmt_cov,
                "missed": stmt_tot - stmt_cov,
            },
            "branches": {
                "total": br_tot,
                "covered": br_cov,
                "missed": br_tot - br_cov,
            },
        })
        stmt_total += stmt_tot
        stmt_hit += stmt_cov
        br_total += br_tot
        br_hit += br_cov
    payload = {
        "files": rows,
        "totals": {
            "statements": {"total": stmt_total, "covered": stmt_hit, "missed": stmt_total - stmt_hit},
            "branches": {"total": br_total, "covered": br_hit, "missed": br_total - br_hit},
        },
    }
    attachments["summary"] = {"rows": rows, "totals": (stmt_total, stmt_hit, br_total, br_hit)}
    return payload, (stmt_total, stmt_hit, br_total, br_hit)


def _build_diff_section(
    base_dataset: CoverageDataset,
    current_dataset: CoverageDataset,
    *,
    filters: PathFilter | None,
    meta: OutputMeta,
    base_path: Path,
    attachments: dict[str, Any],
) -> Mapping[str, object]:
    diff = build_diff(base_dataset, current_dataset)
    new_sections = diff["new"]
    resolved_sections = diff["resolved"]
    if filters is not None:
        new_sections = filters.filter(new_sections)
        resolved_sections = filters.filter(resolved_sections)
    attachments["diff"] = {"new": new_sections, "resolved": resolved_sections}
    return {
        "new": [
            section.to_dict(
                with_code=meta.with_code,
                context_before=meta.context_before,
                context_after=meta.context_after,
                base=base_path,
                show_file=meta.show_paths,
                show_line_numbers=meta.show_line_numbers,
            )
            for section in new_sections
        ],
        "resolved": [
            section.to_dict(
                with_code=meta.with_code,
                context_before=meta.context_before,
                context_after=meta.context_after,
                base=base_path,
                show_file=meta.show_paths,
                show_line_numbers=meta.show_line_numbers,
            )
            for section in resolved_sections
        ],
    }


def _write_output(text: str, destination: Path | None) -> None:
    if destination is None:
        click.echo(text)
        return
    if destination == Path("-"):
        click.echo(text)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("maybe_command", required=False)
@click.argument("extra_paths", nargs=-1)
@click.option("--cov", "cov_paths", multiple=True, type=click.Path(path_type=Path), help="Coverage XML file")
@click.option("--include", "include_patterns", multiple=True, help="Glob of files to include")
@click.option("--exclude", "exclude_patterns", multiple=True, help="Glob of files to exclude")
@click.option(
    "--sections",
    "sections_option",
    help="Comma separated list of sections (lines, branches, summary, diff)",
)
@click.option(
    "--diff-base",
    type=click.Path(path_type=Path),
    help="Coverage XML to compare against for diff section",
)
@click.option(
    "--branches-mode",
    type=click.Choice([mode.value for mode in BranchMode], case_sensitive=False),
    default=BranchMode.PARTIAL.value,
    show_default=True,
)
@click.option(
    "--format",
    "format_option",
    default="auto",
    show_default=True,
    help="Output format (human, markdown, html, json, auto)",
)
@click.option("--output", type=click.Path(path_type=Path), help="Write report to file instead of stdout")
@click.option("--code/--no-code", "with_code", default=False, show_default=True, help="Include code snippets")
@click.option("--context", "context_option", help="Context lines before/after uncovered ranges")
@click.option("--line-numbers", is_flag=True, help="Show line numbers alongside code snippets")
@click.option("--paths/--no-paths", "show_paths", default=True, show_default=True, help="Show file paths")
@click.option(
    "--sort",
    type=click.Choice([choice.value for choice in SummarySort], case_sensitive=False),
    default=SummarySort.FILE.value,
    show_default=True,
    help="Ordering for summary section",
)
@click.option("--stats", is_flag=True, help="Include aggregate uncovered counts for lines")
@click.option("--file-stats", is_flag=True, help="Include per-file counts for lines")
@click.option("--threshold", "threshold_options", multiple=True, help="Coverage thresholds")
@click.option("--color", is_flag=True, help="Force coloured output")
@click.option("--no-color", is_flag=True, help="Disable coloured output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-essential output")
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.version_option(__version__)
@click.pass_context
def cli(  # noqa: C901, PLR0912, PLR0914, PLR0915
    ctx: click.Context,
    maybe_command: str | None,
    extra_paths: tuple[str, ...],
    cov_paths: tuple[Path, ...],
    include_patterns: tuple[str, ...],
    exclude_patterns: tuple[str, ...],
    sections_option: str | None,
    diff_base: Path | None,
    branches_mode: str,
    format_option: str,
    output: Path | None,
    *,
    with_code: bool = False,
    context_option: str | None = None,
    line_numbers: bool = False,
    show_paths: bool = True,
    sort: str = SummarySort.FILE.value,
    stats: bool = False,
    file_stats: bool = False,
    threshold_options: tuple[str, ...] = (),
    color: bool = False,
    no_color: bool = False,
    quiet: bool = False,
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Generate unified coverage reports from one or more coverage XML files.

    Exit status codes:
        0  - success
        1  - generic error (unexpected failure)
        2  - one or more coverage thresholds were not met
        65 - malformed coverage XML data
        66 - required coverage XML input missing
        78 - configuration error (e.g. invalid --config references)
    """
    if maybe_command == "report":
        positional_paths = extra_paths
    else:
        positional_paths = (maybe_command, *extra_paths) if maybe_command else extra_paths

    if color and no_color:
        msg = "--color"
        raise click.BadOptionUsage(msg, "--color and --no-color cannot be combined")
    if quiet and verbose:
        msg = "--quiet"
        raise click.BadOptionUsage(msg, "--quiet and --verbose cannot be combined")

    before, after = _resolve_context(context_option)
    sections_requested = _resolve_sections(sections_option)
    thresholds = _parse_threshold_options(threshold_options)

    if "diff" in sections_requested and diff_base is None:
        msg = "--diff-base"
        raise click.BadOptionUsage(msg, "--diff-base is required when requesting the diff section")

    _configure_logging(quiet=quiet, verbose=verbose, debug=debug)

    try:
        coverage_paths = _resolve_coverage_paths(cov_paths)
    except CoverageXMLNotFoundError as exc:
        click.echo(f"ERROR: {exc}", err=True)
        ctx.exit(EXIT_NOINPUT)

    base_path = coverage_paths[0].parent
    includes = list(include_patterns) + [item for item in positional_paths if item]
    filters = _resolve_filters(includes, exclude_patterns, base=base_path)

    try:
        dataset = CoverageDataset.from_xml_files(coverage_paths, base_path=base_path)
    except OSError as exc:
        if debug:
            raise
        click.echo(f"ERROR: {exc}", err=True)
        ctx.exit(EXIT_NOINPUT)
    except (ElementTree.ParseError, InvalidCoverageXMLError) as exc:
        if debug:
            raise
        click.echo(f"ERROR: failed to parse coverage XML: {exc}", err=True)
        ctx.exit(EXIT_DATAERR)

    if output and output != Path("-") and format_option.lower() == "auto":
        msg = "--format"
        raise click.BadOptionUsage(msg, "--format=auto cannot be used with --output")

    ansi_allowed = not click_utils.should_strip_ansi(sys.stdout)
    color_support = ctx.color if ctx.color is not None else ansi_allowed
    use_color = True if color else False if no_color else color_support
    meta = OutputMeta(
        coverage_xml=coverage_paths[0],
        with_code=with_code,
        color=use_color,
        show_paths=show_paths,
        show_line_numbers=line_numbers,
        context_before=max(0, before),
        context_after=max(0, after),
    )

    attachments: dict[str, Any] = {}
    report_sections: dict[str, object] = {}

    totals: tuple[int, int, int, int] = (0, 0, 0, 0)
    if "lines" in sections_requested or thresholds:
        line_sections = build_lines(dataset, filters=filters)
        if "lines" in sections_requested:
            report_sections["lines"] = _build_lines_section(
                line_sections,
                meta=meta,
                base_path=base_path,
                file_stats=file_stats,
                aggregate_stats=stats,
                attachments=attachments,
            )
        if "lines" not in attachments:
            attachments["lines"] = {"sections": line_sections}
    else:
        line_sections = ()
    if "branches" in sections_requested:
        gaps = build_branches(dataset, filters=filters, mode=BranchMode(branches_mode))
        report_sections["branches"] = _build_branches_section(
            gaps,
            meta=meta,
            base_path=base_path,
            attachments=attachments,
        )
    if "summary" in sections_requested or thresholds:
        summary_payload, totals = _build_summary_section(
            dataset,
            filters=filters,
            sort=SummarySort(sort),
            attachments=attachments,
        )
        if "summary" in sections_requested:
            report_sections["summary"] = summary_payload
    if "diff" in sections_requested and diff_base is not None:
        try:
            base_dataset = CoverageDataset.from_xml_files((diff_base,), base_path=base_path)
        except OSError as exc:
            if debug:
                raise
            click.echo(f"ERROR: {exc}", err=True)
            ctx.exit(EXIT_NOINPUT)
        except (ElementTree.ParseError, InvalidCoverageXMLError) as exc:
            if debug:
                raise

            click.echo(f"ERROR: failed to parse diff base XML: {exc}", err=True)
            ctx.exit(EXIT_DATAERR)
        report_sections["diff"] = _build_diff_section(
            base_dataset,
            dataset,
            filters=filters,
            meta=meta,
            base_path=base_path,
            attachments=attachments,
        )

    report_meta: Mapping[str, object] = {
        "environment": {"coverage_xml": coverage_paths[0].as_posix()},
        "options": {
            "context_lines": meta.context_lines,
            "with_code": meta.with_code,
            "show_paths": meta.show_paths,
            "show_line_numbers": meta.show_line_numbers,
            "aggregate_stats": stats,
            "file_stats": file_stats,
        },
    }

    report = Report(meta=report_meta, sections=report_sections, attachments=attachments)

    allow_tty_output = output in {None, Path("-")}
    format_supports_tty = (ctx.color is True or ansi_allowed) if allow_tty_output else False
    fmt = _resolve_format(format_option, is_tty=format_supports_tty)
    rendered = render_report(report, fmt, meta)
    _write_output(rendered, output)

    if thresholds:
        lines_sections = line_sections
        lines_attachment = attachments.get("lines")
        if isinstance(lines_attachment, dict):
            sections_candidate = lines_attachment.get("sections")
            if isinstance(sections_candidate, list):
                lines_sections = sections_candidate
        result = evaluate_thresholds(
            thresholds,
            totals=totals,
            sections=lines_sections,
        )
        if not result.passed:
            for failure in result.failures:
                message = (
                    "Threshold failed: "
                    f"{failure.metric} {failure.comparison} {failure.required} "
                    f"(actual {failure.actual})"
                )
                click.echo(message, err=True)
            ctx.exit(EXIT_THRESHOLD)

    ctx.exit(EXIT_OK)
