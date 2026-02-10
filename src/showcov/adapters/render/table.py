from __future__ import annotations

import re
import sys
from io import StringIO
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence


from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

_PCT_RE = re.compile(r"^\s*(?P<num>\d+(?:\.\d+)?)\s*%\s*$")

_SRGB_UPPER_THRESHOLD = 0.04045
_SRGB_LOWER_THRESHOLD = 0.0031308
_FLAME_BLEND = 0.25
_FLAME_HALF = 0.5
_TWILIGHT_FG_LUMINANCE = 0.5
_FLAME_FG_LUMINANCE = 0.55


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else min(x, hi)


# --- OKLab utilities (Björn Ottosson) ---


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= _SRGB_UPPER_THRESHOLD else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    return 12.92 * c if c <= _SRGB_LOWER_THRESHOLD else 1.055 * (c ** (1 / 2.4)) - 0.055


def _oklab_to_srgb(lightness: float, a_val: float, b_val: float) -> tuple[int, int, int]:
    # OKLab → LMS
    lms_l = lightness + 0.3963377774 * a_val + 0.2158037573 * b_val
    lms_m = lightness - 0.1055613458 * a_val - 0.0638541728 * b_val
    lms_s = lightness - 0.0894841775 * a_val - 1.2914855480 * b_val

    l_cubed = lms_l**3
    m_cubed = lms_m**3
    s_cubed = lms_s**3

    # LMS → linear RGB
    r = +4.0767416621 * l_cubed - 3.3077115913 * m_cubed + 0.2309699292 * s_cubed
    g = -1.2684380046 * l_cubed + 2.6097574011 * m_cubed - 0.3413193965 * s_cubed
    b = -0.0041960863 * l_cubed - 0.7034186147 * m_cubed + 1.7076147010 * s_cubed

    # linear → sRGB
    r = _linear_to_srgb(_clamp(r))
    g = _linear_to_srgb(_clamp(g))
    b = _linear_to_srgb(_clamp(b))

    return int(r * 255), int(g * 255), int(b * 255)


def _luminance(r: int, g: int, b: int) -> float:
    r_lin, g_lin, b_lin = [_srgb_to_linear(v) for v in (r / 255, g / 255, b / 255)]
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def heat_style(pct: float | None, colormap: Literal["twilight", "flame"] = "twilight") -> Style:
    if colormap == "twilight":
        if pct is None:
            return Style(dim=True)

        t = _clamp(pct / 100.0)

        # --- perceptual design ---
        lightness = 0.78  # fixed lightness (key for contrast)
        a = -0.30 + 0.60 * t  # red → green
        b = 0.22 * (1 - abs(2 * t - 1))  # warm mid

        r, g, b = _oklab_to_srgb(lightness, a, b)
        lum = _luminance(r, g, b)

        fg = "black" if lum > _TWILIGHT_FG_LUMINANCE else "white"

    elif colormap == "flame":
        if pct is None:
            return Style(dim=True)
        t = _clamp(pct / 100.0)

        # red -> yellow -> green ramp
        if t < _FLAME_HALF:
            # red (255, 80, 80) to yellow (255, 210, 80)
            u = t / _FLAME_HALF
            r, g, b = 255, int(80 + u * (210 - 80)), 80
        else:
            # yellow (255, 210, 80) to green (80, 200, 120)
            u = (t - _FLAME_HALF) / _FLAME_HALF
            r, g, b = int(255 + u * (80 - 255)), int(210 + u * (200 - 210)), int(80 + u * (120 - 80))

        # mute background a bit (blend toward dark)
        blend = _FLAME_BLEND  # 0 = no mute, 1 = fully black
        r, g, b = int(r * (1 - blend)), int(g * (1 - blend)), int(b * (1 - blend))

        fg = "black" if _luminance(r, g, b) > _FLAME_FG_LUMINANCE else "white"
    else:
        msg = f"colormap must be 'twilight' or 'flame', not {colormap!r}"
        raise ValueError(msg)

    return Style(color=fg, bgcolor=_rgb_to_hex(r, g, b), bold=True)


def _header_text(parts: Sequence[str]) -> str:
    r"""Convert a grouped header tuple like ('Statements','Covered') to 'Statements\nCovered'."""
    items = [str(p) for p in parts if str(p).strip()]
    return "\n".join(items) if items else ""


def _maybe_style_percent_cell(value: object, *, enable: bool) -> object:
    """Style percentage cells when color/heatmap is enabled."""
    if not enable or isinstance(value, Text):
        return value

    s: str | None = value if isinstance(value, str) else None
    if s is None:
        return value

    s_strip = s.strip()
    if s_strip in {"—", "-"}:
        return Text(s_strip, style=heat_style(None))

    m = _PCT_RE.match(s_strip)
    if not m:
        return value

    try:
        pct = float(m.group("num"))
    except ValueError:
        return value

    return Text(s_strip, style=heat_style(pct))


def render_heatmap_scale(
    *,
    colormap: Literal["flame", "twilight"],
    color: bool = True,
) -> str:
    """Render a 0-100% test scale using heat_style."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("Percent", justify="right")
    table.add_column("Sample", justify="left")

    for p in range(0, 101, 5):
        pct_txt = Text(f"{p:3d}%", style=heat_style(float(p), colormap=colormap))
        table.add_row(f"{p:3d}%", pct_txt)

    return _render_table(table, color=color)


def _render_rich_table(
    headers: Sequence[Sequence[str]], rows: Sequence[Sequence[Any]], *, color: bool
) -> str:
    r"""Render a Rich table captured to a string."""
    table = Table(show_header=True, header_style="bold")
    for h in headers:
        table.add_column(_header_text(h), justify="right")

    # Heuristic: left-align first column (usually file path / label)
    if table.columns:
        table.columns[0].justify = "left"

    # Style only when color output is enabled.
    enable_heatmap = bool(color)

    for row in rows:
        cooked: list[Any] = [_maybe_style_percent_cell(cell, enable=enable_heatmap) for cell in row]
        table.add_row(*cooked)

    return _render_table(table, color=color)


def _render_table(table: Table, *, color: bool) -> str:
    buf = StringIO()
    console = Console(
        file=buf,
        force_terminal=color,
        width=sys.maxsize,
        color_system="standard" if color else None,
        no_color=not color,
    )
    console.print(table)
    return buf.getvalue().rstrip()


def format_table(
    headers: Sequence[Sequence[str]], rows: Sequence[Sequence[Any]], *, color: bool = True
) -> str:
    """Render a Rich table captured to text."""
    if not headers or not rows:
        return ""
    return _render_rich_table(headers, rows, color=color)


def render_table(table: Table, *, color: bool) -> str:
    return _render_table(table, color=color)


__all__ = ["format_table", "heat_style", "render_heatmap_scale", "render_table"]
