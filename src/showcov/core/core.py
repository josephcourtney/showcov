"""Core helpers for working with coverage XML inputs.

Utilities in this module are shared across the unified ``showcov`` pipeline: they resolve the
coverage XML configured for a project, build structured uncovered sections, and normalise file
paths in a deterministic way.
"""

from __future__ import annotations

import operator
import tomllib
from configparser import ConfigParser
from configparser import Error as ConfigError
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from more_itertools import consecutive_groups

from showcov import logger
from showcov.core.exceptions import CoverageXMLNotFoundError
from showcov.core.files import detect_line_tag, normalize_path, read_file_lines

if TYPE_CHECKING:
    from types import SimpleNamespace

    from showcov.core.types import FilePath, LineRange


def _determine_context_offsets(
    context_lines: int | None,
    context_before: int | None,
    context_after: int | None,
) -> tuple[int, int]:
    if context_lines is not None and (context_before is not None or context_after is not None):
        msg = "context_lines cannot be combined with context_before/context_after"
        raise ValueError(msg)

    if context_lines is not None:
        if context_lines < 0:
            msg = "context_lines must be non-negative"
            raise ValueError(msg)
        before = after = context_lines
    else:
        before = context_before or 0
        after = context_after or 0

    if before < 0 or after < 0:
        msg = "context offsets must be non-negative"
        raise ValueError(msg)
    return before, after


@dataclass(slots=True)
class UncoveredSection:
    """Structured representation of uncovered code for a single file.

    Parameters
    ----------
    file:
        Path to the source file.
    ranges:
        List of ``(start, end)`` tuples representing uncovered line ranges.
    """

    file: FilePath
    ranges: list[LineRange]

    def to_dict(
        self,
        *,
        with_code: bool = False,
        context_lines: int | None = None,
        context_before: int | None = None,
        context_after: int | None = None,
        base: Path | None = None,
        show_file: bool = True,
        show_line_numbers: bool = True,
    ) -> dict[str, object]:
        """Convert the section into a JSON-serialisable dictionary.

        Parameters
        ----------
        with_code:
            Include raw source lines within each uncovered range. When
            ``context_lines`` is greater than zero, the returned lines will
            also include that many lines of surrounding context.
        context_lines:
            Number of context lines to include before and after each uncovered
            range when ``with_code`` is ``True``.
        """
        before, after = _determine_context_offsets(context_lines, context_before, context_after)

        file_str = normalize_path(self.file, base=base).as_posix()

        uncovered_entries: list[dict[str, object]] = []

        file_lines: list[str] = read_file_lines(self.file) if with_code else []

        for start, end in self.ranges:
            entry: dict[str, object] = {"start": start, "end": end}
            if with_code and file_lines:
                start_idx = max(1, start - before)
                end_idx = min(len(file_lines), end + after)
                source = []
                for i in range(start_idx, end_idx + 1):
                    code = file_lines[i - 1] if 1 <= i <= len(file_lines) else "<line not found>"
                    tag = detect_line_tag(file_lines, i - 1) if 1 <= i <= len(file_lines) else None
                    line_entry: dict[str, object] = {"code": code}
                    if show_line_numbers:
                        line_entry["line"] = i
                    if tag:
                        line_entry["tag"] = tag
                    source.append(line_entry)
                entry["source"] = source
            uncovered_entries.append(entry)
        out: dict[str, object] = {"uncovered": uncovered_entries}
        if show_file:
            out["file"] = file_str
        return out

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> UncoveredSection:
        """Create an :class:`UncoveredSection` from a dictionary."""
        file = Path(str(data["file"]))
        items = cast("list[dict[str, object]]", data.get("uncovered", []))
        ranges = [(int(item["start"]), int(item["end"])) for item in items]
        return cls(file.resolve(), ranges)


def _get_xml_from_config(config_path: Path, section: str, option: str) -> str | None:
    """Extract an XML path from the configuration file."""
    config = ConfigParser()
    try:
        config.read(config_path)
    except (OSError, ConfigError, ValueError) as e:
        logger.warning("Failed to parse %s: %s", config_path, e)
        return None

    return (
        config.get(section, option)
        if config.has_section(section) and config.has_option(section, option)
        else None
    )


