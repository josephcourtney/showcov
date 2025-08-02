import logging
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("showcov")
except PackageNotFoundError:  # pragma: no cover - fallback for src layout
    __version__ = "0.0.0"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


__all__ = ["__version__", "logger"]
