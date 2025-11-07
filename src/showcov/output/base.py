"""Base types and interface for output formatters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from showcov.core import UncoveredSection
    from showcov.core.types import FilePath


@dataclass(slots=True)
class OutputMeta:
    """Container for options shared by all formatters."""

    context_lines: int
    with_code: bool
    coverage_xml: FilePath
    color: bool
    show_paths: bool
    show_line_numbers: bool


class Formatter(Protocol):
    def __call__(self, sections: list[UncoveredSection], meta: OutputMeta) -> str: ...
