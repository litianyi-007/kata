---
name: wiki-spec
description: "Spec history management. Before authoring a new spec (PRD / design / RFC / ADR / task-spec / decisions), surface related prior specs so the author can declare relationships (supersedes / refines / extends / parallel / contradicts). v1.13 Phase 0 — advisory only. Phase 1 adds external sources; Phase 2 enforces relationship declaration; Phase 3 auto-propagates."
user-invocable: true
argument-hint: "preflight --new-spec <path> [--wiki=<path>] [--limit=10] [--include-archived]"
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

## Phase 0 — advisory only (current)

Scope:
- Print a ranked list of related prior specs from the wiki
- Surface tier + relevance signals (title overlap, tag overlap, wikilink reference, hub score, type match)
- Do **not** enforce relationship declaration
- Do **not** auto-propagate (e.g. archive old specs marked superseded)
- Do **not** query external sources (added in Phase 1)

## Phase 1+ (future)

| Phase | Adds |
|---|---|
| 1 | External sources via `.wiki-plugins.yaml` `treatment: raw\|frozen\|active` |
| 2 | Required `spec_relationships:` frontmatter; ingest rejects on missing |
| 3 | Auto-propagation: superseded specs get banner + tier flip + reverse-link |
| 4 | `wiki-graph --spec-history <topic>` coherence view |

See `docs/PRD-v1.13-spec-history-management.md` (forthcoming) for full design.

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
  enforce_relationship_declaration: false  # Phase 2 toggle, off in Phase 0
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
# Basic: scan wiki for specs related to a new draft
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec ~/.llm-wiki/myproject/raw/drafts/F017-new-spec.md

# Include archived (decisions/ pages often archived):
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec ~/work/F017-new-spec.md \
    --include-archived

# Cap the candidate list:
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec <path> --limit 5
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
  "advisory": "Phase 0 (advisory): ... declare relationships in spec_relationships ...",
  "phase": 0
}
```

## Relationship declaration convention (Phase 0 — manual)

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

The `target` is a wiki path relative to the wiki root. Phase 1 will introduce
`external://<source-name>/<path>` URI scheme for external-source targets. The
`note` field is free-form and recommended.

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

## Known limitations (Phase 0)

- **No external sources** — Phase 1
- **No enforcement** — Phase 2
- **No auto-propagation** — Phase 3
- **No coherence view** (lineage tree) — Phase 4
- **Heuristic scoring** — title/tag/link/hub weights are hardcoded; Phase 1+ may make them schema-configurable
- **No relationship suggestion** — Phase 0 surfaces candidates but does NOT suggest a relationship kind; the author decides

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
