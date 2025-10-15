from __future__ import annotations

import re
import xml.etree.ElementTree as ET  # noqa: S405
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


# --------------------------- Models ------------------------------------------
@dataclass(frozen=True)
class LineAgg:
    hits: int = 0
    br_cov: int = 0
    br_tot: int = 0


@dataclass
class FileAgg:
    lines: dict[int, LineAgg]  # lineno -> agg


# --------------------------- Discovery/Parsing -------------------------------
def _find_coverage_xml_paths(root: Path, patterns: Sequence[str]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for pat in patterns:
        for p in root.rglob(pat):
            if p.is_file() and p not in seen:
                seen.add(p)
                out.append(p)
    return out


def _read_coverage_xml_file(path: Path) -> ET.Element | None:
    try:
        return ET.parse(path).getroot()  # noqa: S314 (trusted local file)
    except ET.ParseError:
        return None


def _read_all_coverage_roots(root: Path, patterns: Sequence[str]) -> list[ET.Element]:
    roots: list[ET.Element] = []
    for path in _find_coverage_xml_paths(root, patterns):
        r = _read_coverage_xml_file(path)
        if r is not None:
            roots.append(r)
    return roots


_cond_re = re.compile(r"\(?\s*(\d+)\s*/\s*(\d+)\s*\)?")


def _parse_condition_coverage(text: str) -> tuple[int, int] | None:
    # Accept "50% (1/2)" or "(1/2)" or "1/2"
    m = _cond_re.search(text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _iter_lines(root: ET.Element) -> Iterable[tuple[str, int, int, int, int]]:
    """Yield per-line stats: (filename, lineno, hits, br_covered, br_total)."""
    for cls in root.findall(".//class"):
        fname = cls.get("filename", "")
        lines_node = cls.find("lines")
        if not fname or lines_node is None:
            continue
        for ln in lines_node.findall("line"):
            try:
                lineno = int(ln.get("number", "0"))
            except ValueError:
                continue
            hits = int(ln.get("hits", "0") or 0)
            br_cov = 0
            br_tot = 0
            if ln.get("branch") == "true":
                cc = ln.get("condition-coverage") or ""
                parsed = _parse_condition_coverage(cc)
                if parsed is not None:
                    br_cov, br_tot = parsed
            yield fname, lineno, hits, br_cov, br_tot


# --------------------------- Aggregation -------------------------------------
def _compile_filters(include: str | None, exclude: str | None):
    inc = re.compile(include) if include else None
    exc = re.compile(exclude) if exclude else None

    def ok(p: Path) -> bool:
        s = str(p)
        if inc and not inc.search(s):
            return False
        return not (exc and exc.search(s))

    return ok


def _aggregate(roots: Sequence[ET.Element], include: str | None, exclude: str | None) -> dict[str, FileAgg]:
    ok = _compile_filters(include, exclude)
    acc: dict[str, FileAgg] = {}
    for root in roots:
        for fname, lineno, hits, br_cov, br_tot in _iter_lines(root):
            fpath = Path(fname).resolve()
            if not ok(fpath):
                continue
            key = str(fpath)
            fa = acc.setdefault(key, FileAgg(lines={}))
            la = fa.lines.get(lineno, LineAgg())
            # Combine across reports: take max hits and max covered/total
            new_hits = max(la.hits, hits)
            new_br_cov = max(la.br_cov, br_cov)
            new_br_tot = max(la.br_tot, br_tot)
            fa.lines[lineno] = LineAgg(new_hits, new_br_cov, new_br_tot)
    return acc


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


def _relativize(path: str, rel_to: Path | None) -> str:
    if not rel_to:
        return path
    try:
        return str(Path(path).resolve().relative_to(rel_to.resolve()))
    except Exception:
        return path


# --------------------------- Table -------------------------------------------
def _build_table(rows, totals, show_branches: bool) -> Table:
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


# --------------------------- Main --------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    root = Path()
    patterns = [".coverage.xml", "coverage.xml"]
    include = None
    exclude = None
    rel_to = Path()
    sort = "file"  # "stmt_cov", "br_cov", "miss"
    show_branches = True
    green = 90.0
    yellow = 75.0
    fail_under_line = None
    fail_under_branch = None

    roots = _read_all_coverage_roots(root, patterns)
    if not roots:
        return 0

    acc = _aggregate(roots, include, exclude)
    if not acc:
        return 0

    # Per-file
    rows_raw = []
    sum_stmt_tot = sum_stmt_hit = sum_br_tot = sum_br_hit = 0
    for fpath, fa in acc.items():
        stmt_tot = len(fa.lines)
        stmt_hit = sum(1 for la in fa.lines.values() if la.hits > 0)
        stmt_miss = stmt_tot - stmt_hit
        br_tot = sum(la.br_tot for la in fa.lines.values())
        br_hit = sum(la.br_cov for la in fa.lines.values())
        br_miss = br_tot - br_hit

        sum_stmt_tot += stmt_tot
        sum_stmt_hit += stmt_hit
        sum_br_tot += br_tot
        sum_br_hit += br_hit

        rows_raw.append((
            fpath,
            stmt_tot,
            stmt_hit,
            stmt_miss,
            (100.0 * stmt_hit / stmt_tot) if stmt_tot else None,
            br_tot,
            br_hit,
            br_miss,
            (100.0 * br_hit / br_tot) if br_tot else None,
        ))

    # Sorting
    keyfuncs = {
        "file": lambda r: (Path(r[0]), r[0]),
        "stmt_cov": lambda r: (-(r[4] or -1), r[0]),
        "br_cov": lambda r: (-(r[8] or -1), r[0]),
        "miss": lambda r: (-(r[3] + r[7]), r[0]),
    }
    rows_raw.sort(key=keyfuncs[sort])

    # Render rows
    stmt_cov_overall = (100.0 * sum_stmt_hit / sum_stmt_tot) if sum_stmt_tot else None
    br_cov_overall = (100.0 * sum_br_hit / sum_br_tot) if sum_br_tot else None

    def fmt_row(r):
        file_rel = _relativize(r[0], rel_to)
        return [
            file_rel,
            str(r[1]),
            str(r[2]),
            _style_miss(r[3]),
            _style_percent(r[4], green, yellow),
            str(r[5]),
            str(r[6]),
            _style_miss(r[7]),
            _style_percent(r[8], green, yellow),
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

    console = Console()
    console.print()
    console.print(_build_table(rows, totals, show_branches))
    console.print()

    # CI thresholds
    fail = False
    if fail_under_line is not None and (stmt_cov_overall or 0.0) < fail_under_line:
        fail = True
    if fail_under_branch is not None and (br_cov_overall or 0.0) < fail_under_branch:
        fail = True
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
