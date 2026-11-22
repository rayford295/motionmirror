"""Sport profiles. Each module exposes the same interface:

``NAME``, ``PHASES``, ``SIDE_HELP``, ``frame_metrics``, ``build_rows``,
``detect_reps``, ``summarize_rep``, ``CHECKS``, ``CONSISTENCY_KEYS``,
``summarize_sequence``; optionally ``checks_for(summary)`` for per-rep checks.
"""

from __future__ import annotations

from types import ModuleType

from motionmirror.profiles import badminton, basketball, golf

PROFILES: dict[str, ModuleType] = {
    golf.NAME: golf, basketball.NAME: basketball, badminton.NAME: badminton}


def get_profile(name: str) -> ModuleType:
    try:
        return PROFILES[name.lower()]
    except KeyError:
        raise ValueError(f"Unknown sport {name!r}; choose from {sorted(PROFILES)}.") from None


__all__ = ["PROFILES", "badminton", "basketball", "get_profile", "golf"]
