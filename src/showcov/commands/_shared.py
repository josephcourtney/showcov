from __future__ import annotations

import tomllib
from dataclasses import replace
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import click.utils as click_utils
import typer
from defusedxml import ElementTree

from showcov import logger
from showcov.engine.build import BuildOptions, build_report
from showcov.engine.enrich import enrich_report
from showcov.errors import CoverageXMLNotFoundError, InvalidCoverageXMLError
from showcov.model.path_filter import PathFilter
from showcov.model.thresholds import Threshold
from showcov.model.thresholds import evaluate as evaluate_thresholds
from showcov.render.render import RenderOptions, render

if TYPE_CHECKING:
    from collections.abc import Sequence

    from showcov.model.types import BranchMode, SummarySort

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_DATAERR = 65
EXIT_NOINPUT = 66
EXIT_THRESHOLD = 2

_PATTERN_FILE_SUFFIXES = {".txt", ".ignore", ".gitignore", ".showcovignore", ".patterns"}


class OutputFormat(StrEnum):
    AUTO = "auto"
    HUMAN = "human"
    GREP = "grep"


class AutoOnOff(StrEnum):
    AUTO = "auto"
    ON = "on"
    OFF = "off"


class BranchToggle(StrEnum):
    AUTO = "auto"
    ON = "on"
    OFF = "off"


def write_output(text: str, destination: Path | None) -> None:
    """Write output to stdout or a file (PATH or '-' for stdout)."""
    if destination is None or destination == Path("-"):
        print(text)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def _find_project_root(start: Path) -> Path:
    """Heuristic project root finder: walks upward looking for pyproject.toml or .git."""
    cur = start.resolve()
    for p in (cur, *cur.parents):
        if (p / "pyproject.toml").exists():
            return p
        if (p / ".git").exists():
            return p
    return cur


def _pyproject_coverage_xml_output(project_root: Path) -> Path | None:
    """Return tool.coverage.xml.output if present."""
    pp = project_root / "pyproject.toml"
    if not pp.exists():
        return None
    try:
        data = tomllib.loads(pp.read_text(encoding="utf-8"))
    except OSError:
        return None
    except Exception:
        return None

    tool = data.get("tool", {})
    cov = tool.get("coverage", {})
    xml = cov.get("xml", {})
    out = xml.get("output")
    if isinstance(out, str) and out.strip():
        return (project_root / out.strip()).resolve()
    return None


def discover_coverage_paths(*, cwd: Path) -> tuple[Path, ...]:
    """Discover coverage XML paths based on common conventions + pyproject config."""
    root = _find_project_root(cwd)

    from_pyproject = _pyproject_coverage_xml_output(root)
    if from_pyproject and from_pyproject.exists():
        return (from_pyproject,)

    candidates = [
        (cwd / ".coverage.xml").resolve(),
        (cwd / "coverage.xml").resolve(),
        (root / ".coverage.xml").resolve(),
        (root / "coverage.xml").resolve(),
    ]
    for c in candidates:
        if c.exists():
            return (c,)

    msg = (
        "no coverage XML provided and none discovered.\n"
        "Tried: pyproject.toml [tool.coverage.xml].output, .coverage.xml, coverage.xml "
        f"in {cwd} and {root}"
    )
    raise CoverageXMLNotFoundError(msg)


def resolve_coverage_paths(cov_xmls: Sequence[Path] | None, *, cwd: Path) -> tuple[Path, ...]:
    """Resolve explicit XMLs or discover if none are provided."""
    paths = tuple(cov_xmls or ())
    if paths:
        missing = [p for p in paths if not p.exists()]
        if missing:
            msg = f"coverage XML not found: {', '.join(str(p) for p in missing)}"
            raise CoverageXMLNotFoundError(msg)
        return tuple(p.resolve() for p in paths)
    return discover_coverage_paths(cwd=cwd)


def _coerce_pattern_token(token: str) -> str | Path:
    """Support @FILE patterns and auto-detect pattern files by suffix."""
    raw = (token or "").strip()
    if not raw:
        return ""

    if raw.startswith("@"):
        return Path(raw[1:])

    p = Path(raw)
    if p.exists() and p.is_file() and p.suffix.lower() in _PATTERN_FILE_SUFFIXES:
        return p

    return raw


