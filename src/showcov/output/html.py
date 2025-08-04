from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

from showcov.core.files import normalize_path, read_file_lines

if TYPE_CHECKING:  # pragma: no cover
    from showcov.core import UncoveredSection
    from showcov.output.base import OutputMeta


def format_html(sections: list[UncoveredSection], meta: OutputMeta) -> str:
    """Return an HTML report for *sections*."""
    context_lines = max(0, meta.context_lines)
    root = meta.coverage_xml.parent.resolve()
    parts: list[str] = ["<html>", "<body>"]
    for section in sections:
        rel = normalize_path(section.file, base=root)
        parts.append(f"<h2>{escape(rel.as_posix())}</h2>")
        file_lines: list[str] = read_file_lines(section.file) if meta.with_code else []
        for start, end in section.ranges:
            header = f"Lines {start}-{end}" if start != end else f"Line {start}"
            parts.append(f"<h3>{header}</h3>")
            if meta.with_code and file_lines:
                start_idx = max(1, start - context_lines)
                end_idx = min(len(file_lines), end + context_lines)
                snippet = []
                for ln in range(start_idx, end_idx + 1):
                    code = file_lines[ln - 1] if 1 <= ln <= len(file_lines) else "<line not found>"
                    snippet.append(f"{ln}: {code}")
                code_html = "<br/>".join(escape(line) for line in snippet)
                parts.append(f"<pre>{code_html}</pre>")
    parts.extend(("</body>", "</html>"))
    return "\n".join(parts)
