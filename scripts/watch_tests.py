from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class WatchConfig:
    root: Path
    debounce_s: float
    extensions: tuple[str, ...]
    ignore_dirs: tuple[str, ...]
    pytest_args: tuple[str, ...]


def _is_ignored(path: Path, root: Path, ignore_dirs: Iterable[str]) -> bool:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except Exception:
        return True
    parts = set(rel.parts)
    return any(d in parts for d in ignore_dirs)


class DebouncedPytestHandler(FileSystemEventHandler):
    def __init__(self, cfg: WatchConfig) -> None:
        self.cfg = cfg
        self._lock = threading.Lock()
        self._deadline: float | None = None
        self._timer: threading.Thread | None = None
        self._running_proc: subprocess.Popen[str] | None = None

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return

        path = Path(event.src_path)

        # Filter by extension (e.g., .py)
        if path.suffix not in self.cfg.extensions:
            return

        # Ignore typical noisy directories
        if _is_ignored(path, self.cfg.root, self.cfg.ignore_dirs):
            return

        # Debounce: coalesce bursts of writes
        with self._lock:
            self._deadline = time.time() + self.cfg.debounce_s
            if self._timer is None or not self._timer.is_alive():
                self._timer = threading.Thread(target=self._debounce_loop, daemon=True)
                self._timer.start()

    def _debounce_loop(self) -> None:
        while True:
            with self._lock:
                if self._deadline is None:
                    return
                remaining = self._deadline - time.time()
            if remaining > 0:
                time.sleep(min(remaining, 0.25))
                continue
            break

        self._run_pytest()

        with self._lock:
            self._deadline = None

    def _run_pytest(self) -> None:
        # If a prior run is still going, terminate it (keeps feedback tight)
        if self._running_proc and self._running_proc.poll() is None:
            self._running_proc.terminate()
            try:
                self._running_proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._running_proc.kill()

        cmd = [sys.executable, "-m", "pytest", "--testmon", "--no-cov", *self.cfg.pytest_args]
        print("\n=== Change detected: running:", " ".join(cmd), "===\n", flush=True)

        env = os.environ.copy()
        # (Optional) Ensure consistent output
        env.setdefault("PYTHONUNBUFFERED", "1")

        self._running_proc = subprocess.Popen(cmd, cwd=str(self.cfg.root), env=env)
        rc = self._running_proc.wait()
        print(f"\n=== pytest exit code: {rc} ===\n", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Watch a project and run pytest --testmon on changes.")
    p.add_argument("--root", default=".", help="Project root to watch (default: .)")
    p.add_argument("--debounce", type=float, default=0.4, help="Debounce seconds (default: 0.4)")
    p.add_argument(
        "--ext",
        action="append",
        default=[".py"],
        help="File extension to watch (repeatable). Default: .py",
    )
    p.add_argument(
        "--ignore-dir",
        action="append",
        default=[
            ".git",
            ".tox",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "build",
            "dist",
        ],
        help="Directory name to ignore (repeatable).",
    )
    p.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to pytest after -- (e.g. -- -q --ff -m 'not slow')",
    )
    args = p.parse_args()

    root = Path(args.root).resolve()

    # argparse captures the leading '--' into pytest_args; strip it if present
    pytest_args = tuple(a for a in args.pytest_args if a != "--")

    cfg = WatchConfig(
        root=root,
        debounce_s=args.debounce,
        extensions=tuple(args.ext),
        ignore_dirs=tuple(args.ignore_dir),
        pytest_args=pytest_args,
    )

    handler = DebouncedPytestHandler(cfg)
    observer = Observer()
    observer.schedule(handler, str(cfg.root), recursive=True)
    observer.start()

    print(f"Watching: {cfg.root}")
    print(f"Extensions: {cfg.extensions}")
    print(f"Ignoring dirs: {cfg.ignore_dirs}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopping...")
        observer.stop()
    observer.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
