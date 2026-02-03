from pathlib import Path
from collections.abc import Iterable, Sequence

def _display_path(path: str, *, base: Path) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(base.resolve()).as_posix()
        except (OSError, RuntimeError, ValueError):
            return p.as_posix()
    return p.as_posix()





def _group_consecutive(nums: Iterable[int]) -> list[tuple[int, int]]:
    it = iter(sorted(set(nums)))
    out: list[tuple[int, int]] = []
    try:
        start = prev = next(it)
    except StopIteration:
        return out
    for n in it:
        if n == prev + 1:
            prev = n
            continue
        out.append((start, prev))
        start = prev = n
    out.append((start, prev))
    return out
