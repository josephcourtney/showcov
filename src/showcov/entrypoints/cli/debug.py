from __future__ import annotations

import typer

from showcov.adapters.render.table import render_heatmap_scale


def debug_cmd() -> int:
    typer.echo(render_heatmap_scale())
    return 0


def register(app: typer.Typer) -> None:
    app.command("debug")(debug_cmd)


__all__ = ["register"]
