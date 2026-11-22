"""``swingform`` command-line interface.

    swingform analyze VIDEO_OR_POSE_JSON --sport golf --out runs/session1
    swingform highlights LONG_VIDEO --session-id range-day
    swingform register VIDEO --sport golf
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from swingform_ai import __version__
from swingform_ai.profiles import PROFILES


def _analyze(args: argparse.Namespace) -> int:
    from swingform_ai.pipeline import run

    out = args.out or Path("runs") / Path(args.source).stem
    result = run(
        args.source, out, sport=args.sport, side=args.side, model=args.model,
        labels=args.labels, render=not args.no_render, ball_trail=args.ball_trail,
        min_confidence=args.min_confidence, width=args.width, height=args.height,
    )
    report = result.analysis.to_report()
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"\n{report['sport']}: {report['rep_count']} rep(s), side={report['side']}")
    for rep in report["reps"]:
        flagged = [f for f in rep["findings"] if f["status"] in ("low", "high")]
        score = rep.get("score")
        head = f"  rep {rep['index']}: " + (f"{score:.0f}% in range" if score is not None else "")
        print(head + f" (confidence {rep['confidence']:.2f})")
        for f in flagged:
            print(f"    - {f['label']}: {f['message']}")
    for w in report["warnings"]:
        print(f"  note: {w}")
    print("\nWrote:")
    for path in result.files.values():
        print(f"  {path}")
    return 0


def _highlights(args: argparse.Namespace) -> int:
    from swingform_ai import reel

    reel.main(args.rest)
    return 0


def _register(args: argparse.Namespace) -> int:
    from swingform_ai.local_sessions import build_session_manifest, write_manifest

    manifest = build_session_manifest(video_path=args.video, sport=args.sport,
                                      session_id=args.session_id, notes=args.notes,
                                      include_hash=not args.no_hash)
    path = write_manifest(manifest, args.sessions_root)
    print(json.dumps({"manifest_path": str(path), "session_id": manifest["session_id"]}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="swingform", description="Explainable sports posture "
                                     "analysis from ordinary video.")
    parser.add_argument("--version", action="version", version=f"swingform-ai {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="Analyze a video or an exported pose JSON.")
    a.add_argument("source", type=Path, help="Video file (.mp4/.mov/...) or pose .json")
    a.add_argument("--sport", choices=sorted(PROFILES), default="golf")
    a.add_argument("--side", choices=["right", "left", "auto"], default="right",
                   help="Golf handedness or basketball shooting hand; 'auto' tries both.")
    a.add_argument("--out", type=Path, help="Output folder (default: runs/<video name>).")
    a.add_argument("--model", default="full",
                   help="MediaPipe model: lite, full (default), heavy, or a .task path.")
    a.add_argument("--labels", type=Path, help="JSON with hand-marked phase times per rep.")
    a.add_argument("--no-render", action="store_true", help="Skip overlay video and images.")
    a.add_argument("--ball-trail", choices=["off", "detect", "proxy"], default="off",
                   help="Golf only: detect = draw detected ball trail; proxy = also draw a "
                   "dashed, unmeasured arc when detection fails.")
    a.add_argument("--min-confidence", type=float, default=0.0,
                   help="Drop auto-detected reps below this confidence (0-1).")
    a.add_argument("--width", type=int, help="Frame width, for pose JSON without size info.")
    a.add_argument("--height", type=int, help="Frame height, for pose JSON without size info.")
    a.add_argument("--json", action="store_true", help="Print the full report JSON.")
    a.set_defaults(func=_analyze)

    h = sub.add_parser("highlights", help="Cut the best swings from a long practice video.",
                       add_help=False)
    h.add_argument("rest", nargs=argparse.REMAINDER)
    h.set_defaults(func=_highlights)

    r = sub.add_parser("register", help="Write a private local manifest for a practice video.")
    r.add_argument("video", type=Path)
    r.add_argument("--sport", choices=sorted(PROFILES), default="golf")
    r.add_argument("--session-id")
    r.add_argument("--notes", default="")
    r.add_argument("--sessions-root", type=Path, default=Path("data/local/sessions"))
    r.add_argument("--no-hash", action="store_true")
    r.set_defaults(func=_register)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
