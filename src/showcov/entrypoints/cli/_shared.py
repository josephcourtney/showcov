from __future__ import annotations


def resolve_use_color(*, color: bool, no_color: bool, color_allowed: bool) -> bool:
    # CLI flags take precedence over the IO policy default.
    if no_color:
        return False
    if color:
        return True
    return color_allowed
