#!/usr/bin/env python3
"""Spec auto-propagation — v1.13 Phase 3 (v2.12.0).

When a newly-ingested spec contains `spec_relationships: [{kind:
supersedes, target: ...}]`, propagate the supersession to the target
page automatically:

1. **Banner** — prepend a marker-delimited block at the top of the
   target page body warning the reader that the page is superseded
2. **Reverse link** — append `spec_superseded_by:` entry to target's
   frontmatter
3. **Tier flip** — set `tier_override: archived` on target with
   `tier_reason: "Superseded by <new-spec> on <date>"` (skip if author
   already pinned the page to a tier)

All three operations are **idempotent**: re-ingesting the same new
spec doesn't duplicate banner / reverse-link / tier override. Banner
uses sentinel markers (`<!-- kata:spec-banner BEGIN/END -->`) so we
can detect existing application and replace in-place.

**Federation carve-out (v1.12 interaction)**: when `target:` is a
`kata://<peer>/<path>` URI, kata does NOT modify the peer page (would
violate the read-only federation contract). Instead, kata writes the
supersession to a kata-internal `{wiki_path}/.spec-reverse-index.yaml`
that Phase 4 lineage view reads. PRD originally wrote this for
external://; the principle is the same for kata://.

Configuration in SCHEMA.md `spec_authoring.auto_propagation:`:

```yaml
spec_authoring:
  auto_propagation:
    enabled: false                  # opt-in per wiki
    kinds_to_propagate:             # which relationship kinds trigger
      - supersedes                  # safe default — only supersession
    auto_tier_flip: true            # set tier_override: archived
    banner_template: |              # optional; default below works
      > **⚠ Superseded by [[{new_stem}]] on {date}.**
      > Reason: {note}
      > This page is preserved for historical reference only.
```

Called by `wiki-ingest` step ②c (after page write, before commit) when
the ingested source's frontmatter `type` is in `spec_types` AND
`auto_propagation.enabled` is true.

Usage:

    spec_propagate.py --wiki <path> --new-spec <new-spec-page-path>
                      [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

from wiki_lib import (
    emit,
    find_wiki_root,
    load_schema,
    parse_frontmatter,
)


# Sentinel markers — must NOT collide with anything an author would
# realistically write. Comment syntax is markdown HTML comment so it
# renders invisibly in both Obsidian and GitHub.
BANNER_BEGIN = "<!-- kata:spec-banner BEGIN -->"
BANNER_END = "<!-- kata:spec-banner END -->"

DEFAULT_BANNER_TEMPLATE = (
    "> **⚠ Superseded by [[{new_stem}]] on {date}.**\n"
    "> Reason: {note}\n"
    "> This page is preserved for historical reference only."
)

DEFAULT_KINDS_TO_PROPAGATE = ["supersedes"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_kata_uri(target: str) -> bool:
    return isinstance(target, str) and target.startswith("kata://")


def _strip_wikilink_brackets(s: str) -> str:
    s = s.strip()
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2].strip()
    if "|" in s:
        s = s.split("|", 1)[0].strip()
    return s


def _resolve_local_target(wiki_root: Path, target: str) -> Path | None:
    """Given a `spec_relationships.target` string, resolve to a local
    wiki page on disk. Returns None for kata:// URIs (caller handles
    those via the reverse-index path), unresolvable references, or
    paths that would escape the wiki root.

    Path-traversal guard: absolute targets are rejected outright; relative
    targets with `..` segments are resolved and then checked with
    `relative_to(wiki_root)`. Without this guard, a malicious or accidental
    `spec_relationships.target` of `"../../../etc/foo"` could cause kata to
    propagate a banner/tier flip onto a file outside the wiki.
    """
    if _is_kata_uri(target):
        return None
    t = _strip_wikilink_brackets(target)
    if not t:
        return None
    # Reject absolute targets. The spec contract says `target` is wiki-
    # relative path (or stem, or kata:// URI). An absolute path is a
    # bug, an attack, or both — never legitimate.
    if Path(t).is_absolute():
        return None
    if not t.endswith(".md"):
        t = t + ".md"
    root_resolved = wiki_root.resolve()
    candidate = (wiki_root / t).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        # Resolved path escapes the wiki root — reject. This catches
        # `../../etc/foo`, Windows alt-separator escape, and symlink
        # traversal.
        return None
    if candidate.is_file():
        return candidate
    # Stem-only declaration ("F015-old") — search wiki for matching stem.
    # rglob is scoped to wiki_root so this branch can't escape.
    stem = Path(t).stem.lower()
    for md in wiki_root.rglob("*.md"):
        if "raw" in md.parts or "_archive" in md.parts:
            continue
        if md.stem.lower() == stem:
            return md
    return None


def _render_banner(template: str, new_stem: str, today: str,
                   note: str) -> str:
    """Fill the banner template; return the marker-delimited block."""
    body = template.format(
        new_stem=new_stem,
        date=today,
        note=(note or "(no note)").replace("\n", " "),
    )
    return f"{BANNER_BEGIN}\n{body}\n{BANNER_END}\n"


def _replace_or_prepend_banner(text: str, banner_block: str) -> str:
    """If the text already contains a kata:spec-banner block, replace
    it in-place. Otherwise prepend after the frontmatter (or at the
    start if no frontmatter)."""
    # Strip any existing banner block (idempotent re-application)
    pattern = re.compile(
        re.escape(BANNER_BEGIN) + r".*?" + re.escape(BANNER_END) + r"\n?",
        re.DOTALL,
    )
    text_no_banner = pattern.sub("", text, count=1)
    # Insert new banner after frontmatter close
    fm_match = re.match(r"^---\s*\n.*?\n---\s*\n", text_no_banner, re.DOTALL)
    if fm_match:
        insert_at = fm_match.end()
        return (
            text_no_banner[:insert_at]
            + "\n" + banner_block + "\n"
            + text_no_banner[insert_at:]
        )
    # No frontmatter — prepend
    return banner_block + "\n" + text_no_banner


# Frontmatter mutation: regex-based, line-oriented (same pattern as
# wiki_dream._apply_promote). The kata-stdlib YAML subset can't write
# back nested structures, so we work directly with the text.

_TIER_KEYS = ("tier_override", "tier_reason", "tier_set_at")


def _strip_keys(fm_lines: list[str], keys: tuple[str, ...]) -> list[str]:
    """Remove any top-level frontmatter lines matching `<key>:` or `<key>`."""
    out = []
    skip_until_dedent = False
    for line in fm_lines:
        stripped = line.lstrip()
        # If we're inside a block we're stripping (e.g. list under
        # spec_superseded_by:), skip indented lines until we find a
        # new top-level key.
        if skip_until_dedent:
            if line and not line[0].isspace():
                skip_until_dedent = False
            else:
                continue
        # New top-level key check
        if line and not line[0].isspace():
            is_target = any(
                stripped.startswith(k + ":") or stripped == k
                for k in keys
            )
            if is_target:
                # If the value is `:` with nothing after (list-style),
                # also strip indented child lines.
                if stripped.endswith(":") or stripped.rstrip() == \
                        stripped.split(":", 1)[0] + ":":
                    skip_until_dedent = True
                continue
        out.append(line)
    return out


def _existing_superseded_by_entries(fm_dict: dict) -> list[dict]:
    """Parse existing spec_superseded_by from a parsed frontmatter dict."""
    raw = fm_dict.get("spec_superseded_by") or []
    if not isinstance(raw, list):
        return []
    return [e for e in raw if isinstance(e, dict)]


def _format_superseded_by_block(entries: list[dict]) -> list[str]:
    """Render list[{path, date, note}] as YAML lines."""
    lines = ["spec_superseded_by:"]
    for e in entries:
        lines.append(f"  - path: {e.get('path', '')}")
        lines.append(f"    date: {e.get('date', '')}")
        note = (e.get("note") or "").replace("\n", " ").replace('"', '\\"')
        lines.append(f"    note: \"{note}\"")
    return lines


def _apply_propagation_to_local(target_path: Path, new_spec_stem: str,
                                 new_spec_rel_path: str, today: str,
                                 note: str, banner_template: str,
                                 auto_tier_flip: bool) -> dict:
    """Apply the 3 propagation actions to a local target page. Returns
    a result dict with what changed (caller logs it)."""
    text = target_path.read_text(encoding="utf-8")
    original = text

    # --- Step 1: banner ---
    banner = _render_banner(banner_template, new_spec_stem, today, note)
    text_with_banner = _replace_or_prepend_banner(text, banner)
    banner_changed = (text_with_banner != text)
    text = text_with_banner

    # --- Step 2: reverse link in frontmatter + Step 3: tier flip ---
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not fm_match:
        # Target has no frontmatter; create one for our metadata
        fm_lines = []
        body = text
    else:
        fm_text = fm_match.group(1)
        body = text[fm_match.end():]
        fm_lines = fm_text.splitlines()

    # Parse existing frontmatter to detect prior superseded_by entries
    if fm_match:
        parsed_fm, _ = parse_frontmatter(text)
    else:
        parsed_fm = {}

    existing_entries = _existing_superseded_by_entries(parsed_fm)
    new_entry = {
        "path": new_spec_rel_path,
        "date": today,
        "note": note or "",
    }
    # Dedup by `path` — if a prior entry has same path, replace it (note may
    # have been updated). Else append.
    by_path = {e.get("path"): e for e in existing_entries}
    by_path[new_spec_rel_path] = new_entry
    merged_entries = list(by_path.values())

    # Strip ALL prior spec_superseded_by block + tier_override keys (if
    # auto_tier_flip is on AND we're the one who set it).
    superseded_keys = ("spec_superseded_by",)
    keys_to_strip = superseded_keys
    author_pinned_tier = False
    if auto_tier_flip:
        existing_tier_override = parsed_fm.get("tier_override")
        existing_tier_reason = parsed_fm.get("tier_reason") or ""
        # Heuristic: if the existing tier_reason starts with "Superseded by"
        # then we set it; safe to overwrite. Otherwise the author pinned the
        # page manually; leave it alone.
        if existing_tier_override and not str(existing_tier_reason).startswith(
                "Superseded by"):
            author_pinned_tier = True
        else:
            keys_to_strip = keys_to_strip + _TIER_KEYS

    fm_lines = _strip_keys(fm_lines, keys_to_strip)

    # Append new superseded_by block + (optionally) tier override
    fm_lines.extend(_format_superseded_by_block(merged_entries))
    tier_flipped = False
    if auto_tier_flip and not author_pinned_tier:
        fm_lines.append("tier_override: archived")
        fm_lines.append(
            f"tier_reason: \"Superseded by {new_spec_stem} on {today}\""
        )
        fm_lines.append(f"tier_set_at: {today}")
        tier_flipped = True

    new_fm = "\n".join(fm_lines)
    new_text = "---\n" + new_fm + "\n---\n" + body

    if new_text != original:
        target_path.write_text(new_text, encoding="utf-8")

    return {
        "target_path": str(target_path),
        "banner_inserted_or_updated": banner_changed,
        "reverse_link_count": len(merged_entries),
        "tier_flipped": tier_flipped,
        "author_tier_preserved": author_pinned_tier,
        "page_unchanged": new_text == original,
    }


# ---------------------------------------------------------------------------
# kata:// federation supersede — write to local reverse-index
# ---------------------------------------------------------------------------

REVERSE_INDEX_FILENAME = ".spec-reverse-index.yaml"


def _append_to_reverse_index(wiki_root: Path, kata_uri: str,
                              superseded_by: str, today: str,
                              note: str) -> dict:
    """Record a cross-wiki supersession in the local reverse-index file.
    Idempotent: if an entry with the same `external_target` +
    `superseded_by` pair exists, update the note + date in place
    instead of appending a duplicate.
    """
    idx_path = wiki_root / REVERSE_INDEX_FILENAME
    if idx_path.is_file():
        existing = idx_path.read_text(encoding="utf-8")
    else:
        existing = ""

    # Append-with-dedup. Simple line-based detection — the file is
    # owned by kata, format is stable, so a regex marker per entry is
    # enough.
    marker = f"  - external_target: {kata_uri}\n    superseded_by: {superseded_by}\n"
    if marker in existing:
        # Already recorded; only date/note might have changed. Replace
        # the existing entry block.
        pattern = re.compile(
            re.escape(marker) + r"    date: [^\n]*\n    note: [^\n]*\n",
        )
        new_block = (
            marker
            + f"    date: {today}\n"
            + f"    note: \"{(note or '').replace(chr(34), chr(92) + chr(34))}\"\n"
        )
        new_text = pattern.sub(new_block, existing, count=1)
        was_added = False
    else:
        header_needed = "external_supersessions:" not in existing
        prefix = "external_supersessions:\n" if header_needed else ""
        new_block = (
            marker
            + f"    date: {today}\n"
            + f"    note: \"{(note or '').replace(chr(34), chr(92) + chr(34))}\"\n"
        )
        new_text = existing + prefix + new_block
        was_added = True

    if new_text != existing:
        idx_path.write_text(new_text, encoding="utf-8")
    return {
        "reverse_index_path": str(idx_path),
        "added": was_added,
        "kata_uri": kata_uri,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description="Auto-propagate spec_relationships from a newly-ingested "
                    "spec to its targets (banner + reverse-link + tier flip)."
    )
    p.add_argument("--wiki", default=None,
                   help="Wiki root path. If omitted, find_wiki_root() resolves it.")
    p.add_argument("--new-spec", required=True,
                   help="Wiki-relative path (or absolute) to the just-ingested "
                        "spec page that holds the spec_relationships block.")
    p.add_argument("--dry-run", action="store_true",
                   help="Compute what would change but do not write.")
    args = p.parse_args()

    root = find_wiki_root(args.wiki)
    schema = load_schema(root)
    spec_authoring = schema.get("spec_authoring") or {}
    auto_prop = spec_authoring.get("auto_propagation") or {}

    # Strict bool check — `bool("false")` is True in Python, and SCHEMA.md
    # is YAML which doesn't always coerce; require the value to be exactly
    # the literal True. Anything else (missing, false, "false", null, 0)
    # disables propagation.
    if auto_prop.get("enabled") is not True:
        emit({
            "phase": 3,
            "enabled": False,
            "advisory": ("auto_propagation.enabled is not literal true in "
                         "SCHEMA.md; no propagation performed. Set "
                         "`spec_authoring.auto_propagation.enabled: true` "
                         "to opt in. **Phase 3 PREVIEW**: see "
                         "PRD-v1.14-spec-propagation-reconcile.md for the "
                         "transactional reland; v2.13.x propagation is "
                         "append-only and not reversible — opt in at own "
                         "risk."),
        })
        return 0

    kinds_to_propagate = auto_prop.get("kinds_to_propagate") or list(
        DEFAULT_KINDS_TO_PROPAGATE
    )
    auto_tier_flip = bool(auto_prop.get("auto_tier_flip", True))
    banner_template = auto_prop.get("banner_template") or DEFAULT_BANNER_TEMPLATE

    new_spec_path = Path(args.new_spec).expanduser()
    if not new_spec_path.is_absolute():
        new_spec_path = (root / new_spec_path).resolve()
    if not new_spec_path.is_file():
        emit({"error": f"--new-spec not found: {new_spec_path}"})
        return 1

    try:
        new_spec_rel = new_spec_path.resolve().relative_to(
            root.resolve()
        ).as_posix()
    except ValueError:
        # spec lives outside the wiki — unusual but tolerate
        new_spec_rel = str(new_spec_path)
    new_spec_stem = Path(new_spec_rel).stem

    new_text = new_spec_path.read_text(encoding="utf-8")
    new_fm, _ = parse_frontmatter(new_text)
    relationships = new_fm.get("spec_relationships") or []
    if not isinstance(relationships, list):
        emit({
            "phase": 3,
            "enabled": True,
            "advisory": "new spec has no spec_relationships list; nothing to propagate.",
            "propagations": [],
        })
        return 0

    today = date.today().isoformat()
    propagations: list[dict] = []
    skipped: list[dict] = []

    for rel in relationships:
        if not isinstance(rel, dict):
            continue
        kind = rel.get("kind")
        target = rel.get("target")
        note = str(rel.get("note") or "")
        if kind not in kinds_to_propagate:
            skipped.append({
                "kind": kind,
                "target": target,
                "reason": (
                    f"kind={kind!r} not in kinds_to_propagate "
                    f"({kinds_to_propagate})"
                ),
            })
            continue
        if not target:
            skipped.append({"kind": kind, "target": None,
                            "reason": "missing target"})
            continue

        # kata:// federation target → write to local reverse-index
        if _is_kata_uri(str(target)):
            if args.dry_run:
                propagations.append({
                    "kind": kind,
                    "target": target,
                    "channel": "reverse-index",
                    "dry_run": True,
                })
                continue
            r = _append_to_reverse_index(
                root, str(target), new_spec_rel, today, note,
            )
            r["kind"] = kind
            r["target"] = target
            r["channel"] = "reverse-index"
            propagations.append(r)
            continue

        # Local target — resolve to wiki page on disk
        local_target = _resolve_local_target(root, str(target))
        if local_target is None:
            skipped.append({
                "kind": kind,
                "target": target,
                "reason": (
                    "could not resolve target to a local wiki page; "
                    "for cross-wiki supersession use a kata:// URI"
                ),
            })
            continue

        if args.dry_run:
            propagations.append({
                "kind": kind,
                "target": str(local_target.relative_to(root).as_posix()),
                "channel": "in-place",
                "dry_run": True,
            })
            continue

        r = _apply_propagation_to_local(
            local_target,
            new_spec_stem=new_spec_stem,
            new_spec_rel_path=new_spec_rel,
            today=today,
            note=note,
            banner_template=banner_template,
            auto_tier_flip=auto_tier_flip,
        )
        r["kind"] = kind
        r["target"] = target
        r["channel"] = "in-place"
        try:
            r["target_rel"] = local_target.relative_to(root).as_posix()
        except ValueError:
            r["target_rel"] = str(local_target)
        propagations.append(r)

    emit({
        "phase": 3,
        "enabled": True,
        "new_spec": new_spec_rel,
        "new_spec_stem": new_spec_stem,
        "kinds_propagated": kinds_to_propagate,
        "auto_tier_flip": auto_tier_flip,
        "propagations": propagations,
        "skipped": skipped,
        "dry_run": args.dry_run,
        "advisory": (
            "Phase 3: each `kind: supersedes` (and any other kind in "
            "kinds_to_propagate) on a local target writes a sentinel-"
            "marked banner + frontmatter reverse-link + tier_override: "
            "archived (unless author pinned the tier manually). kata:// "
            "targets are recorded in .spec-reverse-index.yaml (peer "
            "wiki is NOT modified — read-only federation contract)."
        ),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
