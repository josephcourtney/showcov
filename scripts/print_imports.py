from __future__ import annotations

import argparse
import ast
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    "__pycache__",
    "docs",
    "site",
    "tests",
    "test",
}


def find_repo_root(start: Path) -> Path:
    p = start.resolve()
    for d in [p, *p.parents]:
        if (d / "pyproject.toml").is_file():
            return d
    raise FileNotFoundError(f"Could not find pyproject.toml above {start}")


def read_pyproject(repo_root: Path) -> dict:
    return tomllib.loads((repo_root / "pyproject.toml").read_text("utf-8"))


def read_workspace_members(repo_root: Path, data: dict) -> list[Path]:
    members = data.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
    return [repo_root / m for m in members]


def member_source_root(member_dir: Path) -> Path:
    src = member_dir / "src"
    return src if src.is_dir() else member_dir


def iter_py_files(src_root: Path) -> Iterable[Path]:
    for p in src_root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if any(part.startswith(".") for part in p.parts):
            continue
        yield p


def module_name_from_path(src_root: Path, py_file: Path) -> str | None:
    try:
        rel = py_file.relative_to(src_root)
    except ValueError:
        return None
    parts = list(rel.parts)
    if not parts:
        return None
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]  # strip .py
    if not parts:
        return None
    # ignore weird names
    if any(not part.isidentifier() for part in parts):
        return None
    return ".".join(parts)


def add_prefixes(mod: str, acc: set[str]) -> None:
    parts = mod.split(".")
    for i in range(1, len(parts) + 1):
        acc.add(".".join(parts[:i]))


@dataclass(frozen=True)
class ImportOccur:
    file: Path
    lineno: int
    col: int
    stmt: str | None  # reconstructed / full segment if available
    kind: str  # module|symbol|star
    aliased: bool
    relative_level: int
    local: bool
    type_checking: bool
    try_importerror: bool
    conditional: bool  # if-guarded but not TYPE_CHECKING


def is_type_checking_test(test: ast.AST) -> bool:
    # TYPE_CHECKING
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    # typing.TYPE_CHECKING
    if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
        v = test.value
        if isinstance(v, ast.Name) and v.id == "typing":
            return True
    return False


def resolve_relative(importer: str, level: int, module: str | None) -> str | None:
    """
    Resolve 'from ...module import ...' to an absolute module string,
    based on importer module name.
    """
    if level == 0:
        return module
    # importer "a.b.c" => current package is "a.b" if this is a module file;
    # since importer is a module name (not file), treat it as "a.b.c" and drop one to get package.
    pkg_parts = importer.split(".")[:-1]  # package containing the module
    if level > len(pkg_parts) + 1:
        return None
    base = pkg_parts[: len(pkg_parts) - (level - 1)]
    if module:
        base += module.split(".")
    return ".".join(base) if base else module


def longest_internal_prefix(name: str, internal: set[str]) -> str | None:
    """
    Return the longest prefix of `name` (including itself) that exists in `internal`.
    `internal` should include prefixes.
    """
    parts = name.split(".")
    for i in range(len(parts), 0, -1):
        cand = ".".join(parts[:i])
        if cand in internal:
            return cand
    return None


