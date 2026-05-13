#!/usr/bin/env python3
"""Deterministic 3-pass naive search for kata.

The wiki-search skill shells out to this script when qmd is not available.
Order: index.md scan → frontmatter scan → body scan. Ranking is
deterministic so two runs over the same wiki produce identical output —
which is what makes wiki-search testable.

Usage:
    search_naive.py --wiki <path> --query "..." [--tag T] [--type entity]
        [--limit 10] [--tier active|archived|frozen|all]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from wiki_lib import (
    build_graph,
    compute_tier,
    discover_pages,
    emit,
    find_wiki_root,
    hub_score,
    load_schema,
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wiki", default=None)
    p.add_argument("--query", required=True)
    p.add_argument("--tag", default=None)
    p.add_argument("--type", dest="type_filter", default=None)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--tier", default=None,
                   choices=["active", "archived", "frozen", "all"])
    args = p.parse_args()

    root = find_wiki_root(args.wiki)
    schema = load_schema(root)
    pages = discover_pages(root)
    if not pages:
        emit({"query": args.query, "results": [], "total": 0,
              "passes": {"index": 0, "frontmatter": 0, "body": 0}})
        return 0

    # Resolve [[wikilinks]] so each page knows its in_links count — this is
    # what hub centrality scores against. build_graph mutates pages in place.
    build_graph(pages)

    tier_map = {p.path: compute_tier(p, schema) for p in pages}

    # Default tier filter: active when tiers enabled, else all.
    tier_filter = args.tier
    if tier_filter is None:
        mt = schema.get("memory_tiers")
        if isinstance(mt, dict) and mt.get("enabled", True):
            tier_filter = "active"
        else:
            tier_filter = "all"

    query_terms = [t.lower() for t in re.findall(r"[a-zA-Z0-9_-]+", args.query)
                   if len(t) > 1]
    if not query_terms:
        emit({"error": "query has no usable terms"})
        return 2

    # Pass 1: index.md
    pass1 = _scan_index(root, query_terms, pages)

    # Pass 2: frontmatter (title, tags, type)
    pass2 = _scan_frontmatter(pages, query_terms, args.tag, args.type_filter)

    # Pass 3: body (only if pass 1+2 yielded < 3 results)
    candidate_set = pass1 | pass2
    pass3 = set()
    if len(candidate_set) < 3:
        pass3 = _scan_body(pages, query_terms) - candidate_set

    all_candidates = pass1 | pass2 | pass3

    # Apply tier filter and type/tag filters (re-applied for pass3 hits)
    filtered = []
    for pid in all_candidates:
        page = next(p for p in pages if p.path == pid)
        if tier_filter != "all" and tier_map[pid] != tier_filter:
            continue
        if args.tag:
            tags = page.frontmatter.get("tags") or []
            if args.tag not in (tags if isinstance(tags, list) else [tags]):
                continue
        if args.type_filter:
            if page.frontmatter.get("type") != args.type_filter:
                continue
        filtered.append(page)

    # Rank order (higher is better, negated for sort-ascending):
    #   1. title match  — direct relevance
    #   2. frontmatter tag match
    #   3. hub centrality — well-connected pages outrank fringe ones at parity
    #   4. body match count
    #   5. recency (`updated`)
    #   6. path (deterministic tiebreak)
    def rank_key(p):
        title_match = sum(1 for t in query_terms if t in p.title.lower())
        tag_match = 0
        tags = p.frontmatter.get("tags") or []
        if isinstance(tags, list):
            tag_match = sum(1 for t in query_terms
                            for tg in tags if t in str(tg).lower())
        body_match = sum(p.body.lower().count(t) for t in query_terms)
        hub = hub_score(p)
        updated = str(p.frontmatter.get("updated") or "0000-00-00")
        return (-title_match, -tag_match, -hub, -body_match,
                _negstr(updated), p.path)

    filtered.sort(key=rank_key)
    top = filtered[:args.limit]

    # Build "tier hint" for results suppressed by tier filter
    suppressed = {"active": 0, "archived": 0, "frozen": 0}
    if tier_filter != "all":
        for pid in all_candidates:
            t = tier_map.get(pid)
            if t and t != tier_filter:
                suppressed[t] += 1

    # Aggregate tier distribution over the full unfiltered match set.
    # Lets a caller see "this query has X active / Y archived coverage"
    # without scanning every result.
    tier_breakdown = {"active": 0, "archived": 0, "frozen": 0}
    for pid in all_candidates:
        t = tier_map.get(pid)
        if t in tier_breakdown:
            tier_breakdown[t] += 1
    total_matches = sum(tier_breakdown.values())
    low_active_coverage = (
        total_matches >= 3
        and tier_breakdown["active"] / total_matches < 0.2
    )

    emit({
        "query": args.query,
        "tier_filter": tier_filter,
        "passes": {"index": len(pass1), "frontmatter": len(pass2),
                   "body": len(pass3)},
        "tier_breakdown": tier_breakdown,
        "low_active_coverage": low_active_coverage,
        "results": [
            {
                "path": p.path,
                "title": p.title,
                "type": p.frontmatter.get("type"),
                "tags": p.frontmatter.get("tags") or [],
                "tier": tier_map[p.path],
                "excerpt": _excerpt(p.body, query_terms),
            } for p in top
        ],
        "total": len(filtered),
        "suppressed_other_tiers": suppressed,
    })
    return 0


def _negstr(s: str) -> str:
    """Inverse-lex sort key so newer dates sort before older."""
    # Map each char to its complement so sort-ascending yields newest first
    return "".join(chr(0x10FFFF - ord(c)) if ord(c) <= 0x10FFFE else c
                   for c in s)


def _scan_index(root: Path, terms: list[str], pages) -> set:
    idx = root / "index.md"
    if not idx.exists():
        return set()
    text = idx.read_text(encoding="utf-8").lower()
    hits = set()
    by_path = {p.path: p for p in pages}
    for line in text.splitlines():
        if any(t in line for t in terms):
            for path in by_path:
                if path.lower() in line or Path(path).stem.lower() in line:
                    hits.add(path)
    return hits


def _scan_frontmatter(pages, terms, tag_filter, type_filter) -> set:
    hits = set()
    for p in pages:
        title = (p.title or "").lower()
        tags = p.frontmatter.get("tags") or []
        type_val = p.frontmatter.get("type")
        if tag_filter and tag_filter not in (tags if isinstance(tags, list) else [tags]):
            pass
        if any(t in title for t in terms):
            hits.add(p.path)
            continue
        if isinstance(tags, list):
            joined = " ".join(str(x).lower() for x in tags)
            if any(t in joined for t in terms):
                hits.add(p.path)
                continue
        if type_filter and type_val == type_filter:
            hits.add(p.path)
    return hits


def _scan_body(pages, terms) -> set:
    hits = set()
    for p in pages:
        body_l = p.body.lower()
        if any(t in body_l for t in terms):
            hits.add(p.path)
    return hits


def _excerpt(body: str, terms: list[str], pad: int = 60) -> str:
    # Prefer body-content matches over heading matches. Wiki pages tend to
    # repeat the title's keywords in H1/H2; matching the first occurrence
    # then yielded excerpts that were just "# Title  ## Section Header …"
    # with no substantive content. Strip heading lines first; fall back to
    # the raw match if the body has no non-heading hit.
    cleaned = re.sub(r"(?m)^#+[ \t].*$", "", body)
    cleaned = re.sub(r"[ \t]*\n+[ \t]*", " ", cleaned).strip()
    cleaned_l = cleaned.lower()
    for t in terms:
        i = cleaned_l.find(t)
        if i >= 0:
            start = max(0, i - pad)
            end = min(len(cleaned), i + len(t) + pad)
            snippet = cleaned[start:end].strip()
            if snippet:
                return (("…" if start > 0 else "") + snippet
                        + ("…" if end < len(cleaned) else ""))
    # Fallback: original heading-inclusive behavior — only reached when
    # the term occurs solely inside heading lines.
    body_l = body.lower()
    for t in terms:
        i = body_l.find(t)
        if i >= 0:
            start = max(0, i - pad)
            end = min(len(body), i + len(t) + pad)
            return (("…" if start > 0 else "")
                    + body[start:end].replace("\n", " ")
                    + ("…" if end < len(body) else ""))
    return body[:120].replace("\n", " ") + "…"


if __name__ == "__main__":
    sys.exit(main())
