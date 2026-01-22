"""Utility helpers for generating CLI documentation artefacts."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Literal

import click
from click.shell_completion import BashComplete, FishComplete, ShellComplete, ZshComplete

ShellName = Literal["bash", "zsh", "fish"]

_COMPLETE_CLASSES: dict[ShellName, type[ShellComplete]] = {
    "bash": BashComplete,
    "zsh": ZshComplete,
    "fish": FishComplete,
}

_COMPLETE_VAR = "_SHOWCOV_COMPLETE"

_EXIT_STATUS = """\
0  success
1  generic error (unexpected failure)
2  coverage threshold failure
65 malformed coverage XML data
66 required coverage XML input missing
"""


def _get_main_command() -> click.Command:
    # Local import prevents circular import:
    # - completion command imports scripts
    # - scripts importing cli at import time would cycle
    from showcov.cli import main  # noqa: PLC0415

    return main


def _collect_option_flags(command: click.Command) -> tuple[str, ...]:
    flags: set[str] = set()

    def visit(cmd: click.Command) -> None:
        for param in getattr(cmd, "params", []):
            if isinstance(param, click.Option):
                flags.update(param.opts)
                flags.update(param.secondary_opts)

        if isinstance(cmd, click.Group):
            for sub in cmd.commands.values():
                visit(sub)

    visit(command)
    return tuple(sorted({f for f in flags if f}))


def build_man_page() -> str:
    """Return a plain-text manual page for showcov's CLI."""
    main = _get_main_command()
    ctx = click.Context(main, info_name="showcov")
    buf = io.StringIO()
    with redirect_stdout(buf):
        help_text = main.get_help(ctx).strip()
    help_text = help_text or buf.getvalue().strip()

    sections = [
        "SHOWCOV(1)\n",
        "NAME\n----\nshowcov - unified coverage report generator\n\n",
        "SYNOPSIS\n--------\nshowcov [COMMAND] [ARGS]...\n\n",
        "DESCRIPTION\n-----------\n",
        help_text,
        "\n\nEXIT STATUS\n-----------\n",
        _EXIT_STATUS.strip(),
        "\n",
    ]
    return "".join(sections)


def build_completion_script(shell: ShellName) -> str:
    """Return a shell completion script for *shell*."""
    main = _get_main_command()
    option_comment = "# showcov options: " + " ".join(_collect_option_flags(main))

    complete_cls = _COMPLETE_CLASSES[shell]
    complete = complete_cls(main, {}, "showcov", _COMPLETE_VAR)
    script = complete.source()
    return f"{option_comment}\n{script}"
