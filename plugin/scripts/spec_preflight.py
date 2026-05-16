#!/usr/bin/env python3
"""Spec preflight scan — v1.13 SHM Phase 0.

When a new spec is about to be authored / ingested, scan the wiki for
related prior specs (by tag overlap, title overlap, and wikilink
references) and print a ranked list. The author (human or agent) reads
this list and decides whether to declare relationships in the new spec
before ingest.

Phase 0 is **advisory only**:
- No enforcement (Phase 2 will require relationship declaration)
- No auto-propagation (Phase 3 will update related specs)
- No external sources (Phase 1 will add `.wiki-plugins.yaml` integration)

Spec types are configured in SCHEMA.md under `spec_authoring.spec_types`.
Default: prd, design, rfc, adr, task-spec.

Usage:

    spec_preflight.py --new-spec <path-to-new-spec-file>
    spec_preflight.py --new-spec <path> --wiki <path> --limit 20
    spec_preflight.py --new-spec <path> --include-archived

The new spec file need not exist in the wiki yet — typically it's a
draft sitting in raw/ or a separate working directory. The script
parses its frontmatter to discover title, tags, and wikilinks for
matching against the wiki.

Output: JSON envelope with candidates ranked by relevance score.
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
    extract_links,
    find_wiki_root,
    hub_score,
    load_schema,
    parse_frontmatter,
)


# Default spec types if SCHEMA.md has no spec_authoring config.
#
# Covers two adoption modes:
# 1. SDD / superpowers / fresh-project authoring: uses prd / design / rfc /
#    adr / task-spec as page types
# 2. Kata-native wikis with conventions used at scale (e.g. NECallKit): uses
#    `decisions/` as the spec-like category (ratified positions, dated)
#
# Users override per-wiki by setting `spec_authoring.spec_types` in SCHEMA.md.
DEFAULT_SPEC_TYPES = ["prd", "design", "rfc", "adr", "task-spec", "decisions"]


def main() -> int:
    p = argparse.ArgumentParser(
        description="Spec preflight scan: list prior specs related to a new "
                    "draft, advisory only (Phase 0)."
    )
    p.add_argument("--wiki", default=None,
                   help="Wiki root path. If omitted, find_wiki_root() resolves it.")
    p.add_argument("--new-spec", required=True,
                   help="Path to the new spec file being authored "
                        "(need not exist in wiki yet).")
    p.add_argument("--limit", type=int, default=10,
                   help="Max number of candidates to return (default: 10).")
    p.add_argument("--include-archived", action="store_true",
                   help="Include archived-tier pages in candidate set "
                        "(default: active only). Frozen pages are always "
                        "excluded unless --include-frozen is also set.")
    p.add_argument("--include-frozen", action="store_true",
                   help="Include frozen-tier pages in candidate set "
                        "(default: false). Implies --include-archived.")
    args = p.parse_args()

    # Read the new spec file
    new_spec_path = Path(args.new_spec).expanduser()
    if not new_spec_path.is_file():
        emit({"error": f"new-spec not found: {new_spec_path}"})
        return 2
    new_text = new_spec_path.read_text(encoding="utf-8")
    new_fm, new_body = parse_frontmatter(new_text)
    new_title = str(new_fm.get("title") or new_spec_path.stem)
    new_type = new_fm.get("type")

    new_tags_raw = new_fm.get("tags") or []
    if not isinstance(new_tags_raw, list):
        new_tags_raw = [new_tags_raw]
    new_tags = {str(t).lower() for t in new_tags_raw if t}

    # Wikilinks in the new spec body — strong signal that the author is
    # already aware of those pages. We treat each link as an explicit
    # relationship hint.
    new_links_raw = extract_links(new_body)
    new_links = {Path(link).stem.lower() for link in new_links_raw}

    # Title terms for matching (drop short tokens to reduce noise)
    new_title_terms = {
        t.lower() for t in re.findall(r"[a-zA-Z0-9]+", new_title)
        if len(t) > 2
    }

    # Load wiki
    root = find_wiki_root(args.wiki)
    schema = load_schema(root)
    pages = discover_pages(root)
    if not pages:
        emit({
            "new_spec": str(new_spec_path),
            "new_spec_title": new_title,
            "candidates": [],
            "candidates_found": 0,
            "advisory": "Wiki has no pages.",
        })
        return 0
    build_graph(pages)

    # Configured spec types from SCHEMA.md (with default fallback)
    spec_authoring = schema.get("spec_authoring") or {}
    if not isinstance(spec_authoring, dict):
        spec_authoring = {}
    spec_types_cfg = spec_authoring.get("spec_types")
    if isinstance(spec_types_cfg, list) and spec_types_cfg:
        spec_types = [str(t).lower() for t in spec_types_cfg]
    else:
        spec_types = list(DEFAULT_SPEC_TYPES)
    spec_types_set = set(spec_types)

    # Tier filter
    tier_map = {pg.path: compute_tier(pg, schema) for pg in pages}
    allowed_tiers = {"active"}
    if args.include_archived or args.include_frozen:
        allowed_tiers.add("archived")
    if args.include_frozen:
        allowed_tiers.add("frozen")

    # Filter to spec-type pages in allowed tiers, excluding the new spec
    # itself (in case the new spec is already in the wiki as a stub).
    new_spec_relpath = None
    try:
        new_spec_relpath = new_spec_path.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        # New spec sits outside wiki root — normal case
        pass

    candidates = []
    for page in pages:
        if new_spec_relpath and page.path == new_spec_relpath:
            continue  # skip self
        page_type = page.frontmatter.get("type")
        if page_type not in spec_types_set:
            continue
        if tier_map[page.path] not in allowed_tiers:
            continue
        candidates.append(page)

    # Score each candidate
    results = []
    for page in candidates:
        # Per-iteration read — do NOT reuse the page_type variable from the
        # outer (filter) loop; that one held the last-iteration leftover.
        cand_type = page.frontmatter.get("type")

        # Title overlap
        page_title_terms = {
            t.lower() for t in re.findall(r"[a-zA-Z0-9]+", page.title)
            if len(t) > 2
        }
        title_overlap = len(new_title_terms & page_title_terms)

        # Tag overlap
        page_tags_raw = page.frontmatter.get("tags") or []
        if not isinstance(page_tags_raw, list):
            page_tags_raw = [page_tags_raw]
        page_tags = {str(t).lower() for t in page_tags_raw if t}
        tag_overlap = len(new_tags & page_tags)

        # Wikilink reference: does the new spec body link to this page?
        page_stem = Path(page.path).stem.lower()
        link_reference = page_stem in new_links

        # Hub centrality — well-connected pages are more likely to be
        # canonical anchors that a new spec should explicitly relate to.
        hub = hub_score(page)

        # Skip non-matches (zero signal)
        if title_overlap == 0 and tag_overlap == 0 and not link_reference:
            continue

        # Combined score. Weights are heuristic, tunable in Phase 1+ via
        # schema. Rough intent: explicit link is strongest, then title,
        # then tags, then hub.
        score = (
            3.0 * (1 if link_reference else 0)
            + 2.0 * title_overlap
            + 1.5 * tag_overlap
            + 0.5 * hub
        )

        # Type-match bonus: same-type prior spec is a stronger candidate
        # for explicit relationship declaration than a cross-type page.
        type_match = bool(new_type and cand_type == new_type)
        if type_match:
            score += 1.0

        results.append({
            "path": page.path,
            "title": page.title,
            "type": cand_type,
            "tier": tier_map[page.path],
            "score": round(score, 2),
            "signals": {
                "title_overlap": title_overlap,
                "tag_overlap": tag_overlap,
                "link_reference": link_reference,
                "hub_score": round(hub, 2),
                "type_match": type_match,
            },
        })

    # Rank: highest score first; stable tiebreak by path
    results.sort(key=lambda r: (-r["score"], r["path"]))
    results = results[:args.limit]

    # Tier breakdown across full candidate pool (before --limit) for the
    # caller's coverage shape signal — same pattern as search_naive.py.
    tier_breakdown = {"active": 0, "archived": 0, "frozen": 0}
    for page in candidates:
        t = tier_map[page.path]
        if t in tier_breakdown:
            tier_breakdown[t] += 1

    emit({
        "new_spec": str(new_spec_path),
        "new_spec_title": new_title,
        "new_spec_type": new_type,
        "new_spec_tags": sorted(new_tags),
        "new_spec_wikilinks": sorted(new_links),
        "spec_types_configured": sorted(spec_types_set),
        "tier_filter": sorted(allowed_tiers),
        "tier_breakdown": tier_breakdown,
        "candidates_found": len(results),
        "candidates": results,
        "advisory": (
            "Phase 0 (advisory): The author (human or agent) should read "
            "these candidates and declare relationships in the new spec's "
            "frontmatter under `spec_relationships:` before ingest. Phase 1 "
            "will extend the scan to external sources; Phase 2 will enforce "
            "relationship declaration."
        ),
        "phase": 0,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
