#!/usr/bin/env python3
"""Mechanical inputs for wiki-digest — activity counts, tier distribution,
stale dimension list. The skill does the narrative summarization on top
of this JSON.

Usage:
    digest.py --wiki <path> [--since 7d] [--focus <topic>]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from wiki_lib import (
    compute_tier,
    discover_pages,
    emit,
    find_wiki_root,
    load_schema,
    parse_log,
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wiki", default=None)
    p.add_argument("--since", default="7d",
                   help="Window: 7d / 30d / 90d / all")
    p.add_argument("--focus", default=None,
                   help="Restrict to pages tagged with this value")
    args = p.parse_args()

    root = find_wiki_root(args.wiki)
    schema = load_schema(root)
    pages = discover_pages(root)

    cutoff = _parse_since(args.since)
    today = date.today()

    if args.focus:
        pages = [p for p in pages if _has_tag(p, args.focus)]

    # Activity (from log.md)
    activity = _activity(root, cutoff)

    # Inventory
    by_type = Counter()
    by_tag = Counter()
    for p_obj in pages:
        t = p_obj.frontmatter.get("type")
        if t:
            by_type[str(t)] += 1
        tags = p_obj.frontmatter.get("tags") or []
        if isinstance(tags, list):
            for tag in tags:
                by_tag[str(tag).lower()] += 1

    # Tier distribution
    tier_counts = Counter()
    for p_obj in pages:
        tier_counts[compute_tier(p_obj, schema, today=today)] += 1

    # Recent activity — split "newly created" from "updated since cutoff"
    # so the wiki-digest skill can tell the user what's new vs. what was
    # touched. SKILL.md ③ explicitly asks for both signals; before this we
    # only emitted updated-since-cutoff and the skill was forced to fake
    # the "new pages" line from log.md ingest entries.
    recently_updated = []
    recently_created = []
    for p_obj in pages:
        upd = _coerce_date(p_obj.frontmatter.get("updated"))
        crt = _coerce_date(p_obj.frontmatter.get("created"))
        if upd is not None and upd >= cutoff:
            recently_updated.append({
                "path": p_obj.path, "title": p_obj.title, "updated": str(upd),
            })
        if crt is not None and crt >= cutoff:
            recently_created.append({
                "path": p_obj.path, "title": p_obj.title, "created": str(crt),
            })
    recently_updated.sort(key=lambda x: x["updated"], reverse=True)
    recently_created.sort(key=lambda x: x["created"], reverse=True)

    # Stale custom-dimension values (refresh_on includes 'digest')
    stale_dimensions = _stale_dimensions(pages, schema)

    # Hub pages — most-linked-to in the active set
    inbound: Counter = Counter()
    paths = {p.path: p for p in pages}
    title_to_id = {(p.title or "").lower(): p.path for p in pages if p.title}
    stem_to_id = {Path(p.path).stem.lower(): p.path for p in pages}
    for p_obj in pages:
        for link in p_obj.out_links:
            link_l = link.lower()
            tid = title_to_id.get(link_l) or stem_to_id.get(link_l)
            if tid:
                inbound[tid] += 1
    top_hubs = [{"path": pid, "title": paths[pid].title, "inbound": cnt}
                for pid, cnt in inbound.most_common(10)]

    emit({
        "wiki": str(root),
        "since": cutoff.isoformat(),
        "today": today.isoformat(),
        "focus": args.focus,
        "page_count": len(pages),
        "activity": activity,
        "inventory": {
            "by_type": dict(by_type),
            "top_tags": dict(by_tag.most_common(15)),
        },
        "tier_distribution": dict(tier_counts),
        "recently_updated": recently_updated[:20],
        "recently_created": recently_created[:20],
        "top_hubs": top_hubs,
        "stale_dimensions": stale_dimensions,
    })
    return 0


def _coerce_date(value):
    """Best-effort date coercion. Returns date or None."""
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _parse_since(spec: str) -> date:
    if spec == "all":
        return date(1970, 1, 1)
    m = re.fullmatch(r"(\d+)([dwmy])", spec)
    if not m:
        return date.today() - timedelta(days=7)
    n = int(m.group(1))
    unit = m.group(2)
    days = {"d": 1, "w": 7, "m": 30, "y": 365}[unit] * n
    return date.today() - timedelta(days=days)


def _activity(root: Path, cutoff: date) -> dict:
    entries = parse_log(root / "log.md")
    in_window = [e for e in entries if e.date >= cutoff]
    by_action = Counter(e.action for e in in_window)
    return {
        "total_entries_in_window": len(in_window),
        "by_action": dict(by_action),
        "first": in_window[0].date.isoformat() if in_window else None,
        "last": in_window[-1].date.isoformat() if in_window else None,
    }


def _has_tag(p, tag: str) -> bool:
    tags = p.frontmatter.get("tags") or []
    if isinstance(tags, list):
        return tag.lower() in {str(t).lower() for t in tags}
    return False


def _stale_dimensions(pages, schema) -> list[dict]:
    dims = schema.get("custom_dimensions") or []
    targets = []
    for d in dims:
        if not isinstance(d, dict):
            continue
        refresh_on = d.get("refresh_on") or []
        if isinstance(refresh_on, list) and "digest" in refresh_on:
            targets.append(d)
    if not targets:
        return []

    findings = []
    for p_obj in pages:
        page_type = p_obj.frontmatter.get("type")
        for d in targets:
            applies = d.get("applies_to")
            if applies and page_type not in applies:
                continue
            value = p_obj.frontmatter.get(d["name"])
            if value in (None, "", []):
                findings.append({
                    "page": p_obj.path,
                    "dimension": d["name"],
                    "current_value": value,
                })
    return findings


if __name__ == "__main__":
    sys.exit(main())
