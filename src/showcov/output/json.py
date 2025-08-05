from __future__ import annotations

import json
from typing import TYPE_CHECKING

from jsonschema import validate

from showcov import __version__
from showcov.core import get_schema
from showcov.core.files import normalize_path, read_file_lines

if TYPE_CHECKING:
    from showcov.core import UncoveredSection
    from showcov.output.base import OutputMeta


def format_json(
    sections: list[UncoveredSection],
    meta: OutputMeta,
    *,
    aggregate_stats: bool = False,
    file_stats: bool = False,
) -> str:
    context_lines = max(0, meta.context_lines)
    xml_path = normalize_path(meta.coverage_xml)
    files = [
        sec.to_dict(
            with_code=meta.with_code,
            context_lines=context_lines,
            base=meta.coverage_xml.parent,
            show_file=meta.show_paths,
            show_line_numbers=meta.show_line_numbers,
        )
        for sec in sections
    ]
    if file_stats:
        for sec_dict, sec in zip(files, sections, strict=False):
            uncovered = sum(end - start + 1 for start, end in sec.ranges)
            total_lines = len(read_file_lines(sec.file))
            sec_dict["counts"] = {"uncovered": uncovered, "total": total_lines}
    data: dict[str, object] = {
        "version": __version__,
        "environment": {
            "coverage_xml": xml_path.as_posix(),
            "context_lines": context_lines,
            "with_code": meta.with_code,
        },
        "files": files,
    }
    if aggregate_stats:
        total_uncovered = sum(end - start + 1 for sec in sections for start, end in sec.ranges)
        data["summary"] = {"uncovered": total_uncovered}
    validate(data, get_schema())
    return json.dumps(data, indent=2, sort_keys=True)
