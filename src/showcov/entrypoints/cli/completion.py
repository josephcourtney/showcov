from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Annotated, Literal

import click
import typer
from click.shell_completion import BashComplete, FishComplete, ShellComplete, ZshComplete
from typer.main import get_command

from showcov.adapters.output import write_output
from showcov.entrypoints.cli.exit_codes import EXIT_OK

ShellName = Literal["bash", "zsh", "fish"]

_COMPLETE_CLASSES: dict[ShellName, type[ShellComplete]] = {
    "bash": BashComplete,
    "zsh": ZshComplete,
    "fish": FishComplete,
}

_COMPLETE_VAR = "_SHOWCOV_COMPLETE"


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


def build_completion_script(shell: ShellName, *, command: click.Command) -> str:
    """Return a shell completion script for *shell*."""
    option_comment = "# showcov options: " + " ".join(_collect_option_flags(command))

    complete_cls = _COMPLETE_CLASSES[shell]
    complete = complete_cls(command, {}, "showcov", _COMPLETE_VAR)
    script = complete.source()
    return f"{option_comment}\n{script}"


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
        ],
    ) -> None:
        """Generate shell completion scripts."""
        script = build_completion_script(shell, command=get_command(app))
        write_output(script, output)
        raise typer.Exit(code=EXIT_OK)


__all__ = ["build_completion_script", "register"]
