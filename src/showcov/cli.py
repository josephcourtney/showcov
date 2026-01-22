from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import typer
from typer.main import get_command

from showcov import __version__
from showcov.commands import completion as completion_cmd
from showcov.commands import diff as diff_cmd
from showcov.commands import man as man_cmd
from showcov.commands import report as report_cmd

if TYPE_CHECKING:
    from types import ModuleType

app = typer.Typer(help="Unified coverage reporting for Cobertura-style coverage XML.")


@app.callback()
def _root(
    *,
    version: bool = typer.Option(False, "--version", help="Show the version and exit."),  # noqa: FBT003
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit(code=0)


def _patch_typer_annotation_globals(module: ModuleType) -> None:
    """Ensure names referenced by string annotations exist at runtime.

    Typer (via Click) inspects command callback signatures with `eval_str=True` on
    Python 3.14+, which evaluates string annotations created by
    `from __future__ import annotations`. If a command module only imports names like
    `Path`/`pathlib` under TYPE_CHECKING, signature evaluation can raise NameError.
    """
    if not hasattr(module, "Path"):
        module.Path = pathlib.Path
    if not hasattr(module, "pathlib"):
        module.pathlib = pathlib


# Patch modules before building the Click command so annotation evaluation is safe.
for _mod in (completion_cmd, man_cmd, diff_cmd, report_cmd):
    _patch_typer_annotation_globals(_mod)

report_cmd.register(app)
diff_cmd.register(app)
completion_cmd.register(app)
man_cmd.register(app)

main = get_command(app)
cli = main

__all__ = ["app", "cli", "main"]
