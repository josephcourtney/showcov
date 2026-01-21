from __future__ import annotations

import logging
from importlib.metadata import version

__version__ = version("showcov")

logger = logging.getLogger("showcov")

__all__ = ["__version__", "logger"]
