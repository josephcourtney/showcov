from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path


def _xml_escape(s: str) -> str:
    return (
        s
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def write_source_file(base: Path, rel: str, text: str) -> Path:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def write_cobertura_xml(
    base: Path,
    name: str = "coverage.xml",
    *,
    classes: list[dict[str, Any]],
    with_namespace: bool = False,
) -> Path:
    """
    Write a minimal Cobertura-style coverage.xml.

    classes item schema:
      {
        "filename": "pkg/mod.py" or "/abs/path/pkg/mod.py",
        "lines": [
            {
              "number": 1,
              "hits": 1,
              # optional branch info:
              "branch": True,
              "condition_coverage": "50% (1/2)",
              "missing_branches": "1,2",
              "conditions": [
                  {"number": 0, "type": "jump", "coverage": "100%"},
                  {"number": 1, "type": "jump", "coverage": "0%"},
              ],
            },
            ...
        ]
      }
    """
    root_open = (
        '<ns0:coverage xmlns:ns0="http://cobertura.sourceforge.net/xml/coverage-04.dtd">'
        if with_namespace
        else "<coverage>"
    )
    root_close = "</ns0:coverage>" if with_namespace else "</coverage>"

    parts: list[str] = []
    parts.extend(('<?xml version="1.0" ?>', root_open, "<packages>", '<package name="pkg">', "<classes>"))

    for idx, cls in enumerate(classes):
        filename = _xml_escape(str(cls["filename"]))
        parts.extend((f'<class name="C{idx}" filename="{filename}">', "<lines>"))

        for line in cls.get("lines", []):
            number = int(line["number"])
            hits = int(line["hits"])

            attrs: list[str] = [f'number="{number}"', f'hits="{hits}"']
            if line.get("branch") is True:
                attrs.append('branch="true"')
            elif line.get("branch") is False:
                attrs.append('branch="false"')

            if "condition_coverage" in line and line["condition_coverage"] is not None:
                attrs.append(f'condition-coverage="{_xml_escape(str(line["condition_coverage"]))}"')

            if "missing_branches" in line and line["missing_branches"] is not None:
                attrs.append(f'missing-branches="{_xml_escape(str(line["missing_branches"]))}"')

            conditions = line.get("conditions") or []
            if conditions:
                parts.extend((f"<line {' '.join(attrs)}>", "<conditions>"))
                for c in conditions:
                    cnum = int(c.get("number", -1))
                    ctype = _xml_escape(str(c.get("type", "jump")))
                    ccov = _xml_escape(str(c.get("coverage", "0%")))
                    parts.append(f'<condition number="{cnum}" type="{ctype}" coverage="{ccov}"/>')
                parts.extend(("</conditions>", "</line>"))
            else:
                parts.append(f"<line {' '.join(attrs)}/>")

        parts.extend(("</lines>", "</class>"))

    parts.extend(("</classes>", "</package>", "</packages>", root_close))

    xml = "\n".join(parts) + "\n"
    out = base / name
    out.write_text(xml, encoding="utf-8")
    return out


@pytest.fixture
def project(tmp_path: Path) -> dict[str, Path]:
    """A tiny “project” on disk with a couple of source files."""
    write_source_file(
        tmp_path,
        "pkg/mod.py",
        "# comment\ndef f(x):\n    if x:\n        return 1\n    return 0\n",
    )
    write_source_file(
        tmp_path,
        "pkg/other.py",
        "class C:\n    pass\n",
    )
    return {"root": tmp_path, "mod": tmp_path / "pkg/mod.py", "other": tmp_path / "pkg/other.py"}
