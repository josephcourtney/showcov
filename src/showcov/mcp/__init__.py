"""Model Context Protocol helpers."""

from __future__ import annotations

import json
from importlib import resources
from typing import TYPE_CHECKING

from jsonschema import validate

from showcov import __version__
from showcov.core.files import normalize_path

if TYPE_CHECKING:  # pragma: no cover
    from showcov.core import UncoveredSection
    from showcov.output.base import OutputMeta


def _get_schema() -> dict[str, object]:
    """Return the JSON schema for MCP payloads."""
    text = resources.files("showcov.data").joinpath("mcp_schema.json").read_text(encoding="utf-8")
    return json.loads(text)


def get_model_context(sections: list[UncoveredSection], meta: OutputMeta) -> dict:
    """Return a dictionary describing *sections* for LLM consumption."""
    context_lines = max(0, meta.context_lines)
    root = meta.coverage_xml.parent.resolve()
    xml_path = normalize_path(meta.coverage_xml, base=root)
    data: dict[str, object] = {
        "version": __version__,
        "environment": {
            "coverage_xml": xml_path.as_posix(),
            "context_lines": context_lines,
            "with_code": meta.with_code,
        },
        "sections": [
            sec.to_dict(with_code=meta.with_code, context_lines=context_lines, base=root) for sec in sections
        ],
    }
    return data


def generate_llm_payload(sections: list[UncoveredSection], meta: OutputMeta) -> str:
    """Return JSON payload for LLMs, validated against the MCP schema."""
    data = get_model_context(sections, meta)
    validate(data, _get_schema())
    return json.dumps(data, indent=2, sort_keys=True)


__all__ = ["generate_llm_payload", "get_model_context"]
