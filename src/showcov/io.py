from pathlib import Path


def write_output(text: str, destination: Path | None) -> None:
    """Write output to stdout or a file (PATH or '-' for stdout)."""
    if destination is None or destination == Path("-"):
        print(text)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
