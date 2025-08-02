import argparse
import logging
import sys
import textwrap
from configparser import ConfigParser
from pathlib import Path

import pytest
from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch
from defusedxml import ElementTree

from showcov.cli import (
    disable_colors,
    main,
    parse_args,
    print_uncovered_sections,
)

# Import functions and exceptions from your module.
from showcov.core import (
    CoverageXMLNotFoundError,
    _get_xml_from_config,
    _get_xml_from_pyproject,
    determine_xml_file,
    gather_uncovered_lines,
    get_config_xml_file,
    group_consecutive_numbers,
    merge_blank_gap_groups,
    parse_large_xml,
)

# Set logging level to capture output for tests
logging.basicConfig(level=logging.INFO)


# --- Tests for `_get_xml_from_config` ---


def test_get_xml_from_config_success(tmp_path: Path) -> None:
    config_file = tmp_path / "config.ini"
    config_file.write_text("[section]\noption = value")
    assert _get_xml_from_config(config_file, "section", "option") == "value"


def test_get_xml_from_config_no_section(tmp_path: Path) -> None:
    config_file = tmp_path / "config.ini"
    config_file.write_text("[other_section]\noption = value")
    assert _get_xml_from_config(config_file, "section", "option") is None


def test_get_xml_from_config_no_option(tmp_path: Path) -> None:
    config_file = tmp_path / "config.ini"
    config_file.write_text("[section]\nother_option = value")
    assert _get_xml_from_config(config_file, "section", "option") is None


# --- Tests for `get_config_xml_file` ---


def test_get_config_xml_file_pyproject(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.coverage]\nxml_report = 'coverage.xml'")
    monkeypatch.chdir(tmp_path)
    assert get_config_xml_file() == "coverage.xml"


# --- Tests for `determine_xml_file` ---


def test_determine_xml_file_argument(monkeypatch: MonkeyPatch) -> None:
    test_args = ["prog", "coverage.xml"]
    monkeypatch.setattr(sys, "argv", test_args)
    assert determine_xml_file(argparse.Namespace(xml_file="coverage.xml")) == Path("coverage.xml")


def test_determine_xml_file_from_config(monkeypatch: MonkeyPatch) -> None:
    test_args = ["prog"]
    monkeypatch.setattr(sys, "argv", test_args)
    monkeypatch.setattr("showcov.core.get_config_xml_file", lambda: "coverage.xml")
    assert determine_xml_file(argparse.Namespace(xml_file="coverage.xml")) == Path("coverage.xml")


def test_determine_xml_file_no_args(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["prog"])
    monkeypatch.setattr("showcov.core.get_config_xml_file", lambda: None)
    with pytest.raises(CoverageXMLNotFoundError, match="No coverage XML file specified"):
        determine_xml_file(xml_file=None)


# --- Tests for `parse_args` ---


def test_parse_args_no_file(monkeypatch: MonkeyPatch) -> None:
    test_args = ["prog"]
    monkeypatch.setattr(sys, "argv", test_args)
    args = parse_args()
    assert args.xml_file is None
    assert args.no_color is False


def test_parse_args_with_file(monkeypatch: MonkeyPatch) -> None:
    test_args = ["prog", "coverage.xml"]
    monkeypatch.setattr(sys, "argv", test_args)
    args = parse_args()
    assert args.xml_file == "coverage.xml"
    assert args.no_color is False


def test_parse_args_no_color_flag(monkeypatch: MonkeyPatch) -> None:
    test_args = ["prog", "--no-color"]
    monkeypatch.setattr(sys, "argv", test_args)
    args = parse_args()
    assert args.no_color is True


# --- Tests for `print_uncovered_sections` ---


def test_print_uncovered_sections(tmp_path: Path, capsys: CaptureFixture) -> None:
    source_file = tmp_path / "dummy.py"
    source_file.write_text("def foo():\n    pass\n\ndef bar():\n    return 42")
    uncovered = {source_file: [2, 4, 5]}
    print_uncovered_sections(uncovered)
    captured = capsys.readouterr().out
    assert "Uncovered sections in" in captured
    assert "Line" in captured
    assert "2" in captured
    assert "4" in captured
    assert "5" in captured


def test_print_uncovered_sections_no_color(tmp_path: Path, capsys: CaptureFixture) -> None:
    source_file = tmp_path / "dummy.py"
    source_file.write_text("print('hi')\n")
    uncovered = {source_file: [1]}
    disable_colors()
    print_uncovered_sections(uncovered)
    captured = capsys.readouterr().out
    assert "\x1b" not in captured


