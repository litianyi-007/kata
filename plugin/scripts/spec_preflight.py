#!/usr/bin/env python3
"""Spec preflight scan — v1.13 SHM Phase 0 + Phase 2.

When a new spec is about to be authored / ingested, scan kata-managed
pages for related prior specs (by tag overlap, title overlap, and
wikilink references) and print a ranked list. The author (human or
agent) reads this list and decides whether to declare relationships in
the new spec before ingest.

Phase 0 (shipped 2026-05-16, v2.2.0):
- Scan kata-managed wiki pages whose frontmatter `type` ∈ spec_types
- Advisory only — no enforcement, no auto-propagation

Phase 1 (shipped v2.3.0, REMOVED in v2.5.0):
- Was: external source backfill via `.wiki-plugins.yaml`
- Removed 2026-05-17: see ADR
  ~/.llm-wiki/kata/decisions/2026-05-17-external-sources-removed.md
- Short reason: reaching outside `{wiki_path}/` violated the
  self-closing principle; cross-source needs are served by `wiki-import`
  (human-curated bulk ingest) or v1.12 cross-wiki federation
  (kata-to-kata cooperation).

Phase 2 (shipped 2026-05-16, v2.4.0):
- `--enforce` mode parses the new spec's `spec_relationships:` block
  and rejects ingest when above-threshold candidates are not addressed.
- Threshold + mode (strict|confirm) sourced from `spec_authoring`
  in SCHEMA.md; CLI flags override per-invocation.
- Exit codes: 0 covered/no enforcement, 1 uncovered+confirm-mode,
  2 uncovered+strict-mode (or general failure).

Phase 3+ (future):
- Auto-propagation of supersedes / refines (Phase 3) — kata-internal only
- Lineage view via wiki-graph --spec-history (Phase 4)

Spec types are configured in SCHEMA.md under `spec_authoring.spec_types`.

Default: prd, design, rfc, adr, task-spec, decisions.

Usage:

    spec_preflight.py --new-spec <path-to-new-spec-file>
    spec_preflight.py --new-spec <path> --wiki <path> --limit 20
    spec_preflight.py --new-spec <path> --include-archived
    spec_preflight.py --new-spec <path> --enforce
    spec_preflight.py --new-spec <path> --enforce --enforce-threshold 4.0
    spec_preflight.py --new-spec <path> --enforce --enforce-mode confirm

The new spec file need not exist in the wiki yet — typically it's a
draft sitting in raw/ or a separate working directory. The script
parses its frontmatter to discover title, tags, and wikilinks for
matching against the wiki + external sources.

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


def _normalize_target(s: str) -> str:
    """Reduce a relationship target string to a canonical match key.

    Strips wikilink brackets, trailing `.md`, surrounding whitespace, and
    lowercases. The same normalization is applied to both declared
    targets (from spec_relationships[].target) and candidate identifiers
    (kata page path, or external URI), so equality compares apples to
    apples.
    """
    if not s:
        return ""
    t = str(s).strip()
    # [[wikilink]] → wikilink
    if t.startswith("[[") and t.endswith("]]"):
        t = t[2:-2].strip()
    # foo|alias-display → foo (Obsidian aliased wikilink)
    if "|" in t:
        t = t.split("|", 1)[0].strip()
    # Trailing .md (case-insensitive)
    if t.lower().endswith(".md"):
        t = t[:-3]
    return t.lower()


def _candidate_match_keys(candidate: dict) -> set[str]:
    """Return the set of normalized strings that should match a declared
    target for this candidate. Includes wiki-relative path, bare stem,
    and (for federated candidates) the `kata://<name>/<path>` URI in
    both name and wiki_id forms (PRD D2.2)."""
    keys: set[str] = set()
    full = candidate.get("path") or ""
    keys.add(_normalize_target(full))
    stem = full.split("/")[-1] if "/" in full else full
    keys.add(_normalize_target(stem))

    # Phase 3 (v2.11.0): federated candidates carry kata:// URI + the
    # peer's wiki_id. Authors may have declared targets in either form
    # (PRD D2.2 name-first daily, wiki_id-form for long-lived).
    uri = candidate.get("uri")
    if uri:
        keys.add(_normalize_target(uri))
    peer_name = candidate.get("source_wiki_name")
    peer_wiki_id = candidate.get("source_wiki")
    if peer_name and full:
        # Already covered by `uri` but defend against missing uri field.
        keys.add(_normalize_target(f"kata://{peer_name}/{full}"))
    if peer_wiki_id and peer_wiki_id != "self" and full:
        # wiki_id form — long-lived citation form per PRD D2.2.
        keys.add(_normalize_target(f"kata://{peer_wiki_id}/{full}"))

    keys.discard("")
    return keys


def _parse_spec_relationships(new_fm: dict) -> list[dict]:
    """Pull `spec_relationships:` out of the new-spec frontmatter, return
    a list of dicts with `kind`, `target`, `note` keys. Malformed
    entries (non-dict, missing target) are dropped silently — the
    advisory output captures the declaration count so callers can audit.
    """
    raw = new_fm.get("spec_relationships") or []
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        target = entry.get("target")
        if not target:
            continue
        out.append({
            "kind": str(entry.get("kind", "references")),
            "target": str(target),
            "note": str(entry.get("note", "")),
            "_normalized": _normalize_target(str(target)),
        })
    return out


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
    p.add_argument("--enforce", action="store_true",
                   help="Phase 2 enforcement mode. Parse the new spec's "
                        "`spec_relationships:` frontmatter and reject ingest "
                        "when any above-threshold candidate is not addressed. "
                        "Exit code 2 (strict) or 1 (confirm) on uncovered.")
    p.add_argument("--enforce-threshold", type=float, default=None,
                   help="Override `spec_authoring.enforcement_score_threshold` "
                        "for this run. Default: schema value (5.0 fallback).")
    p.add_argument("--enforce-mode", choices=["strict", "confirm"], default=None,
                   help="Override `spec_authoring.enforcement_mode` for this "
                        "run. strict=exit 2 on uncovered; confirm=exit 1.")
    p.add_argument("--federate", action="store_true",
                   help="Phase 3 (v2.11.0): also fan out to peer kata wikis "
                        "listed in {wiki_path}/.federation.yaml, merge their "
                        "preflight candidates into the ranked list with "
                        "kata://<peer>/<path> URIs as provenance. Default "
                        "off; opt-in per invocation.")
    p.add_argument("--federate-peers", default=None,
                   help="Comma-separated peer names to restrict the fan-out "
                        "(default: all enabled peers in .federation.yaml).")
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

    # Annotate local candidates with source_wiki="self" so federation
    # downstream can tell them apart cleanly from peer candidates.
    for r in results:
        r["source_wiki"] = "self"

    # Phase 3 (v2.11.0): federated fan-out. When --federate is set and
    # .federation.yaml exists, ask each enabled peer to run its own
    # wiki-spec-preflight on this draft and merge their candidates.
    federation_block: dict | None = None
    if args.federate:
        from federation_client import (  # noqa: PLC0415 — lazy import
            load_federation_config, federate_spec_preflight,
        )
        peers = load_federation_config(root)
        peer_filter = None
        if args.federate_peers:
            peer_filter = {
                n.strip() for n in args.federate_peers.split(",") if n.strip()
            }
        fed_envelope = federate_spec_preflight(
            wiki_root=root,
            new_spec_path=str(new_spec_path),
            peers=peers,
            limit=args.limit,
            include_archived=bool(args.include_archived or args.include_frozen),
            include_frozen=bool(args.include_frozen),
            peer_filter=peer_filter,
        )
        # Peer candidates get their tier label normalized so caller code
        # that branches on `tier` doesn't have to know about federation.
        # Use "federated" as the synthetic tier — keeps active/archived/
        # frozen pure and lets `tier_breakdown` track federated count.
        for c in fed_envelope["peer_candidates"]:
            c.setdefault("tier", "federated")
            results.append(c)
        federation_block = fed_envelope["federation"]

    # Rank: highest score first; stable tiebreak by path
    results.sort(key=lambda r: (-r["score"], r.get("path", "")))

    # Keep the unbounded set for Phase 2 enforcement — a low --limit
    # must not hide above-threshold candidates from the coverage check.
    full_results = list(results)
    results = results[:args.limit]

    # Tier breakdown across full candidate pool (before --limit) for the
    # caller's coverage shape signal — same pattern as search_naive.py.
    tier_breakdown = {"active": 0, "archived": 0, "frozen": 0}
    for page in candidates:
        t = tier_map[page.path]
        if t in tier_breakdown:
            tier_breakdown[t] += 1
    # Federated candidates aren't in `candidates` (they came from peers,
    # not from local discover_pages), so add their count to the breakdown
    # separately. Track under a "federated" key (NOT "external" — that
    # was the removed v1.13 Phase 1; "federated" means a peer kata wiki).
    federated_count = sum(1 for r in full_results
                          if r.get("source_wiki") not in (None, "self"))
    if federated_count or args.federate:
        tier_breakdown["federated"] = federated_count

    phase = 0
    if args.federate:
        phase = 3  # Phase 3 fan-out was active this run

    # Phase 2: enforcement check.
    # Active when --enforce is passed OR schema's
    # `spec_authoring.enforce_relationship_declaration` is true.
    # Strict bool check — `bool("false")` is True in Python; require the
    # schema value to be exactly literal true. CLI flag is a normal bool.
    schema_enforce = spec_authoring.get("enforce_relationship_declaration") is True
    enforcement_active = bool(args.enforce) or schema_enforce

    enforcement_block: dict | None = None
    exit_code = 0
    if enforcement_active:
        threshold = (
            args.enforce_threshold
            if args.enforce_threshold is not None
            else float(spec_authoring.get("enforcement_score_threshold", 5.0))
        )
        mode = (
            args.enforce_mode
            or str(spec_authoring.get("enforcement_mode", "strict"))
        )
        if mode not in ("strict", "confirm"):
            mode = "strict"
        # phase = 2 represents enforcement-active. But if federation
        # already set phase = 3 (the larger-numbered overlay), keep that
        # — phase is reported as the highest-numbered active feature so
        # callers can switch on it without losing info.
        if phase < 2:
            phase = 2

        declared = _parse_spec_relationships(new_fm)
        declared_normalized = {d["_normalized"] for d in declared if d["_normalized"]}

        above_threshold = [r for r in full_results if r["score"] >= threshold]
        covered: list[dict] = []
        uncovered: list[dict] = []
        for cand in above_threshold:
            keys = _candidate_match_keys(cand)
            is_covered = bool(keys & declared_normalized)
            target = dict(cand)
            target["match_keys"] = sorted(keys)
            (covered if is_covered else uncovered).append(target)

        if uncovered:
            decision = "reject"
            exit_code = 2 if mode == "strict" else 1
        else:
            decision = "accept"
            exit_code = 0

        enforcement_block = {
            "enabled": True,
            "mode": mode,
            "threshold": threshold,
            "declared_relationships": [
                {k: v for k, v in d.items() if not k.startswith("_")}
                for d in declared
            ],
            "declared_count": len(declared),
            "above_threshold_count": len(above_threshold),
            "covered_count": len(covered),
            "uncovered_count": len(uncovered),
            "uncovered": [
                {
                    "path": u.get("path"),
                    "title": u.get("title"),
                    "type": u.get("type"),
                    "tier": u.get("tier"),
                    "score": u.get("score"),
                    # Provenance — caller needs to know whether to chase
                    # a missing declaration locally or via federation
                    "source_wiki": u.get("source_wiki", "self"),
                    "source_wiki_name": u.get("source_wiki_name"),
                    "uri": u.get("uri"),
                }
                for u in uncovered
            ],
            "decision": decision,
        }

    payload = {
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
            "Phase 0 (advisory): the author (human or agent) reads these "
            "candidates and declares relationships in the new spec's "
            "frontmatter under `spec_relationships:` before ingest. Phase 2 "
            "enforces relationship declaration for above-threshold candidates "
            "when --enforce is set or "
            "`spec_authoring.enforce_relationship_declaration` is true in "
            "SCHEMA.md. Phase 3 (--federate) merges peer-kata candidates "
            "into the ranked list; federated candidates appear with "
            "kata://<peer>/<path> URIs and participate in the enforcement "
            "coverage check just like local ones."
        ),
        "phase": phase,
    }
    if enforcement_block is not None:
        payload["enforcement"] = enforcement_block
    if federation_block is not None:
        payload["federation"] = federation_block
    emit(payload)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
