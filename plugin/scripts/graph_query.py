#!/usr/bin/env python3
"""Deterministic graph query for kata.

Skills (wiki-graph) shell out to this script with a query mode. The script
scans all .md files, builds an in-memory graph, runs the query, and emits
JSON. The skill formats the JSON for the user.

Usage:
    graph_query.py --wiki <path> --mode neighbors --seed <page> [--depth N]
    graph_query.py --wiki <path> --mode shortest-path --src A --dst B
    graph_query.py --wiki <path> --mode hubs [--limit 20]
    graph_query.py --wiki <path> --mode orphans
    graph_query.py --wiki <path> --mode cluster --tag <tag>
    graph_query.py --wiki <path> --mode stats
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
    is_structural_page,
    load_schema,
    neighbors as bfs_neighbors,
    shortest_path,
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wiki", default=None)
    p.add_argument("--mode", required=True,
                   choices=["neighbors", "shortest-path", "hubs", "orphans",
                            "cluster", "stats", "spec-history"])
    p.add_argument("--seed")
    p.add_argument("--src")
    p.add_argument("--dst")
    p.add_argument("--tag")
    p.add_argument("--depth", type=int, default=1)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--tier", choices=["active", "archived", "frozen", "all"])
    # spec-history (Phase 4, v2.13.0) renders the supersession + refinement
    # lineage for a seed page. text = ASCII tree (default); json = nested
    # dict; mermaid = graph DSL for markdown / Obsidian embedding.
    p.add_argument("--format", choices=["text", "json", "mermaid"],
                   default="text", help="Output format for spec-history mode.")
    args = p.parse_args()

    root = find_wiki_root(args.wiki)
    if not root.exists():
        emit({"error": f"wiki root not found: {root}"})
        return 2

    schema = load_schema(root)
    pages = discover_pages(root)
    id_map, dangling = build_graph(pages)

    # Compute tiers
    tier_map = {p.path: compute_tier(p, schema) for p in pages}

    def filter_by_tier(items):
        if not args.tier or args.tier == "all":
            return items
        return [x for x in items if tier_map.get(x) == args.tier]

    if args.mode == "stats":
        emit({
            "wiki": str(root),
            "pages": len(pages),
            "edges": sum(len(p.out_links) for p in pages),
            "dangling_links": sum(len(v) for v in dangling.values()),
            "tier_distribution": {
                "active": sum(1 for t in tier_map.values() if t == "active"),
                "archived": sum(1 for t in tier_map.values() if t == "archived"),
                "frozen": sum(1 for t in tier_map.values() if t == "frozen"),
            },
        })
        return 0

    if args.mode == "neighbors":
        if not args.seed:
            emit({"error": "--seed required"})
            return 2
        seed_id = _resolve(args.seed, id_map)
        if not seed_id:
            emit({"error": f"page not found: {args.seed}"})
            return 1
        layers = bfs_neighbors(id_map, seed_id, args.depth)
        emit({
            "mode": "neighbors",
            "seed": seed_id,
            "depth": args.depth,
            "layers": {
                str(d): [{"id": n, "tier": tier_map.get(n),
                          "type": id_map[n].frontmatter.get("type"),
                          "tags": id_map[n].frontmatter.get("tags", [])[:2]}
                         for n in nodes]
                for d, nodes in layers.items()
            },
        })
        return 0

    if args.mode == "shortest-path":
        if not (args.src and args.dst):
            emit({"error": "--src and --dst required"})
            return 2
        sid = _resolve(args.src, id_map)
        did = _resolve(args.dst, id_map)
        if not sid or not did:
            emit({"error": "src or dst not found",
                  "src_resolved": sid, "dst_resolved": did})
            return 1
        path = shortest_path(id_map, sid, did)
        emit({
            "mode": "shortest-path",
            "src": sid, "dst": did,
            "path": [{"id": n, "tier": tier_map.get(n),
                      "type": id_map[n].frontmatter.get("type")}
                     for n in path] if path else None,
            "length": len(path) - 1 if path else None,
        })
        return 0

    if args.mode == "hubs":
        ranked = sorted(pages, key=hub_score, reverse=True)
        ranked = [p for p in ranked if not args.tier or args.tier == "all"
                  or tier_map.get(p.path) == args.tier]
        out = [{"id": p.path, "title": p.title,
                "in": len(p.in_links), "out": len(p.out_links),
                "score": hub_score(p), "tier": tier_map.get(p.path)}
               for p in ranked[:args.limit]]
        emit({"mode": "hubs", "limit": args.limit, "hubs": out})
        return 0

    if args.mode == "orphans":
        # Structural/meta files (SCHEMA.md, index.md, log.md, dreaming/*.md)
        # are never "content pages" — they're bookkeeping or auto-generated
        # run reports that legitimately have zero real graph edges (e.g. a
        # candidate-less dreaming digest, or a bookkeeping file nothing is
        # meant to cite). Without this exemption every wiki reports them as
        # orphans/leaves unconditionally, which is noise, not a real finding.
        # See wiki_lib.is_structural_page() for the full rationale.
        true_orphans = [p.path for p in pages
                        if not p.in_links and not p.out_links
                        and not is_structural_page(p.path)]
        leaves = [p.path for p in pages if p.in_links and not p.out_links
                  and not is_structural_page(p.path)]
        emit({
            "mode": "orphans",
            "true_orphans": filter_by_tier(true_orphans),
            "leaves": filter_by_tier(leaves),
            "dangling_links": dangling,
        })
        return 0

    if args.mode == "cluster":
        if not args.tag:
            emit({"error": "--tag required"})
            return 2
        members = []
        for p in pages:
            tags = p.frontmatter.get("tags") or []
            if isinstance(tags, list) and args.tag in tags:
                members.append(p)
        member_ids = {p.path for p in members}
        intra = sum(1 for p in members for n in p.out_links if n in member_ids)
        external = sum(1 for p in members for n in p.out_links if n not in member_ids)
        n = len(members)
        density = intra / (n * (n - 1) / 2) if n > 1 else 0.0
        anchor = max(members, key=hub_score) if members else None
        emit({
            "mode": "cluster",
            "tag": args.tag,
            "members": [p.path for p in members],
            "anchor": anchor.path if anchor else None,
            "intra_edges": intra,
            "external_edges": external,
            "density": round(density, 4),
        })
        return 0

    if args.mode == "spec-history":
        if not args.seed:
            emit({"error": "--seed required for spec-history"})
            return 2
        seed_path = _resolve(args.seed, id_map)
        if not seed_path:
            emit({"error": f"seed not found: {args.seed}"})
            return 2

        reverse_index = _load_reverse_index(root)
        tree = _build_spec_history_tree(
            seed_path, id_map, tier_map, reverse_index,
            max_depth=args.depth if args.depth and args.depth > 0 else 3,
        )

        if args.format == "json":
            emit({"mode": "spec-history", "format": "json", "tree": tree})
            return 0
        if args.format == "mermaid":
            mermaid = _render_spec_history_mermaid(tree)
            emit({"mode": "spec-history", "format": "mermaid",
                  "mermaid": mermaid})
            return 0
        # text (default)
        text = _render_spec_history_text(tree)
        emit({"mode": "spec-history", "format": "text",
              "text": text, "tree": tree})
        return 0

    return 0


def _resolve(name: str, id_map) -> str | None:
    """Resolve a user-supplied page name to a path id."""
    if name in id_map:
        return name
    name_l = name.lower()
    for pid, page in id_map.items():
        if page.title and page.title.lower() == name_l:
            return pid
        if Path(pid).stem.lower() == name_l:
            return pid
    return None


# ---------------------------------------------------------------------------
# spec-history mode (Phase 4, v2.13.0) — supersession + refinement lineage
# ---------------------------------------------------------------------------

def _load_reverse_index(wiki_root) -> list[dict]:
    """Parse {wiki_path}/.spec-reverse-index.yaml (written by
    spec_propagate.py Phase 3 for kata:// federation supersedes).
    Returns list of {external_target, superseded_by, date, note}.
    Tolerates missing file / malformed YAML."""
    idx_path = wiki_root / ".spec-reverse-index.yaml"
    if not idx_path.is_file():
        return []
    try:
        text = idx_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    # Format is fixed (written by spec_propagate.py); line-based parse.
    entries: list[dict] = []
    current: dict = {}
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("- external_target:"):
            if current:
                entries.append(current)
            current = {"external_target": s.split(":", 1)[1].strip()}
        elif s.startswith("superseded_by:") and current:
            current["superseded_by"] = s.split(":", 1)[1].strip()
        elif s.startswith("date:") and current:
            current["date"] = s.split(":", 1)[1].strip()
        elif s.startswith("note:") and current:
            note = s.split(":", 1)[1].strip()
            if note.startswith('"') and note.endswith('"'):
                note = note[1:-1]
            current["note"] = note
    if current:
        entries.append(current)
    return entries


def _spec_node(page_id: str, id_map, tier_map) -> dict:
    """Build a node dict for a wiki page (used in tree leaves and roots)."""
    page = id_map.get(page_id)
    if not page:
        return {"path": page_id, "title": None, "tier": "unknown",
                "published_at": None, "_missing": True}
    return {
        "path": page_id,
        "title": page.frontmatter.get("title") or page.title,
        "type": page.frontmatter.get("type"),
        "tier": tier_map.get(page_id, "unknown"),
        "published_at": str(page.frontmatter.get("published_at") or ""),
    }


def _build_spec_history_tree(seed_path: str, id_map, tier_map,
                              reverse_index: list[dict],
                              max_depth: int = 3) -> dict:
    """Walk supersession + relationship graph from seed. Returns a
    nested dict tree:

      {
        ...seed_node_fields...,
        "outbound": [
          {kind, target, target_node, target_outbound, note, ...},
          {kind, target_uri, federated: true, note}   # for kata:// URIs
        ],
        "inbound": [
          {kind: "supersedes", source_path, source_node, note, ...},
          {kind: "supersedes", source_external_target, federated_inbound: true}
        ]
      }

    Cycle protection via `visited` set on the recursion. `max_depth`
    bounds how deep outbound chains expand (inbound is one level only —
    we list pages that supersede us; we don't recurse into their own
    inbound, which would be unbounded).
    """

    def _outbound(page_id: str, depth_remaining: int,
                  visited: set) -> list[dict]:
        if depth_remaining <= 0 or page_id in visited:
            return []
        visited = visited | {page_id}
        page = id_map.get(page_id)
        if not page:
            return []
        rels = page.frontmatter.get("spec_relationships") or []
        if not isinstance(rels, list):
            return []
        out = []
        for rel in rels:
            if not isinstance(rel, dict):
                continue
            kind = rel.get("kind")
            target = rel.get("target")
            note = rel.get("note") or ""
            if not target:
                continue
            target_s = str(target)
            if target_s.startswith("kata://"):
                out.append({
                    "kind": kind,
                    "target_uri": target_s,
                    "federated": True,
                    "note": note,
                })
                continue
            # Local target — resolve via id_map; the resolver in main()
            # already exists, but we need stem-based fallback here.
            target_id = target_s
            if target_id not in id_map:
                # try stem match
                stem = target_id.split("/")[-1].replace(".md", "").lower()
                if "[[" in target_id:
                    inner = target_id.strip("[]").split("|")[0]
                    stem = inner.lower()
                for pid in id_map:
                    if pid.split("/")[-1].replace(".md", "").lower() == stem:
                        target_id = pid
                        break
            target_node = _spec_node(target_id, id_map, tier_map)
            target_outbound = _outbound(target_id, depth_remaining - 1,
                                         visited)
            out.append({
                "kind": kind,
                "target": target_id,
                "target_node": target_node,
                "outbound": target_outbound,
                "note": note,
            })
        return out

    def _inbound(page_id: str) -> list[dict]:
        """Find pages that supersede / refine / etc. THIS page.
        Looks at every other page's spec_relationships AND the local
        .spec-reverse-index.yaml for cross-wiki entries."""
        inbound_local = []
        for pid, page in id_map.items():
            if pid == page_id:
                continue
            rels = page.frontmatter.get("spec_relationships") or []
            if not isinstance(rels, list):
                continue
            for rel in rels:
                if not isinstance(rel, dict):
                    continue
                target = rel.get("target")
                if not target:
                    continue
                target_s = str(target)
                # Match local target to seed (path or stem)
                if target_s == page_id or target_s.replace(".md", "") == \
                        page_id.replace(".md", ""):
                    inbound_local.append({
                        "kind": rel.get("kind"),
                        "source_path": pid,
                        "source_node": _spec_node(pid, id_map, tier_map),
                        "note": rel.get("note") or "",
                    })
                else:
                    # Stem-only declarations
                    seed_stem = page_id.split("/")[-1].replace(".md", "").lower()
                    tgt_stem = target_s.split("/")[-1].replace(".md", "")
                    if "[[" in target_s:
                        inner = target_s.strip("[]").split("|")[0]
                        tgt_stem = inner
                    if tgt_stem.lower() == seed_stem:
                        inbound_local.append({
                            "kind": rel.get("kind"),
                            "source_path": pid,
                            "source_node": _spec_node(pid, id_map, tier_map),
                            "note": rel.get("note") or "",
                        })
        return inbound_local

    def _federated_inbound(page_id: str) -> list[dict]:
        """Cross-wiki: did any kata://<peer>/<this-page> supersession get
        recorded in .spec-reverse-index.yaml?
        (This is the reverse-direction lookup — index records OUR
        supersedes of peer pages, not the other way around. But if a
        peer wrote our page into THEIR reverse-index, we won't see it
        — that requires peer to publish it back. For MVP, we only show
        our own outbound to peers; inbound from peers is a Phase 5+
        federation feature.)"""
        # Keeping the hook + comment in place but returning [] for MVP.
        return []

    seed_node = _spec_node(seed_path, id_map, tier_map)
    seed_node["outbound"] = _outbound(seed_path, max_depth, set())
    seed_node["inbound"] = _inbound(seed_path) + _federated_inbound(seed_path)
    seed_node["reverse_index_size"] = len(reverse_index)
    return seed_node


def _render_spec_history_text(node: dict, prefix: str = "",
                               is_root: bool = True) -> str:
    """ASCII tree."""
    def _label(n: dict) -> str:
        title = n.get("title") or n.get("path") or "?"
        tier = n.get("tier") or "unknown"
        date_part = (f", {n.get('published_at')}"
                     if n.get("published_at") else "")
        return f"{title} ({tier}{date_part})"

    lines: list[str] = []
    if is_root:
        lines.append(_label(node))

    for rel in node.get("outbound", []):
        if rel.get("federated"):
            lines.append(f"{prefix}  {rel.get('kind')}→ {rel.get('target_uri')} (federated)")
        else:
            target_node = rel.get("target_node", {})
            lines.append(f"{prefix}  {rel.get('kind')}→ {_label(target_node)}")
            child = {
                **target_node,
                "outbound": rel.get("outbound", []),
                "inbound": [],
            }
            child_text = _render_spec_history_text(
                child, prefix + "                 ", is_root=False,
            )
            if child_text:
                lines.append(child_text)

    for rel in node.get("inbound", []):
        src_node = rel.get("source_node", {})
        lines.append(f"{prefix}  ← {rel.get('kind')} by {_label(src_node)}")

    return "\n".join(l for l in lines if l)


def _render_spec_history_mermaid(node: dict) -> str:
    """Mermaid graph DSL, suitable for embedding in markdown."""
    lines = ["graph LR"]
    seen_nodes: set = set()

    def _node_id(path_or_uri: str) -> str:
        # Mermaid node ids need to be alphanumeric-safe — use the stem.
        if path_or_uri.startswith("kata://"):
            return "EXT_" + re.sub(r"[^a-zA-Z0-9]", "_", path_or_uri)[:40]
        stem = path_or_uri.split("/")[-1].replace(".md", "")
        return re.sub(r"[^a-zA-Z0-9]", "_", stem) or "node"

    def _emit_node(n: dict, is_uri: bool = False):
        nid = _node_id(n.get("path") or n.get("target_uri") or "?")
        if nid in seen_nodes:
            return nid
        seen_nodes.add(nid)
        if is_uri:
            label = n.get("target_uri", "?")
            lines.append(f'  {nid}[("{label}")]')
        else:
            title = (n.get("title") or n.get("path") or "?").replace('"', "'")
            tier = n.get("tier", "")
            lines.append(f'  {nid}["{title} ({tier})"]')
        return nid

    def _walk_outbound(parent_nid: str, outbound: list):
        for rel in outbound:
            if rel.get("federated"):
                child_nid = _emit_node(rel, is_uri=True)
                lines.append(f"  {parent_nid} -->|{rel.get('kind')}| {child_nid}")
            else:
                target_node = rel.get("target_node", {})
                child_nid = _emit_node(target_node)
                lines.append(f"  {parent_nid} -->|{rel.get('kind')}| {child_nid}")
                _walk_outbound(child_nid, rel.get("outbound", []))

    root_nid = _emit_node(node)
    _walk_outbound(root_nid, node.get("outbound", []))

    for rel in node.get("inbound", []):
        src_node = rel.get("source_node", {})
        src_nid = _emit_node(src_node)
        lines.append(f"  {src_nid} -->|{rel.get('kind')}| {root_nid}")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
