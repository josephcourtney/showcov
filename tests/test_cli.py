import json
import sys
from pathlib import Path

from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from showcov.cli import main, print_json_output


def test_print_json_output(tmp_path: Path, capsys: CaptureFixture) -> None:
    source_file = tmp_path / "dummy.py"
    source_file.write_text("print('hi')\n")
    uncovered = {source_file: [1, 2, 4]}
    print_json_output(uncovered)
    captured = capsys.readouterr().out
    assert "\x1b" not in captured
    data = json.loads(captured)
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
    assert data["files"] == []
