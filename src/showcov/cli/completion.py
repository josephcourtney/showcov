from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Annotated, Literal

import typer

from showcov.io import write_output
from showcov.run import EXIT_OK
from showcov.scripts import build_completion_script

ShellName = Literal["bash", "zsh", "fish"]


def register(app: typer.Typer) -> None:
    @app.command("completion")
    def completion(
        shell: Annotated[
            ShellName,
            typer.Argument(..., help="Shell name: bash, zsh, or fish."),
        ],
        output: Annotated[
            Path | None,
            typer.Option("--output", help="Write script to PATH (use '-' for stdout)."),
        ] = None,
    ) -> None:
        """Generate shell completion scripts."""
        script = build_completion_script(shell)
        write_output(script, output)
        raise typer.Exit(code=EXIT_OK)


__all__ = ["register"]
