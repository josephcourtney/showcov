from __future__ import annotations

from typing import TYPE_CHECKING

from showcov.inputs.cobertura import iter_line_records, read_root

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from showcov.core.build.records import Record


def collect_cobertura_records(paths: Sequence[Path]) -> list[Record]:
    out: list[Record] = []
    for p in paths:
        root = read_root(p)
        out.extend(
            (rec.file, rec.line, rec.hits, rec.branch_counts, rec.missing_branches, rec.conditions)
            for rec in iter_line_records(root)
        )
    return out
