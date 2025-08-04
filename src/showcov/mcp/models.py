"""
Typed objects exchanged by the MCP tools.

*The models mirror the public JSON interface while giving FastMCP enough type
information to generate accurate input/output schemas automatically.*
"""

from __future__ import annotations

from pydantic import BaseModel, Field, PositiveInt, model_validator

# --------------------------------------------------------------------------- #
# Primitives                                                                  #
# --------------------------------------------------------------------------- #


class SourceLine(BaseModel):
    line: PositiveInt
    code: str


class UncoveredRange(BaseModel):
    start: PositiveInt
    end: PositiveInt
    source: list[SourceLine] | None = None

    # Ensure callers pass sensible data when reconstructing from JSON
    @model_validator(mode="after")
    def _end_not_before_start(self) -> UncoveredRange:
        if self.end < self.start:
            msg = "end must be ≥ start"
            raise ValueError(msg)
        return self


class CoverageFile(BaseModel):
    file: str
    uncovered: list[UncoveredRange]


# --------------------------------------------------------------------------- #
# Top-level aggregates                                                         #
# --------------------------------------------------------------------------- #


class Environment(BaseModel):
    coverage_xml: str
    context_lines: int = Field(ge=0, le=20)
    with_code: bool


class CoverageReport(BaseModel):
    """
    Machine-readable coverage payload.

    Tools & agents should rely on the generated JSON schema rather than hard-coding
    field paths.
    """

    version: str
    environment: Environment
    files: list[CoverageFile]


class CoverageStats(BaseModel):
    """Lightweight numeric summary suitable for CI gating."""

    files: int = Field(ge=0)
    regions: int = Field(ge=0)
    lines: int = Field(ge=0)
    passes_threshold: bool
