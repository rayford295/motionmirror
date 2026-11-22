#!/usr/bin/env python
"""Regenerate the Examples tables in both READMEs from examples/*/report.json.

Every cell comes from the committed reports, so the tables cannot drift from
the artifacts. Run after adding or re-analyzing a session:

    python tools/generate_examples_table.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START, END = "<!-- examples-table:start -->", "<!-- examples-table:end -->"
ICON = {"golf": "⛳ Golf", "basketball": "🏀 Basketball", "badminton": "🏸 Badminton"}
WORD = {"golf": "swing", "basketball": "shot", "badminton": "stroke"}
# Sports featured in the README tables (other sessions stay in examples/).
FEATURED = {"basketball", "badminton"}
# Display order and optional context notes; sessions not listed are appended.
ORDER = [("rayford-basketball", "120 fps"), ("chen-jingyi-badminton", None),
         ("yifan-basketball-0710", "1v1"), ("yifan-golf-0601", None),
         ("yifan-golf-0520", None), ("golf-swing-demo", None)]


def rows() -> list[str]:
    known = [name for name, _ in ORDER]
    extra = sorted(p.parent.name for p in ROOT.glob("examples/*/report.json")
                   if p.parent.name not in known)
    notes = dict(ORDER)
    out = ["| Session | Sport | Clip | Pose frames | Reps | Report |",
           "|---|---|---|---|---|---|"]
    for name in known + extra:
        path = ROOT / "examples" / name / "report.json"
        if not path.exists():
            continue
        r = json.loads(path.read_text(encoding="utf-8"))
        if r["sport"] not in FEATURED:
            continue
        q = r["quality"]
        sport = ICON.get(r["sport"], r["sport"]) + (f" · {notes[name]}" if notes.get(name) else "")
        n = r["rep_count"]
        reps = f"{n} {WORD.get(r['sport'], 'rep')}{'s' if n != 1 else ''}"
        out.append(
            f"| [{name}](examples/{name}/) | {sport} | {q['duration_s']:.1f} s · "
            f"{q['width']}×{q['height']} | {q['pose_frames']} / {q['total_frames']} | {reps} | "
            f"[report.md](examples/{name}/report.md) |")
    return out


def main() -> None:
    table = "\n".join(rows())
    for readme in ("README.md", "README.zh-CN.md"):
        path = ROOT / readme
        text = path.read_text(encoding="utf-8")
        i, j = text.index(START) + len(START), text.index(END)
        path.write_text(text[:i] + "\n" + table + "\n" + text[j:], encoding="utf-8")
        print(f"updated {readme}")


if __name__ == "__main__":
    main()
