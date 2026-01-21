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
from typing import TYPE_CHECKING, cast

import click.utils as click_utils
import rich_click as click
from defusedxml import ElementTree

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

# --- rich-click configuration ---
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.MAX_WIDTH = cast("int | None", CONTEXT_SETTINGS["max_content_width"])

_OPTION_GROUPS_BASE: list[click.rich_click.OptionGroupDict] = [
    {
        "name": "Input & selection",
        "options": [
            "--cov",
            "--diff-base",
            "--include",
            "--exclude",
        ],
    },
    {
        "name": "Report content & layout",
        "options": [
            "--sections",
            "--branches-mode",
            "--code",
            "--no-code",
            "--context",
            "--line-numbers",
            "--paths",
            "--no-paths",
            "--sort",
        ],
    },
    {
        "name": "Thresholds & stats (for CI)",
        "options": [
            "--threshold",
            "--stats",
            "--file-stats",
        ],
    },
    {
        "name": "Output format & presentation",
        "options": [
            "--format",
            "--output",
            "--color",
            "--no-color",
        ],
    },
    {
        "name": "Logging & misc",
        "options": [
            "-q",
            "--quiet",
            "-v",
            "--verbose",
            "--debug",
            "--version",
            "--help",
        ],
    },
]

click.rich_click.OPTION_GROUPS = {
    "showcov": _OPTION_GROUPS_BASE,
    "cli": _OPTION_GROUPS_BASE,
}
# ---------------------------------


_SECTION_CHOICES = {"lines", "branches", "summary", "diff"}
_DEFAULT_SECTIONS = ("lines", "branches", "summary")

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_DATAERR = 65
EXIT_NOINPUT = 66
EXIT_THRESHOLD = 2


def _configure_logging(*, quiet: bool, verbose: bool, debug: bool) -> None:
    level = (
        logging.ERROR if quiet else (logging.DEBUG if debug else (logging.DEBUG if verbose else logging.INFO))
    )
    logging.basicConfig(level=level, format="%(message)s")
    if debug:
        logger.debug("debug logging enabled")


class _ContextType(click.ParamType):
    name = "context"

    def convert(self, value, param, ctx):
        if not value:
            return (0, 0)
        parts = [p.strip() for p in value.replace(",", " ").split() if p.strip()]
        try:
            if len(parts) == 1:
                n = int(parts[0])
                return (n, n)
            if len(parts) == 2:  # noqa: PLR2004
                return (int(parts[0]), int(parts[1]))
        except ValueError:
            self.fail("expects N or N,M", param, ctx)
        self.fail("expects N or N,M", param, ctx)
        return None


_CONTEXT = _ContextType()


def _parse_sections(value: str | None) -> tuple[str, ...]:
    if not value:
        return _DEFAULT_SECTIONS
    parts = [p.strip().lower() for p in value.split(",") if p.strip()]
    bad = [p for p in parts if p not in _SECTION_CHOICES]
    if bad:
        msg = f"unknown section(s): {', '.join(bad)}"
        raise click.BadParameter(msg, param_hint="--sections")
    # de-dupe while preserving order
    seen: list[str] = []
    for p in parts:
        if p not in seen:
            seen.append(p)
    return tuple(seen)


def _thresholds_cb(
    _ctx: click.Context,
    _param: click.Parameter | None,
    values: tuple[str, ...],
) -> tuple[Threshold, ...]:
    try:
        return tuple(parse_threshold(v) for v in values)
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc


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


def _write_output(text: str, destination: Path | None) -> None:
    if destination is None or destination == Path("-"):
        click.echo(text)
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


