from __future__ import annotations

from typing import TYPE_CHECKING

from showcov.adapters.coverage.input_kind import partition_inputs
from showcov.adapters.coverage.records import collect_cobertura_records
from showcov.adapters.coverage.sqlite_db import collect_coverage_db_records

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from showcov.model.records import Record


def collect_records(paths: Sequence[Path]) -> list[Record]:
    """Collect records from a mix of XML and Coverage.py sqlite inputs."""
    xml_paths, db_paths = partition_inputs(tuple(paths))
    out: list[Record] = []
    if xml_paths:
        out.extend(collect_cobertura_records(xml_paths))
    if db_paths:
        out.extend(collect_coverage_db_records(db_paths))
    return out


__all__ = ["collect_records"]