def test_print_uncovered_sections_sorted_files(tmp_path: Path, capsys: CaptureFixture) -> None:
    file_b = tmp_path / "b.py"
    file_a = tmp_path / "a.py"
    file_a.write_text("a=1\n")
    file_b.write_text("b=1\n")
    uncovered = {file_b: [1], file_a: [1]}
    print_uncovered_sections(uncovered)
    captured = capsys.readouterr().out
    first = captured.find(file_a.as_posix())
    second = captured.find(file_b.as_posix())
    assert first < second


# --- Tests for `gather_uncovered_lines` ---


def test_gather_uncovered_lines_invalid_hits() -> None:
    xml_content = textwrap.dedent("""
    <coverage>
      <packages>
        <package>
          <classes>
            <class filename="dummy.py">
              <lines>
                <line number="1" hits="notanumber"/>
                <line number="2" hits="0"/>
              </lines>
            </class>
          </classes>
        </package>
      </packages>
    </coverage>
    """)
    root = ElementTree.fromstring(xml_content)
    uncovered = gather_uncovered_lines(root)
    key = next(iter(uncovered))
    assert key.name == "dummy.py"
    assert uncovered[key] == [2]


# --- Tests for `parse_large_xml` ---


def test_parse_large_xml(tmp_path: Path) -> None:
    xml_content = textwrap.dedent("""
    <coverage>
      <packages>
        <package>
          <classes>
            <class filename="dummy.py">
              <lines>
                <line number="3" hits="0"/>
                <line number="5" hits="0"/>
              </lines>
            </class>
          </classes>
        </package>
      </packages>
    </coverage>
    """)
    xml_file = tmp_path / "coverage.xml"
    xml_file.write_text(xml_content)
    root = parse_large_xml(xml_file)
    assert root is not None
    uncovered = gather_uncovered_lines(root)
    key = next(iter(uncovered))
    assert key.name == "dummy.py"
    assert uncovered[key] == [3, 5]


