"""Central configuration and constants for ``showcov``."""

from __future__ import annotations

import json
from functools import cache
from importlib import resources

# Step size when grouping consecutive uncovered line numbers.
CONSECUTIVE_STEP = 1

# Default logging format used by the CLI entry point.
LOG_FORMAT = "%(levelname)s: %(message)s"


@cache
def get_schema() -> dict[str, object]:
    """Load and cache the JSON schema for structured output."""
    return json.loads(resources.files("showcov.data").joinpath("schema.json").read_text(encoding="utf-8"))


__all__ = ["CONSECUTIVE_STEP", "LOG_FORMAT", "get_schema"]
