from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

T = TypeVar("T")


def _load_patterns(p: Path) -> list[str]:
    """Load glob patterns from a file (one per line). Supports # comments and blank lines."""
    out: list[str] = []
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def _coerce_patterns(items: Sequence[str | Path]) -> tuple[str, ...]:
    pats: list[str] = []
    for it in items:
        if isinstance(it, Path):
            pats.extend(_load_patterns(it) if it.exists() and it.is_file() else [str(it)])
        else:
            pats.append(str(it))
    # de-dupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for p in pats:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class PathFilter:
    """Simple include/exclude filter for file paths.

    Patterns are treated as globs matched against:
      - the base-relative posix path (preferred)
      - the raw posix path (fallback)
    """

    include: tuple[str, ...]
    exclude: tuple[str, ...]
    base: Path

    def __init__(
        self,
        include: Sequence[str | Path] = (),
        exclude: Sequence[str | Path] = (),
        *,
        base: Path,
    ) -> None:
        object.__setattr__(self, "include", _coerce_patterns(tuple(include)))
        object.__setattr__(self, "exclude", _coerce_patterns(tuple(exclude)))
        object.__setattr__(self, "base", base)

    def _labels(self, path: str | Path) -> tuple[str, str]:
        p = Path(path)
        try:
            rel = p if p.is_absolute() else (self.base / p)
            rel = rel.resolve().relative_to(self.base.resolve())
            rel_s = rel.as_posix()
        except (OSError, RuntimeError, ValueError):
            rel_s = p.as_posix()
        raw = p.as_posix()
        return rel_s, raw

    def allow(self, path: str | Path) -> bool:
        rel_s, raw = self._labels(path)

        # includes: if specified, must match at least one
        if self.include:
            ok = any(fnmatch(rel_s, pat) or fnmatch(raw, pat) for pat in self.include)
            if not ok:
                return False

        # excludes: if any match, reject
        if self.exclude:
            bad = any(fnmatch(rel_s, pat) or fnmatch(raw, pat) for pat in self.exclude)
            if bad:
                return False

        return True

    def filter_files(self, files: Iterable[tuple[str, T]]) -> list[tuple[str, T]]:
        """Filter (path, payload) pairs whose path is allowed."""
        out: list[tuple[str, T]] = []
        for path, payload in files:
            if self.allow(path):
                out.append((path, payload))
        return out


__all__ = ["PathFilter"]
