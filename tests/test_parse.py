from __future__ import annotations

from typing import TYPE_CHECKING

from showcov.coverage.parse import iter_line_records, parse_condition_coverage, parse_conditions
from showcov.coverage.xml_reader import read_root

if TYPE_CHECKING:
    from pathlib import Path


def test_parse_condition_coverage() -> None:
    assert parse_condition_coverage("50% (1/2)") == (1, 2)
    assert parse_condition_coverage("  66 % ( 2 / 3 ) ") == (2, 3)
    assert parse_condition_coverage("") is None
    assert parse_condition_coverage("n/a") is None


def test_iter_line_records_and_conditions(project: dict[str, Path]) -> None:
    root_dir = project["root"]

    # Root tag with namespace to validate xml_reader's tolerant tag handling.
    from tests.conftest import write_cobertura_xml

    xml = write_cobertura_xml(
        root_dir,
        "coverage.xml",
        with_namespace=True,
        classes=[
            {
                "filename": "pkg/mod.py",
                "lines": [
                    {"number": 1, "hits": 1},
                    {
                        "number": 3,
                        "hits": 1,
                        "branch": True,
                        "condition_coverage": "50% (1/2)",
                        "missing_branches": "1",
                        "conditions": [
                            {"number": 0, "type": "jump", "coverage": "100%"},
                            {"number": 1, "type": "jump", "coverage": "0%"},
                        ],
                    },
                ],
            }
        ],
    )

    root = read_root(xml)
    recs = list(iter_line_records(root))
    assert len(recs) == 2

    br = next(r for r in recs if r.line == 3)
    assert br.branch_counts == (1, 2)
    assert br.missing_branches == (1,)

    # parse_conditions includes explicit conditions + a synthetic line aggregate (type="line")
    # missing branches are represented as conditions too (type="branch", coverage=None)
    conds = br.conditions
    assert any(c.type == "jump" and c.number == 0 and c.coverage == 100 for c in conds)
    assert any(c.type == "jump" and c.number == 1 and c.coverage == 0 for c in conds)
    assert any(c.type == "line" and c.number == -1 and c.coverage == 50 for c in conds)

    # Direct parse_conditions on the actual element path (smoke)
    cls = root.findall(".//class")[0]
    line_elem = cls.findall("./lines/line")[1]
    conds2 = parse_conditions(line_elem)
    assert conds2
