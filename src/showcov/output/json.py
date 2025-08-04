from __future__ import annotations

import json
from typing import TYPE_CHECKING

from jsonschema import validate

from showcov import __version__
from showcov.core import get_schema
from showcov.core.files import normalize_path

if TYPE_CHECKING:
    from showcov.core import UncoveredSection
    from showcov.output.base import OutputMeta


def format_json(sections: list[UncoveredSection], meta: OutputMeta) -> str:
    context_lines = max(0, meta.context_lines)
    xml_path = normalize_path(meta.coverage_xml)
    data: dict[str, object] = {
        "version": __version__,
        "environment": {
            "coverage_xml": xml_path.as_posix(),
            "context_lines": context_lines,
            "with_code": meta.with_code,
        },
        "files": [
            sec.to_dict(with_code=meta.with_code, context_lines=context_lines, base=meta.coverage_xml.parent)
            for sec in sections
        ],
    }
    validate(data, get_schema())
    return json.dumps(data, indent=2, sort_keys=True)
