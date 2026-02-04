from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path  # noqa: TC003
from typing import Annotated

import click
import typer
from typer.main import get_command

from showcov.adapters.output import write_output
from showcov.entrypoints.cli.exit_codes import EXIT_OK

_EXIT_STATUS = """\
0  success
1  generic error (unexpected failure)
2  coverage threshold failure
65 malformed coverage XML data
66 required coverage XML input missing
"""


def build_man_page(command: click.Command) -> str:
    """Return a plain-text manual page for showcov's CLI."""
    ctx = click.Context(command, info_name="showcov")
    buf = io.StringIO()
    with redirect_stdout(buf):
        help_text = command.get_help(ctx).strip()
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


def register(app: typer.Typer) -> None:
    command = get_command(app)

    @app.command("man")
    def man(
        output: Annotated[
            Path | None,
            typer.Option("--output", help="Write man page to PATH (use '-' for stdout)."),
        ],
    ) -> None:
        """Print a plain-text manual page."""
        text = build_man_page(command)
        write_output(text, output)
        raise typer.Exit(code=EXIT_OK)


__all__ = ["build_man_page", "register"]