@click.command(
    context_settings=CONTEXT_SETTINGS,
    help=(
        "\b"
        "Generate unified coverage reports from one or more coverage XML files.\n\n"
        "Common examples:\n"
        "  showcov --cov coverage.xml\n"
        "  showcov --cov coverage.xml --threshold statements=90\n"
        "  showcov --cov py.xml --cov js.xml --sections summary,branches\n"
        "  showcov --cov coverage.xml --diff-base baseline.xml --sections diff,summary\n\n"
        "EXTRA_PATHS are optional extra source paths used when resolving files. "
        "Most users can ignore them.\n"
    ),
    epilog=(
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
    ),
)
@click.argument("extra_paths", nargs=-1)
@click.option(
    "--cov",
    "cov_paths",
    multiple=True,
    type=click.Path(path_type=Path),
    help="Coverage XML file. Can be passed multiple times.",
)
@click.option(
    "--include",
    "include_patterns",
    multiple=True,
    help="Glob of source files to include (can repeat).",
)
@click.option(
    "--exclude",
    "exclude_patterns",
    multiple=True,
    help="Glob of source files to exclude (can repeat).",
)
@click.option(
    "--sections",
    "sections_option",
    help="Comma-separated list of sections: lines, branches, summary, diff.",
)
@click.option(
    "--diff-base",
    type=click.Path(path_type=Path),
    help="Coverage XML to compare against when using the diff section.",
)
@click.option(
    "--branches-mode",
    type=click.Choice([mode.value for mode in BranchMode], case_sensitive=False),
    default=BranchMode.PARTIAL.value,
    show_default=True,
    help=(
        "Which branches count as uncovered:\n"
        "  missing-only  only missing branches\n"
        "  partial       missing + partial branches\n"
        "  all           all branches"
    ),
)
@click.option(
    "--format",
    "format_option",
    default="auto",
    show_default=True,
    help="Output format: human, rg, json, or auto (TTY → human, non-TTY → json).",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Write report to PATH instead of stdout (use '-' for stdout).",
)
@click.option(
    "--code/--no-code",
    "with_code",
    default=False,
    show_default=True,
    help="Include code snippets around uncovered ranges (requires file reads).",
)
@click.option(
    "--context",
    "context_option",
    type=_CONTEXT,
    help="Lines before/after uncovered ranges as N or N,M (implies --code).",
)
@click.option(
    "--line-numbers",
    is_flag=True,
    help="Show line numbers alongside code snippets.",
)
@click.option(
    "--paths/--no-paths",
    "show_paths",
    default=True,
    show_default=True,
    help="Show file paths in report output.",
)
@click.option(
    "--sort",
    type=click.Choice([choice.value for choice in SummarySort], case_sensitive=False),
    default=SummarySort.FILE.value,
    show_default=True,
    help="Ordering for the summary section.",
)
@click.option(
    "--stats",
    is_flag=True,
    help="Include aggregate uncovered line counts across all files.",
)
@click.option(
    "--file-stats",
    is_flag=True,
    help="Include per-file uncovered line counts (requires file reads).",
)
@click.option(
    "--threshold",
    "threshold_options",
    multiple=True,
    callback=_thresholds_cb,
    help=(
        "Coverage thresholds; can be passed multiple times. "
        "Each value is SPEC like statements=90,branches=80,misses=10. "
        "Exit status 2 if any threshold is not met."
    ),
)
@click.option(
    "--color",
    is_flag=True,
    help="Force coloured output even if stdout is not a TTY.",
)
@click.option(
    "--no-color",
    is_flag=True,
    help="Disable coloured output.",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Suppress non-essential output (errors only).",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Verbose logging.",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging (includes tracebacks on errors).",
)
@click.version_option(__version__)
@click.pass_context
def main(  # noqa: C901, PLR0912, PLR0914, PLR0915
    ctx: click.Context,
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
    context_option: tuple[int, int] | None = None,
    line_numbers: bool = False,
    show_paths: bool = True,
    sort: str = SummarySort.FILE.value,
    stats: bool = False,
    file_stats: bool = False,
    threshold_options: tuple[Threshold, ...] = (),
    color: bool = False,
    no_color: bool = False,
    quiet: bool = False,
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Unified coverage reporting for one or more XML files."""
    if color and no_color:
        msg = "--color"
        raise click.BadOptionUsage(msg, "--color and --no-color cannot be combined")
    if quiet and verbose:
        msg = "--quiet"
        raise click.BadOptionUsage(msg, "--quiet and --verbose cannot be combined")

    _configure_logging(quiet=quiet, verbose=verbose, debug=debug)

    # Parse sections early so we can validate diff requirements.
    sections_requested = _parse_sections(sections_option)

    if "diff" in sections_requested and diff_base is None:
        msg = "--diff-base"
        raise click.BadOptionUsage(msg, "--diff-base is required when requesting the diff section")

    # Threshold evaluation requires specific sections to be present in the report.
    # If the user overrides --sections, ensure we still build what thresholds need.
    if threshold_options:
        need_stmt = any(t.statement is not None for t in threshold_options)
        need_br = any(t.branch is not None for t in threshold_options)
        need_miss = any(t.misses is not None for t in threshold_options)

        # Start from user-requested sections, then add requirements.
        sec_set = set(sections_requested)
        if need_stmt or need_br:
            sec_set.add("summary")
        if need_miss:
            sec_set.add("lines")

        # Preserve original order for existing items; append any newly-required sections.
        ordered: list[str] = list(sections_requested)
        for name in ("lines", "branches", "summary", "diff"):
            if name in sec_set and name not in ordered:
                ordered.append(name)
        sections_requested = tuple(ordered)

    before, after = context_option or (0, 0)

    # If user requested context but did not explicitly enable code, turn it on.
    if context_option is not None and not with_code:
        with_code = True

    # Resolve coverage XML input paths.
    try:
        coverage_paths = resolve_coverage_paths(cov_paths)
    except CoverageXMLNotFoundError as exc:
        click.echo(f"ERROR: {exc}", err=True)
        ctx.exit(EXIT_NOINPUT)

    base_path = coverage_paths[0].parent

    # Build filters (include patterns incorporate extra_paths).
    includes = list(include_patterns) + [item for item in extra_paths if item]
    filters = _resolve_filters(includes, exclude_patterns, base=base_path)

    # Output/TTY/color decisions (CLI-only).
    if output and output != Path("-") and format_option.strip().lower() == "auto":
        msg = "--format"
        raise click.BadOptionUsage(msg, "--format=auto cannot be used with --output")

    ansi_allowed = not click_utils.should_strip_ansi(sys.stdout)
    stdout_is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)()) or ansi_allowed

    allow_tty_output = output in {None, Path("-")}
    is_tty_like = stdout_is_tty if allow_tty_output else False

    use_color = (
        True if color else False if no_color else (ctx.color if ctx.color is not None else ansi_allowed)
    )
    fmt = _resolve_format(format_option, is_tty_like=is_tty_like)

    # Build report.
    build_opts = BuildOptions(
        coverage_paths=coverage_paths,
        base_path=base_path,
        filters=filters,
        sections=set(sections_requested),
        diff_base=diff_base,
        branches_mode=BranchMode(branches_mode),
        summary_sort=SummarySort(sort),
        want_aggregate_stats=bool(stats),
        want_file_stats=bool(file_stats),
        # If code is requested, we enrich with snippets.
        want_snippets=bool(with_code),
        context_before=max(0, before),
        context_after=max(0, after),
        meta_show_paths=bool(show_paths),
        meta_show_line_numbers=bool(line_numbers),
    )

    try:
        report = build_report(build_opts)
        # Enrich only if we need filesystem-derived data (snippets and/or per-file totals).
        if build_opts.want_snippets or build_opts.want_file_stats:
            report = enrich_report(report, build_opts)
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

    # Render.
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
        click.echo(f"ERROR: {exc}", err=True)
        ctx.exit(EXIT_GENERIC)

    _write_output(text, output)

    # Threshold evaluation (CI).
    if threshold_options:
        result = evaluate_thresholds(report, threshold_options)
        if not result.passed:
            for failure in result.failures:
                click.echo(
                    f"Threshold failed: {failure.metric} {failure.comparison} {failure.required} "
                    f"(actual {failure.actual})",
                    err=True,
                )
            ctx.exit(EXIT_THRESHOLD)

    ctx.exit(EXIT_OK)
