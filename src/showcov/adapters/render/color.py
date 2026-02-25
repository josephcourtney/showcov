from __future__ import annotations

import math
import os
import re
import select
import sys
import termios
import time
import tty
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
from typing import TYPE_CHECKING, Literal

import darkdetect
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from collections.abc import Callable

_SRGB_UPPER_THRESHOLD = 0.04045
_SRGB_LOWER_THRESHOLD = 0.0031308
_HEX_SHORT_LEN = 3
_HEX_LONG_LEN = 6
_BYTE_MAX = 255
_LUMINANCE_MIDPOINT = 0.5


_RGB_RE = re.compile(r"\x1b\]11;rgb:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)(?:\x07|\x1b\\)")


@dataclass
class ColorBase:
    """Base class for all color representations."""


# ---------------------------------------------------------------------------
# Generic / device RGB-type spaces
# ---------------------------------------------------------------------------


@dataclass
class RGB(ColorBase):
    r: float
    g: float
    b: float


@dataclass
class SRGB(ColorBase):
    # gamma-encoded
    r: float
    g: float
    b: float

    def to_hex(self, length: int | None = None) -> str:
        length = length or _HEX_LONG_LEN
        r_i = round(_clamp(self.r) * _BYTE_MAX)
        g_i = round(_clamp(self.g) * _BYTE_MAX)
        b_i = round(_clamp(self.b) * _BYTE_MAX)
        if length == _HEX_LONG_LEN:
            return f"#{r_i:02x}{g_i:02x}{b_i:02x}"
        if length == _HEX_SHORT_LEN:
            return f"#{r_i >> 4:x}{g_i >> 4:x}{b_i >> 4:x}"
        msg = f"`length` must be either 3 or 6, not {length!r}"
        raise ValueError(msg)

    @classmethod
    def from_hex(cls, hex_color: str) -> SRGB:
        s = hex_color.strip().removeprefix("#")
        if len(s) == _HEX_SHORT_LEN:
            s = "".join(ch * 2 for ch in s)
        if len(s) != _HEX_LONG_LEN:
            msg = f"background must be '#RGB' or '#RRGGBB', got {s!r}"
            raise ValueError(msg)
        r = int(s[0:2], 16) / _BYTE_MAX
        g = int(s[2:4], 16) / _BYTE_MAX
        b = int(s[4:6], 16) / _BYTE_MAX
        return cls(r, g, b)

    def __str__(self) -> str:
        """Return the color as a #RRGGBB string."""
        return self.to_hex(length=_HEX_LONG_LEN)


@dataclass
class CIERGB(ColorBase):
    """Historic CIE RGB space (color-matching primaries)."""

    R: float
    G: float
    B: float


# ---------------------------------------------------------------------------
# Other simple component models
# ---------------------------------------------------------------------------


@dataclass
class CMYK(ColorBase):
    C: float
    M: float
    Y: float
    K: float


@dataclass
class HSL(ColorBase):
    """Hue-Saturation-Lightness from an RGB space."""

    H: float  # degrees, typically [0, 360)
    S: float  # [0, 1]
    L: float  # [0, 1]


@dataclass
class HSV(ColorBase):
    """Hue-Saturation-Value from an RGB space."""

    H: float  # degrees, typically [0, 360)
    S: float  # [0, 1]
    V: float  # [0, 1]


@dataclass
class RYB(ColorBase):
    """Red-Yellow-Blue artist's primaries."""

    R: float
    Y: float
    B: float


# ---------------------------------------------------------------------------
# Natural / notation-like systems
# ---------------------------------------------------------------------------


@dataclass
class Natural(ColorBase):
    """
    Placeholder for a 'Natural' system (e.g. NCS-like).

    Interpreted here as whiteness / blackness / chroma + hue.
    """

    whiteness: float
    blackness: float
    chroma: float
    hue: str  # e.g. 'Y90R', or some other notation


@dataclass
class Munsell(ColorBase):
    """
    Munsell notation: Hue - Value / Chroma, e.g. '5R 5/10'.

    Here split into (hue, value, chroma).
    """

    hue: str  # e.g. '5R', '10YR'
    value: float  # lightness-like, typically [0, 10]
    chroma: float  # radial distance from neutral, typically >= 0


# ---------------------------------------------------------------------------
# LMS / physiological-like
# ---------------------------------------------------------------------------


@dataclass
class LMS(ColorBase):
    """Cone-response-like coordinates."""

    L: float
    M: float
    S: float


# ---------------------------------------------------------------------------
# CIE XYZ / xyY variants
# ---------------------------------------------------------------------------


@dataclass
class CIEXYZ(ColorBase):
    """Generic CIE XYZ tristimulus values."""

    X: float
    Y: float
    Z: float