class ImportCollector(ast.NodeVisitor):
    def __init__(self, *, file: Path, importer: str, source: str):
        self.file = file
        self.importer = importer
        self.source = source

        # context flags
        self._func_depth = 0
        self._type_checking_depth = 0
        self._try_importerror_depth = 0
        self._conditional_depth = 0

        self.occurs: list[tuple[str | None, ImportOccur, list[str] | None]] = []
        # Each entry: (raw_module_string, occur, imported_names_for_from)

    def _stmt_segment(self, node: ast.AST) -> str | None:
        seg = ast.get_source_segment(self.source, node)
        if seg is None:
            return None
        seg = " ".join(seg.strip().split())
        return seg

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._func_depth += 1
        self.generic_visit(node)
        self._func_depth -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._func_depth += 1
        self.generic_visit(node)
        self._func_depth -= 1

    def visit_Try(self, node: ast.Try) -> None:
        has_importerror = any(
            isinstance(h.type, ast.Name)
            and h.type.id == "ImportError"
            or isinstance(h.type, ast.Attribute)
            and h.type.attr == "ImportError"
            for h in node.handlers
            if h.type is not None
        )
        if has_importerror:
            self._try_importerror_depth += 1
        self.generic_visit(node)
        if has_importerror:
            self._try_importerror_depth -= 1

    def visit_If(self, node: ast.If) -> None:
        is_tc = is_type_checking_test(node.test)
        if is_tc:
            self._type_checking_depth += 1
        else:
            self._conditional_depth += 1
        self.generic_visit(node)
        if is_tc:
            self._type_checking_depth -= 1
        else:
            self._conditional_depth -= 1

    def visit_Import(self, node: ast.Import) -> None:
        aliased = any(a.asname is not None for a in node.names)
        occ = ImportOccur(
            file=self.file,
            lineno=node.lineno,
            col=node.col_offset,
            stmt=self._stmt_segment(node),
            kind="module",
            aliased=aliased,
            relative_level=0,
            local=self._func_depth > 0,
            type_checking=self._type_checking_depth > 0,
            try_importerror=self._try_importerror_depth > 0,
            conditional=self._conditional_depth > 0 and self._type_checking_depth == 0,
        )
        for a in node.names:
            self.occurs.append((a.name, occ, None))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        imported_names = [a.name for a in node.names]
        aliased = any(a.asname is not None for a in node.names)
        kind = "star" if any(a.name == "*" for a in node.names) else "symbol"
        occ = ImportOccur(
            file=self.file,
            lineno=node.lineno,
            col=node.col_offset,
            stmt=self._stmt_segment(node),
            kind=kind,
            aliased=aliased,
            relative_level=node.level or 0,
            local=self._func_depth > 0,
            type_checking=self._type_checking_depth > 0,
            try_importerror=self._try_importerror_depth > 0,
            conditional=self._conditional_depth > 0 and self._type_checking_depth == 0,
        )
        raw = node.module  # may be None for "from . import x"
        self.occurs.append((raw, occ, imported_names))
        self.generic_visit(node)


def discover_members(repo_root: Path) -> list[Path]:
    data = read_pyproject(repo_root)
    member_dirs = read_workspace_members(repo_root, data)
    if not member_dirs:
        member_dirs = [repo_root]
    return [m for m in member_dirs if m.is_dir()]


def build_internal_index(src_roots: list[Path]) -> tuple[set[str], dict[str, Path]]:
    modules: set[str] = set()
    mod_to_file: dict[str, Path] = {}

    for src_root in src_roots:
        for f in iter_py_files(src_root):
            mod = module_name_from_path(src_root, f)
            if not mod:
                continue
            # map the module name to its defining file (best-effort; last wins)
            mod_to_file[mod] = f
            add_prefixes(mod, modules)

    return modules, mod_to_file


def resolve_import_edge(
    *,
    importer: str,
    raw_module: str | None,
    occur: ImportOccur,
    imported_names: list[str] | None,
    internal_modules: set[str],
) -> str | None:
    """
    Return a resolved internal module name for the imported side, or None if external/unknown.
    """
    if occur.kind == "module":
        if raw_module is None:
            return None
        return longest_internal_prefix(raw_module, internal_modules)

    # from-import: resolve base (possibly relative)
    base = resolve_relative(importer, occur.relative_level, raw_module)
    if not base:
        return None

    # If the base itself is internal, that's at least a dependency
    base_res = longest_internal_prefix(base, internal_modules)

    # If importing a name that corresponds to a submodule, prefer that (more precise)
    if imported_names and occur.kind != "star":
        for name in imported_names:
            if name == "*":
                continue
            cand = f"{base}.{name}"
            cand_res = longest_internal_prefix(cand, internal_modules)
            if cand_res is not None:
                return cand_res

    return base_res


