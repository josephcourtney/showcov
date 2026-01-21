from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from functools import cache
from importlib import resources
from typing import TYPE_CHECKING, Any, cast

from jsonschema import validate

from showcov import __version__

if TYPE_CHECKING:
    from showcov.model.report import Report

# -----------------------------------------------------------------------------
# JSON schema loading
# -----------------------------------------------------------------------------

_SCHEMA_FILES: dict[str, str] = {
    "v1": "schema.json",
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

    text = resources.files("showcov.data").joinpath(filename).read_text(encoding="utf-8")
    return json.loads(text)


SCHEMA_ID = str(get_schema("v1")["$id"])


def _to_obj(x: object) -> object:
    """Convert dataclasses to plain containers."""
    if is_dataclass(x):
        return asdict(cast("Any", x))
    return x


def _prune_none(obj: object) -> object:
    """Recursively drop dict keys with None values."""
    if isinstance(obj, dict):
        mapping = cast("dict[str, object]", obj)
        out: dict[str, object] = {}
        for k, v in mapping.items():
            if v is None:
                continue
            out[k] = _prune_none(v)
        return out
    if isinstance(obj, list):
        return [_prune_none(v) for v in obj]
    return obj


def _sections_payload(report: Report) -> dict[str, object]:
    """Emit schema-shaped sections object, including only present sections."""
    sec = report.sections
    out: dict[str, object] = {}

    if sec.lines is not None:
        out["lines"] = _prune_none(_to_obj(sec.lines))
    if sec.branches is not None:
        out["branches"] = _prune_none(_to_obj(sec.branches))
    if sec.summary is not None:
        out["summary"] = _prune_none(_to_obj(sec.summary))
    if sec.diff is not None:
        out["diff"] = _prune_none(_to_obj(sec.diff))

    return out


def format_json(report: Report) -> str:
    """Render a typed Report as validated JSON according to schema v1."""
    payload: dict[str, object] = {
        "schema": SCHEMA_ID,
        "schema_version": 1,
        "tool": {"name": "showcov", "version": __version__},
        "meta": _prune_none(_to_obj(report.meta)),
        "sections": _sections_payload(report),
    }

    validate(payload, get_schema("v1"))
    return json.dumps(payload, indent=2, sort_keys=True)


__all__ = ["SCHEMA_ID", "format_json", "get_schema"]
