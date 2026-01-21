from __future__ import annotations

from typing import TYPE_CHECKING

from defusedxml import ElementTree

from showcov.errors import InvalidCoverageXMLError

if TYPE_CHECKING:
    from pathlib import Path

    from showcov.coverage.types import ElementLike


def read_root(path: Path) -> ElementLike:
    """Parse coverage XML and return the root element.

    Accepts Cobertura-style reports, which typically use `<coverage>` as root.
    """
    root = ElementTree.parse(path).getroot()
    tag = (root.tag or "").split("}")[-1]  # tolerate namespaces
    if tag.lower() != "coverage":
        msg = f"unexpected root tag {root.tag!r} in {path}"
        raise InvalidCoverageXMLError(msg)
    return root


__all__ = ["read_root"]
