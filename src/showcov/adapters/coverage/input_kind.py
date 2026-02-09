from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class CoverageInputKind(StrEnum):
    XML = "xml"
    SQLITE = "sqlite"


class CoverageInputBackend(StrEnum):
    AUTO = "auto"
    XML = "xml"
    SQLITE = "sqlite"

    def required_kind(self) -> CoverageInputKind | None:
        if self == CoverageInputBackend.XML:
            return CoverageInputKind.XML
        if self == CoverageInputBackend.SQLITE:
            return CoverageInputKind.SQLITE
        return None


_SQLITE_HEADER = b"SQLite format 3\x00"


def detect_input_kind(path: Path) -> CoverageInputKind:
    """Detect whether `path` is Cobertura XML or a Coverage.py SQLite data file."""
    try:
        with path.open("rb") as f:
            head = f.read(len(_SQLITE_HEADER))
    except OSError:
        # Let upstream IO error handling surface this consistently.
        return CoverageInputKind.XML

    if head == _SQLITE_HEADER:
        return CoverageInputKind.SQLITE
    return CoverageInputKind.XML


def partition_inputs(paths: tuple[Path, ...]) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Split inputs into (xml_paths, sqlite_paths) in a stable order."""
    xml: list[Path] = []
    db: list[Path] = []
    for p in paths:
        (db if detect_input_kind(p) == CoverageInputKind.SQLITE else xml).append(p)
    return tuple(xml), tuple(db)


__all__ = [
    "CoverageInputBackend",
    "CoverageInputKind",
    "detect_input_kind",
    "partition_inputs",
]
