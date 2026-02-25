from __future__ import annotations

import math
import os
import re
import select
import sys
import termios
import time
import tty
from io import StringIO
from typing import TYPE_CHECKING, Any, Literal

import darkdetect
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from collections.abc import Sequence


_PCT_RE = re.compile(r"^\s*(?P<num>\d+(?:\.\d+)?)\s*%\s*$")

_SRGB_UPPER_THRESHOLD = 0.04045
_SRGB_LOWER_THRESHOLD = 0.0031308
_FLAME_BLEND = 0.25
_FLAME_HALF = 0.5
_LUMINANCE_THRESHOLD = 0.5
_BYTE_MAX = 255
_HEX_SHORT_LEN = 3
_HEX_LONG_LEN = 6
_LUMINANCE_MIDPOINT = 0.5

_NO_LINES = "No uncovered lines."
_NO_BRANCHES = "No uncovered branches."
_NO_SUMMARY = "No summary data."


_RGB_RE = re.compile(r"\x1b\]11;rgb:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)(?:\x07|\x1b\\)")


# ignore PLR0914 because the large number of local variables is caused by unpacking to improve readability
def query_terminal_bg_osc11(timeout: float = 0.15) -> tuple[int, int, int] | None:  # noqa: PLR0914
    """
    Best-effort query for terminal default background color using OSC 11.

    Returns (r,g,b) in 0..255, or None if unavailable / unsupported.

    Notes
    -----
      - Requires a real TTY.
      - Works on some terminals; may fail under tmux/screen unless configured.
      - POSIX only (uses termios/tty).
    """
    # Must be interactive
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None

    # Prefer /dev/tty so replies aren't lost when stdin is redirected.
    tty_path = "/dev/tty"
    try:
        fd = os.open(tty_path, os.O_RDWR | os.O_NOCTTY)
        close_fd = True
    except OSError:
        fd = sys.stdin.fileno()
        close_fd = False
        if not os.isatty(fd):
            return None

    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)

        # OSC 11 query: ESC ] 11 ; ? ST
        # Using ST (ESC \) is often more robust than BEL.
        os.write(fd, b"\x1b]11;?\x1b\\")
        # also try BEL if you want maximum compatibility:
        # os.write(fd, b"\x1b]11;?\x07")

        end = time.monotonic() + timeout
        buf = bytearray()

        while time.monotonic() < end:
            remaining = end - time.monotonic()
            r, _, _ = select.select([fd], [], [], max(0.0, remaining))
            if not r:
                break

            chunk = os.read(fd, 4096)
            if not chunk:
                break
            buf.extend(chunk)

            m = _RGB_RE.search(buf.decode("latin1", errors="ignore"))
            if m:
                r_s, g_s, b_s = m.groups()
                r_i, g_i, b_i = (int(x, 16) for x in (r_s, g_s, b_s))

                # Normalize: replies may be 8/12/16-bit-ish. Commonly:
                # - "rr/gg/bb" (8-bit) => <= 0xFF
                # - "rrrr/gggg/bbbb" (16-bit) => > 0xFF
                if max(r_i, g_i, b_i) > _BYTE_MAX:
                    r_i >>= 8
                    g_i >>= 8
                    b_i >>= 8

                return r_i, g_i, b_i

        return None

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if close_fd:
            os.close(fd)


def get_bg(
    force: Literal["dark", "light"] | None = None,
    dark_bg: tuple[int, int, int] = (49, 56, 61),
    light_bg: tuple[int, int, int] = (237, 230, 222),
) -> str:
    if force is None:
        bg = query_terminal_bg_osc11(timeout=0.15)
        if bg is None:
            bg = dark_bg if darkdetect.isDark() else light_bg
    elif force == "dark":
        bg = dark_bg
    elif force == "light":
        bg = light_bg

    return _rgb_to_hex(*bg)


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


def dimmest_text_over_contrast(
    bgcolor: str,
    *,
    min_contrast: float = 2.0,
) -> tuple[float, float]:
    bg_rgb = _parse_hex(bgcolor)
    bg_lum = _luminance(*bg_rgb)

    return (
        _clamp01(bg_lum * min_contrast),
        _clamp01(bg_lum / min_contrast),
    )


def scalar_to_text_style(
    value: float,
    bgcolor: str,
    *,
    min_contrast: float = 2.0,
) -> str:
    """
    Map a scalar in [0, 1] to a text color *lightness* (theme-aware) given a background color.

    - If bgcolor is dark: value=0 -> darker gray, value=1 -> near-white.
    - If bgcolor is light: value=0 -> mid gray, value=1 -> near-black.
    - Enforces a minimum WCAG contrast ratio by nudging lightness away from the bgcolor.

    Parameters
    ----------
    value:
        Scalar in [0, 1]. Values outside are clamped.
    bgcolor:
        Background color string in "#RRGGBB" or "#RGB".
    min_contrast:
        Minimum contrast ratio (WCAG). 2.0 is a common default for normal text.

    Returns
    -------
    Hex foreground color string suitable for Rich styles.
    """
    t = _clamp01(value)
    bg_rgb = _parse_hex(bgcolor)
    bg_lum = _luminance(*bg_rgb)
    bg_is_dark = bg_lum < _LUMINANCE_MIDPOINT
    l0_low, l0_high = dimmest_text_over_contrast(
        bgcolor=bgcolor,
        min_contrast=min_contrast,
    )
    l0 = l0_low if bg_is_dark else l0_high
    l1 = 1.0 if bg_is_dark else 0.0
    target_l = _lerp(l0, l1, t)

    rgb = _gray_from_lightness(target_l)

    return _rgb_to_hex(*rgb)


