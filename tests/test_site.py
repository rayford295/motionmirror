"""Structure checks for the project website (docs/index.html). Stdlib only."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
PAGE = (DOCS / "index.html").read_text(encoding="utf-8")


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: set[str] = set()
        self.refs: list[str] = []
        self.tags: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        for key, val in attrs:
            if key == "id" and val:
                self.ids.add(val)
            if key in ("src", "href", "poster") and val:
                self.refs.append(val)

    def handle_data(self, data):
        self.text.append(data)


def _parsed() -> _Collector:
    c = _Collector()
    c.feed(PAGE)
    return c


def test_sections_present():
    ids = _parsed().ids
    for sid in ("hero", "watch", "results", "tracking", "pipeline", "bonus",
                "examples", "compare", "quickstart"):
        assert sid in ids, sid


def test_local_refs_exist():
    missing = []
    for ref in _parsed().refs:
        if re.match(r"^(https?:|#|mailto:|data:|javascript:)", ref):
            continue
        path = DOCS / ref.split("#")[0].split("?")[0]
        if not path.exists():
            missing.append(ref)
    assert not missing, missing


def test_video_is_click_to_load():
    assert "Kd4xoJ1RMb0" in PAGE
    assert "iframe" not in _parsed().tags


def test_reduced_motion_rule():
    assert "prefers-reduced-motion: reduce" in PAGE


def test_facts_kept():
    text = " ".join(_parsed().text)
    for fact in ("176°", "0.37 s", "3 → 2", "33", "0/2", "2/4", "3/3"):
        assert fact in text, fact
    for slug in ("rayford-basketball", "chen-jingyi-badminton", "yifan-golf-0601",
                 "yifan-basketball-0710", "yifan-golf-0520", "golf-swing-demo"):
        assert slug in PAGE, slug
