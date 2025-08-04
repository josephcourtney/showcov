"""Common file and path utilities for showcov."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@lru_cache(maxsize=256)
def read_file_lines(path: Path) -> list[str]:
    """Return the lines of *path* without trailing newlines.

    If the file cannot be read or contains invalid UTF-8 sequences an empty
    list is returned instead.  The result is cached to avoid repeated disk
    access when the same file is referenced multiple times.
    """
    try:
        with path.open(encoding="utf-8") as f:
            return [ln.rstrip("\n") for ln in f.readlines()]
    except (OSError, UnicodeDecodeError):
        return []


def normalize_path(path: Path, base: Path | None = None) -> Path:
    """Return *path* normalised relative to *base* if possible.

    When ``base`` is provided and ``path`` is within it the returned path will
    be relative to ``base``.  Otherwise an absolute path is returned.  This
    keeps output stable regardless of the current working directory.
    """
    resolved = path.resolve()
    if base is not None:
        try:
            return resolved.relative_to(base.resolve())
        except ValueError:
            pass
    return resolved


def detect_line_tag(lines: list[str], index: int) -> str | None:
    """Return a tag describing why a line may be uncovered.

    The function uses simple heuristics based on the source line and its
    predecessor:

    * ``# pragma: no cover`` → ``"no-cover"``
    * ``@abstractmethod`` decorator on the previous line → ``"abstractmethod"``
    """
    line = lines[index]
    if "# pragma: no cover" in line:
        return "no-cover"
    if index > 0 and "@abstractmethod" in lines[index - 1]:
        return "abstractmethod"
    return None
