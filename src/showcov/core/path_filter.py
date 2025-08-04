"""Utilities for filtering :class:`UncoveredSection` objects by path."""

from collections.abc import Iterable, Sequence
from pathlib import Path

from pathspec import PathSpec

from .core import UncoveredSection


class PathFilter:
    """Filter uncovered sections using include and exclude rules."""

    def __init__(self, includes: Sequence[str | Path] = (), excludes: Sequence[str | Path] = ()) -> None:
        include_patterns = self._prepare_patterns(includes)
        exclude_patterns = self._prepare_patterns(excludes)
        self._include_spec = PathSpec.from_lines("gitwildmatch", include_patterns)
        self._exclude_spec = PathSpec.from_lines("gitwildmatch", exclude_patterns)
        self._has_includes = bool(include_patterns)

    @staticmethod
    def _prepare_patterns(patterns: Sequence[str | Path]) -> list[str]:
        """Normalize patterns and resolve concrete paths."""
        prepared: list[str] = []
        for pat in patterns:
            s = str(pat)
            if any(ch in s for ch in "*?[]"):
                prepared.append(s)
            else:
                prepared.append(Path(s).resolve().as_posix())
        return prepared

    def _match_includes(self, path: Path) -> bool:
        if not self._has_includes:
            return True
        return self._include_spec.match_file(path.resolve().as_posix())

    def _match_excludes(self, path: Path) -> bool:
        return self._exclude_spec.match_file(path.resolve().as_posix())

    def filter(self, sections: Iterable[UncoveredSection]) -> list[UncoveredSection]:
        """Return sections that satisfy include/exclude rules."""
        return [
            sec for sec in sections if self._match_includes(sec.file) and not self._match_excludes(sec.file)
        ]
