"""Tests for configuration helpers and module side-effect behavior."""

from __future__ import annotations

import importlib
import logging
import sys
import textwrap
from typing import TYPE_CHECKING

from showcov.core.core import _get_xml_from_pyproject, get_config_xml_file

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch


def test_get_schema_cached(monkeypatch: MonkeyPatch) -> None:
    """``get_schema`` should load the schema once and cache the result."""
    from showcov.core import config

    config.get_schema.cache_clear()
    calls = 0
    original = config.resources.files

    def tracking_files(package: str):
        nonlocal calls
        calls += 1
        return original(package)

    monkeypatch.setattr(config.resources, "files", tracking_files)

    schema1 = config.get_schema()
    schema2 = config.get_schema()

    assert schema1 == schema2
    assert calls == 1


def test_import_has_no_side_effects(monkeypatch):
    """Importing the package should not configure logging or colorama."""
    basic_called = False
    init_called = False

    def fake_basic(*args, **kwargs):
        nonlocal basic_called
        basic_called = True

    def fake_init(*args, **kwargs):
        nonlocal init_called
        init_called = True

    monkeypatch.setattr(logging, "basicConfig", fake_basic)

    sys.modules.pop("showcov", None)
    sys.modules.pop("showcov.output", None)

    importlib.import_module("showcov.output")

    assert not basic_called
    assert not init_called


def test_get_xml_from_pyproject_valid(tmp_path: Path) -> None:
    py = tmp_path / "pyproject.toml"
    py.write_text(
        textwrap.dedent(
            """
            [tool.coverage.xml]
            output = ".coverage.xml"
            """
        ),
        encoding="utf-8",
    )
    assert _get_xml_from_pyproject(py) == ".coverage.xml"


def test_get_config_xml_file_uses_pyproject(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    # create a project with a pyproject specifying coverage xml
    py = tmp_path / "pyproject.toml"
    (tmp_path / ".coverage.xml").write_text("<coverage/>", encoding="utf-8")
    py.write_text(
        textwrap.dedent(
            """
            [tool.coverage.xml]
            output = ".coverage.xml"
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert get_config_xml_file() == ".coverage.xml"


def test_get_xml_from_pyproject_does_not_return_addopts_like_values(tmp_path: Path) -> None:
    py = tmp_path / "pyproject.toml"
    py.write_text(
        textwrap.dedent(
            """
            [tool.coverage]
            # no xml defined here; ensure function does not fall back to unrelated lists
            [tool.pytest.ini_options]
            addopts = ["-q"]
            """
        ),
        encoding="utf-8",
    )
    assert _get_xml_from_pyproject(py) is None
