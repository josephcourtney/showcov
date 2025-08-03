import logging
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("showcov")
except PackageNotFoundError:  # pragma: no cover - fallback for src layout
    __version__ = "0.0.0"

logger = logging.getLogger(__name__)


def __getattr__(name: str) -> object:
    try:
        return import_module(f"{__name__}.{name}")
    except ModuleNotFoundError as e:  # pragma: no cover - defensive
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg) from e


__all__ = ["__version__", "logger"]
