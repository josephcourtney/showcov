"""Centralised exception hierarchy for showcov."""

from __future__ import annotations


class ShowcovError(Exception):
    """Base class for all custom showcov exceptions."""


class CoverageInputError(ShowcovError):
    """Base class for errors related to coverage inputs (XML or DB)."""


class CoverageInputNotFoundError(CoverageInputError):
    """Coverage input file could not be located on disk."""


class CoverageInputDataError(CoverageInputError):
    """Coverage input data is malformed or could not be parsed/read."""


class CoverageXMLError(ShowcovError):
    """Base class for errors related to coverage XML handling."""


class CoverageXMLNotFoundError(CoverageXMLError):
    """Coverage XML file could not be located on disk."""


class InvalidCoverageXMLError(CoverageXMLError):
    """Coverage XML file was found but does not contain a valid report."""


__all__ = [
    "CoverageInputDataError",
    "CoverageInputError",
    "CoverageInputNotFoundError",
    "CoverageXMLError",
    "CoverageXMLNotFoundError",
    "InvalidCoverageXMLError",
    "ShowcovError",
]
