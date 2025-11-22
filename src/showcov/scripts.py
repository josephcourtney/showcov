"""Utility helpers for generating CLI documentation artefacts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import click
from click.shell_completion import BashComplete, FishComplete, ShellComplete, ZshComplete

from .cli import cli

if TYPE_CHECKING:
    from pathlib import Path

ShellName = Literal["bash", "zsh", "fish"]

_COMPLETE_CLASSES: dict[ShellName, type[ShellComplete]] = {
    "bash": BashComplete,
    "zsh": ZshComplete,
    "fish": FishComplete,
}

_COMPLETE_VAR = "_SHOWCOV_COMPLETE"


def _collect_option_flags(command: click.Command) -> tuple[str, ...]:
    flags: list[str] = []
    for param in command.params:
        if isinstance(param, click.Option):
            flags.extend(param.opts)
            flags.extend(param.secondary_opts)
    return tuple(sorted({flag for flag in flags if flag}))


_OPTION_COMMENT = "# showcov options: " + " ".join(_collect_option_flags(cli))

_EXIT_STATUS = """\
0  success
1  generic error (unexpected failure)
2  coverage threshold failure
65 malformed coverage XML data
66 required coverage XML input missing
78 configuration error
"""


def _build_plain_command() -> click.Command:
    """Return a plain Click command mirroring :data:`cli`.

    This avoids the rich-click `RichCommand` help machinery, which expects a
    Rich-specific formatter object with extra attributes (like ``config``).
    For man-page generation we only need a stable, plain-text help string.
    """
    return click.Command(
        name="showcov",
        callback=cli.callback,
        params=cli.params,
        help=cli.help,
        epilog=cli.epilog,
        context_settings=cli.context_settings,
    )


def build_man_page() -> str:
    """Return a plain-text manual page for :mod:`showcov`'s CLI."""
    plain_cmd = _build_plain_command()
    ctx = click.Context(plain_cmd, info_name="showcov")
    help_text = plain_cmd.get_help(ctx).strip()
    sections = [
        "SHOWCOV(1)\n",
        "NAME\n----\nshowcov - unified coverage report generator\n\n",
        "SYNOPSIS\n--------\nshowcov [OPTIONS] [PATHS]...\n\n",
        "DESCRIPTION\n-----------\n",
        help_text,
        "\n\nEXIT STATUS\n-----------\n",
        _EXIT_STATUS.strip(),
        "\n",
    ]
    return "".join(sections)


def write_man_page(destination: Path) -> None:
    """Write the generated manual page to *destination*."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_man_page(), encoding="utf-8")


def build_completion_script(shell: ShellName) -> str:
    """Return a shell completion script for *shell*."""
    complete_cls = _COMPLETE_CLASSES[shell]
    complete = complete_cls(cli, {}, "showcov", _COMPLETE_VAR)
    script = complete.source()
    return f"{_OPTION_COMMENT}\n{script}"


def write_completion_script(shell: ShellName, destination: Path) -> None:
    """Write the completion script for *shell* to *destination*."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_completion_script(shell), encoding="utf-8")