@dataclass
class CIE32XYZ(ColorBase):
    """CIE 1931 2° XYZ (your 'CIE32XYZ')."""

    X: float
    Y: float
    Z: float


@dataclass
class CIE32xyY(ColorBase):
    """CIE 1931 2° xyY (your 'CIE32xyY')."""

    x: float
    y: float
    Y: float


# ---------------------------------------------------------------------------
# CIE 1976 uniform-ish spaces
# ---------------------------------------------------------------------------


@dataclass
class CIELab(ColorBase):
    L: float
    a: float
    b: float


@dataclass
class CIELUV(ColorBase):
    L: float
    u: float
    v: float


@dataclass
class CIELChab(ColorBase):
    """Cylindrical form of CIELab."""

    L: float
    C: float
    h: float  # degrees


@dataclass
class CIELChuv(ColorBase):
    """Cylindrical form of CIELUV."""

    L: float
    C: float
    h: float  # degrees


# ---------------------------------------------------------------------------
# Appearance-model-based spaces
# ---------------------------------------------------------------------------


@dataclass
class CIECAM02Jab(ColorBase):
    """
    CIECAM02-derived uniform space (Jab).

    Often denoted J', a', b'; primes omitted in field names.
    """

    J: float
    a: float
    b: float


@dataclass
class CAM16UCS(ColorBase):
    """
    CAM16-UCS uniform space.

    Typically J', a', b'; primes omitted in field names.
    """

    J: float
    a: float
    b: float


@dataclass
class CAM16HCT(ColorBase):
    """CAM16-HCT (Hue-Chroma-Tone) coordinates."""

    h: float  # degrees
    C: float  # chroma
    T: float  # tone / lightness-like coordinate


# ---------------------------------------------------------------------------
# Modern perceptual spaces
# ---------------------------------------------------------------------------


@dataclass
class OKLab(ColorBase):
    L: float
    a: float
    b: float


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else min(x, hi)


def _cbrt(x: float) -> float:
    # Numerically stable for negative values (unlike x ** (1/3) in Python for x<0).
    return math.copysign(abs(x) ** (1.0 / 3.0), x)


def _srgb_component_to_rgb_component(c: float) -> float:
    return c / 12.92 if c <= _SRGB_UPPER_THRESHOLD else ((c + 0.055) / 1.055) ** 2.4


def _rgb_component_to_srgb_component(c: float) -> float:
    return 12.92 * c if c <= _SRGB_LOWER_THRESHOLD else 1.055 * (c ** (1 / 2.4)) - 0.055


def _srgb_to_rgb(srgb: SRGB) -> RGB:
    return RGB(
        _srgb_component_to_rgb_component(srgb.r),
        _srgb_component_to_rgb_component(srgb.g),
        _srgb_component_to_rgb_component(srgb.b),
    )


def _rgb_to_srgb(rgb: RGB) -> SRGB:
    return SRGB(
        _rgb_component_to_srgb_component(_clamp(rgb.r)),
        _rgb_component_to_srgb_component(_clamp(rgb.g)),
        _rgb_component_to_srgb_component(_clamp(rgb.b)),
    )


def _rgb_to_lms(rgb: RGB) -> LMS:
    # OKLab forward: linear RGB -> LMS (M1) -> cube-root -> l_,m_,s_.
    l_lin = 0.4122214708 * rgb.r + 0.5363325363 * rgb.g + 0.0514459929 * rgb.b
    m_lin = 0.2119034982 * rgb.r + 0.6806995451 * rgb.g + 0.1073969566 * rgb.b
    s_lin = 0.0883024619 * rgb.r + 0.2817188376 * rgb.g + 0.6299787005 * rgb.b
    return LMS(_cbrt(l_lin), _cbrt(m_lin), _cbrt(s_lin))


def _lms_to_rgb(lms: LMS) -> RGB:
    # OKLab inverse path: l_,m_,s_ -> cube -> LMS -> linear RGB (M1^-1).
    l_cubed = lms.L**3
    m_cubed = lms.M**3
    s_cubed = lms.S**3

    return RGB(
        +4.0767416621 * l_cubed - 3.3077115913 * m_cubed + 0.2309699292 * s_cubed,
        -1.2684380046 * l_cubed + 2.6097574011 * m_cubed - 0.3413193965 * s_cubed,
        -0.0041960863 * l_cubed - 0.7034186147 * m_cubed + 1.7076147010 * s_cubed,
    )


def _oklab_to_lms(oklab: OKLab) -> LMS:
    # OKLab inverse: OKLab -> l_,m_,s_ (M2^-1).
    return LMS(
        oklab.L + 0.3963377774 * oklab.a + 0.2158037573 * oklab.b,
        oklab.L - 0.1055613458 * oklab.a - 0.0638541728 * oklab.b,
        oklab.L - 0.0894841775 * oklab.a - 1.2914855480 * oklab.b,
    )


