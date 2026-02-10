from __future__ import annotations

from typing import Annotated, Literal

import typer

from showcov.adapters.render.table import render_heatmap_scale


def debug_cmd(
    colormap: Annotated[
        Literal["flame", "twilight", "all"],
        typer.Argument(
            help="Colormap to display (pass 'all' to inspect both).",
        ),
    ] = "flame",
    color: Annotated[
        bool | None,
        typer.Option(
            "--color/--no-color",
            help="Enable ANSI coloring for the scale.",
        ),
    ] = None,
) -> int:
    targets: tuple[str, ...] = ("flame", "twilight") if colormap == "all" else (colormap,)
    color_value = True if color is None else color
    for name in targets:
        typer.echo(f"\n{name} colormap:")
        typer.echo(render_heatmap_scale(colormap=name, color=bool(color_value)))
    return 0


def register(app: typer.Typer) -> None:
    app.command("debug")(debug_cmd)


__all__ = ["register"]
