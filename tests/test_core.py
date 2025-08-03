import logging
import sys
import types
from collections.abc import Callable
from configparser import ConfigParser
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch
from defusedxml import ElementTree

from showcov.cli import main

# Import functions and exceptions from your module.
from showcov.core import (
    CoverageXMLNotFoundError,
    _get_xml_from_config,
    _get_xml_from_pyproject,
    _read_file_lines,
    build_sections,
    determine_xml_file,
    gather_uncovered_lines,
    gather_uncovered_lines_from_xml,
    get_config_xml_file,
    group_consecutive_numbers,
    merge_blank_gap_groups,
    parse_large_xml,
)
from showcov.output import OutputMeta, format_human

# Set logging level to capture output for tests
logging.basicConfig(level=logging.INFO)


# --- Tests for `_get_xml_from_config` ---


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("[section]\noption = value", "value"),
        ("[other_section]\noption = value", None),
        ("[section]\nother_option = value", None),
    ],
)
def test_get_xml_from_config_cases(tmp_path: Path, content: str, expected: str | None) -> None:
    config_file = tmp_path / "config.ini"
    config_file.write_text(content)
    assert _get_xml_from_config(config_file, "section", "option") == expected


# --- Tests for `get_config_xml_file` ---


def test_get_config_xml_file_pyproject(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.coverage]\nxml_report = 'coverage.xml'")
    monkeypatch.chdir(tmp_path)
    assert get_config_xml_file() == "coverage.xml"


# --- Tests for `determine_xml_file` ---


def test_determine_xml_file_argument(
    monkeypatch: MonkeyPatch, coverage_xml_file: Callable[..., Path]
) -> None:
    xml = coverage_xml_file({})
    test_args = ["prog", str(xml)]
    monkeypatch.setattr(sys, "argv", test_args)

    ns = types.SimpleNamespace(xml_file=str(xml))
    assert determine_xml_file(ns) == xml.resolve()


def test_determine_xml_file_from_config(
    monkeypatch: MonkeyPatch, coverage_xml_file: Callable[..., Path]
) -> None:
    xml = coverage_xml_file({})
    test_args = ["prog"]
    monkeypatch.setattr(sys, "argv", test_args)
    monkeypatch.setattr("showcov.core.get_config_xml_file", lambda: str(xml))
    ns = types.SimpleNamespace(xml_file=None)
    assert determine_xml_file(ns) == xml.resolve()


def test_determine_xml_file_no_args(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["prog"])
    monkeypatch.setattr("showcov.core.get_config_xml_file", lambda: None)
    with pytest.raises(CoverageXMLNotFoundError, match="No coverage XML file specified"):
        determine_xml_file(xml_file=None)


# --- Tests for `print_uncovered_sections` ---


