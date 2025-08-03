#!.venv/bin/python

import re
from pathlib import Path
import sys
import tomllib


def get_pyproject_version(pyproject_path: Path) -> str:
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def get_changelog_version(changelog_path: Path) -> str:
    text = changelog_path.read_text(encoding="utf-8")
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\] - ", text, re.MULTILINE)
    if not match:
        raise ValueError("No valid version heading found in CHANGELOG.md")
    return match.group(1)


def main() -> int:
    pyproject = Path("pyproject.toml")
    changelog = Path("CHANGELOG.md")

    if not pyproject.exists() or not changelog.exists():
        print("Required files not found", file=sys.stderr)
        return 1

    py_version = get_pyproject_version(pyproject)
    ch_version = get_changelog_version(changelog)

    if py_version != ch_version:
        print(f"❌ Version mismatch: pyproject.toml={py_version}, CHANGELOG.md={ch_version}", file=sys.stderr)
        return 1

    print(f"✅ Version match: {py_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
