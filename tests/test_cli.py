import json
import sys
from importlib import resources
from pathlib import Path

import pytest
from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch
from jsonschema import ValidationError, validate

from showcov import __version__
from showcov.cli import main
from showcov.core import build_sections
from showcov.output import format_json


def test_format_json_output(tmp_path: Path) -> None:
    source_file = tmp_path / "dummy.py"
    source_file.write_text("print('hi')\n")
    sections = build_sections({source_file: [1, 2, 4]})
    out = format_json(
        sections,
        with_code=False,
        context_lines=0,
        coverage_xml=tmp_path / "cov.xml",
        color=True,
    )
    assert "\x1b" not in out
    data = json.loads(out)
    assert data["environment"]["coverage_xml"] == (tmp_path / "cov.xml").resolve().as_posix()
    assert data["files"][0]["file"] == source_file.resolve().as_posix()
    assert data["files"][0]["uncovered"] == [
        {"start": 1, "end": 2},
        {"start": 4, "end": 4},
    ]


def test_main_json_output(tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture) -> None:
    source_file = tmp_path / "dummy.py"
    source_file.write_text("print('hi')\n")
    xml_content = f"""
        <coverage>
          <packages>
            <package>
              <classes>
                <class filename=\"{source_file}\">
                  <lines>
                    <line number=\"1\" hits=\"0\"/>
                  </lines>
                </class>
              </classes>
            </package>
          </packages>
        </coverage>
    """
    xml_file = tmp_path / "coverage.xml"
    xml_file.write_text(xml_content)
    monkeypatch.setattr(sys, "argv", ["prog", str(xml_file), "--format", "json"])
    main()
    captured = capsys.readouterr().out
    assert "\x1b" not in captured
    data = json.loads(captured)
    assert data["environment"]["coverage_xml"] == xml_file.resolve().as_posix()
    assert data["files"][0]["file"] == source_file.resolve().as_posix()
    assert data["files"][0]["uncovered"] == [{"start": 1, "end": 1}]


def test_main_json_output_no_uncovered(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture
) -> None:
    xml_content = """
        <coverage>
          <packages>
            <package>
              <classes>
                <class filename=\"dummy.py\">
                  <lines>
                    <line number=\"1\" hits=\"1\"/>
                  </lines>
                </class>
              </classes>
            </package>
          </packages>
        </coverage>
    """
    xml_file = tmp_path / "coverage.xml"
    xml_file.write_text(xml_content)
    monkeypatch.setattr(sys, "argv", ["prog", str(xml_file), "--format", "json"])
    main()
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["environment"]["coverage_xml"] == xml_file.resolve().as_posix()
    assert data["files"] == []


def test_format_json_output_with_code_and_context(tmp_path: Path) -> None:
    source_file = tmp_path / "dummy.py"
    source_file.write_text("a\nb\nc\n")
    sections = build_sections({source_file: [2]})
    out = format_json(
        sections,
        with_code=True,
        context_lines=1,
        coverage_xml=tmp_path / "cov.xml",
        color=True,
    )
    data = json.loads(out)
    assert data["files"][0]["uncovered"][0]["lines"] == ["a", "b", "c"]


def test_json_schema_validation(tmp_path: Path, capsys: CaptureFixture) -> None:
    source_file = tmp_path / "dummy.py"
    source_file.write_text("print('hi')\n")
    sections = build_sections({source_file: [1]})
    out = format_json(
        sections,
        with_code=True,
        context_lines=0,
        coverage_xml=tmp_path / "cov.xml",
        color=True,
    )
    data = json.loads(out)
    schema = json.loads(resources.files("showcov.data").joinpath("schema.json").read_text(encoding="utf-8"))
    validate(data, schema)
    bad = {"version": __version__, "files": [{"file": "x", "uncovered": [{"start": "a", "end": 2}]}]}
    with pytest.raises(ValidationError):
        validate(bad, schema)


def test_format_json_output_relative_path(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    source_file = Path("dummy.py")
    source_file.write_text("print('hi')\n", encoding="utf-8")
    sections = build_sections({source_file: [1]})
    out = format_json(
        sections,
        with_code=False,
        context_lines=0,
        coverage_xml=Path("cov.xml"),
        color=True,
    )
    data = json.loads(out)
    assert data["files"][0]["file"] == "dummy.py"
