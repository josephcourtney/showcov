from pathlib import Path

from showcov.core import build_sections
from showcov.output import FORMATTERS


def _build_sections() -> list:
    src = Path("tests/data/sample.py")
    return build_sections({src: [2, 4, 5]})


def test_json_output_snapshot() -> None:
    sections = _build_sections()
    json_out = FORMATTERS["json"](
        sections,
        context_lines=1,
        with_code=True,
        coverage_xml=Path("coverage.xml"),
        color=False,
    )
    expected = Path("tests/snapshots/json_output.json").read_text(encoding="utf-8").rstrip("\n")
    assert json_out == expected


def test_llm_prompt_snapshot() -> None:
    sections = _build_sections()
    json_out = FORMATTERS["json"](
        sections,
        context_lines=1,
        with_code=True,
        coverage_xml=Path("coverage.xml"),
        color=False,
    )
    prompt = f"Please review the following coverage data and suggest tests:\n{json_out}\n"
    expected = Path("tests/snapshots/llm_prompt.txt").read_text(encoding="utf-8").rstrip("\n")
    assert prompt.rstrip("\n") == expected
