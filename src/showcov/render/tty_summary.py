from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from showcov.model.report import SummarySection


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


def render_tty_summary(
    summary: SummarySection,
    *,
    color: bool = True,
    show_branches: bool = True,
    green: float = 90.0,
    yellow: float = 75.0,
) -> str:
    """Render a Rich-style coverage summary table from the typed SummarySection.

    No path normalization is performed here; `SummaryRow.file` is assumed to
    already be the desired display label.
    """
    table = Table(title="Coverage Report", box=box.SIMPLE_HEAVY, header_style="bold", expand=True)

    table.add_column("File", overflow="fold")
    table.add_column("Stmt\nTot.", justify="right")
    table.add_column("Stmt\nHit", justify="right")
    table.add_column("Stmt\nMiss", justify="right")
    table.add_column("Stmt\nCov.", justify="right")

    if show_branches:
        table.add_column("Branch\nTot.", justify="right")
        table.add_column("Branch\nHit", justify="right")
        table.add_column("Branch\nMiss", justify="right")
        table.add_column("Branch\nCov.", justify="right")

    for r in summary.files:
        st = r.statements
        bt = r.branches

        stmt_pct = (100.0 * st.covered / st.total) if st.total else None
        br_pct = (100.0 * bt.covered / bt.total) if bt.total else None

        row = [
            r.file,
            str(st.total),
            str(st.covered),
            _style_miss(st.missed),
            _style_percent(stmt_pct, green, yellow),
        ]
        if show_branches:
            row.extend([
                str(bt.total),
                str(bt.covered),
                _style_miss(bt.missed),
                _style_percent(br_pct, green, yellow),
            ])
        table.add_row(*row)

    table.add_section()

    stt = summary.totals.statements
    btt = summary.totals.branches
    stmt_pct_overall = (100.0 * stt.covered / stt.total) if stt.total else None
    br_pct_overall = (100.0 * btt.covered / btt.total) if btt.total else None

    totals = [
        "[bold]Overall[/bold]",
        f"[bold]{stt.total}[/bold]",
        f"[bold]{stt.covered}[/bold]",
        f"[bold]{stt.missed}[/bold]",
        f"[bold]{_style_percent(stmt_pct_overall, green, yellow)}[/bold]",
    ]
    if show_branches:
        totals.extend([
            f"[bold]{btt.total}[/bold]",
            f"[bold]{btt.covered}[/bold]",
            f"[bold]{btt.missed}[/bold]",
            f"[bold]{_style_percent(br_pct_overall, green, yellow)}[/bold]",
        ])
    table.add_row(*totals)

    buf = StringIO()
    console = Console(file=buf, force_terminal=color, no_color=not color)
    console.print()
    console.print(table)
    console.print()
    return buf.getvalue().rstrip()


__all__ = ["render_tty_summary"]