def test_gather_uncovered_lines_resolves_paths(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    source_file = pkg / "dummy.py"
    source_file.write_text("print('hi')\n")
    xml_content = f"""
    <coverage>
      <sources>
        <source>{tmp_path}</source>
      </sources>
      <packages>
        <package>
          <classes>
            <class filename="pkg/dummy.py">
              <lines>
                <line number="1" hits="0"/>
              </lines>
            </class>
          </classes>
        </package>
      </packages>
    </coverage>
    """
    root = ElementTree.fromstring(xml_content)
    uncovered = gather_uncovered_lines(root)
    key = next(iter(uncovered))
    assert key.is_absolute()
    assert key.as_posix().endswith("pkg/dummy.py")


# --- Tests for `main()` ---


def test_main_no_uncovered(tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture) -> None:
    xml_content = textwrap.dedent("""
        <coverage>
          <packages>
            <package>
              <classes>
                <class filename="dummy.py">
                  <lines>
                    <line number="1" hits="1"/>
                    <line number="2" hits="1"/>
                  </lines>
                </class>
              </classes>
            </package>
          </packages>
        </coverage>
    """)
    xml_file = tmp_path / "coverage.xml"
    xml_file.write_text(xml_content)
    monkeypatch.setattr(sys, "argv", ["prog", str(xml_file)])
    main()
    captured = capsys.readouterr().out
    assert "No uncovered lines found!" in captured


def test_main_with_uncovered(tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture) -> None:
    source_file = tmp_path / "dummy.py"
    source_file.write_text("def foo():\n    pass\n\ndef bar():\n    return 42")
    xml_content = f"""
        <coverage>
          <packages>
            <package>
              <classes>
                <class filename="{source_file}">
                  <lines>
                    <line number="2" hits="0"/>
                    <line number="4" hits="0"/>
                    <line number="5" hits="0"/>
                  </lines>
                </class>
              </classes>
            </package>
          </packages>
        </coverage>
    """
    xml_file = tmp_path / "coverage.xml"
    xml_file.write_text(xml_content)
    monkeypatch.setattr(sys, "argv", ["prog", str(xml_file)])
    main()
    captured = capsys.readouterr().out
    assert "Uncovered sections in" in captured
    assert "2" in captured
    assert "4" in captured
    assert "5" in captured


# --- Tests for _get_xml_from_config exception branch (lines 53-55) ---


def test_get_xml_from_config_exception(monkeypatch, tmp_path):
    config_file = tmp_path / "config.ini"
    config_file.write_text("some invalid content")

    # Force an exception when reading the config file so that the exception branch is taken.
    def fake_read(self, filenames, encoding=None):
        msg = "simulated error"
        raise OSError(msg)

    monkeypatch.setattr(ConfigParser, "read", fake_read)
    result = _get_xml_from_config(config_file, "section", "option")
    assert result is None


# --- Tests for _get_xml_from_pyproject exception branch (lines 69-71) ---


def test_get_xml_from_pyproject_exception(monkeypatch, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("invalid content")

    # Force an exception during tomllib.load to simulate a failure parsing the pyproject.toml.
    def fake_tomllib_load(f):
        msg = "simulated error"
        raise OSError(msg)

    monkeypatch.setattr("showcov.core.tomllib.load", fake_tomllib_load)
    result = _get_xml_from_pyproject(pyproject)
    assert result is None


# --- Test for get_config_xml_file fallback (line 93) ---


def test_get_config_xml_file_no_config(monkeypatch, tmp_path):
    # When no configuration file is present, get_config_xml_file should return None.
    # Change into an empty temporary directory.
    monkeypatch.chdir(tmp_path)
    result = get_config_xml_file()
    assert result is None


# --- Test for group_consecutive_numbers (line 136) ---


def test_group_consecutive_numbers():
    # Provide a list of numbers and verify that they are grouped into consecutive ranges.
    numbers = [1, 2, 3, 5, 6, 8]
    groups = group_consecutive_numbers(numbers)
    assert groups == [[1, 2, 3], [5, 6], [8]]


# --- Test for merge_blank_gap_groups branch (line 147) ---


def test_merge_blank_gap_groups_no_merge():
    # Provide two groups separated by a gap that contains non-blank content.
    #
    # In this case, the groups should not be merged.
    groups = [[1, 2], [4, 5]]
    # Simulate file lines where the gap (line 3) is not blank.
    file_lines = [
        "line 1\n",
        "line 2\n",
        "non blank line\n",  # line 3 (not blank)
        "line 4\n",
        "line 5\n",
    ]
    merged = merge_blank_gap_groups(groups, file_lines)
    assert merged == groups


# --- Test for print_uncovered_sections exception branch (lines 163-166, 171) ---


def test_print_uncovered_sections_file_open_error(monkeypatch, capsys, tmp_path):
    fake_file = tmp_path / "nonexistent.py"
    uncovered = {fake_file: [1, 2]}

    # Simulate an OSError when trying to open a source file. The function should catch the exception,
    # log the error, and still print the grouped line numbers.
    def fake_open(*args, **kwargs):
        msg = "simulated file open error"
        raise OSError(msg)

    # Monkey-patch the open() method on the Path object.
    monkeypatch.setattr(Path, "open", fake_open)
    print_uncovered_sections(uncovered)
    captured = capsys.readouterr().out
    assert "Uncovered sections in" in captured
    assert "Line" in captured


# --- Test for parse_large_xml fallback (line 218) ---


def test_parse_large_xml_no_coverage(tmp_path):
    # Provide an XML file that does not contain a <coverage> element. parse_large_xml should return None.
    xml_file = tmp_path / "bad.xml"
    xml_file.write_text("<root></root>")
    result = parse_large_xml(xml_file)
    assert result is None


# --- Tests for main() error-handling branches ---


def test_main_coverage_xml_not_found(monkeypatch):
    # Force determine_xml_file to throw CoverageXMLNotFoundError and verify that main() calls sys.exit(1).
    monkeypatch.setattr(sys, "argv", ["prog"])

    def fail(*_):
        msg = "No coverage XML file specified"
        raise CoverageXMLNotFoundError(msg)

    monkeypatch.setattr("showcov.core.determine_xml_file", fail)

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert isinstance(exc_info.value, SystemExit)
    assert exc_info.value.code == 1


def test_main_parse_error(monkeypatch):
    # Force parse_large_xml to raise an ElementTree.ParseError and verify that main() calls sys.exit(1).
    fake_path = Path("dummy.xml")
    monkeypatch.setattr(sys, "argv", ["prog"])
    monkeypatch.setattr("showcov.core.determine_xml_file", lambda _args: fake_path)

    def fake_parse_large_xml(_):
        msg = "simulated parse error"
        raise ElementTree.ParseError(msg)

    monkeypatch.setattr("showcov.core.parse_large_xml", fake_parse_large_xml)
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert isinstance(exc_info.value, SystemExit)
    assert exc_info.value.code == 1


def test_main_os_error(monkeypatch):
    # Force parse_large_xml to raise an OSError and verify that main() calls sys.exit(1).
    fake_path = Path("dummy.xml")
    monkeypatch.setattr(sys, "argv", ["prog"])
    monkeypatch.setattr("showcov.core.determine_xml_file", lambda _args: fake_path)

    def fake_parse_large_xml(_):
        msg = "simulated OS error"
        raise OSError(msg)

    monkeypatch.setattr("showcov.core.parse_large_xml", fake_parse_large_xml)
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert isinstance(exc_info.value, SystemExit)
    assert exc_info.value.code == 1
