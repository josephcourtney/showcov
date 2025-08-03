"""Utilities for filtering :class:`UncoveredSection` objects by path."""

from collections.abc import Iterable, Sequence
from fnmatch import fnmatch
from pathlib import Path

from .core import UncoveredSection


class PathFilter:
    """Filter uncovered sections using include and exclude rules."""

    def __init__(self, includes: Sequence[str | Path] = (), excludes: Sequence[str] = ()) -> None:
        self._include_paths = self._expand_paths(includes) if includes else []
        self._excludes = tuple(excludes)

    @staticmethod
    def _expand_paths(patterns: Sequence[str | Path]) -> list[Path]:
        """Expand files, directories, and globs into concrete paths."""
        expanded: set[Path] = set()
        for pat in patterns:
            pat_str = str(pat)
            try:
                matches = list(Path().glob(pat_str))
            except NotImplementedError:
                matches = []
            if matches:
                expanded.update(p.resolve() for p in matches)
            else:
                expanded.add(Path(pat).resolve())
        return sorted(expanded)

    def _match_includes(self, path: Path) -> bool:
        if not self._include_paths:
            return True
        return any(path == p or (p.is_dir() and path.is_relative_to(p)) for p in self._include_paths)

    def _match_excludes(self, path: Path) -> bool:
        return any(fnmatch(path.as_posix(), pat) for pat in self._excludes)

    def filter(self, sections: Iterable[UncoveredSection]) -> list[UncoveredSection]:
        """Return sections that satisfy include/exclude rules."""
        return [
            sec for sec in sections if self._match_includes(sec.file) and not self._match_excludes(sec.file)
        ]
