import logging
from importlib import import_module
from importlib.metadata import version

__version__ = version("showcov")

logger = logging.getLogger(__name__)

cli = import_module("showcov.cli")
core = import_module("showcov.core")

__all__ = ["__version__", "cli", "core", "logger"]
