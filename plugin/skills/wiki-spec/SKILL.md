---
name: wiki-spec
description: "Spec history management. Before authoring a new spec (PRD / design / RFC / ADR / task-spec / decisions), surface related prior specs from the kata wiki so the author can declare relationships (supersedes / refines / extends / parallel / contradicts). v1.13 Phase 0+2: scan + advisory + enforcement. Phase 3 auto-propagates. Cross-source authoring is served by wiki-import (bulk human ingest) or v1.12 cross-wiki federation."
user-invocable: true
argument-hint: "preflight --new-spec <path> [--wiki=<path>] [--limit=10] [--include-archived] [--enforce] [--enforce-threshold=<float>] [--enforce-mode=strict|confirm]"
---

# wiki-spec

Spec-aware authoring helper. The problem this solves: SDD / superpowers-style
flows generate many specs over time. New specs frequently overlap, refine, or
override older specs, but most tools have no mechanism to make the new-spec
author "answer for" the older specs. Result: a corpus that drifts from a
coherent decision record into a pile of disconnected pages.

`wiki-spec` closes this gap by scanning the wiki at the moment a new spec is
about to be ingested, surfacing prior specs that overlap on tags / title /
explicit wikilinks, and (in Phase 2+) enforcing that the new spec declare
relationships before ingest succeeds.

## Phase 0+2 — advisory scan + enforcement (current)

Scope:
- Scan kata-managed wiki pages whose frontmatter `type` is in `spec_types`
- Score and rank candidates by relevance (title overlap, tag overlap,
  wikilink reference, hub centrality, type match)
- **Phase 2 enforcement (v2.4.0+)**: with `--enforce` (or
  `spec_authoring.enforce_relationship_declaration: true` in SCHEMA.md),
  the script rejects ingest when any candidate scored at-or-above
  `enforcement_score_threshold` is not addressed in the new spec's
  `spec_relationships:` block. Exit codes: 0 = accept, 2 = reject (strict),
  1 = reject (confirm — agent should prompt for resolution).
- Kata-internal only by design — no reaching outside `{wiki_path}/`.

## Cross-source authoring (NOT this skill)

Two valid paths for legacy / cross-project spec corpora:

1. **`wiki-import`** — human-curated bulk import of an existing
   markdown corpus into the kata wiki, with checkpoint/resume +
   per-file prompt. Use this when adopting kata mid-project.
2. **v1.12 cross-wiki federation** (planned) — two kata wikis
   cooperating at the `wiki-query` ↔ `wiki-query` layer. Each side
   stays self-closed; cooperation happens at the query layer, not the
   data layer.

An earlier v1.13 Phase 1 (`external_sources` in `.wiki-plugins.yaml`)
was shipped in v2.3.0 and removed in v2.5.0 — see ADR
`~/.llm-wiki/kata/decisions/2026-05-17-external-sources-removed.md`
and CHANGELOG `[2.5.0]` for the architectural reasoning. Short version:
reaching outside the wiki root for "transit" data violates kata's
self-closing principle and required inventing a lifecycle (graduation /
blocklist / TTL) that didn't belong inside a preflight skill.

## Phase 3 (v2.12.0+) — auto-propagation

When `spec_authoring.auto_propagation.enabled: true` and a newly-
ingested spec contains `kind: supersedes` (or other kinds in
`kinds_to_propagate`), kata automatically applies three changes to
each target page:

1. **Banner** — prepends a marker-delimited block at the top of the
   target body warning the reader the page is superseded
2. **Reverse link** — appends `spec_superseded_by: [{path, date, note}]`
   to the target's frontmatter
3. **Tier flip** — sets `tier_override: archived` + `tier_reason:
   "Superseded by <stem> on <date>"` (skipped if the author already
   pinned the target to a different tier — detected by tier_reason
   NOT starting with "Superseded by")

All three are **idempotent**: re-ingesting the same new spec doesn't
duplicate (banner uses `<!-- kata:spec-banner BEGIN/END -->` sentinel
markers; frontmatter uses dedup-by-path for the spec_superseded_by
list).

**Federation carve-out**: when `target:` is a `kata://<peer>/<path>`
URI (v1.12 cross-wiki federation), kata records the supersession in
a local `{wiki_path}/.spec-reverse-index.yaml` instead of modifying
the peer page (read-only federation contract). Phase 4 lineage view
reads this index alongside in-wiki reverse-links.

**Dreamer integration** (v1.6 dogfood Week 1 channel-mismatch fix):
pages with `spec_superseded_by:` populated, or with `tier_override:
archived` + `tier_reason:` starting with "Superseded by", are
automatically excluded from `wiki-dream` co-occurrence candidates.
The supersede declaration is an explicit reject signal — never
resurface dead specs via inference.

Invoked by `wiki-ingest` step ②c (after page write, before commit)
when `auto_propagation.enabled` is true. Standalone CLI:

```bash
python {plugin_root}/scripts/spec_propagate.py \
    --wiki {wiki_path} \
    --new-spec {wiki-relative-or-absolute-path}
```

## Phase 3 PREVIEW caveat

Phase 3 (auto-propagation) is shipped as **opt-in preview** in v2.13.x.
`spec_authoring.auto_propagation.enabled` defaults to `false` and **must be
the literal `true`** (string `"false"` no longer coerces to truthy).

The v2.13.x implementation is **append-only**: when a new spec is later
edited to drop or downgrade a `kind: supersedes` declaration, the previously
written banner / `spec_superseded_by` / `tier_override` on the old target
**are not reverted**. This means stale propagation state can itself become a
new drift source — exactly the failure mode v1.13 set out to prevent.

The transactional reland with reconcile / rollback semantics is tracked in
`docs/PRD-v1.14-spec-propagation-reconcile.md`. Until v1.14 ships:

- Default-off is the safe state for production wikis
- If you opt in, treat the file edit on the **superseded** page as a deliberate
  write — do not assume removing the source spec's relationship will undo it
- For untrusted spec authoring (e.g. ingest of third-party files), keep Phase 3
  off and rely on Phase 0 advisory + Phase 2 enforcement only

## Phase 4 (shipped v2.13.0)

| Phase | Adds |
|---|---|
| 4 | `wiki-graph --spec-history <topic>` coherence view (lineage tree); text / json / mermaid output |

See `docs/PRD-v1.13-spec-history-management.md` for full design.

## When to use

- Before authoring a new PRD / design doc / RFC / ADR / task spec / ratified decision
- When picking up an SDD-style project at mid-state and adopting kata
- As a periodic audit ("which existing specs overlap and should be merged?")

Skip if:
- The new spec is the very first one in this wiki — no prior specs to compare
- Working in a non-spec-bearing wiki (e.g. pure research wiki with no decisions
  category enabled)

## Configuration in SCHEMA.md

```yaml
spec_authoring:
  enabled: true              # opt-in per wiki
  spec_types:                # frontmatter `type` values treated as specs
    - decisions              # kata-native convention
    - prd
    - design
    - rfc
    - adr
    - task-spec
  preflight: auto            # auto | manual | off
  relationship_kinds:        # allowed `kind` values in spec_relationships entries
    - supersedes             # new replaces old entirely; old should archive
    - refines                # new adds detail to old; old stays but is no longer canonical for the refined part
    - extends                # new builds on old without overriding; old stays canonical
    - parallel               # different concern, same domain
    - contradicts            # explicit disagreement — needs reconciliation
  enforce_relationship_declaration: false  # Phase 2 toggle, off by default
  enforcement_score_threshold: 5.0         # Phase 2: candidates >= this require declaration
  enforcement_mode: strict                 # strict (exit 2) | confirm (exit 1)
```

All fields optional. Defaults are sensible for most kata wikis.

## Path resolution

Same 9-step resolver every other skill uses. Pass `--wiki=<path>` to override.

## Steps

⓪ **Resolve wiki path** (delegated): the script calls `find_wiki_root()`
internally. You do not need to read `SCHEMA.md` first — wiki-spec runs cold.

① **Parse the new spec file**: extract frontmatter (title, type, tags) and
wikilink references from the body. The file need not exist in the wiki yet;
typical drafting flow puts it in `raw/` or a separate working dir.

② **Filter wiki pages**: keep pages where `frontmatter.type` is in
`spec_authoring.spec_types`. Default tier filter is `active` only; pass
`--include-archived` for archived-tier matches (commonly needed for `decisions`
since ratified decisions age into archived tier).

③ **Score each candidate** on:
- title term overlap with new spec (weight 2.0)
- frontmatter tag overlap (weight 1.5)
- wikilink reference from new spec body (weight 3.0 — explicit acknowledgement)
- hub centrality (weight 0.5 — well-connected canonical pages bubble up)
- same-type bonus (+1.0 — same-type prior specs are stronger relationship candidates)

④ **Output JSON** with candidates ranked descending. Includes the new spec's
extracted metadata so callers can verify the parse landed correctly.

⑤ **(Author / agent reads and decides)**: for each top-N candidate, decide
whether to add a `spec_relationships:` entry in the new spec's frontmatter.
Phase 0 does **not** enforce this — it's an advisory step.

## CLI

```bash
# Basic: scan kata wiki
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec ~/.llm-wiki/myproject/raw/drafts/F017-new-spec.md

# Include archived (decisions/ pages often archived):
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec ~/work/F017-new-spec.md \
    --include-archived

# Cap the candidate list:
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec <path> --limit 5

# Phase 2 enforcement: reject ingest if above-threshold candidates not declared
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec <path> --enforce

# Override schema threshold (one-shot tuning for a stricter / looser gate):
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec <path> --enforce --enforce-threshold 4.0

# Confirm mode instead of strict — exit code 1 so caller can prompt the user:
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec <path> --enforce --enforce-mode confirm
```