def _lms_to_oklab(lms: LMS) -> OKLab:
    # OKLab: l_,m_,s_ -> OKLab (M2).
    return OKLab(
        0.2104542553 * lms.L + 0.7936177850 * lms.M - 0.0040720468 * lms.S,
        1.9779984951 * lms.L - 2.4285922050 * lms.M + 0.4505937099 * lms.S,
        0.0259040371 * lms.L + 0.7827717662 * lms.M - 0.8086757660 * lms.S,
    )


# Minimal conversion set needed to connect all spaces.
_CONVERTERS: dict[tuple[type[ColorBase], type[ColorBase]], Callable[..., ColorBase]] = {
    (SRGB, RGB): _srgb_to_rgb,
    (RGB, SRGB): _rgb_to_srgb,
    (RGB, LMS): _rgb_to_lms,
    (LMS, RGB): _lms_to_rgb,
    (LMS, OKLab): _lms_to_oklab,
    (OKLab, LMS): _oklab_to_lms,
}


class Color:
    _orig: ColorBase

    def __init__(
        self,
        color_base: ColorBase | None = None,
        *,
        srgb: tuple[float, float, float] | None = None,
        rgb: tuple[float, float, float] | None = None,
        lms: tuple[float, float, float] | None = None,
        oklab: tuple[float, float, float] | None = None,
    ) -> None:
        nargs = sum((bool(color_base), bool(srgb), bool(rgb), bool(lms), bool(oklab)))
        if nargs == 1:
            if color_base:
                self._orig = color_base
            elif srgb:
                self._orig = SRGB(*srgb)
            elif rgb:
                self._orig = RGB(*rgb)
            elif lms:
                self._orig = LMS(*lms)
            elif oklab:
                self._orig = OKLab(*oklab)
        else:
            msg = (
                "Either a ColorBase must be supplied or one of "
                "`srgb`, `rgb`, `lms`, `oklab`, must be supplied as a tuple[float,float,float]."
            )
            raise ValueError(msg)

    @staticmethod
    def conversion_path(
        start: type[ColorBase], target: type[ColorBase]
    ) -> tuple[Callable[[ColorBase], ColorBase], ...]:
        """Shortest-path (fewest edges) colorspace conversion sequence."""
        if start is target:
            return ()

        # BFS over types using the directed edges in _CONVERTERS.

        q = deque([start])
        prev: dict[type[ColorBase], tuple[type[ColorBase], Callable[[ColorBase], ColorBase]]] = {}
        seen = {start}

        while q:
            u = q.popleft()
            for (a, b), f in _CONVERTERS.items():
                if a is not u:
                    continue
                if b in seen:
                    continue
                prev[b] = (u, f)
                if b is target:
                    # Reconstruct path of functions.
                    funcs: list[Callable[[ColorBase], ColorBase]] = []
                    cur = b
                    while cur is not start:
                        p, fn = prev[cur]
                        funcs.append(fn)
                        cur = p
                    funcs.reverse()
                    return tuple(funcs)
                seen.add(b)
                q.append(b)

        msg = f"No conversion path from {start.__name__} to {target.__name__}"
        raise ValueError(msg)

    def _convert_to(self, target: type[ColorBase]) -> ColorBase:
        funcs = self.conversion_path(type(self._orig), target)
        c_tmp: ColorBase = deepcopy(self._orig)
        for f in funcs:
            c_tmp = f(c_tmp)
        return c_tmp

    def to_rgb(self) -> RGB:
        out = self._convert_to(RGB)
        if not isinstance(out, RGB):
            msg = f"Conversion produced unexpected type: {type(out).__name__}"
            raise TypeError(msg)
        return out

    def to_srgb(self) -> SRGB:
        out = self._convert_to(SRGB)
        if not isinstance(out, SRGB):
            msg = f"Conversion produced unexpected type: {type(out).__name__}"
            raise TypeError(msg)
        return out

    def to_hex(self, length: int | None = None) -> str:
        out = self._convert_to(SRGB)
        if not isinstance(out, SRGB):
            msg = f"Conversion produced unexpected type: {type(out).__name__}"
            raise TypeError(msg)
        return out.to_hex(length=length)

    def to_lms(self) -> LMS:
        out = self._convert_to(LMS)
        if not isinstance(out, LMS):
            msg = f"Conversion produced unexpected type: {type(out).__name__}"
            raise TypeError(msg)
        return out

    def to_oklab(self) -> OKLab:
        out = self._convert_to(OKLab)
        if not isinstance(out, OKLab):
            msg = f"Conversion produced unexpected type: {type(out).__name__}"
            raise TypeError(msg)
        return out

    @property
    def lightness(self) -> float:
        return self.to_oklab().L


