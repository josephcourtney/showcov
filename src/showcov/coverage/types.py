from __future__ import annotations

from typing import Protocol


class ElementLike(Protocol):
    """Simplified Element protocol that matches the subset of behavior we consume."""

    tag: str | None

    def findall(self, path: str) -> list[ElementLike]: ...

    def get(self, key: str, default: str | None = None) -> str | None: ...


__all__ = ["ElementLike"]
