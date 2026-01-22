from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from showcov.commands._shared import EXIT_OK, write_output
from showcov.scripts import build_man_page

if TYPE_CHECKING:
    from pathlib import Path


def register(app: typer.Typer) -> None:
    @app.command("man")
    def man(
        output: Annotated[
            Path | None,
            typer.Option("--output", help="Write man page to PATH (use '-' for stdout)."),
        ] = None,
    ) -> None:
        """Print a plain-text manual page."""
        text = build_man_page()
        write_output(text, output)
        raise typer.Exit(code=EXIT_OK)


__all__ = ["register"]
