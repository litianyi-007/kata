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
    neighbors as bfs_neighbors,
    shortest_path,
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wiki", default=None)
    p.add_argument("--mode", required=True,
                   choices=["neighbors", "shortest-path", "hubs", "orphans",
                            "cluster", "stats"])
    p.add_argument("--seed")
    p.add_argument("--src")
    p.add_argument("--dst")
    p.add_argument("--tag")
    p.add_argument("--depth", type=int, default=1)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--tier", choices=["active", "archived", "frozen", "all"])
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
        true_orphans = [p.path for p in pages
                        if not p.in_links and not p.out_links]
        leaves = [p.path for p in pages if p.in_links and not p.out_links]
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


if __name__ == "__main__":
    sys.exit(main())
