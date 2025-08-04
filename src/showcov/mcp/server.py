"""Fast-MCP server exposing *showcov* coverage-analysis tools."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, PositiveInt

from showcov import __version__
from showcov.cli.util import ShowcovOptions, resolve_sections
from showcov.core import (
    UncoveredSection,
    build_sections,
    gather_uncovered_lines_from_xml,
)
from showcov.output.base import OutputMeta

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic primitives reused by many tools
# ─────────────────────────────────────────────────────────────────────────────


class SourceLine(BaseModel):
    line: PositiveInt
    code: str


class UncoveredRange(BaseModel):
    start: PositiveInt
    end: PositiveInt
    source: list[SourceLine] | None = None


class CoverageFile(BaseModel):
    file: str
    uncovered: list[UncoveredRange]


class Environment(BaseModel):
    coverage_xml: str
    context_lines: int = Field(ge=0, le=20)
    with_code: bool


class CoverageReport(BaseModel):
    version: str
    environment: Environment
    files: list[CoverageFile]


class CoverageStats(BaseModel):
    files: int = Field(ge=0)
    regions: int = Field(ge=0)
    lines: int = Field(ge=0)
    passes_threshold: bool


class DiffEntry(BaseModel):
    file: str
    added: list[UncoveredRange]
    removed: list[UncoveredRange]


class CoverageDiff(BaseModel):
    version: str
    baseline: str
    current: str
    changed_files: list[DiffEntry]


class ErrorResponse(BaseModel):
    code: int
    message: str
    detail: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Prompt templates bundled as simple strings (keep <50 lines each)
# ─────────────────────────────────────────────────────────────────────────────
_TEMPLATES: dict[str, str] = {
    "suggest_tests": (
        "Write Pytest unit tests that cover each uncovered range below.\n"
        "Focus on behavioural assertions, not implementation details.\n"
        "{{ coverage_json }}"
    )
}

# ─────────────────────────────────────────────────────────────────────────────
# Fast-MCP setup
# ─────────────────────────────────────────────────────────────────────────────
mcp = FastMCP("showcov")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _sections_from_xml(xml_path: Path) -> list[UncoveredSection]:
    """Return cached *UncoveredSection* list for *xml_path*."""
    mtime = xml_path.stat().st_mtime

    @lru_cache(maxsize=8)
    def _cached(path_str: str, _mtime_val: float) -> list[UncoveredSection]:
        uncovered = gather_uncovered_lines_from_xml(Path(path_str))
        return build_sections(uncovered)

    return _cached(str(xml_path), mtime)  # type: ignore[arg-type]


def _sections_and_meta(
    include: Iterable[str] | None,
    exclude: Iterable[str] | None,
    context_lines: int,
    *,
    with_code: bool,
) -> tuple[list[UncoveredSection], OutputMeta]:
    """Resolve uncovered sections using CLI helpers so config-file logic stays central."""
    opts = ShowcovOptions(
        include=list(include or []),
        exclude=list(exclude or []),
        context_before=context_lines,
        context_after=context_lines,
        show_code=with_code,
    )
    sections, xml_path = resolve_sections(opts)
    meta = OutputMeta(
        context_lines=context_lines,
        with_code=with_code,
        coverage_xml=xml_path,
        color=False,
    )
    return sections, meta


def _make_report(sections: list[UncoveredSection], meta: OutputMeta) -> CoverageReport:
    files = [
        section.to_dict(with_code=meta.with_code, context_lines=meta.context_lines) for section in sections
    ]
    env = Environment(
        coverage_xml=str(meta.coverage_xml),
        context_lines=meta.context_lines,
        with_code=meta.with_code,
    )
    return CoverageReport(version=__version__, environment=env, files=files)  # type: ignore[arg-type]


def _paginate(items: list, page: int, per_page: int) -> list:
    if per_page <= 0:
        return items
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end]


# ─────────────────────────────────────────────────────────────────────────────
# Public resources
# ─────────────────────────────────────────────────────────────────────────────
@mcp.resource("mcp://showcov/coverage/version")
def get_version() -> str:
    return __version__


@mcp.prompt("mcp://showcov/prompts/suggest_tests")
def suggest_tests_prompt() -> str:
    return (
        "Write Pytest unit tests that cover each uncovered range below.\n"
        "Focus on behavioural assertions, not implementation details.\n"
        "{{ coverage_json }}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public tools
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool(
    name="coverage/list_files",
    title="List files having uncovered code",
    description="Return paths of all source files that still have uncovered lines.",
)
def list_files(
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> list[str]:
    """Return paths of all source files with uncovered lines.

    Examples
    --------
    >>> client.call("coverage/list_files", {"include": ["src/**.py"]})
    """
    sections, _ = _sections_and_meta(include, exclude, context_lines=0, with_code=False)
    return [s.file.as_posix() for s in sections]


@mcp.tool(
    name="coverage/get_sections",
    title="Uncovered code sections",
    description=(
        "Return uncovered line ranges, optionally with source code.\n"
        "Large reports can be paged with *page* and *per_page*."
    ),
)
def get_sections(
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    *,
    context_lines: int = 0,
    with_code: bool = True,
    page: int = 1,
    per_page: int = 100,  # number of files per page, not ranges
) -> CoverageReport:
    """Return uncovered line ranges, optionally with source code.

    Examples
    --------
    Basic use
    >>> client.call("coverage/get_sections")

    Fetch first 10 files only
    >>> client.call("coverage/get_sections", {"per_page": 10})
    """
    sections, meta = _sections_and_meta(include, exclude, context_lines, with_code=with_code)
    paged = _paginate(sections, max(1, page), max(1, per_page))
    return _make_report(paged, meta)


@mcp.tool(
    name="coverage/stats",
    title="Coverage statistics",
    description="Return counts of files, regions, and lines that remain uncovered.",
)
def stats(
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    threshold_lines: int | None = None,
) -> CoverageStats:
    """Return counts of files, regions, and lines that remain uncovered.

    Examples
    --------
    >>> client.call("coverage/stats", {"threshold_lines": 50})
    """
    sections, _meta = _sections_and_meta(include, exclude, 0, with_code=False)
    total_files = len(sections)
    total_regions = sum(len(s.ranges) for s in sections)
    total_lines = sum(end - start + 1 for s in sections for start, end in s.ranges)
    passes = threshold_lines is None or total_lines <= threshold_lines
    return CoverageStats(
        files=total_files,
        regions=total_regions,
        lines=total_lines,
        passes_threshold=passes,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(_app: object) -> AsyncIterator[None]:
    """Lifecycle hooks for FastMCP."""
    print("🚀 Starting Showcov MCP server...")
    await asyncio.sleep(0)
    try:
        yield
    finally:
        await asyncio.sleep(0)
        print("🛑 Shutting down Showcov MCP server...")


def main() -> None:  # pragma: no cover
    """Run the server with the default streamable-HTTP transport and lifespan."""
    mcp.run(transport="streamable-http", mount_path="/mcp")
