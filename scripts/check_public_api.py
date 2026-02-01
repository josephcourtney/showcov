from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    src_path = root / "src"
    sys.path.insert(0, str(src_path))

    try:
        import bvp
        import bvp.api as bvp_api
    except ImportError as exc:
        print(f"[public-api] ERROR: failed to import bvp: {exc}")
        return 1

    api_all = getattr(bvp_api, "__all__", None)
    if not isinstance(api_all, (list, tuple)):
        print("[public-api] ERROR: bvp.api.__all__ must be defined as a list or tuple")
        return 1

    pkg_all = getattr(bvp, "__all__", None)
    if not isinstance(pkg_all, (list, tuple)):
        print("[public-api] ERROR: bvp.__all__ must be defined as a list or tuple")
        return 1

    if list(pkg_all) != list(api_all):
        print("[public-api] ERROR: bvp.__all__ must match bvp.api.__all__ exactly")
        return 1

    missing = [name for name in pkg_all if not hasattr(bvp, name)]
    if missing:
        print(f"[public-api] ERROR: bvp is missing public symbols: {sorted(missing)}")
        return 1

    print("[public-api] OK: public API is explicit and consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