def format_flags(occurs: list[ImportOccur]) -> str:
    kind_counts = Counter(o.kind for o in occurs)
    flags = []
    for k in ("module", "symbol", "star"):
        if kind_counts.get(k):
            flags.append(f"{k}×{kind_counts[k]}")
    aliased = sum(1 for o in occurs if o.aliased)
    if aliased:
        flags.append(f"aliased×{aliased}")
    local = sum(1 for o in occurs if o.local)
    if local:
        flags.append(f"local×{local}")
    tc = sum(1 for o in occurs if o.type_checking)
    if tc:
        flags.append(f"type_checking×{tc}")
    tie = sum(1 for o in occurs if o.try_importerror)
    if tie:
        flags.append(f"try_importerror×{tie}")
    cond = sum(1 for o in occurs if o.conditional)
    if cond:
        flags.append(f"conditional×{cond}")
    return " [" + " ".join(flags) + "]" if flags else ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Print internal import edges (AST-based).")
    ap.add_argument("--include-external", action="store_true", help="Include edges to non-internal modules.")
    ap.add_argument("--locations", action="store_true", help="Include file:line locations.")
    ap.add_argument(
        "--code", action="store_true", help="Include reconstructed import statement (best-effort)."
    )
    ap.add_argument("--max-locations", type=int, default=3, help="Max locations printed per edge.")
    ap.add_argument("--focus-importer", type=str, default=None, help="Only show importers with this prefix.")
    ap.add_argument(
        "--focus-imported", type=str, default=None, help="Only show imported modules with this prefix."
    )
    args = ap.parse_args()

    repo_root = find_repo_root(Path(__file__).parent)
    member_dirs = discover_members(repo_root)
    src_roots = [member_source_root(m) for m in member_dirs]

    # Ensure workspace roots are importable if you later add runtime resolution (not used here),
    # but harmless and often convenient.
    for p in reversed(src_roots):
        sys.path.insert(0, str(p))

    internal_modules, mod_to_file = build_internal_index(src_roots)

    # edge -> occurrences
    edge_occurs: dict[tuple[str, str], list[ImportOccur]] = defaultdict(list)

    # Walk and parse
    for src_root in src_roots:
        for f in iter_py_files(src_root):
            importer = module_name_from_path(src_root, f)
            if not importer:
                continue
            if args.focus_importer and not importer.startswith(args.focus_importer):
                continue

            try:
                source = f.read_text("utf-8")
            except OSError:
                continue

            try:
                tree = ast.parse(source, filename=str(f))
            except SyntaxError:
                continue

            coll = ImportCollector(file=f, importer=importer, source=source)
            coll.visit(tree)

            for raw_module, occ, imported_names in coll.occurs:
                imported = resolve_import_edge(
                    importer=importer,
                    raw_module=raw_module,
                    occur=occ,
                    imported_names=imported_names,
                    internal_modules=internal_modules,
                )
                if imported is None:
                    if not args.include_external:
                        continue
                    # For externals, keep the best raw label we can
                    if occ.kind == "module":
                        imported = raw_module or "<unknown>"
                    else:
                        imported = resolve_relative(importer, occ.relative_level, raw_module) or "<unknown>"

                if args.focus_imported and not imported.startswith(args.focus_imported):
                    continue

                edge_occurs[(importer, imported)].append(occ)

    if not edge_occurs:
        raise SystemExit("No import edges found (check filters, SKIP_DIRS, or repo layout).")

    # Summaries (distinct deps)
    fan_out = Counter()
    fan_in = Counter()
    for importer, imported in edge_occurs:
        fan_out[importer] += 1
        fan_in[imported] += 1

    print("\nTop importers (distinct deps)")
    for mod, n in fan_out.most_common(10):
        print(f"  {mod} ({n})")

    print("\nTop imported (fan-in)")
    for mod, n in fan_in.most_common(10):
        print(f"  {mod} ({n})")

    print("\nImports (grouped)")
    # Sort by occurrence count desc, then importer/imported
    for (importer, imported), occs in sorted(
        edge_occurs.items(), key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1])
    ):
        flags = format_flags(occs)
        print(f"{importer}  →  {imported}  ({len(occs)}){flags}")

        if args.locations:
            # stable order: file, line, col
            shown = 0
            for o in sorted(occs, key=lambda x: (str(x.file), x.lineno, x.col)):
                if shown >= args.max_locations:
                    break
                loc = f"{o.file}:{o.lineno}"
                if args.code and o.stmt:
                    print(f"  - {loc}: {o.stmt}")
                else:
                    print(f"  - {loc}")
                shown += 1
            if len(occs) > shown:
                print(f"  … +{len(occs) - shown} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