@pytest.mark.parametrize("color", [True, False])
def test_format_human(tmp_path: Path, *, color: bool) -> None:
    source_file = tmp_path / "dummy.py"
    source_file.write_text("def foo():\n    pass\n\ndef bar():\n    return 42")
    sections = build_sections({source_file: [2, 4, 5]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=color,
    )
    out = format_human(sections, meta)
    assert "Uncovered sections in" in out
    assert "Line" in out
    assert "2" in out
    assert "4" in out
    assert "5" in out
    assert ("\x1b" in out) is color


def test_format_human_sorted_files(tmp_path: Path) -> None:
    file_b = tmp_path / "b.py"
    file_a = tmp_path / "a.py"
    file_a.write_text("a=1\n")
    file_b.write_text("b=1\n")
    sections = build_sections({file_b: [1], file_a: [1]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=True,
    )
    out = format_human(sections, meta)
    first = out.find(file_a.as_posix())
    second = out.find(file_b.as_posix())
    assert first < second


# --- Tests for `gather_uncovered_lines` ---


def test_gather_uncovered_lines_invalid_hits(coverage_xml_content: Callable[..., str]) -> None:
    xml_content = coverage_xml_content({"dummy.py": {1: "notanumber", 2: 0}})
    root = ElementTree.fromstring(xml_content)
    uncovered = gather_uncovered_lines(root)
    key = next(iter(uncovered))
    assert key.name == "dummy.py"
    assert uncovered[key] == [2]


# --- Tests for `parse_large_xml` ---


def test_parse_large_xml(coverage_xml_file: Callable[..., Path]) -> None:
    xml_file = coverage_xml_file({"dummy.py": [3, 5]})
    root = parse_large_xml(xml_file)
    assert root is not None
    uncovered = gather_uncovered_lines(root)
    key = next(iter(uncovered))
    assert key.name == "dummy.py"
    assert uncovered[key] == [3, 5]


def test_gather_uncovered_lines_resolves_paths(
    tmp_path: Path, coverage_xml_content: Callable[..., str]
) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    source_file = pkg / "dummy.py"
    source_file.write_text("print('hi')\n")
    xml_content = coverage_xml_content({"pkg/dummy.py": [1]}, sources=tmp_path)
    root = ElementTree.fromstring(xml_content)
    uncovered = gather_uncovered_lines(root)
    key = next(iter(uncovered))
    assert key.is_absolute()
    assert key.as_posix().endswith("pkg/dummy.py")


def test_gather_uncovered_lines_from_xml(tmp_path: Path, coverage_xml_file: Callable[..., Path]) -> None:
    src = tmp_path / "dummy.py"
    src.write_text("print('hi')\n")
    xml_file = coverage_xml_file({src: [1]})
    uncovered = gather_uncovered_lines_from_xml(xml_file)
    key = next(iter(uncovered))
    assert key == src.resolve()
    assert uncovered[key] == [1]


def test_read_file_lines_handles_unicode_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_bytes(b"\xff\xfe")
    _read_file_lines.cache_clear()
    assert _read_file_lines(bad) == []


def test_read_file_lines_caches(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    file = tmp_path / "a.py"
    file.write_text("print(1)\n")
    _read_file_lines.cache_clear()
    assert _read_file_lines(file) == ["print(1)"]

    def fail(*args, **kwargs):
        msg = "should not open file again"
        raise AssertionError(msg)

    monkeypatch.setattr(Path, "open", fail)
    assert _read_file_lines(file) == ["print(1)"]


def test_read_file_lines_cache_evicted(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    files = [tmp_path / f"{i}.py" for i in range(260)]
    for f in files:
        f.write_text("print(1)\n")
    _read_file_lines.cache_clear()
    first = files[0]

    open_count = 0
    orig_open = Path.open

    def wrapper(self, *args, **kwargs):
        nonlocal open_count
        if self == first:
            open_count += 1
        return orig_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", wrapper)
    assert _read_file_lines.cache_info().maxsize == 256
    assert _read_file_lines(first) == ["print(1)"]
    assert open_count == 1

    for f in files[1:]:
        _read_file_lines(f)

    assert _read_file_lines(first) == ["print(1)"]
    assert open_count == 2
    _read_file_lines.cache_clear()


# --- Tests for `main()` ---
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


def test_format_human_file_open_error(tmp_path: Path) -> None:
    fake_file = tmp_path / "nonexistent.py"
    sections = build_sections({fake_file: [1, 2]})
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=tmp_path / "cov.xml",
        color=True,
    )
    out = format_human(sections, meta)
    assert "Uncovered sections in" in out
    assert "Line" in out


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
    assert exc_info.value.code == 66


def test_main_parse_error(monkeypatch, tmp_path):
    # Force gather_uncovered_lines_from_xml to raise an ElementTree.ParseError and verify exit code 65.
    fake_path = tmp_path / "dummy.xml"
    fake_path.write_text("<coverage>", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["prog"])
    monkeypatch.setattr("showcov.cli.determine_xml_file", lambda _args: fake_path)

    def fake_gather(_):
        msg = "simulated parse error"
        raise ElementTree.ParseError(msg)

    monkeypatch.setattr("showcov.cli.gather_uncovered_lines_from_xml", fake_gather)
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert isinstance(exc_info.value, SystemExit)
    assert exc_info.value.code == 65


def test_main_os_error(monkeypatch, tmp_path):
    # Force gather_uncovered_lines_from_xml to raise an OSError and verify exit code 1.
    fake_path = tmp_path / "dummy.xml"
    fake_path.write_text("<coverage></coverage>", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["prog"])
    monkeypatch.setattr("showcov.cli.determine_xml_file", lambda _args: fake_path)

    def fake_gather(_):
        msg = "simulated OS error"
        raise OSError(msg)

    monkeypatch.setattr("showcov.cli.gather_uncovered_lines_from_xml", fake_gather)
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert isinstance(exc_info.value, SystemExit)
    assert exc_info.value.code == 1
