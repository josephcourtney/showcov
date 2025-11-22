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
    context_before: int = 0
    context_after: int = 0
    with_code: bool = True
    color: bool = True
    show_paths: bool = True
    show_line_numbers: bool = True
    is_tty: bool = False

    def __init__(
        self,
        coverage_xml: FilePath,
        context_before: int = 0,
        context_after: int = 0,
        *,
        with_code: bool = True,
        color: bool = True,
        show_paths: bool = True,
        show_line_numbers: bool = True,
        is_tty: bool = False,
    ) -> None:
        self.coverage_xml = coverage_xml
        self.with_code = with_code
        self.color = color
        self.show_paths = show_paths
        self.show_line_numbers = show_line_numbers
        self.context_before = context_before
        self.context_after = context_after
        self.is_tty = is_tty

    @property
    def context_lines(self) -> int:
        """Return the maximum symmetric context span."""
        return max(self.context_before, self.context_after)


class Formatter(Protocol):
    def __call__(self, sections: list[UncoveredSection], meta: OutputMeta) -> str: ...
