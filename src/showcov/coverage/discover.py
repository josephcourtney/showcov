from __future__ import annotations

import tomllib
from tomllib import TOMLDecodeError
from typing import TYPE_CHECKING

from showcov.errors import CoverageXMLNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


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
    except (TOMLDecodeError, UnicodeError, ValueError):
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


def resolve_coverage_paths(cov_paths: Sequence[Path] | None, *, cwd: Path) -> tuple[Path, ...]:
    """Resolve explicit XMLs or discover if none are provided."""
    paths = tuple(cov_paths or ())
    if paths:
        missing = [p for p in paths if not p.exists()]
        if missing:
            msg = f"coverage XML not found: {', '.join(str(p) for p in missing)}"
            raise CoverageXMLNotFoundError(msg)
        return tuple(p.resolve() for p in paths)

    return discover_coverage_paths(cwd=cwd)


__all__ = ["discover_coverage_paths", "resolve_coverage_paths"]
