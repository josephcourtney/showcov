from __future__ import annotations

import tomllib
from tomllib import TOMLDecodeError
from typing import TYPE_CHECKING

from showcov.adapters.coverage.discover import discover_coverage_paths as discover_xml_paths
from showcov.adapters.coverage.input_kind import (
    CoverageInputBackend,
    detect_input_kind,
)
from showcov.errors import (
    CoverageInputDataError,
    CoverageInputNotFoundError,
    CoverageXMLNotFoundError,
)

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
    output = xml.get("output")
    if isinstance(output, str) and output.strip():
        return (project_root / output.strip()).resolve()
    return None


def _pyproject_coverage_data_file(project_root: Path) -> Path | None:
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
    run = cov.get("run", {})
    data_file = run.get("data_file")
    if isinstance(data_file, str) and data_file.strip():
        return (project_root / data_file.strip()).resolve()
    return None


def _discover_sqlite_candidates(root: Path, cwd: Path) -> tuple[Path, ...]:
    candidates = [
        (cwd / ".coverage").resolve(),
        (root / ".coverage").resolve(),
    ]
    found: list[Path] = [c for c in candidates if c.exists()]
    if found:
        return tuple(dict.fromkeys(found))

    globbed = sorted(cwd.resolve().glob(".coverage.*"))
    if globbed:
        return tuple(globbed)

    globbed = sorted(root.resolve().glob(".coverage.*"))
    if globbed:
        return tuple(globbed)

    return ()


def _discover_xml_only(*, cwd: Path) -> tuple[Path, ...]:
    return discover_xml_paths(cwd=cwd)


def _discover_sqlite_only(*, cwd: Path) -> tuple[Path, ...]:
    root = _find_project_root(cwd)
    from_pyproject = _pyproject_coverage_data_file(root)
    if from_pyproject and from_pyproject.exists():
        return (from_pyproject,)

    candidates = _discover_sqlite_candidates(root, cwd)
    if candidates:
        return candidates

    msg = (
        "no coverage sqlite input provided and none discovered.\n"
        "Tried: pyproject.toml [tool.coverage.run].data_file, .coverage, "
        f".coverage.* in {cwd} and {root}"
    )
    raise CoverageInputNotFoundError(msg.format(cwd=cwd, root=root))


def _discover_auto(*, cwd: Path) -> tuple[Path, ...]:
    root = _find_project_root(cwd)
    try:
        return discover_xml_paths(cwd=cwd)
    except CoverageXMLNotFoundError:
        pass

    from_pyproject = _pyproject_coverage_data_file(root)
    if from_pyproject and from_pyproject.exists():
        return (from_pyproject,)

    candidates = _discover_sqlite_candidates(root, cwd)
    if candidates:
        return candidates

    msg = (
        "no coverage input provided and none discovered.\n"
        "Tried: pyproject.toml [tool.coverage.xml].output, .coverage.xml, coverage.xml, "
        f"pyproject.toml [tool.coverage.run].data_file, .coverage, .coverage.* in {cwd} and {root}"
    )
    raise CoverageInputNotFoundError(msg)


def discover_coverage_inputs(
    *,
    cwd: Path,
    backend: CoverageInputBackend = CoverageInputBackend.AUTO,
) -> tuple[Path, ...]:
    """Discover coverage inputs (Cobertura XML or Coverage.py sqlite DB)."""
    if backend == CoverageInputBackend.XML:
        return _discover_xml_only(cwd=cwd)
    if backend == CoverageInputBackend.SQLITE:
        return _discover_sqlite_only(cwd=cwd)
    return _discover_auto(cwd=cwd)


def _validate_backend_paths(paths: tuple[Path, ...], backend: CoverageInputBackend) -> None:
    required = backend.required_kind()
    if required is None:
        return
    mismatches = [p for p in paths if detect_input_kind(p) != required]
    if mismatches:
        names = ", ".join(str(p) for p in mismatches)
        msg = f"input {names} does not match requested backend {backend.value}"
        raise CoverageInputDataError(msg)


def resolve_coverage_inputs(
    cov_paths: Sequence[Path] | None,
    *,
    cwd: Path,
    backend: CoverageInputBackend = CoverageInputBackend.AUTO,
) -> tuple[Path, ...]:
    """Resolve explicit inputs or discover if none are provided."""
    paths = tuple(cov_paths or ())
    if paths:
        missing = [p for p in paths if not p.exists()]
        if missing:
            msg = f"coverage input not found: {', '.join(str(p) for p in missing)}"
            raise CoverageInputNotFoundError(msg)
        resolved = tuple(p.resolve() for p in paths)
        _validate_backend_paths(resolved, backend)
        return resolved

    return discover_coverage_inputs(cwd=cwd, backend=backend)


__all__ = ["discover_coverage_inputs", "resolve_coverage_inputs"]
