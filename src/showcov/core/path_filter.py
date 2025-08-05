"""Utilities for filtering :class:`UncoveredSection` objects by path."""

from collections.abc import Iterable, Sequence
from pathlib import Path

from pathspec import PathSpec

from showcov import logger

from .core import UncoveredSection
from .files import normalize_path


class PathFilter:
    """Filter uncovered sections using include and exclude rules."""

    def __init__(
        self,
        includes: Sequence[str | Path] = (),
        excludes: Sequence[str | Path] = (),
        *,
        base: Path | None = None,
    ) -> None:
        self._base = base or Path.cwd()
        include_patterns = self._prepare_patterns(includes, expand_dirs=True)
        exclude_patterns = self._prepare_patterns(excludes, expand_dirs=False)
        self._include_spec = PathSpec.from_lines("gitwildmatch", include_patterns)
        self._exclude_spec = PathSpec.from_lines("gitwildmatch", exclude_patterns)
        self._has_includes = bool(include_patterns)

    def _prepare_patterns(self, patterns: Sequence[str | Path], *, expand_dirs: bool) -> list[str]:
        """Normalize patterns and resolve concrete paths."""
        prepared: list[str] = []
        for pat in patterns:
            s = str(pat)
            if any(ch in s for ch in "*?[]"):
                p = Path(s)
                if p.is_absolute():
                    s = normalize_path(p, base=self._base).as_posix()
                prepared.append(s.replace("\\", "/"))
                continue
            p = Path(s)
            if p.is_dir() and expand_dirs:
                p /= "**/*"
            prepared.append(normalize_path(p, base=self._base).as_posix())
        return prepared

    def _match_includes(self, path: Path) -> bool:
        if not self._has_includes:
            return True
        rel = normalize_path(path, base=self._base).as_posix()
        return self._include_spec.match_file(rel)

    def _match_excludes(self, path: Path) -> bool:
        rel = normalize_path(path, base=self._base).as_posix()
        return self._exclude_spec.match_file(rel)

    def filter(self, sections: Iterable[UncoveredSection]) -> list[UncoveredSection]:
        """Return sections that satisfy include/exclude rules."""
        result: list[UncoveredSection] = []
        for sec in sections:
            inc = self._match_includes(sec.file)
            exc = self._match_excludes(sec.file)
            logger.debug("path filter %s include=%s exclude=%s", sec.file, inc, exc)
            if inc and not exc:
                result.append(sec)
        return result
