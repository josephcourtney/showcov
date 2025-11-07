from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from jsonschema import validate

from showcov import __version__
from showcov.core import Report, get_schema

SCHEMA_V2_ID = "https://example.com/showcov.schema.v2.json"


def _normalize(obj: object) -> object:
    if isinstance(obj, Mapping):
        return {key: _normalize(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(item) for item in obj]
    return obj


def format_json_v2(report: Report) -> str:
    payload: dict[str, Any] = {
        "schema": SCHEMA_V2_ID,
        "schema_version": 2,
        "tool": {"name": "showcov", "version": __version__},
        "meta": _normalize(report.meta),
        "sections": _normalize(report.sections),
    }
    validate(payload, get_schema("v2"))
    return json.dumps(payload, indent=2, sort_keys=True)


__all__ = ["SCHEMA_V2_ID", "format_json_v2"]
