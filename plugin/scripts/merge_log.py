#!/usr/bin/env python3
"""Custom git merge driver for log.md (PRD-v1.8 §8).

Git invocation contract: `merge_log.py %A %O %B`
- %A = ours (current branch's version, also output target)
- %O = base (common ancestor)
- %B = theirs (branch being merged in)

Driver behavior (PRD-v1.8 §8 / round-3 + round-4 + round-5):
- exit 0  = wrote merged content to %A; git accepts the result
- exit 1  = driver could not auto-merge; wrote AKWIKI-SEMANTIC-CONFLICT
            block to %A (NOT git merge-file). git keeps %A as unmerged.

Entry classification (round-5 finalized):
- **Common**: same entry_hash present in 2+ of {ours, base, theirs}.
  Render with `render_body_clean` (strip any old Sync-side annotations,
  no new annotation added).
- **Unique-side**: hash present in exactly one of {ours, theirs} and not
  in base. Render with `render_body_with_side(body, "ours" or "theirs")`.
- **Same-triple-different-body**: same (date, action, canonical_subject)
  triple in both ours and theirs but with different hashes. Both kept with
  Sync-side labels. Base version of this triple (if any) is dropped.

Sync-side semantics: a body line `- Sync-side: ours/theirs` rendered AFTER
the entry's existing body lines, idempotently (any pre-existing Sync-side
line is stripped first; a single fresh one is appended).

entry_hash canonical form (M1 round-3):
- subject: strip (side: ...) annotations + .strip()
- body: skip Sync-side lines; for known unordered fields (Files:, Created:,
  Updated:, Promoted:, Linked to:, Skipped:) sort the comma-separated list
  internally; preserve line order otherwise; drop blank lines
- payload: f"{date}|{action}|{subject}\\n" + "\\n".join(canonical_body)
- hash: SHA-256 hexdigest

Failure path (round-4 simplification): any exception (parse error, IO,
unexpected exception) → write_semantic_marker + exit 1. Never call git
merge-file; wiki structure semantics outweigh textual 3-way ability.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

# Make wiki_lib importable when git invokes us from within the repo
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wiki_lib import parse_log, LogEntry  # noqa: E402

# ────────────────────── canonical form ──────────────────────────

# `(side: ours)` / `(side: theirs)` suffix stripped from subject before hash
SIDE_LABEL_RE = re.compile(r"\s*\(side:\s*(ours|theirs)\s*\)\s*$",
                           re.IGNORECASE)

# `- Sync-side: ours` / `- Sync-side: theirs` body line — stripped before
# hash and before render (idempotent rendering)
SYNC_BODY_RE = re.compile(r"^\s*-\s*Sync-side:\s*(ours|theirs)\s*$",
                          re.IGNORECASE)

# Body fields whose value is a comma-separated UNORDERED set; sort their
# items so wave-by-wave write-order doesn't produce different hashes
UNORDERED_LIST_FIELDS = ("Files:", "Created:", "Updated:",
                         "Promoted:", "Linked to:", "Skipped:")


def canonicalize_subject(subject: str) -> str:
    """Strip side label and whitespace. PRD-v1.8 §8 H5 round 3."""
    return SIDE_LABEL_RE.sub("", subject).strip()


def canonicalize_body_line(line: str):
    """Return canonical form, or None if the line should be dropped from hash.

    - Sync-side body lines → None (stripped from hash)
    - Known unordered list fields → sort comma-separated items
    - Other lines → preserved as-is (right-stripped)
    """
    s = line.rstrip()
    if SYNC_BODY_RE.match(s):
        return None
    for prefix in UNORDERED_LIST_FIELDS:
        m = re.match(rf"^(\s*-?\s*{re.escape(prefix)})\s*(.*)$", s)
        if m:
            head, tail = m.groups()
            items = sorted(x.strip() for x in tail.split(",") if x.strip())
            return f"{head} {', '.join(items)}"
    return s


def entry_hash(entry: LogEntry) -> str:
    """SHA-256 over canonicalized (date, action, subject, body) payload.

    PRD-v1.8 §8 M1 round-3: preserve body line order (only sort within
    UNORDERED_LIST_FIELDS), strip blank lines, strip Sync-side annotations.
    """
    canon_subject = canonicalize_subject(entry.subject)
    canon_body_lines = []
    for line in entry.body_lines:
        c = canonicalize_body_line(line)
        if c is not None and c.strip():
            canon_body_lines.append(c)
    payload = (f"{entry.date.isoformat()}|{entry.action}|{canon_subject}\n"
               + "\n".join(canon_body_lines))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ────────────────────── rendering ──────────────────────────

def render_body_with_side(body_lines: list[str], side: str) -> list[str]:
    """For unique-side / same-triple-diff-body entries.

    Idempotent: strips ALL existing Sync-side lines, then appends ONE fresh
    line. Multi-round sync converges to a single annotation per entry.
    """
    cleaned = [l for l in body_lines if not SYNC_BODY_RE.match(l)]
    cleaned.append(f"- Sync-side: {side}")
    return cleaned


def render_body_clean(body_lines: list[str]) -> list[str]:
    """For common entries — only strip old Sync-side, no new annotation."""
    return [l for l in body_lines if not SYNC_BODY_RE.match(l)]


def write_semantic_marker(a_path: str, o_path: str, b_path: str,
                          reason: str) -> None:
    """Driver-failure handler (round-4 / round-5 simplification).

    Writes an AKWIKI-SEMANTIC-CONFLICT block to %A containing the reason
    and the three-way originals for user reference. Always followed by
    exit 1 — never trust git to write conflict markers for us.
    """
    try:
        ours = Path(a_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        ours = "<<could not read ours>>"
    try:
        base = Path(o_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        base = "<<could not read base>>"
    try:
        theirs = Path(b_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        theirs = "<<could not read theirs>>"
    block = (
        f"<<<<<<< AKWIKI-SEMANTIC-CONFLICT: {reason}\n"
        f"# Driver could not auto-merge this file.\n"
        f"# Reason: {reason}\n"
        f"# Resolve manually then `git add` and `git commit`.\n"
        f"# (Three versions below are for your reference; replace the\n"
        f"#  entire block with your resolved content.)\n"
        f"#\n"
        f"# --- ours (your local) ---\n"
        f"{ours}\n"
        f"# --- base (common ancestor) ---\n"
        f"{base}\n"
        f"# --- theirs (remote) ---\n"
        f"{theirs}\n"
        f">>>>>>> AKWIKI-SEMANTIC-CONFLICT-END\n"
    )
    Path(a_path).write_text(block, encoding="utf-8")


# ────────────────────── main merge ──────────────────────────

LOG_HEADER_LINE_RE = re.compile(r"^##\s+\[\d{4}-\d{2}-\d{2}\]\s")


def _extract_header(text: str) -> str:
    """Header = everything before the first `## [YYYY-MM-DD]` line.

    Includes the trailing blank line(s). If the file has no entry headers
    (empty log), the entire content is treated as header.
    """
    lines = text.splitlines(keepends=False)
    header = []
    for line in lines:
        if LOG_HEADER_LINE_RE.match(line):
            break
        header.append(line)
    return "\n".join(header).rstrip() + "\n\n"


def _triple(entry: LogEntry):
    """Identity tuple for same-triple detection (canonicalized)."""
    return (entry.date, entry.action, canonicalize_subject(entry.subject))


def _classify_and_merge(ours: list[LogEntry], base: list[LogEntry],
                       theirs: list[LogEntry]) -> list[tuple[LogEntry, str | None]]:
    """Return list of (entry, side) tuples, sorted, with side label decided
    per PRD-v1.8 §8 M5 round-5 classification."""
    ours_h = {entry_hash(e): e for e in ours}
    base_h = {entry_hash(e): e for e in base}
    theirs_h = {entry_hash(e): e for e in theirs}

    # Build triple → hash maps for ours/theirs (assume one entry per triple
    # per side; if user manually wrote duplicate-triple entries, we keep
    # only the last one — log.md hand-edits are user-error territory).
    ours_by_triple = {_triple(e): h for h, e in ours_h.items()}
    theirs_by_triple = {_triple(e): h for h, e in theirs_h.items()}
    base_by_triple = {_triple(e): h for h, e in base_h.items()}

    # Diverged-triple = same triple in both ours and theirs but different
    # hashes (different bodies). Both versions get kept with side labels.
    diverged_triples = set()
    for trip in ours_by_triple.keys() & theirs_by_triple.keys():
        if ours_by_triple[trip] != theirs_by_triple[trip]:
            diverged_triples.add(trip)

    output: list[tuple[LogEntry, str | None]] = []
    placed: set[str] = set()

    # Pass 1: handle diverged triples (both sides keep their version)
    for trip in diverged_triples:
        ours_h_for_trip = ours_by_triple[trip]
        theirs_h_for_trip = theirs_by_triple[trip]
        output.append((ours_h[ours_h_for_trip], "ours"))
        output.append((theirs_h[theirs_h_for_trip], "theirs"))
        placed.add(ours_h_for_trip)
        placed.add(theirs_h_for_trip)
        # Drop base's version for this triple (it's been replaced by both
        # sides' divergent versions — keeping base would be a third version
        # the user never picked).
        if trip in base_by_triple:
            placed.add(base_by_triple[trip])

    # Pass 2: remaining hashes — classify by side membership
    all_hashes = set(ours_h) | set(base_h) | set(theirs_h)

    # review-1 MEDIUM-1: a base-only hash whose triple has a representative
    # in ours OR theirs is the OBSOLETE pre-update version — drop it.
    # Example caught by reviewer: base = "Files: old.md", ours/theirs both
    # update to "Files: new.md" → previously we kept BOTH old + new.
    triples_with_non_base_version = (set(ours_by_triple.keys())
                                     | set(theirs_by_triple.keys()))

    for h in all_hashes - placed:
        in_ours = h in ours_h
        in_base = h in base_h
        in_theirs = h in theirs_h

        # Pick representative (preferring ours' object for stable line
        # order, since canonical hash already normalized the data fields)
        e = ours_h.get(h) or theirs_h.get(h) or base_h.get(h)

        # Drop base-only entries that have been replaced on at least one
        # side (review-1 MEDIUM-1).
        if (in_base and not in_ours and not in_theirs
                and _triple(e) in triples_with_non_base_version):
            continue

        # Side decision per PRD §8 M5 round-5:
        # - 2+ sides have this hash → common (no side label)
        # - 1 side has this hash → unique-side (label that side)
        side: str | None
        if (in_ours + in_theirs + in_base) >= 2:
            side = None  # common
        elif in_ours:
            side = "ours"
        elif in_theirs:
            side = "theirs"
        else:  # only in base, neither ours nor theirs has it AND triple
            # is also absent from both sides → both sides independently
            # deleted. log.md is append-only by convention, keep (zero
            # data loss). No Sync-side label since no side claims it.
            side = None
        output.append((e, side))

    # Sort: date asc, action lex, hash for tiebreak (deterministic)
    output.sort(key=lambda item: (item[0].date, item[0].action,
                                   entry_hash(item[0])))
    return output


def _render_output(header: str,
                   merged: list[tuple[LogEntry, str | None]]) -> str:
    """Render merged entries back to log.md text."""
    lines = [header.rstrip()]
    for entry, side in merged:
        # Entry header — use canonicalized subject (strips any (side: ...)
        # remnants from prior rounds)
        canon_subject = canonicalize_subject(entry.subject)
        lines.append("")  # blank line before entry
        lines.append(f"## [{entry.date.isoformat()}] "
                     f"{entry.action} | {canon_subject}")
        # Body
        if side:
            body = render_body_with_side(entry.body_lines, side)
        else:
            body = render_body_clean(entry.body_lines)
        for ln in body:
            lines.append(ln)
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) != 4:
        sys.stderr.write(f"usage: {sys.argv[0]} %A %O %B\n")
        return 2
    a_path, o_path, b_path = sys.argv[1], sys.argv[2], sys.argv[3]
    try:
        ours = parse_log(Path(a_path))
        base = parse_log(Path(o_path))
        theirs = parse_log(Path(b_path))
    except Exception as e:
        write_semantic_marker(
            a_path, o_path, b_path,
            f"merge_log: parse_log failed ({type(e).__name__}: {e})")
        return 1

    try:
        merged = _classify_and_merge(ours, base, theirs)
        # Header taken from ours (per PRD §8: 三方相同保留 / 不同取 ours)
        header = _extract_header(Path(a_path).read_text(encoding="utf-8"))
        output = _render_output(header, merged)
        Path(a_path).write_text(output, encoding="utf-8")
    except Exception as e:
        write_semantic_marker(
            a_path, o_path, b_path,
            f"merge_log: classify/render failed ({type(e).__name__}: {e})")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
