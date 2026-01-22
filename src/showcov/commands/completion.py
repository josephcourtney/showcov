from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

import typer

from showcov.commands._shared import EXIT_OK, write_output
from showcov.scripts import build_completion_script

if TYPE_CHECKING:
    from pathlib import Path

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
