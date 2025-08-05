"""Output formatting utilities for showcov."""

from __future__ import annotations

from typing import TYPE_CHECKING

from showcov.core.files import normalize_path, read_file_lines

if TYPE_CHECKING:
    from showcov.core import UncoveredSection
    from showcov.output.base import OutputMeta


def format_markdown(sections: list[UncoveredSection], meta: OutputMeta) -> str:
    context_lines = max(0, meta.context_lines)
    parts: list[str] = []
    root = meta.coverage_xml.parent.resolve()
    for section in sections:
        rel = normalize_path(section.file, base=root)
        if meta.with_code:
            code_blocks: list[str] = []
            file_lines = read_file_lines(section.file)
            for start, end in section.ranges:
                start_idx = max(1, start - context_lines)
                end_idx = min(len(file_lines), end + context_lines)
                snippet_lines = []
                for i in range(start_idx, end_idx + 1):
                    code = file_lines[i - 1] if 1 <= i <= len(file_lines) else "<line not found>"
                    prefix = f"{i:4d}: " if meta.show_line_numbers else ""
                    snippet_lines.append(f"{prefix}{code}")
                snippet = "\n".join(snippet_lines)
                code_blocks.append(f"```python\n{snippet}\n```")
            details = "\n\n".join(code_blocks)
        else:
            details = "\n".join(f"lines {s}-{e}" if s != e else f"line {s}" for s, e in section.ranges)
        summary = f"Uncovered sections in {rel.as_posix()}" if meta.show_paths else "Uncovered sections"
        parts.append(f"<details>\n<summary>{summary}</summary>\n\n{details}\n</details>")
    return "\n\n".join(parts)
