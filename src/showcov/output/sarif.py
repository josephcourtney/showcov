from __future__ import annotations

import json
from typing import TYPE_CHECKING

from showcov import __version__

if TYPE_CHECKING:
    from showcov.core import UncoveredSection
    from showcov.output.base import OutputMeta


def format_sarif(sections: list[UncoveredSection], meta: OutputMeta) -> str:  # noqa: ARG001
    results: list[dict[str, object]] = []
    for section in sections:
        for start, end in section.ranges:
            results.append({
                "ruleId": "uncovered-code",
                "level": "note",
                "message": {"text": "Uncovered code"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": section.file.as_posix()},
                            "region": {"startLine": start, "endLine": end},
                        }
                    }
                ],
            })
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "showcov",
                        "semanticVersion": __version__,
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, indent=2, sort_keys=True)
