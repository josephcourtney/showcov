from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from jsonschema import validate

from showcov import __version__
from showcov.core import get_schema

if TYPE_CHECKING:
    from showcov.core import UncoveredSection
    from showcov.output.base import OutputMeta


def format_json(sections: list[UncoveredSection], meta: OutputMeta) -> str:
    context_lines = max(0, meta.context_lines)
    root = Path.cwd().resolve()
    try:
        xml_path = meta.coverage_xml.resolve().relative_to(root)
    except ValueError:
        xml_path = meta.coverage_xml.resolve()
    data: dict[str, object] = {
        "version": __version__,
        "environment": {
            "coverage_xml": xml_path.as_posix(),
            "context_lines": context_lines,
            "with_code": meta.with_code,
        },
        "files": [sec.to_dict(with_code=meta.with_code, context_lines=context_lines) for sec in sections],
    }
    validate(data, get_schema())
    return json.dumps(data, indent=2, sort_keys=True)