def build_path_filter(
    *,
    include: Sequence[str],
    exclude: Sequence[str],
    base: Path,
) -> PathFilter | None:
    if not include and not exclude:
        return None
    inc: list[str | Path] = [_coerce_pattern_token(x) for x in include if x]
    exc: list[str | Path] = [_coerce_pattern_token(x) for x in exclude if x]
    return PathFilter(inc, exc, base=base)


def compute_io_policy(
    *,
    fmt: OutputFormat,
    output: Path | None,
) -> tuple[str, bool, bool]:
    """Return (render_fmt, is_tty_like, color_allowed)."""
    import sys

    allow_tty_output = output in {None, Path("-")}
    stdout = sys.stdout

    stdout_is_tty = allow_tty_output and bool(getattr(stdout, "isatty", lambda: False)())
    ansi_allowed = not click_utils.should_strip_ansi(stdout)

    if fmt == OutputFormat.AUTO:
        fmt_resolved = OutputFormat.HUMAN if stdout_is_tty else OutputFormat.GREP
    else:
        fmt_resolved = fmt

    render_fmt = "human" if fmt_resolved == OutputFormat.HUMAN else "rg"
    is_tty_like = stdout_is_tty
    color_allowed = bool(render_fmt == "human" and is_tty_like and ansi_allowed)

    return render_fmt, is_tty_like, color_allowed


def apply_thresholds_or_exit(
    report,
    *,
    fail_under_stmt: float | None,
    fail_under_branches: float | None,
    max_misses: int | None,
) -> None:
    thresholds: list[Threshold] = []
    if fail_under_stmt is not None:
        thresholds.append(Threshold(statement=float(fail_under_stmt)))
    if fail_under_branches is not None:
        thresholds.append(Threshold(branch=float(fail_under_branches)))
    if max_misses is not None:
        thresholds.append(Threshold(misses=int(max_misses)))

    if not thresholds:
        return

    result = evaluate_thresholds(report, thresholds)
    if result.passed:
        return

    for f in result.failures:
        typer.echo(
            f"Threshold failed: {f.metric} {f.comparison} {f.required} (actual {f.actual})",
            err=True,
        )
    raise typer.Exit(code=EXIT_THRESHOLD)


def build_and_render(
    *,
    coverage_paths: tuple[Path, ...],
    base_path: Path,
    filters: PathFilter | None,
    sections: set[str],
    diff_base: Path | None,
    branches_mode: BranchMode,
    summary_sort: SummarySort,
    want_stats: bool,
    want_file_stats: bool,
    want_snippets: bool,
    context_before: int,
    context_after: int,
    show_paths: bool,
    show_line_numbers: bool,
    render_fmt: str,
    is_tty_like: bool,
    color: bool,
    drop_empty_branches: bool,
):
    opts = BuildOptions(
        coverage_paths=coverage_paths,
        base_path=base_path,
        filters=filters,
        sections=sections,
        diff_base=diff_base,
        branches_mode=branches_mode,
        summary_sort=summary_sort,
        want_aggregate_stats=want_stats,
        want_file_stats=want_file_stats,
        want_snippets=want_snippets,
        context_before=context_before,
        context_after=context_after,
        meta_show_paths=show_paths,
        meta_show_line_numbers=show_line_numbers,
    )

    try:
        report = build_report(opts)
        if want_snippets or want_file_stats:
            report = enrich_report(report, opts)
    except CoverageXMLNotFoundError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=EXIT_NOINPUT) from exc
    except (ElementTree.ParseError, InvalidCoverageXMLError) as exc:
        typer.echo(f"ERROR: failed to parse coverage XML: {exc}", err=True)
        raise typer.Exit(code=EXIT_DATAERR) from exc
    except OSError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=EXIT_NOINPUT) from exc
    except Exception as exc:
        logger.exception("unexpected failure")
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=EXIT_GENERIC) from exc

    if drop_empty_branches and report.sections.branches is not None and not report.sections.branches.gaps:
        report = replace(report, sections=replace(report.sections, branches=None))

    text = render(
        report,
        fmt=render_fmt,
        options=RenderOptions(
            color=bool(color),
            show_paths=bool(show_paths),
            show_line_numbers=bool(show_line_numbers),
            is_tty=bool(is_tty_like),
        ),
    )
    return report, text


__all__ = [
    "EXIT_DATAERR",
    "EXIT_GENERIC",
    "EXIT_NOINPUT",
    "EXIT_OK",
    "EXIT_THRESHOLD",
    "write_output",
]
