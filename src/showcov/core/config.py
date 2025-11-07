"""Central configuration and constants for ``showcov``."""

from __future__ import annotations

import json
from functools import cache
from importlib import resources

# Step size when grouping consecutive uncovered line numbers.
CONSECUTIVE_STEP = 1

# Default logging format used by the CLI entry point.
LOG_FORMAT = "%(levelname)s: %(message)s"


_SCHEMA_FILES: dict[str, str] = {
    "v1": "schema.json",
    "v2": "schema.v2.json",
}


@cache
def get_schema(version: str = "v1") -> dict[str, object]:
    """Load and cache the JSON schema for structured output."""
    try:
        filename = _SCHEMA_FILES[version]
    except KeyError as exc:
        choices = ", ".join(sorted(_SCHEMA_FILES))
        msg = f"Unsupported schema version: {version!r}. Available versions: {choices}"
        raise ValueError(msg) from exc
    return json.loads(resources.files("showcov.data").joinpath(filename).read_text(encoding="utf-8"))


__all__ = ["CONSECUTIVE_STEP", "LOG_FORMAT", "get_schema"]
