#!/usr/bin/env python3
"""Auto-dreamer for kata — re-promotes frozen/archived pages whose
relevance has resurfaced in recent activity.

Reads three things, all from the wiki filesystem:
  1. log.md entries since the last `## [date] dream | …` watermark
  2. wiki pages whose frontmatter `ingested_at` or `updated` ≥ watermark
     (NOT file mtime — mtimes don't survive `git clone`, and we want
     dream behavior to be reproducible across checkouts)
  3. the frozen + archived pool (the candidates to evaluate)

NEVER reads chat sessions or any external state. The wiki is the only input.

Usage:
    wiki_dream.py --wiki <path> [--since YYYY-MM-DD] [--strategy co-occurrence]
        [--apply --pages 1,2,3] [--explain <page>] [--out <file>] [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

from wiki_lib import (
    Page,
    compute_increment,
    compute_tier,
    detect_resurgence,
    discover_pages,
    emit,
    find_wiki_root,
    load_schema,
    parse_log,
    read_watermark,
)

DEFAULT_WEIGHTS = {"entity": 0.5, "tag": 0.2, "citation": 0.4}
DEFAULT_THRESHOLD = 0.6
DEFAULT_MAX_REPROMOTE = 10
DEFAULT_DORMANCY_DAYS = 180
DEFAULT_RESURGENCE_MIN_COUNT = 3
DEFAULT_LOOKBACK_DAYS = 30  # When no watermark exists


@dataclass
class Candidate:
    page: str
    title: str
    current_tier: str
    score: float
    reasons: list[str] = field(default_factory=list)
    components: dict = field(default_factory=dict)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wiki", default=None)
    p.add_argument("--since", default=None,
                   help="Override watermark (YYYY-MM-DD)")
    p.add_argument("--strategy", default="co-occurrence",
                   choices=["co-occurrence"])
    p.add_argument("--today", default=None,
                   help="Override 'today' for fixture-style determinism")
    p.add_argument("--apply", action="store_true",
                   help="Write tier_override:active to selected pages")
    p.add_argument("--pages", default=None,
                   help="With --apply: comma-separated 1-based candidate indices")
    p.add_argument("--explain", default=None,
                   help="Show full scoring for a single page (by id or title)")
    p.add_argument("--out", default=None,
                   help="Output JSON file (also written to dreaming/YYYY-MM-DD.md "
                        "for human reading)")
    args = p.parse_args()

    root = find_wiki_root(args.wiki)
    if not root.exists():
        emit({"error": f"wiki root not found: {root}"})
        return 2

    today = date.fromisoformat(args.today) if args.today else date.today()
    schema = load_schema(root)

    # Resolve `since`
    if args.since:
        since = date.fromisoformat(args.since)
    else:
        wm = read_watermark(root / "log.md", action="dream")
        since = wm or (today - timedelta(days=DEFAULT_LOOKBACK_DAYS))

    # Pull dreaming config from schema
    dreaming_cfg = schema.get("dreaming") or {}
    if isinstance(dreaming_cfg, dict) and dreaming_cfg.get("enabled") is False:
        emit({"error": "dreaming.enabled is false in SCHEMA.md"})
        return 0
    weights = {**DEFAULT_WEIGHTS, **(dreaming_cfg.get("weights") or {})}
    threshold = float(dreaming_cfg.get("confidence_threshold", DEFAULT_THRESHOLD))
    max_repromote = int(dreaming_cfg.get("max_repromote_per_run", DEFAULT_MAX_REPROMOTE))
    resurgence_cfg = dreaming_cfg.get("resurgence") or {}
    dormancy = int(resurgence_cfg.get("dormancy_window_days", DEFAULT_DORMANCY_DAYS))
    min_count = int(resurgence_cfg.get("min_count", DEFAULT_RESURGENCE_MIN_COUNT))

    pages = discover_pages(root)
    id_map = {p.path: p for p in pages}
    tier_map = {p.path: compute_tier(p, schema, today=today) for p in pages}

    # Build the increment
    increment = compute_increment(pages, root / "log.md", since, id_map=id_map)
    resurgent_tags = detect_resurgence(pages, increment,
                                       dormancy_days=dormancy,
                                       min_count=min_count)
    increment_resurgent_tags = resurgent_tags

    # Candidate pool: archived + frozen only
    candidate_pool = [p for p in pages
                      if tier_map[p.path] in ("archived", "frozen")]

    # v2.12.0 — v1.13 Phase 3 dreamer reject-signal hook. Pages that
    # were superseded by an explicit `kind: supersedes` declaration
    # (frontmatter `spec_superseded_by:` non-empty) are dead by
    # declaration, not by inference — never resurface them via
    # co-occurrence dreaming regardless of score. Same for pages auto-
    # tier-flipped by Phase 3 (tier_reason starts with "Superseded by").
    # Closes the v1.6 dogfood Week 1 channel-mismatch finding with an
    # even more targeted reject channel than tier_override alone.
    def _is_superseded(page) -> bool:
        sb = page.frontmatter.get("spec_superseded_by")
        if isinstance(sb, list) and sb:
            return True
        if page.frontmatter.get("tier_override") == "archived":
            reason = str(page.frontmatter.get("tier_reason") or "")
            if reason.startswith("Superseded by"):
                return True
        return False

    candidate_pool = [p for p in candidate_pool if not _is_superseded(p)]

    # Score every candidate
    scored: list[Candidate] = []
    for p in candidate_pool:
        cand = score_page(p, increment, increment_resurgent_tags, weights,
                          id_map)
        cand.current_tier = tier_map[p.path]
        if cand.score >= threshold:
            scored.append(cand)

    scored.sort(key=lambda c: -c.score)
    top = scored[:max_repromote]

    # --explain: print one specific page's full score
    if args.explain:
        target = _resolve_page(args.explain, id_map)
        if not target:
            emit({"error": f"page not found: {args.explain}"})
            return 1
        page_obj = id_map[target]
        cand = score_page(page_obj, increment, increment_resurgent_tags,
                          weights, id_map)
        cand.current_tier = tier_map[target]
        emit({
            "mode": "explain",
            "page": target,
            "score": cand.score,
            "components": cand.components,
            "reasons": cand.reasons,
            "current_tier": cand.current_tier,
            "would_pass_threshold": cand.score >= threshold,
            "threshold": threshold,
            "increment_summary": _summarize_increment(increment),
            "resurgent_tags": sorted(increment_resurgent_tags),
        })
        return 0

    # --apply: mutate frontmatter on selected candidates
    if args.apply:
        if not args.pages:
            emit({"error": "--apply requires --pages 1,2,3"})
            return 2
        try:
            indices = [int(s.strip()) for s in args.pages.split(",")]
        except ValueError:
            emit({"error": "--pages must be comma-separated 1-based integers"})
            return 2
        applied = []
        for i in indices:
            if not (1 <= i <= len(top)):
                emit({"error": f"--pages index {i} out of range (1..{len(top)})"})
                return 2
            cand = top[i - 1]
            ok = _apply_promote(root, cand, today)
            if ok:
                applied.append(cand.page)
        # Append to log.md
        _log_apply(root, today, applied, since)
        emit({
            "mode": "apply",
            "applied": applied,
            "watermark_advanced_to": today.isoformat(),
        })
        return 0

    # Default mode: emit candidates + write a dated dreaming/ file
    payload = {
        "mode": "dream",
        "wiki": str(root),
        "today": today.isoformat(),
        "since": since.isoformat(),
        "strategy": args.strategy,
        "config": {
            "weights": weights, "threshold": threshold,
            "max_repromote_per_run": max_repromote,
            "dormancy_window_days": dormancy, "resurgence_min_count": min_count,
        },
        "increment_summary": _summarize_increment(increment),
        "resurgent_tags": sorted(increment_resurgent_tags),
        "candidate_pool_size": len(candidate_pool),
        "candidates": [_cand_to_dict(c) for c in top],
        "candidates_below_threshold": len(scored) - len(top) if len(scored) > max_repromote else 0,
    }

    # Write a human-readable dated file
    dreaming_dir = root / "dreaming"
    dreaming_dir.mkdir(exist_ok=True)
    out_md = dreaming_dir / f"{today.isoformat()}.md"
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    payload["dreaming_md"] = str(out_md.relative_to(root))

    # Append a "dream | run" log entry advancing the watermark
    _log_run(root, today, since, len(top))

    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2,
                                             ensure_ascii=False, default=str),
                                  encoding="utf-8")

    emit(payload)
    return 0


# ────────────────────── SCORING ──────────────────────────

def score_page(page: Page, inc, resurgent_tags: set, weights: dict,
               id_map: dict[str, Page]) -> Candidate:
    cand = Candidate(page=page.path, title=page.title, current_tier="",
                     score=0.0)

    # Page's identity tokens (its title and stem)
    page_ids = {(page.title or "").lower(), Path(page.path).stem.lower(),
                *{l.lower() for l in page.out_links}}
    page_ids.discard("")

    # ENTITY OVERLAP
    overlap = page_ids & inc.entities
    # Don't count self-references (page is fresh and matches itself)
    overlap.discard(page.path.lower())
    if overlap:
        e_score = weights["entity"] * min(len(overlap) / 2, 1.0)
        cand.score += e_score
        cand.components["entity"] = round(e_score, 4)
        sample = sorted(overlap)[:3]
        cand.reasons.append(
            f"shares entities {sample} with new ingests")

    # TAG RESURGENCE
    page_tags = set()
    raw_tags = page.frontmatter.get("tags") or []
    if isinstance(raw_tags, list):
        page_tags = {str(t).lower() for t in raw_tags}
    tag_overlap = page_tags & resurgent_tags
    if tag_overlap:
        t_score = weights["tag"] * min(len(tag_overlap) / 1, 1.0)
        cand.score += t_score
        cand.components["tag"] = round(t_score, 4)
        cand.reasons.append(
            f"tags {sorted(tag_overlap)} resurged this period")

    # CITATION HIT — direct inbound link from a fresh page
    direct_in = []
    page_stem = Path(page.path).stem.lower()
    page_title_l = (page.title or "").lower()
    for fresh in inc.fresh_pages:
        for link in fresh.out_links:
            link_l = link.lower()
            if link_l == page_stem or link_l == page_title_l:
                direct_in.append(fresh.path)
                break
    if direct_in:
        c_score = weights["citation"] * min(len(direct_in) / 1, 1.0)
        cand.score += c_score
        cand.components["citation"] = round(c_score, 4)
        sample = direct_in[:2]
        cand.reasons.append(
            f"directly linked from new pages {sample}")

    cand.score = round(cand.score, 4)
    return cand


# ────────────────────── HELPERS ──────────────────────────

def _summarize_increment(inc) -> dict:
    return {
        "since": inc.since.isoformat(),
        "fresh_page_count": len(inc.fresh_pages),
        "fresh_pages": [p.path for p in inc.fresh_pages],
        "entity_count": len(inc.entities),
        "tag_count": len(inc.tags),
        "top_tags": sorted(inc.tags.items(), key=lambda kv: -kv[1])[:5],
    }


def _resolve_page(name: str, id_map: dict[str, Page]) -> str | None:
    if name in id_map:
        return name
    name_l = name.lower()
    for pid, page in id_map.items():
        if page.title and page.title.lower() == name_l:
            return pid
        if Path(pid).stem.lower() == name_l:
            return pid
    return None


def _cand_to_dict(c: Candidate) -> dict:
    return {
        "page": c.page, "title": c.title, "score": c.score,
        "current_tier": c.current_tier, "components": c.components,
        "reasons": c.reasons,
    }


def _render_markdown(payload: dict) -> str:
    lines = [f"# Dreaming run · {payload['today']}", ""]
    lines.append(f"- Window: {payload['since']} → {payload['today']}")
    lines.append(f"- Strategy: {payload['strategy']}")
    lines.append(f"- Threshold: {payload['config']['threshold']}")
    lines.append(f"- Candidate pool: {payload['candidate_pool_size']} "
                 f"(archived + frozen)")
    lines.append(f"- Fresh pages this period: "
                 f"{payload['increment_summary']['fresh_page_count']}")
    if payload['resurgent_tags']:
        lines.append(f"- Resurgent tags: {', '.join(payload['resurgent_tags'])}")
    lines.append("")
    lines.append(f"## Candidates ({len(payload['candidates'])})")
    lines.append("")
    if not payload['candidates']:
        lines.append("_No frozen/archived pages crossed the threshold this run._")
    for i, c in enumerate(payload['candidates'], 1):
        lines.append(f"### {i}. [[{Path(c['page']).stem}]]  ({c['current_tier']}, "
                     f"score {c['score']})")
        lines.append("")
        lines.append(f"- Path: `{c['page']}`")
        for r in c['reasons']:
            lines.append(f"- {r}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**Apply selected:**  "
                 "`/wiki-dream --apply --pages 1,2,3`  ")
    lines.append("**Explain a candidate:**  "
                 "`/wiki-dream --explain <page>`  ")
    lines.append("**Reject silently:** do nothing — the candidates expire when "
                 "the next run advances the watermark.")
    return "\n".join(lines) + "\n"


_TIER_OVERRIDE_KEYS = (
    "tier_override",
    "tier_override_reason",
    "tier_override_set_at",
)


def _apply_promote(root: Path, cand: Candidate, today: date) -> bool:
    page_path = root / cand.page
    if not page_path.exists():
        return False
    text = page_path.read_text(encoding="utf-8")
    import re
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not fm_match:
        return False
    fm = fm_match.group(1)
    body = text[fm_match.end():]
    # Strip ALL prior dream-related override lines (re-applying the same page
    # used to leave duplicate tier_override_reason / tier_override_set_at
    # behind, one new line per apply call). Match either `key: value` or
    # `key:` with nothing after it.
    fm_lines = []
    for line in fm.splitlines():
        stripped = line.lstrip()
        if any(stripped.startswith(k + ":") or stripped == k
               for k in _TIER_OVERRIDE_KEYS):
            continue
        fm_lines.append(line)
    fm_lines.append("tier_override: active")
    fm_lines.append(f"tier_override_reason: \"auto-dream {today.isoformat()}: "
                    f"{'; '.join(cand.reasons)[:200]}\"")
    fm_lines.append(f"tier_override_set_at: {today.isoformat()}")
    new_text = "---\n" + "\n".join(fm_lines) + "\n---\n" + body
    page_path.write_text(new_text, encoding="utf-8")
    return True


def _log_run(root: Path, today: date, since: date, candidate_count: int) -> None:
    log = root / "log.md"
    if not log.exists():
        return
    entry = (
        f"\n## [{today.isoformat()}] dream | weekly run\n"
        f"- Window: {since.isoformat()} to {today.isoformat()}\n"
        f"- Candidates emitted: {candidate_count}\n"
        f"- Watermark: {today.isoformat()}\n"
    )
    with log.open("a", encoding="utf-8") as f:
        f.write(entry)


def _log_apply(root: Path, today: date, applied: list[str],
               since: date) -> None:
    log = root / "log.md"
    if not log.exists():
        return
    entry = (
        f"\n## [{today.isoformat()}] dream | applied {len(applied)} candidates\n"
        f"- Window: {since.isoformat()} to {today.isoformat()}\n"
        f"- Promoted: {', '.join(f'[[{Path(p).stem}]]' for p in applied)}\n"
        f"- Watermark: {today.isoformat()}\n"
    )
    with log.open("a", encoding="utf-8") as f:
        f.write(entry)


if __name__ == "__main__":
    sys.exit(main())
