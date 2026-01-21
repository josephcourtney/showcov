"""Centralised exception hierarchy for showcov."""

from __future__ import annotations


class ShowcovError(Exception):
    """Base class for all custom showcov exceptions."""


class CoverageXMLError(ShowcovError):
    """Base class for errors related to coverage XML handling."""


class CoverageXMLNotFoundError(CoverageXMLError):
    """Coverage XML file could not be located on disk."""


class InvalidCoverageXMLError(CoverageXMLError):
    """Coverage XML file was found but does not contain a valid report."""


__all__ = [
    "CoverageXMLError",
    "CoverageXMLNotFoundError",
    "InvalidCoverageXMLError",
    "ShowcovError",
]
