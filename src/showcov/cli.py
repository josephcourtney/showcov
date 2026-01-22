from __future__ import annotations

import pathlib
from typing import Any

import typer
from typer.main import get_command

from showcov import __version__
from showcov.commands import completion as completion_cmd
from showcov.commands import diff as diff_cmd
from showcov.commands import man as man_cmd
from showcov.commands import report as report_cmd

app = typer.Typer(help="Unified coverage reporting for Cobertura-style coverage XML.")


@app.callback()
def _root(
    version: bool = typer.Option(False, "--version", help="Show the version and exit."),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit(code=0)


completion_module: Any = completion_cmd
report_cmd.register(app)
diff_cmd.register(app)
completion_module.Path = pathlib.Path  # type: ignore[attr-defined]
completion_module.pathlib = pathlib  # type: ignore[attr-defined, assignment]
completion_module.register(app)
man_module: Any = man_cmd
man_module.Path = pathlib.Path  # type: ignore[attr-defined]
man_module.pathlib = pathlib  # type: ignore[attr-defined, assignment]
man_module.register(app)

main = get_command(app)
cli = main

__all__ = ["app", "cli", "main"]
