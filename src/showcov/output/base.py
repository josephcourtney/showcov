"""Base types and interface for output formatters.

Defines:

- `Format`: Enum of supported output formats (human, json, markdown, sarif, html, auto).
- `OutputMeta`: Container for formatting options shared across all formatters.
- `Formatter`: Protocol that all formatter functions must implement.

Each formatter takes a list of `UncoveredSection` objects and an `OutputMeta`
instance, and returns a string suitable for printing or saving.

Formatters are registered in `registry.py` and selected dynamically at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path

    from showcov.core import UncoveredSection


class Format(StrEnum):
    """Supported output formats."""

    HUMAN = "human"
    JSON = "json"
    MARKDOWN = "markdown"
    SARIF = "sarif"
    HTML = "html"
    AUTO = "auto"


@dataclass(slots=True)
class OutputMeta:
    """Container for options shared by all formatters."""

    context_lines: int
    with_code: bool
    coverage_xml: Path
    color: bool


class Formatter(Protocol):
    def __call__(self, sections: list[UncoveredSection], meta: OutputMeta) -> str: ...
