from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Annotated

import typer

from showcov.io import write_output
from showcov.run import EXIT_OK
from showcov.scripts import build_man_page


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
