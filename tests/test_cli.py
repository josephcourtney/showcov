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
        embed_source=False,
        context_lines=0,
        coverage_xml=tmp_path / "cov.xml",
        color=True,
    )
    assert "\x1b" not in out
    data = json.loads(out)
    assert data["environment"] == {
        "coverage_xml": (tmp_path / "cov.xml").resolve().as_posix(),
        "context_lines": 0,
        "embed_source": False,
    }
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
    assert data["environment"] == {
        "coverage_xml": xml_file.resolve().as_posix(),
        "context_lines": 0,
        "embed_source": False,
    }
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
    assert data["environment"] == {
        "coverage_xml": xml_file.resolve().as_posix(),
        "context_lines": 0,
        "embed_source": False,
    }
    assert data["files"] == []


def test_main_json_output_embed_source(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture
) -> None:
    source_file = tmp_path / "dummy.py"
    source_file.write_text("a\nb\nc\n")
    xml_content = f"""
        <coverage>
          <packages>
            <package>
              <classes>
                <class filename=\"{source_file}\">
                  <lines>
                    <line number=\"2\" hits=\"0\"/>
                  </lines>
                </class>
              </classes>
            </package>
          </packages>
        </coverage>
    """
    xml_file = tmp_path / "coverage.xml"
    xml_file.write_text(xml_content)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prog",
            str(xml_file),
            "--format",
            "json",
            "--embed-source",
            "--context-lines",
            "1",
        ],
    )
    main()
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["environment"] == {
        "coverage_xml": xml_file.resolve().as_posix(),
        "context_lines": 1,
        "embed_source": True,
    }
    assert data["files"][0]["uncovered"][0]["source"] == [
        {"line": 1, "code": "a"},
        {"line": 2, "code": "b"},
        {"line": 3, "code": "c"},
    ]


def test_format_json_output_embed_source_with_context(tmp_path: Path) -> None:
    source_file = tmp_path / "dummy.py"
    source_file.write_text("a\nb\nc\n")
    sections = build_sections({source_file: [2]})
    out = format_json(
        sections,
        embed_source=True,
        context_lines=1,
        coverage_xml=tmp_path / "cov.xml",
        color=True,
    )
    data = json.loads(out)
    assert data["files"][0]["uncovered"][0]["source"] == [
        {"line": 1, "code": "a"},
        {"line": 2, "code": "b"},
        {"line": 3, "code": "c"},
    ]


def test_json_schema_validation(tmp_path: Path, capsys: CaptureFixture) -> None:
    source_file = tmp_path / "dummy.py"
    source_file.write_text("print('hi')\n")
    sections = build_sections({source_file: [1]})
    out = format_json(
        sections,
        embed_source=True,
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
        embed_source=False,
        context_lines=0,
        coverage_xml=Path("cov.xml"),
        color=True,
    )
    data = json.loads(out)
    assert data["files"][0]["file"] == "dummy.py"
