"""Base types and interface for output formatters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from showcov.core import UncoveredSection
    from showcov.core.types import FilePath


@dataclass(slots=True)
class OutputMeta:
    """Container for options shared by all renderers."""

    coverage_xml: FilePath
    with_code: bool
    color: bool
    show_paths: bool
    show_line_numbers: bool
    context_before: int = 0
    context_after: int = 0

    @property
    def context_lines(self) -> int:
        """Return the maximum symmetric context span."""
        return max(self.context_before, self.context_after)


class Formatter(Protocol):
    def __call__(self, sections: list[UncoveredSection], meta: OutputMeta) -> str: ...