def query_terminal_bg_osc11(timeout: float = 0.15) -> Color | None:  # noqa: PLR0914
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
                if not len(r_s) == len(g_s) == len(b_s):
                    msg = (
                        "R, G, and B values must have the same bitdepth. "
                        f"({len(r_s) * 8:d}, {len(g_s) * 8:d}, {len(b_s) * 8:d})."
                    )
                    raise ValueError(msg)
                bitdepth = len(r_s)

                r, g, b = (int(x, 16) / (2**bitdepth) for x in (r_s, g_s, b_s))

                return Color(srgb=(r, g, b))

        return None

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if close_fd:
            os.close(fd)


def get_bg(
    force: Literal["dark", "light"] | None = None,
    dark_bg: tuple[int, int, int] = (49, 56, 61),
    light_bg: tuple[int, int, int] = (237, 230, 222),
) -> SRGB:
    if force is None:
        bg = query_terminal_bg_osc11(timeout=0.15)
        if bg is None:
            bg = dark_bg if darkdetect.isDark() else light_bg
    elif force == "dark":
        bg = dark_bg
    elif force == "light":
        bg = light_bg

    if isinstance(bg, Color):
        return bg.to_srgb()
    return SRGB(bg[0] / _BYTE_MAX, bg[1] / _BYTE_MAX, bg[2] / _BYTE_MAX)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def gray(lightness: float) -> Color:
    return Color(oklab=(lightness, 0, 0))


def _parse_hex(bgcolor: str) -> tuple[int, int, int]:
    srgb = SRGB.from_hex(bgcolor)
    return (
        round(srgb.r * _BYTE_MAX),
        round(srgb.g * _BYTE_MAX),
        round(srgb.b * _BYTE_MAX),
    )


def _luminance(r: int, g: int, b: int) -> float:
    r_lin = _srgb_component_to_rgb_component(r / _BYTE_MAX)
    g_lin = _srgb_component_to_rgb_component(g / _BYTE_MAX)
    b_lin = _srgb_component_to_rgb_component(b / _BYTE_MAX)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _oklab_to_srgb(lightness: float, a_val: float, b_val: float) -> tuple[int, int, int]:
    srgb = Color(oklab=(lightness, a_val, b_val)).to_srgb()
    return (
        round(srgb.r * _BYTE_MAX),
        round(srgb.g * _BYTE_MAX),
        round(srgb.b * _BYTE_MAX),
    )


def dimmest_text_over_contrast(
    bgcolor: str,
    *,
    min_contrast: float = 2.0,
) -> tuple[float, float]:
    bg_rgb = _parse_hex(bgcolor)
    bg_lum = _luminance(*bg_rgb)

    return (
        _clamp_0_1(bg_lum * min_contrast),
        _clamp_0_1(bg_lum / min_contrast),
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
    rich.style.Style with a truecolor hex foreground.
    """
    t = _clamp_0_1(value)
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

    rgb = gray(target_l).to_srgb()
    return rgb.to_hex()


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else min(x, hi)


def _clamp_0_1(x: float) -> float:
    return _clamp(x, 0.0, 1.0)


def colormap(pct: float, lightness: float = 0.63) -> str:
    t = _clamp_0_1(pct / 100.0)
    theta = 3.95 * (1 - t) + 0.31 * t
    r = -0.30 * (1 - t) + -0.2 * t
    a = r * math.sin(theta)
    b = r * math.cos(theta)

    r, g, b = _oklab_to_srgb(lightness, a, b)
    return _rgb_to_hex(r, g, b)


def render_heatmap_scale() -> str:
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
    bg_dark_hex = bg_dark.to_hex()
    bg_light_hex = bg_light.to_hex()
    bg_auto_hex = bg_auto.to_hex()

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
                    color=scalar_to_text_style(p / 100, bgcolor=bg_light_hex),
                    bold=True,
                    bgcolor=bg_light_hex,
                ),
            ),
            Text(
                pct_txt,
                style=Style(
                    color=scalar_to_text_style(p / 100, bgcolor=bg_dark_hex),
                    bold=True,
                    bgcolor=bg_dark_hex,
                ),
            ),
            Text(
                pct_txt,
                style=Style(
                    color=scalar_to_text_style(p / 100, bgcolor=bg_auto_hex),
                    bold=True,
                ),
            ),
        )

    buf = StringIO()
    console = Console(
        file=buf,
        force_terminal=True,
        width=sys.maxsize,
    )
    console.print(table)
    return buf.getvalue().rstrip()
