from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from showcov.adapters.render.human import render_human

if TYPE_CHECKING:
    from showcov.model.report import Report


@dataclass(frozen=True, slots=True)
class RenderOptions:
    """Options that affect *presentation* only (not report content).

    Notes
    -----
    - Content decisions (which sections exist, whether snippets exist, etc.)
      come from the Report itself (report.sections / report.meta.options).
    """

    color: bool = True
    show_paths: bool = True
    show_line_numbers: bool = True
    is_tty: bool = False
    # Summary presentation controls
    show_covered: bool = False
    summary_group: bool = True
    summary_group_depth: int = 2


def render(report: Report, *, fmt: str, options: RenderOptions) -> str:
    """Render a typed Report to text.

    Parameters
    ----------
    report:
        Built report model.
    fmt:
        One of: "human".
    options:
        Presentation options (color/tty/path display).
    """
    f = (fmt or "").strip().lower()

    if f == "human":
        return render_human(report, options)
    msg = f"Unsupported format: {fmt!r}. Expected one of: human."
    raise ValueError(msg)


__all__ = ["RenderOptions", "render"]
