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
        code_blocks: list[str] = []
        file_lines = read_file_lines(section.file)
        for start, end in section.ranges:
            start_idx = max(1, start - context_lines)
            end_idx = min(len(file_lines), end + context_lines)
            snippet = "\n".join(
                f"{i:4d}: {file_lines[i - 1] if 1 <= i <= len(file_lines) else '<line not found>'}"
                for i in range(start_idx, end_idx + 1)
            )
            code_blocks.append(f"```python\n{snippet}\n```")
        details = "\n\n".join(code_blocks)
        parts.append(
            f"<details>\n<summary>Uncovered sections in {rel.as_posix()}</summary>\n\n{details}\n</details>"
        )
    return "\n\n".join(parts)
