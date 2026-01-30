import sys
from enum import StrEnum
from pathlib import Path

import click.utils as click_utils


class OutputFormat(StrEnum):
    AUTO = "auto"
    HUMAN = "human"
    RG = "rg"
    JSON = "json"


def write_output(text: str, destination: Path | None) -> None:
    """Write output to stdout or a file (PATH or '-' for stdout)."""
    if destination is None or destination == Path("-"):
        print(text)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def compute_io_policy(
    *,
    fmt: OutputFormat,
    output: Path | None,
) -> tuple[str, bool, bool]:
    """Return (render_fmt, is_tty_like, color_allowed)."""
    allow_tty_output = output in {None, Path("-")}
    stdout = sys.stdout

    stdout_is_tty = allow_tty_output and bool(getattr(stdout, "isatty", lambda: False)())
    ansi_allowed = not click_utils.should_strip_ansi(stdout)

    if fmt == OutputFormat.AUTO:
        fmt_resolved = OutputFormat.HUMAN if stdout_is_tty else OutputFormat.RG
    else:
        fmt_resolved = fmt

    if fmt_resolved == OutputFormat.HUMAN:
        render_fmt = "human"
    elif fmt_resolved == OutputFormat.JSON:
        render_fmt = "json"
    else:
        render_fmt = "rg"

    # "tty-like" affects heading/compact behavior for human/rg; JSON is always non-tty.
    is_tty_like = bool(stdout_is_tty and render_fmt != "json")
    color_allowed = bool(render_fmt == "human" and is_tty_like and ansi_allowed)

    return render_fmt, is_tty_like, color_allowed
