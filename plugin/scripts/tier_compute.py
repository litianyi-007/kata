#!/usr/bin/env python3
"""Tier computation and distribution for kata.

Wraps wiki_lib.compute_tier so wiki-tier doesn't have to rederive.

Usage:
    tier_compute.py --wiki <path> [--show]
    tier_compute.py --wiki <path> --preview --set-active 540 --set-archived 1095
    tier_compute.py --wiki <path> --list active
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path

from wiki_lib import (
    compute_tier,
    discover_pages,
    emit,
    find_wiki_root,
    load_schema,
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wiki", default=None)
    p.add_argument("--show", action="store_true")
    p.add_argument("--preview", action="store_true")
    p.add_argument("--set-active", type=int, dest="set_active")
    p.add_argument("--set-archived", type=int, dest="set_archived")
    p.add_argument("--set-field", dest="set_field")
    p.add_argument("--list", dest="list_tier",
                   choices=["active", "archived", "frozen"])
    args = p.parse_args()

    root = find_wiki_root(args.wiki)
    schema = load_schema(root)
    pages = discover_pages(root)

    current_tiers = {p.path: compute_tier(p, schema) for p in pages}

    proposed_schema = copy.deepcopy(schema)
    proposed_tiers = current_tiers
    delta = None
    if args.set_active or args.set_archived or args.set_field:
        mt = proposed_schema.setdefault("memory_tiers", {})
        if not isinstance(mt, dict):
            mt = {}
            proposed_schema["memory_tiers"] = mt
        if args.set_active:
            mt["active_days"] = args.set_active
        if args.set_archived:
            mt["archived_days"] = args.set_archived
        if args.set_field:
            mt["driving_field"] = args.set_field
        proposed_tiers = {p.path: compute_tier(p, proposed_schema) for p in pages}
        delta = _delta(current_tiers, proposed_tiers)

    if args.list_tier:
        emit({
            "wiki": str(root),
            "tier": args.list_tier,
            "pages": [p.path for p in pages
                      if current_tiers[p.path] == args.list_tier],
        })
        return 0

    payload = {
        "wiki": str(root),
        "config": schema.get("memory_tiers") or {"enabled": False},
        "distribution": _distribution(current_tiers),
        "total_pages": len(pages),
        "pinned_overrides": [
            {"page": p.path, "tier": p.frontmatter.get("tier_override")}
            for p in pages
            if p.frontmatter.get("tier_override")
        ],
    }
    if delta:
        payload["proposed_config"] = proposed_schema.get("memory_tiers")
        payload["proposed_distribution"] = _distribution(proposed_tiers)
        payload["delta"] = delta
        payload["preview_only"] = bool(args.preview)
    emit(payload)
    return 0


def _distribution(tier_map: dict[str, str]) -> dict[str, int]:
    out = {"active": 0, "archived": 0, "frozen": 0}
    for t in tier_map.values():
        out[t] = out.get(t, 0) + 1
    return out


def _delta(before: dict[str, str], after: dict[str, str]) -> list[dict]:
    return [
        {"page": k, "from": before[k], "to": after[k]}
        for k in before if before[k] != after[k]
    ]


if __name__ == "__main__":
    raise SystemExit(main())
