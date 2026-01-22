"""Unified command line interface for ``showcov``.

Design goals
------------
- CLI contains only argument parsing + wiring.
- All coverage parsing/building lives in engine/coverage modules.
- Renderers consume a typed Report model; no back-compat coercions.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
import click.utils as click_utils
import typer
from defusedxml import ElementTree
from typer.main import get_command

from showcov import __version__, logger
from showcov.coverage.discover import resolve_coverage_paths
from showcov.engine.build import BuildOptions, build_report
from showcov.engine.enrich import enrich_report
from showcov.errors import CoverageXMLNotFoundError, InvalidCoverageXMLError
from showcov.model.path_filter import PathFilter
from showcov.model.thresholds import Threshold, parse_threshold
from showcov.model.thresholds import evaluate as evaluate_thresholds
from showcov.model.types import BranchMode, SummarySort
from showcov.render.render import RenderOptions, render

if TYPE_CHECKING:
    from collections.abc import Sequence


CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "auto_envvar_prefix": "SHOWCOV",
    "max_content_width": 100,
}

_SECTION_CHOICES = {"lines", "branches", "summary", "diff"}
_DEFAULT_SECTIONS = ("lines", "branches", "summary")

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_DATAERR = 65
EXIT_NOINPUT = 66
EXIT_THRESHOLD = 2

# Treat these as "pattern files" when passed to --include/--exclude without an explicit "@"
_PATTERN_FILE_SUFFIXES = {".txt", ".ignore", ".gitignore", ".showcovignore", ".patterns"}


def _configure_logging(*, quiet: bool, verbose: bool, debug: bool) -> None:
    level = (
        logging.ERROR if quiet else (logging.DEBUG if debug else (logging.DEBUG if verbose else logging.INFO))
    )
    logging.basicConfig(level=level, format="%(message)s")
    if debug:
        logger.debug("debug logging enabled")


def _parse_sections(value: str | None) -> tuple[str, ...]:
    if not value:
        return _DEFAULT_SECTIONS
    parts = [p.strip().lower() for p in value.split(",") if p.strip()]
    bad = [p for p in parts if p not in _SECTION_CHOICES]
    if bad:
        msg = f"unknown section(s): {', '.join(bad)}"
        raise typer.BadParameter(msg)
    # de-dupe while preserving order
    seen: list[str] = []
    for p in parts:
        if p not in seen:
            seen.append(p)
    return tuple(seen)


def _parse_context(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    raw = (value or "").strip()
    if not raw:
        return (0, 0)
    parts = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    try:
        if len(parts) == 1:
            n = int(parts[0])
            return (n, n)
        if len(parts) == 2:  # noqa: PLR2004
            return (int(parts[0]), int(parts[1]))
    except ValueError as exc:
        msg = "expects N or N,M"
        raise typer.BadParameter(msg) from exc
    msg = "expects N or N,M"
    raise typer.BadParameter(msg)


def _parse_thresholds(values: Sequence[str] | None) -> tuple[Threshold, ...]:
    if not values:
        return ()
    try:
        return tuple(parse_threshold(v) for v in values)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _coerce_pattern_token(token: str) -> str | Path:
    """Coerce an --include/--exclude token to a glob string or a patterns file Path.

    Rules:
    - Prefix with '@' to explicitly load patterns from a file.
    - Otherwise, only treat existing files with common "pattern file" suffixes as pattern files.
      This avoids surprising behavior when a real source file (e.g. pkg/mod.py) exists.
    """
    raw = (token or "").strip()
    if not raw:
        return ""

    if raw.startswith("@"):
        return Path(raw[1:])

    p = Path(raw)
    if p.exists() and p.is_file() and p.suffix.lower() in _PATTERN_FILE_SUFFIXES:
        return p

    return raw


def _resolve_filters(
    includes: Sequence[str],
    excludes: Sequence[str],
    *,
    base: Path,
) -> PathFilter | None:
    if not includes and not excludes:
        return None
    include_patterns: list[str | Path] = [_coerce_pattern_token(item) for item in includes if item]
    exclude_patterns: list[str | Path] = [_coerce_pattern_token(item) for item in excludes if item]
    return PathFilter(include_patterns, exclude_patterns, base=base)


def _write_output(text: str, destination: Path | None) -> None:
    if destination is None or destination == Path("-"):
        typer.echo(text)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def _resolve_format(value: str, *, is_tty_like: bool) -> str:
    v = (value or "").strip().lower()
    if v in {"human", "json", "rg"}:
        return v
    if v in {"auto", ""}:
        return "human" if is_tty_like else "json"
    # Defensive fallback:
    return "json"


def _validate_option_combos(
    *,
    color: bool,
    no_color: bool,
    quiet: bool,
    verbose: bool,
) -> None:
    if color and no_color:
        msg = "--color and --no-color cannot be combined"
        raise typer.BadParameter(msg)
    if quiet and verbose:
        msg = "--quiet and --verbose cannot be combined"
        raise typer.BadParameter(msg)


def _compute_sections_requested(
    *,
    sections_option: str | None,
    threshold_options: tuple[Threshold, ...],
    diff_base: Path | None,
) -> tuple[str, ...]:
    sections_requested = _parse_sections(sections_option)

    if "diff" in sections_requested and diff_base is None:
        msg = "--diff-base is required when requesting the diff section"
        raise typer.BadParameter(msg)

    if threshold_options:
        need_stmt = any(t.statement is not None for t in threshold_options)
        need_br = any(t.branch is not None for t in threshold_options)
        need_miss = any(t.misses is not None for t in threshold_options)

        sec_set = set(sections_requested)
        if need_stmt or need_br:
            sec_set.add("summary")
        if need_miss:
            sec_set.add("lines")

        ordered: list[str] = list(sections_requested)
        for name in ("lines", "branches", "summary", "diff"):
            if name in sec_set and name not in ordered:
                ordered.append(name)
        sections_requested = tuple(ordered)

    return sections_requested


def _compute_context_settings(
    *,
    with_code: bool,
    context_option: tuple[int, int] | None,
) -> tuple[bool, int, int]:
    before, after = context_option or (0, 0)
    if context_option is not None and not with_code:
        with_code = True
    return with_code, before, after


def _compute_output_policy(
    ctx: typer.Context,
    *,
    output: Path | None,
    format_option: str,
    color: bool,
    no_color: bool,
) -> tuple[str, bool, bool]:
    if output and output != Path("-") and format_option.strip().lower() == "auto":
        msg = "--format=auto cannot be used with --output"
        raise typer.BadParameter(msg)

    ansi_allowed = not click_utils.should_strip_ansi(sys.stdout)
    stdout_is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)()) or ansi_allowed

    allow_tty_output = output in {None, Path("-")}
    is_tty_like = stdout_is_tty if allow_tty_output else False

    use_color = (
        True if color else False if no_color else (ctx.color if ctx.color is not None else ansi_allowed)
    )
    fmt = _resolve_format(format_option, is_tty_like=is_tty_like)

    return fmt, bool(use_color), bool(is_tty_like)


def _version_callback(value: bool) -> bool:
    if value:
        typer.echo(__version__)
        raise typer.Exit(code=EXIT_OK)
    return value


_APP_HELP = (
    "\b"
    "Generate unified coverage reports from one or more coverage XML files.\n\n"
    "Common examples:\n"
    "  showcov --cov coverage.xml\n"
    "  showcov --cov coverage.xml --threshold statements=90\n"
    "  showcov --cov py.xml --cov js.xml --sections summary,branches\n"
    "  showcov --cov coverage.xml --diff-base baseline.xml --sections diff,summary\n\n"
    "EXTRA_PATHS are optional extra source paths used when resolving files. "
    "Most users can ignore them.\n"
)

_APP_EPILOG = (
    "\b\n"
    "Exit status (for CI):\n"
    "  Code  Description\n"
    "  ----  -----------\n"
    "  0     success\n"
    "  2     coverage thresholds not met (--threshold)\n"
    "\n"
    "Other errors:\n"
    "  Code  Description\n"
    "  ----  -----------\n"
    "  1     unexpected failure\n"
    "  65    malformed coverage XML data\n"
    "  66    required coverage XML input missing (--cov)\n"
)

app = typer.Typer(
    context_settings=CONTEXT_SETTINGS,
    add_completion=False,
    help=_APP_HELP,
    epilog=_APP_EPILOG,
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    extra_paths: list[str] = typer.Argument(
        [],
        help="Optional extra source paths used when resolving files.",
    ),
    cov_paths: list[Path] | None = typer.Option(
        None,
        "--cov",
        help="Coverage XML file. Can be passed multiple times.",
    ),
    include_patterns: list[str] | None = typer.Option(
        None,
        "--include",
        help="Glob of source files to include (repeatable). Use '@FILE' to load globs from a file.",
    ),
    exclude_patterns: list[str] | None = typer.Option(
        None,
        "--exclude",
        help="Glob of source files to exclude (repeatable). Use '@FILE' to load globs from a file.",
    ),
    sections_option: str | None = typer.Option(
        None,
        "--sections",
        help="Comma-separated list of sections: lines, branches, summary, diff.",
    ),
    diff_base: Path | None = typer.Option(
        None,
        "--diff-base",
        help="Coverage XML to compare against when using the diff section.",
    ),
    branches_mode: BranchMode = typer.Option(
        BranchMode.PARTIAL,
        "--branches-mode",
        help=(
            "Which branches count as uncovered:\n"
            "  missing-only  only missing branches\n"
            "  partial       missing + partial branches\n"
            "  all           all branches"
        ),
        show_default=True,
    ),
    format_option: str = typer.Option(
        "auto",
        "--format",
        help="Output format: human, rg, json, or auto (TTY → human, non-TTY → json).",
        show_default=True,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Write report to PATH instead of stdout (use '-' for stdout).",
    ),
    with_code: bool = typer.Option(
        False,
        "--code/--no-code",
        help="Include code snippets around uncovered ranges (requires file reads).",
        show_default=True,
    ),
    context_raw: str | None = typer.Option(
        None,
        "--context",
        help="Lines before/after uncovered ranges as N or N,M (implies --code).",
    ),
    line_numbers: bool = typer.Option(
        False,
        "--line-numbers",
        help="Show line numbers alongside code snippets.",
    ),
    show_paths: bool = typer.Option(
        True,
        "--paths/--no-paths",
        help="Show file paths in report output.",
        show_default=True,
    ),
    sort: SummarySort = typer.Option(
        SummarySort.FILE,
        "--sort",
        help="Ordering for the summary section.",
        show_default=True,
    ),
    stats: bool = typer.Option(
        False,
        "--stats",
        help="Include aggregate uncovered line counts across all files.",
    ),
    file_stats: bool = typer.Option(
        False,
        "--file-stats",
        help="Include per-file uncovered line counts (requires file reads).",
    ),
    threshold_raw: list[str] | None = typer.Option(
        None,
        "--threshold",
        help=(
            "Coverage thresholds; can be passed multiple times. "
            "Each value is SPEC like statements=90,branches=80,misses=10. "
            "Exit status 2 if any threshold is not met."
        ),
    ),
    color: bool = typer.Option(
        False,
        "--color",
        help="Force coloured output even if stdout is not a TTY.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable coloured output.",
    ),
    quiet: bool = typer.Option(
        False,
        "-q",
        "--quiet",
        help="Suppress non-essential output (errors only).",
    ),
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Verbose logging.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug logging (includes tracebacks on errors).",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Unified coverage reporting for one or more XML files."""
    _ = version  # handled eagerly by callback

    _validate_option_combos(color=color, no_color=no_color, quiet=quiet, verbose=verbose)
    _configure_logging(quiet=quiet, verbose=verbose, debug=debug)

    threshold_options = _parse_thresholds(threshold_raw)
    sections_requested = _compute_sections_requested(
        sections_option=sections_option,
        threshold_options=threshold_options,
        diff_base=diff_base,
    )

    context_option = _parse_context(context_raw)
    with_code, before, after = _compute_context_settings(with_code=with_code, context_option=context_option)

    # Resolve coverage XML input paths.
    try:
        coverage_paths = resolve_coverage_paths(cov_paths)
    except CoverageXMLNotFoundError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=EXIT_NOINPUT) from exc

    base_path = coverage_paths[0].parent

    # Build filters (include patterns incorporate extra_paths).
    includes = list(include_patterns or ()) + [item for item in (extra_paths or []) if item]
    filters = _resolve_filters(includes, list(exclude_patterns or ()), base=base_path)

    fmt, use_color, is_tty_like = _compute_output_policy(
        ctx,
        output=output,
        format_option=format_option,
        color=color,
        no_color=no_color,
    )

    build_opts = BuildOptions(
        coverage_paths=tuple(coverage_paths),
        base_path=base_path,
        filters=filters,
        sections=set(sections_requested),
        diff_base=diff_base,
        branches_mode=branches_mode,
        summary_sort=sort,
        want_aggregate_stats=bool(stats),
        want_file_stats=bool(file_stats),
        want_snippets=bool(with_code),
        context_before=max(0, before),
        context_after=max(0, after),
        meta_show_paths=bool(show_paths),
        meta_show_line_numbers=bool(line_numbers),
    )

    try:
        report = build_report(build_opts)
        if build_opts.want_snippets or build_opts.want_file_stats:
            report = enrich_report(report, build_opts)
    except OSError as exc:
        if debug:
            raise
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=EXIT_NOINPUT) from exc
    except (ElementTree.ParseError, InvalidCoverageXMLError) as exc:
        if debug:
            raise
        typer.echo(f"ERROR: failed to parse coverage XML: {exc}", err=True)
        raise typer.Exit(code=EXIT_DATAERR) from exc

    render_opts = RenderOptions(
        color=bool(use_color),
        show_paths=bool(show_paths),
        show_line_numbers=bool(line_numbers),
        is_tty=bool(is_tty_like),
    )
    try:
        text = render(report, fmt=fmt, options=render_opts)
    except Exception as exc:
        if debug:
            raise
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=EXIT_GENERIC) from exc

    _write_output(text, output)

    if threshold_options:
        result = evaluate_thresholds(report, threshold_options)
        if not result.passed:
            for failure in result.failures:
                typer.echo(
                    f"Threshold failed: {failure.metric} {failure.comparison} {failure.required} "
                    f"(actual {failure.actual})",
                    err=True,
                )
            raise typer.Exit(code=EXIT_THRESHOLD)

    raise typer.Exit(code=EXIT_OK)


# Export a Click command named `main` for back-compat with:
# - src/showcov/__main__.py (python -m showcov)
# - tests using click.testing.CliRunner
# - scripts.py man/completion generation
main: click.Command = get_command(app)

# Back-compat console entrypoint (some packaging configs expect showcov.cli:cli)
cli = main

__all__ = ["app", "cli", "main"]
