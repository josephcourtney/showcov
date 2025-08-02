from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("showcov")
except PackageNotFoundError:  # pragma: no cover - fallback for src layout
    __version__ = "0.0.0"
