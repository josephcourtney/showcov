import json
from pathlib import Path

from jsonschema import validate

from showcov.core import UncoveredSection, build_sections
from showcov.mcp import generate_llm_payload, get_model_context
from showcov.output.base import OutputMeta


def _sections() -> list[UncoveredSection]:
    src = Path("tests/data/sample.py")
    return build_sections({src: [2, 4, 5]})


def _meta() -> OutputMeta:
    return OutputMeta(
        context_lines=1,
        with_code=True,
        coverage_xml=Path("coverage.xml"),
        color=False,
        show_paths=True,
        show_line_numbers=True,
    )


def test_llm_payload_snapshot() -> None:
    sections = _sections()
    payload = generate_llm_payload(sections, _meta())
    expected = Path("tests/snapshots/llm_interaction.json").read_text(encoding="utf-8")
    actual_data = json.loads(payload)
    expected_data = json.loads(expected)
    actual_data["version"] = "IGNORED"
    expected_data["version"] = "IGNORED"
    assert actual_data == expected_data


def test_round_trip_and_schema_validation() -> None:
    sections = _sections()
    payload = generate_llm_payload(sections, _meta())
    data = json.loads(payload)
    schema = json.loads(Path("src/showcov/data/mcp_schema.json").read_text(encoding="utf-8"))
    validate(data, schema)
    rebuilt = [UncoveredSection.from_dict(d) for d in data["sections"]]
    assert [(s.file.resolve(), s.ranges) for s in rebuilt] == [(s.file.resolve(), s.ranges) for s in sections]


def test_model_context_minimal_state() -> None:
    ctx = get_model_context(_sections(), _meta())
    assert set(ctx.keys()) == {"version", "environment", "sections"}
    assert set(ctx["environment"].keys()) == {"coverage_xml", "context_lines", "with_code"}