def _get_xml_from_pyproject(pyproject: Path) -> str | None:
    """Extract the XML coverage file path from pyproject.toml."""
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        logger.warning("Failed to parse %s: %s", pyproject, e)
        return None

    tool = data.get("tool", {})
    coverage_cfg = tool.get("coverage", {})
    # Only return concrete coverage-XML paths; do NOT fall back to unrelated settings.
    xml = coverage_cfg.get("xml_report") or coverage_cfg.get("xml", {}).get("output")
    return xml if isinstance(xml, str) and xml.strip() else None


def get_config_xml_file() -> str | None:
    """Look for an XML filename in configuration files."""
    config_files = [
        (Path("./pyproject.toml").resolve(), _get_xml_from_pyproject),
        (Path("./.coveragerc").resolve(), lambda p: _get_xml_from_config(p, "xml", "output")),
        (Path("./setup.cfg").resolve(), lambda p: _get_xml_from_config(p, "coverage:xml", "output")),
    ]

    for path, extractor in config_files:
        if path.exists():
            xml_file = extractor(path)
            if xml_file:
                logger.info("Using coverage XML file from config: %s", xml_file)
                return xml_file

    return None


def determine_xml_file(xml_file: SimpleNamespace | str | None = None) -> Path:
    """Determine the coverage XML file path from arguments or config.

    Accepts either a SimpleNamespace with attribute `xml_file`, a raw path string, or ``None``.
    """
    # Normalize input: allow passing types.SimpleNamespace or raw string/None.
    if hasattr(xml_file, "xml_file"):
        xml_file = cast("str | None", xml_file.xml_file)

    if xml_file:
        path = Path(xml_file).resolve()
        if not path.is_file():
            msg = f"Coverage XML file not found: {path}"
            raise CoverageXMLNotFoundError(msg)
        return path

    # avoid circular import
    from showcov.core import get_config_xml_file as _get_config_xml_file  # noqa: PLC0415

    config_xml = _get_config_xml_file()
    if config_xml:
        path = Path(config_xml).resolve()
        if not path.is_file():
            msg = f"Coverage XML file not found: {path}"
            raise CoverageXMLNotFoundError(msg)
        return path

    msg = "No coverage XML file specified or found in configuration."
    raise CoverageXMLNotFoundError(msg)


def group_consecutive_numbers(numbers: list[int]) -> list[list[int]]:
    """Group consecutive numbers into sublists."""
    return [list(grp) for grp in consecutive_groups(numbers)]


def merge_blank_gap_groups(groups: list[list[int]], file_lines: list[str]) -> list[list[int]]:
    """Merge adjacent groups if the gap between them contains only blank lines."""
    if not groups:
        return groups

    merged: list[list[int]] = [groups[0]]
    for grp in groups[1:]:
        last_grp = merged[-1]
        gap_start = last_grp[-1] + 1
        gap_end = grp[0] - 1

        if gap_start <= gap_end and all(
            i - 1 < len(file_lines) and not file_lines[i - 1].strip() for i in range(gap_start, gap_end + 1)
        ):
            merged[-1].extend(grp)
        else:
            merged.append(grp)

    return merged


def build_sections(uncovered: dict[Path, list[int]]) -> list[UncoveredSection]:
    """Convert mapping of uncovered line numbers to structured sections."""
    sections: list[UncoveredSection] = []
    for filename in sorted(uncovered.keys(), key=lambda p: p.as_posix()):
        lines_sorted = sorted(uncovered[filename])
        groups = group_consecutive_numbers(lines_sorted)
        file_lines = read_file_lines(filename)
        if file_lines:
            groups = merge_blank_gap_groups(groups, file_lines)
        ranges = [(grp[0], grp[-1]) for grp in sorted(groups, key=operator.itemgetter(0))]
        sections.append(UncoveredSection(filename, ranges))
    return sections
