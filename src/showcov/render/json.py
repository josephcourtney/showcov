from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from functools import cache
from importlib import resources
from typing import TYPE_CHECKING, Any, cast

from jsonschema import validate

from showcov import __version__

if TYPE_CHECKING:
    from showcov.model.report import Report, SummarySection

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
    """Recursively drop dict keys with None values.

    Also normalizes tuples to lists so the JSON Schema validator sees
    Python `list` for schema `type: "array"`.
    """
    if isinstance(obj, dict):
        mapping = cast("dict[str, object]", obj)
        out: dict[str, object] = {}
        for k, v in mapping.items():
            if v is None:
                continue
            out[k] = _prune_none(v)
        return out
    if isinstance(obj, tuple):
        return [_prune_none(v) for v in obj]
    if isinstance(obj, list):
        return [_prune_none(v) for v in obj]
    return obj


def _summary_section_v1(sec: SummarySection) -> object:
    """Project SummarySection -> schema v1 shape.

    v1 schema only allows:
      sections.summary = { files: [ {file,statements,branches} ], totals: {...} }
    """
    # Keep only file/statements/branches for each row.
    rows_v1 = [
        {
            "file": r.file,
            "statements": {
                "total": r.statements.total,
                "covered": r.statements.covered,
                "missed": r.statements.missed,
            },
            "branches": {
                "total": r.branches.total,
                "covered": r.branches.covered,
                "missed": r.branches.missed,
            },
        }
        for r in sec.files
    ]

    totals = sec.totals
    totals_v1 = {
        "statements": {
            "total": totals.statements.total,
            "covered": totals.statements.covered,
            "missed": totals.statements.missed,
        },
        "branches": {
            "total": totals.branches.total,
            "covered": totals.branches.covered,
            "missed": totals.branches.missed,
        },
    }
    return {"files": rows_v1, "totals": totals_v1}


def _sections_payload(report: Report, *, schema_version: str) -> dict[str, object]:
    """Emit schema-shaped sections object, including only present sections."""
    sec = report.sections
    out: dict[str, object] = {}

    if sec.lines is not None:
        out["lines"] = _prune_none(_to_obj(sec.lines))
    if sec.branches is not None:
        out["branches"] = _prune_none(_to_obj(sec.branches))
    if sec.summary is not None:
        if schema_version == "v1":
            out["summary"] = _prune_none(_summary_section_v1(sec.summary))
        else:
            out["summary"] = _prune_none(_to_obj(sec.summary))
    if sec.diff is not None:
        out["diff"] = _prune_none(_to_obj(sec.diff))

    return out


def format_json(report: Report, *, schema_version: str = "v1") -> str:
    """Render a typed Report as validated JSON according to selected schema version."""
    payload: dict[str, object] = {
        "schema": str(get_schema(schema_version)["$id"]),
        "schema_version": 1 if schema_version == "v1" else 2,
        "tool": {"name": "showcov", "version": __version__},
        "meta": _prune_none(_to_obj(report.meta)),
        "sections": _sections_payload(report, schema_version=schema_version),
    }

    validate(payload, get_schema(schema_version))
    return json.dumps(payload, indent=2, sort_keys=True)


__all__ = ["SCHEMA_ID", "format_json", "get_schema"]
