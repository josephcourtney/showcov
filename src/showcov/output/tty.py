from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console
from rich.table import Table

from showcov.core import normalize_path

if TYPE_CHECKING:
    from collections.abc import Iterable


# --------------------------- Formatting --------------------------------------
def _style_percent(pct: float | None, green: float, yellow: float) -> str:
    if pct is None:
        return "n/a"
    v = round(pct)
    if v >= green:
        return f"[green]{v}%[/green]"
    if v >= yellow:
        return f"[yellow]{v}%[/yellow]"
    return f"[red]{v}%[/red]"


def _style_miss(n: int) -> str:
    return f"[red]{n}[/red]" if n else f"[green]{n}[/green]"


# --------------------------- Table -------------------------------------------
def _build_table(
    rows: Iterable[list[str]],
    totals: list[str],
    *,
    show_branches: bool,
) -> Table:
    table = Table(title="Coverage Report", box=box.SIMPLE_HEAVY, header_style="bold", expand=True)

    table.add_column("File", style="cyan", overflow="fold")
    table.add_column("Stmt\nTot.", justify="right")
    table.add_column("Stmt\nHit", justify="right")
    table.add_column("Stmt\nMiss", justify="right")
    table.add_column("Stmt\nCov.", justify="right")

    if show_branches:
        table.add_column("Branch\nTot.", justify="right")
        table.add_column("Branch\nHit", justify="right")
        table.add_column("Branch\nMiss", justify="right")
        table.add_column("Branch\nCov.", justify="right")

    for r in rows:
        if show_branches:
            table.add_row(*r)
        else:
            table.add_row(*r[:5])

    table.add_section()
    if show_branches:
        table.add_row(*totals)
    else:
        table.add_row(*totals[:5])
    return table


def render_coverage_table(
    rows_raw: Iterable[tuple[str, int, int, int, int, int, int]],
    *,
    sum_stmt_tot: int,
    sum_stmt_hit: int,
    sum_br_tot: int,
    sum_br_hit: int,
    rel_to: Path | None = None,
    show_branches: bool = True,
    green: float = 90.0,
    yellow: float = 75.0,
) -> str:
    """Return a Rich-rendered table as text for the aggregated coverage view.

    Parameters
    ----------
    rows_raw:
        Iterable of per-file tuples:
        (path, stmt_tot, stmt_hit, stmt_miss, br_tot, br_hit, br_miss)
    sum_*:
        Global totals used to compute overall percentages.
    rel_to:
        Base path for relativising file paths in the first column.
    """
    # Percentages
    stmt_cov_overall = (100.0 * sum_stmt_hit / sum_stmt_tot) if sum_stmt_tot else None
    br_cov_overall = (100.0 * sum_br_hit / sum_br_tot) if sum_br_tot else None

    # Convert rows to display rows with styling
    def fmt_row(r: tuple[str, int, int, int, int, int, int]) -> list[str]:
        file_rel = normalize_path(Path(r[0]), base=rel_to).as_posix()
        stmt_cov = (100.0 * r[2] / r[1]) if r[1] else None
        br_cov = (100.0 * r[5] / r[4]) if r[4] else None
        return [
            file_rel,
            str(r[1]),
            str(r[2]),
            _style_miss(r[3]),
            _style_percent(stmt_cov, green, yellow),
            str(r[4]),
            str(r[5]),
            _style_miss(r[6]),
            _style_percent(br_cov, green, yellow),
        ]

    rows = [fmt_row(r) for r in rows_raw]

    totals = [
        "[bold]Overall[/bold]",
        f"[bold]{sum_stmt_tot}[/bold]",
        f"[bold]{sum_stmt_hit}[/bold]",
        f"[bold]{sum_stmt_tot - sum_stmt_hit}[/bold]",
        f"[bold]{_style_percent(stmt_cov_overall, green, yellow)}[/bold]",
        f"[bold]{sum_br_tot}[/bold]",
        f"[bold]{sum_br_hit}[/bold]",
        f"[bold]{sum_br_tot - sum_br_hit}[/bold]",
        f"[bold]{_style_percent(br_cov_overall, green, yellow)}[/bold]",
    ]

    table = _build_table(rows, totals, show_branches=show_branches)
    console = Console()
    with console.capture() as cap:
        console.print()
        console.print(table)
        console.print()
    return cap.get()