# ----------------- helpers -----------------


def _clamp01(x: float) -> float:
    return 0.0 if x <= 0.0 else 1.0 if x >= 1.0 else float(x)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _parse_hex(s: str) -> tuple[int, int, int]:
    s = s.strip()
    s = s.removeprefix("#")
    if len(s) == _HEX_SHORT_LEN:
        s = "".join(ch * 2 for ch in s)
    if len(s) != _HEX_LONG_LEN:
        msg = f"background must be '#RGB' or '#RRGGBB', got {s!r}"
        raise ValueError(msg)
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return r, g, b


def _gray_from_lightness(lightness: float) -> tuple[int, int, int]:
    # HSL with S=0 -> gray; RGB components all equal to L in linear-ish display space.
    # For simplicity and stability in terminals, treat l as sRGB channel value directly.
    v = round(_clamp01(lightness) * _BYTE_MAX)
    return v, v, v


def _srgb_to_linear(c: float) -> float:
    # c in [0,1]
    return c / 12.92 if c <= _SRGB_UPPER_THRESHOLD else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    # WCAG relative luminance for sRGB
    r8, g8, b8 = rgb
    r = _srgb_to_linear(r8 / _BYTE_MAX)
    g = _srgb_to_linear(g8 / _BYTE_MAX)
    b = _srgb_to_linear(b8 / _BYTE_MAX)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(l1: float, l2: float) -> float:
    # l1, l2 are relative luminances
    hi = max(l1, l2)
    lo = min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def gray(x):
    return _rgb_to_hex(
        *_oklab_to_srgb(x, 0, 0),
    )


def colormap(pct: float, lightness: float = 0.63) -> str:
    t = _clamp(pct / 100.0)
    theta = 3.95 * (1 - t) + 0.31 * t
    r = -0.30 * (1 - t) + -0.2 * t
    a = r * math.sin(theta)
    b = r * math.cos(theta)

    r, g, b = _oklab_to_srgb(lightness, a, b)
    return _rgb_to_hex(r, g, b)


def _header_text(parts: Sequence[str]) -> str:
    r"""Convert a grouped header tuple like ('Statements','Covered') to 'Statements\nCovered'."""
    items = [str(p) for p in parts if str(p).strip()]
    return "\n".join(items) if items else ""


def _render_rich_table(
    headers: Sequence[Sequence[str]],
    rows: Sequence[Sequence[Any]],
    footers: Sequence[object] | None,
    *,
    color: bool,
) -> str:
    r"""Render a Rich table captured to a string."""
    table = Table(
        show_header=True,
        header_style="bold",
        show_footer=True,
    )
    footer_cells: Sequence[object] = footers if footers is not None else ("",) * len(headers)
    for h, f in zip(headers, footer_cells, strict=True):
        table.add_column(_header_text(h), f, justify="right")

    if table.columns:
        table.columns[0].justify = "left"

    for row in rows:
        table.add_row(*row)

    return _render_table(table, color=color)


def _render_table(table: Table, *, color: bool) -> str:
    buf = StringIO()
    console = Console(
        file=buf,
        force_terminal=color,
        width=sys.maxsize,
        no_color=not color,
    )
    console.print(table)
    return buf.getvalue().rstrip()


def format_table(
    headers: Sequence[Sequence[str]],
    rows: Sequence[Sequence[Any]],
    footers: Sequence[object] | None = None,
    *,
    color: bool = True,
) -> str:
    """Render a Rich table captured to text."""
    if not headers or not rows:
        return ""
    return _render_rich_table(headers, rows, footers, color=color)


def render_table(table: Table, *, color: bool) -> str:
    return _render_table(table, color=color)


def render_heatmap_scale(
    *,
    color: bool = True,
) -> str:
    """Render a 0-100% test scale using colormap."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("Percent", justify="right")
    table.add_column("Sample", justify="left")
    table.add_column("Brightness\nLight", justify="left")
    table.add_column("Brightness\nDark", justify="left")
    table.add_column("Brightness\nAuto", justify="left")

    bg_dark = get_bg(force="dark")
    bg_light = get_bg(force="light")
    bg_auto = get_bg()

    for p in range(0, 101, 5):
        pct_txt = f"{p:3d}%"
        table.add_row(
            f"{p:3d}%",
            Text(
                pct_txt,
                style=Style(
                    color=colormap(float(p)),
                    dim=False,
                    bold=True,
                ),
            ),
            Text(
                pct_txt,
                style=Style(
                    color=scalar_to_text_style(p / 100, bgcolor=bg_light),
                    bold=True,
                    bgcolor=bg_light,
                ),
            ),
            Text(
                pct_txt,
                style=Style(
                    color=scalar_to_text_style(p / 100, bgcolor=bg_dark),
                    bold=True,
                    bgcolor=bg_dark,
                ),
            ),
            Text(
                pct_txt,
                style=Style(
                    color=scalar_to_text_style(p / 100, bgcolor=bg_auto),
                    bold=True,
                ),
            ),
        )

    buf = StringIO()
    console = Console(
        file=buf,
        force_terminal=color,
        width=sys.maxsize,
        no_color=not color,
    )
    console.print(table)
    return buf.getvalue().rstrip()


__all__ = ["colormap", "format_table", "render_heatmap_scale", "render_table", "scalar_to_text_style"]
