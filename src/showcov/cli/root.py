from __future__ import annotations

from typing import Annotated

import typer
from typer.main import get_command

from showcov import __version__
from showcov.cli import completion, man, report


def create_app() -> typer.Typer:
    app = typer.Typer(help="Unified coverage reporting for Cobertura-style coverage XML.")

    @app.callback()
    def _root(
        *,
        version: Annotated[
            bool,
            typer.Option("--version", help="Show version and exit"),
        ] = False,
    ) -> None:
        if version:
            typer.echo(f"showcov {__version__}")
            raise typer.Exit

    report.register(app)
    completion.register(app)
    man.register(app)

    return app


def main() -> None:
    app = create_app()
    get_command(app)()


# Click-compatible object for tooling that imports it
cli = get_command(create_app())

__all__ = ["cli", "create_app", "main"]
