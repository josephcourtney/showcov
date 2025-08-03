import json
from pathlib import Path

from showcov.core import build_sections
from showcov.output import FORMATTERS, Format, OutputMeta


def _build_sections() -> list:
    src = Path("tests/data/sample.py")
    return build_sections({src: [2, 4, 5]})


def test_json_output_snapshot() -> None:
    sections = _build_sections()
    meta = OutputMeta(
        context_lines=1,
        with_code=True,
        coverage_xml=Path("coverage.xml"),
        color=False,
    )
    json_out = FORMATTERS[Format.JSON](sections, meta)
    expected_text = Path("tests/snapshots/json_output.json").read_text(encoding="utf-8")
    actual = json.loads(json_out)
    expected = json.loads(expected_text)

    actual["version"] = "IGNORED"
    expected["version"] = "IGNORED"

    assert actual == expected


def test_llm_prompt_snapshot() -> None:
    sections = _build_sections()
    meta = OutputMeta(
        context_lines=1,
        with_code=True,
        coverage_xml=Path("coverage.xml"),
        color=False,
    )
    json_out = FORMATTERS[Format.JSON](sections, meta)
    data = json.loads(json_out)
    data["version"] = "IGNORED"
    prompt = (
        "Please review the following coverage data and suggest tests:\n"
        f"{json.dumps(data, indent=2, sort_keys=True)}\n"
    )

    expected_text = Path("tests/snapshots/llm_prompt.txt").read_text(encoding="utf-8")
    expected_data = json.loads(expected_text.split(":\n", 1)[1])
    expected_data["version"] = "IGNORED"
    expected_prompt = (
        "Please review the following coverage data and suggest tests:\n"
        f"{json.dumps(expected_data, indent=2, sort_keys=True)}\n"
    )

    assert prompt.rstrip("\n") == expected_prompt.rstrip("\n")