The output is JSON. Skills calling this script should parse and present the
candidates with their relevance signals; the author then decides relationships.

## Output format

```json
{
  "new_spec": "C:/Users/.../F017-new-spec.md",
  "new_spec_title": "F017 Web Vue2 thin-wrapper migration",
  "new_spec_type": "decisions",
  "new_spec_tags": ["architecture", "callkit", "electron", "vue2", "web"],
  "new_spec_wikilinks": ["f016-electron-vue2-uikit-reuse-resolved", "..."],
  "spec_types_configured": ["adr", "decisions", "design", "prd", "rfc", "task-spec"],
  "tier_filter": ["active", "archived"],
  "tier_breakdown": {"active": 1, "archived": 12, "frozen": 0},
  "candidates_found": 4,
  "candidates": [
    {
      "path": "decisions/F016-...-resolved.md",
      "title": "F016 Electron Vue2 UIKit Reuse — RESOLVED",
      "type": "decisions",
      "tier": "active",
      "score": 14.0,
      "signals": {
        "title_overlap": 1,
        "tag_overlap": 5,
        "link_reference": true,
        "hub_score": 1.0,
        "type_match": true
      }
    }
  ],
  "advisory": "Phase 0 (advisory): ... declare relationships ...",
  "phase": 0
}
```

When `--enforce` is set (or schema's `enforce_relationship_declaration: true`),
the payload adds an `enforcement` block — see `wiki-ingest` SKILL step ②b
and CHANGELOG `[2.4.0]` for full structure.

## Relationship declaration convention

Once the author reviews the candidate list, the new spec's frontmatter should
include:

```yaml
spec_relationships:
  - kind: supersedes
    target: decisions/F015-old-spec.md
    note: "F015's scope absorbed; F015 should be archived"
  - kind: extends
    target: decisions/F011-merge-back.md
    note: "F011 lane discipline carries forward; F017 adds Vue2 specifics"
```

The `target` is a wiki path relative to the wiki root (or a stem-only
form, or `[[wikilink]]`, or `target.md` with or without the extension —
all normalized for the enforcement coverage check). The `note` field is
free-form and recommended.

## Reporting back

After running:

```
[Operation] wiki-spec preflight | <new-spec-title>

[Candidates surfaced]
- decisions/F016-...-resolved.md  (score 14.0, link+title+5tags+type-match)
- decisions/electron-web-master-diff.md  (score 10.25)
- ...

[Suggested next]
→ Author decides relationships for each candidate (or skip if irrelevant)
→ Add `spec_relationships:` to new spec frontmatter before ingest
→ Phase 2+ will block ingest without declaration
```

## Output format conformance

Per `plugin/CLAUDE.md`, use the standard `[Operation] / [Changes] / [Summary] /
[Suggested next]` block on completion.

## Known limitations (Phase 0+2+3+4)

- **Auto-propagation is preview** — Phase 3 ships opt-in (default off) and is append-only. See Phase 3 PREVIEW caveat above; v1.14 will reland with transactional reconcile semantics.
- **Reverse-index not in lineage tree** — Phase 4 reads `.spec-reverse-index.yaml` for counts but does not yet stitch its edges into the rendered lineage. Cross-wiki supersession is recorded but not walked. Tracked for v1.14.
- **Heuristic scoring** — title/tag/link/hub weights are hardcoded; later phases may make them schema-configurable
- **No relationship suggestion** — preflight surfaces candidates but does NOT suggest a relationship kind; the author decides
- **Threshold calibration is per-wiki** — the default `enforcement_score_threshold: 5.0` is calibrated against the smoke-test fixture; high-volume / rich-frontmatter wikis may need a higher threshold to avoid false enforcement triggers
- **Confirm mode is structural only** — `enforcement_mode: confirm` returns exit code 1 with the same envelope as strict; per-candidate explicitly_unrelated marking is a future enhancement (caller currently has to re-run after the user adds declarations or lowers the threshold)

If the candidate list is wrong (false positives / false negatives), check:
- Are the right `spec_types` configured in SCHEMA.md? (Default includes
  `decisions` which is kata's most common spec category)
- Does the new spec have rich frontmatter (tags, type)? Sparse frontmatter
  produces sparse matches
- Does the new spec body have wikilinks? Explicit `[[old-spec]]` links are the
  highest-signal match channel

## See also

- `wiki-ingest` — runs ingest; in Phase 2+ will invoke wiki-spec automatically
  when the source file's `type` is in spec_types
- `wiki-search` — general-purpose search; wiki-spec is the specialized version
  for spec authoring flows
- `wiki-tier` — manage `tier_override` pins; superseded specs may need explicit
  tier flips in Phase 3
- `docs/PRD-v1.13-spec-history-management.md` — full v1.13 design (forthcoming)
