import logging
from importlib.metadata import version

__version__ = version("showcov")

logger = logging.getLogger(__name__)


__all__ = ["__version__", "logger"]
