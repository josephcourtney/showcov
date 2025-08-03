"""Tests for configuration helpers and module side-effect behavior."""

from __future__ import annotations

import importlib
import logging
import sys

import colorama


def test_get_schema_cached(monkeypatch):
    """``get_schema`` should load the schema once and cache the result."""
    from showcov import config

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
    monkeypatch.setattr(colorama, "init", fake_init)

    sys.modules.pop("showcov", None)
    sys.modules.pop("showcov.output", None)

    importlib.import_module("showcov.output")

    assert not basic_called
    assert not init_called
