from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

CORE_FIELDS = {"filename", "location", "code", "message", "fix", "name", "url"}
BACKTICK_RE = re.compile(r"`([^`]*)`")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compact formatter for `ruff check --output-format json`.")
    p.add_argument("--input", metavar="FILE")
    p.add_argument("--sort", choices=("location", "code", "message"), default="code")
    p.add_argument("--group", choices=("file", "code"), default="file")
    p.add_argument("--absolute-paths", action="store_true")
    p.add_argument("--no-extra", action="store_true")
    p.add_argument("--extra-max-chars", type=int, default=160)
    p.add_argument("--summary", action="store_true")
    p.add_argument("--summary-top", type=int, default=5)
    return p.parse_args()


def die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def read_input(args: argparse.Namespace) -> str:
    if args.input:
        try:
            return Path(args.input).read_text(encoding="utf-8")
        except OSError as e:
            die(f"Could not read input file '{args.input}': {e}")
    raw = sys.stdin.read()
    if raw.strip():
        return raw
    die("No input on stdin.", 2)
    return None


def load_diags(raw: str) -> list[dict[str, Any]]:
    try:
        x = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"Input is not valid JSON: {e}")
    if not isinstance(x, list) or any(not isinstance(i, dict) for i in x):
        die("Expected a JSON array of objects.")
    return x  # type: ignore[return-value]


def code_style(code: str) -> str:
    c = (code or "").upper()

    # Security
    if c.startswith("S"):
        return "bold magenta"

    # Error-ish
    if c.startswith(("E", "F")):
        return "bold red"

    # PyLint families
    if c.startswith(("PLR", "PLE", "PLW", "PLC", "PL")):
        return "bold blue"

    # Tryceratops / exception rules
    if c.startswith(("TRY", "BLE")):
        return "bold cyan"

    # Warning-ish / style-ish
    if c.startswith(("W", "B", "C", "N", "D", "UP", "SIM", "PTH", "PERF", "RUF")):
        return "bold yellow"

    return "bold"


def code_text(code: str, url: str | None) -> Text:
    t = Text(code, style=code_style(code))
    if url:
        # OSC8 link when supported
        t.stylize(f"link {url}")
    return t


def highlight_backticks(s: str) -> Text:
    """Style anything inside single backticks (including the backticks): italic cyan."""
    if "`" not in s:
        return Text(s)

    out = Text()
    last = 0
    for m in BACKTICK_RE.finditer(s):
        out.append(s[last : m.start()])
        out.append(m.group(0), style="italic cyan")
        last = m.end()
    out.append(s[last:])
    return out


def display_name(fname: str, *, absolute: bool) -> str:
    if fname == "<unknown>":
        return fname
    p = Path(fname)
    if absolute:
        return str(p if p.is_absolute() else (Path.cwd() / p))
    pa = p if p.is_absolute() else (Path.cwd() / p)
    try:
        return str(pa.relative_to(Path.cwd()))
    except ValueError:
        return fname


def loc_str(d: dict[str, Any]) -> str:
    loc = d.get("location")
    if not isinstance(loc, dict):
        return ""
    row, col = loc.get("row"), loc.get("column")
    if isinstance(row, int) and isinstance(col, int):
        return f"{row}:{col}"
    if isinstance(row, int):
        return f"{row}:"
    return ""


def sort_key(d: dict[str, Any], mode: str) -> tuple:
    code = str(d.get("code") or "")
    msg = str(d.get("message") or "")
    loc = d.get("location") if isinstance(d.get("location"), dict) else {}
    row = loc.get("row") if isinstance(loc.get("row"), int) else 10**9
    col = loc.get("column") if isinstance(loc.get("column"), int) else 10**9
    if mode == "location":
        return (row, col, code, msg)
    if mode == "message":
        return (msg, row, col, code)
    return (code, row, col, msg)


def extra_text(d: dict[str, Any], max_chars: int) -> Text:
    extra = {k: v for k, v in d.items() if k not in CORE_FIELDS and v is not None}
    if not extra:
        return Text("")
    s = json.dumps(extra, ensure_ascii=False, sort_keys=True)
    if max_chars > 0 and len(s) > max_chars:
        s = s[: max_chars - 1] + "…"
    return Text(s, style="dim")


def print_group(
    console: Console, title: str, diags: list[dict[str, Any]], args: argparse.Namespace, *, prefix_file: bool
) -> None:
    console.print(Text(f"\n{title}  [{len(diags)}]", style="bold"))
    t = Table.grid(padding=(0, 1))
    t.add_column(justify="right", no_wrap=True)  # loc
    t.add_column(no_wrap=True)  # code
    t.add_column(no_wrap=True)  # fix
    t.add_column()  # message
    t.add_column()  # extra

    for d in diags:
        code = str(d.get("code") or "")
        url = d.get("url") if isinstance(d.get("url"), str) else None
        fix = "*" if d.get("fix") is not None else ""
        msg = str(d.get("message") or "")
        if prefix_file:
            msg = (
                f"{display_name(str(d.get('filename') or '<unknown>'), absolute=args.absolute_paths)}: {msg}"
            )
        msg_t = highlight_backticks(msg)

        t.add_row(
            loc_str(d),
            code_text(code, url),
            Text(fix, style="green") if fix else Text(""),
            msg_t,
            Text("") if args.no_extra else extra_text(d, args.extra_max_chars),
        )

    console.print(t)


def main() -> int:
    args = parse_args()
    console = Console(highlight=False, emoji=False)

    diags = load_diags(read_input(args))
    if not diags:
        console.print("All checks passed!")
        return 0

    if args.group == "file":
        by = defaultdict(list)
        for d in diags:
            by[str(d.get("filename") or "<unknown>")].append(d)

        for fname in sorted(by, key=lambda s: (s == "<unknown>", s)):
            items = sorted(by[fname], key=lambda d: sort_key(d, args.sort))
            title = display_name(fname, absolute=args.absolute_paths)

            if args.summary:
                c = Counter(str(d.get("code") or "<unknown-code>") for d in items)
                top = ", ".join(f"{k}={v}" for k, v in c.most_common(args.summary_top))
                console.print(Text(f"\n{title}", style="bold dim"))
                console.print(Text("  top codes: ", style="dim") + Text(top))

            print_group(console, title, items, args, prefix_file=False)
        return 1

    # group == "code"
    by = defaultdict(list)
    for d in diags:
        by[str(d.get("code") or "<unknown-code>")].append(d)

    for code in sorted(by):
        items = sorted(by[code], key=lambda d: sort_key(d, args.sort))

        if args.summary:
            c = Counter(
                display_name(str(d.get("filename") or "<unknown>"), absolute=args.absolute_paths)
                for d in items
            )
            top = ", ".join(f"{k}={v}" for k, v in c.most_common(args.summary_top))
            console.print(Text(f"\n{code}", style="bold dim"))
            console.print(Text("  top files: ", style="dim") + Text(top))

        print_group(console, code, items, args, prefix_file=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
