#!/usr/bin/env python3
"""Spec preflight scan — v1.13 SHM Phase 0 + Phase 1.

When a new spec is about to be authored / ingested, scan kata-managed
pages AND configured external sources for related prior specs (by tag
overlap, title overlap, and wikilink references) and print a ranked
list. The author (human or agent) reads this list and decides whether
to declare relationships in the new spec before ingest.

Phase 0 (shipped 2026-05-16, v2.2.0):
- Scan kata-managed wiki pages whose frontmatter `type` ∈ spec_types
- Advisory only — no enforcement, no auto-propagation

Phase 1 (this version):
- Scan external sources via `.wiki-plugins.yaml` `external_sources` array
- `treatment: active|raw|frozen` controls default scope
- URI scheme `external://<source-name>/<path>` for external relationship targets
- External candidates are flagged `writeable: false` — Phase 3
  auto-propagation will skip them

Phase 2+ (future):
- Enforced relationship declaration (Phase 2)
- Auto-propagation of supersedes / refines (Phase 3)
- Lineage view via wiki-graph --spec-history (Phase 4)

Spec types are configured in SCHEMA.md under `spec_authoring.spec_types`.
External sources are configured in `.wiki-plugins.yaml`'s
`external_sources:` block (separate from v1.10's `external_plugins:`).

Default: prd, design, rfc, adr, task-spec, decisions.

Usage:

    spec_preflight.py --new-spec <path-to-new-spec-file>
    spec_preflight.py --new-spec <path> --wiki <path> --limit 20
    spec_preflight.py --new-spec <path> --include-archived
    spec_preflight.py --new-spec <path> --no-external
    spec_preflight.py --new-spec <path> --include-frozen-external

The new spec file need not exist in the wiki yet — typically it's a
draft sitting in raw/ or a separate working directory. The script
parses its frontmatter to discover title, tags, and wikilinks for
matching against the wiki + external sources.

Output: JSON envelope with candidates ranked by relevance score.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

from wiki_lib import (
    _parse_yaml_block,
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


def _load_external_sources(wiki_root: Path) -> list[dict]:
    """Read .wiki-plugins.yaml and return the external_sources array.

    Returns [] if the file doesn't exist or has no external_sources block.
    Each entry is the raw YAML dict; caller validates required fields.
    """
    pf = wiki_root / ".wiki-plugins.yaml"
    if not pf.is_file():
        return []
    try:
        text = pf.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        parsed = _parse_yaml_block(text)
    except Exception:
        return []
    sources = parsed.get("external_sources") or []
    if not isinstance(sources, list):
        return []
    return sources


def _enumerate_external_pages(source: dict, spec_types_set: set[str]) -> list[dict]:
    """Walk a directory-type external source, return spec-typed pages.

    Each returned dict has: path (filesystem absolute), uri (external://
    scheme), title, type, tags, body. Does NOT compute hub centrality —
    external pages don't participate in the kata-internal graph.
    """
    if source.get("type") != "directory":
        return []  # Phase 1 only supports directory; future: git-remote, etc.
    root_raw = source.get("root")
    if not root_raw:
        return []
    root = Path(os.path.expanduser(str(root_raw))).resolve()
    if not root.is_dir():
        return []

    discover = source.get("discover") or {}
    if not isinstance(discover, dict):
        discover = {}
    type_field = discover.get("type_field") or "type"
    exclude_patterns = discover.get("exclude") or []
    if not isinstance(exclude_patterns, list):
        exclude_patterns = []
    # Phase 1 keeps the discover.pattern simple: walk all *.md under root.
    # Future phase can wire a full glob; the schema allows the pattern but
    # we deliberately keep enumeration deterministic and stdlib-only here.

    name = source.get("name", "unnamed")
    pages: list[dict] = []
    for filepath in root.rglob("*.md"):
        try:
            rel = filepath.relative_to(root).as_posix()
        except ValueError:
            continue
        # Apply excludes (Phase 1: simple substring match — keep deterministic)
        excluded = any(pat and pat in rel for pat in exclude_patterns)
        if excluded:
            continue
        try:
            text = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        fm, body = parse_frontmatter(text)
        page_type = str(fm.get(type_field) or "")
        if page_type not in spec_types_set:
            continue
        title = str(fm.get("title") or filepath.stem)
        tags_raw = fm.get("tags") or []
        if not isinstance(tags_raw, list):
            tags_raw = [tags_raw]
        tags = [str(t).lower() for t in tags_raw if t]
        pages.append({
            "fs_path": str(filepath),
            "rel_path": rel,
            "uri": f"external://{name}/{rel}",
            "title": title,
            "type": page_type,
            "tags": tags,
            "body": body,
            "source_name": name,
            "source_treatment": source.get("treatment", "raw"),
        })
    return pages


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
    p.add_argument("--no-external", action="store_true",
                   help="Skip external source enumeration (Phase 1). By "
                        "default, external sources with treatment=raw OR "
                        "treatment=active are scanned. Useful for "
                        "kata-only diagnostic runs.")
    p.add_argument("--include-frozen-external", action="store_true",
                   help="Also scan external sources with treatment=frozen "
                        "(default: only active+raw treatments).")
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

    # Phase 1: enumerate + score external sources
    external_sources_scanned: list[dict] = []
    external_skipped: list[dict] = []
    if not args.no_external:
        ext_sources = _load_external_sources(root)
        allowed_treatments = {"active", "raw"}
        if args.include_frozen_external:
            allowed_treatments.add("frozen")
        for src in ext_sources:
            if not isinstance(src, dict):
                continue
            name = src.get("name", "unnamed")
            treatment = src.get("treatment", "raw")
            if treatment not in allowed_treatments:
                external_skipped.append({
                    "name": name,
                    "reason": (
                        f"treatment={treatment} excluded "
                        f"(allowed={sorted(allowed_treatments)})"
                    ),
                })
                continue
            t0 = time.perf_counter()
            ext_pages = _enumerate_external_pages(src, spec_types_set)
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)

            ext_scored = 0
            for ext in ext_pages:
                # Score external candidate using same heuristics as kata
                # pages, minus hub centrality (no graph index for external).
                ext_title_terms = {
                    t.lower() for t in re.findall(r"[a-zA-Z0-9]+", ext["title"])
                    if len(t) > 2
                }
                title_overlap = len(new_title_terms & ext_title_terms)

                ext_tags = set(ext["tags"])
                tag_overlap = len(new_tags & ext_tags)

                # Wikilink reference: did the new spec link to this external
                # page by stem (e.g. [[old-spec]] → external://X/old-spec.md)?
                ext_stem = Path(ext["rel_path"]).stem.lower()
                link_reference = ext_stem in new_links

                if title_overlap == 0 and tag_overlap == 0 and not link_reference:
                    continue

                # Score formula matches kata-side, with hub set to 0 and a
                # small penalty (-0.5) reflecting "external = lower
                # authority by default — kata-managed pages are more
                # canonical." Tunable in Phase 2+.
                score = (
                    3.0 * (1 if link_reference else 0)
                    + 2.0 * title_overlap
                    + 1.5 * tag_overlap
                    + 0.0  # hub_score: 0 for external
                    - 0.5  # external authority penalty
                )
                ext_type = ext["type"]
                type_match = bool(new_type and ext_type == new_type)
                if type_match:
                    score += 1.0

                results.append({
                    "path": ext["uri"],
                    "fs_path": ext["fs_path"],
                    "title": ext["title"],
                    "type": ext_type,
                    "tier": "external",
                    "source": ext["source_name"],
                    "source_treatment": ext["source_treatment"],
                    "writeable": False,
                    "score": round(score, 2),
                    "signals": {
                        "title_overlap": title_overlap,
                        "tag_overlap": tag_overlap,
                        "link_reference": link_reference,
                        "hub_score": 0.0,
                        "type_match": type_match,
                        "external_penalty": -0.5,
                    },
                })
                ext_scored += 1

            external_sources_scanned.append({
                "name": name,
                "treatment": treatment,
                "page_count": len(ext_pages),
                "scored_count": ext_scored,
                "elapsed_ms": elapsed_ms,
            })

    # Rank: highest score first; stable tiebreak by path
    results.sort(key=lambda r: (-r["score"], r["path"]))
    results = results[:args.limit]

    # Tier breakdown across full candidate pool (before --limit) for the
    # caller's coverage shape signal — same pattern as search_naive.py.
    tier_breakdown = {"active": 0, "archived": 0, "frozen": 0, "external": 0}
    for page in candidates:
        t = tier_map[page.path]
        if t in tier_breakdown:
            tier_breakdown[t] += 1
    # Add external counts from scanned sources
    for src_diag in external_sources_scanned:
        tier_breakdown["external"] += src_diag["scored_count"]

    phase = 1 if external_sources_scanned or external_skipped or not args.no_external else 0

    emit({
        "new_spec": str(new_spec_path),
        "new_spec_title": new_title,
        "new_spec_type": new_type,
        "new_spec_tags": sorted(new_tags),
        "new_spec_wikilinks": sorted(new_links),
        "spec_types_configured": sorted(spec_types_set),
        "tier_filter": sorted(allowed_tiers),
        "tier_breakdown": tier_breakdown,
        "external_sources_scanned": external_sources_scanned,
        "external_skipped": external_skipped,
        "candidates_found": len(results),
        "candidates": results,
        "advisory": (
            "Phase 0+1 (advisory): The author (human or agent) should read "
            "these candidates and declare relationships in the new spec's "
            "frontmatter under `spec_relationships:` before ingest. External "
            "candidates use the URI scheme `external://<source>/<path>`; "
            "Phase 3 auto-propagation will NOT modify external pages (the "
            "`writeable: false` flag enforces this contract). Phase 2 will "
            "enforce relationship declaration for above-threshold candidates."
        ),
        "phase": phase,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
