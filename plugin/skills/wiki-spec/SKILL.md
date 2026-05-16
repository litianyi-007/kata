---
name: wiki-spec
description: "Spec history management. Before authoring a new spec (PRD / design / RFC / ADR / task-spec / decisions), surface related prior specs (from the kata wiki AND configured external-source backfills) so the author can declare relationships (supersedes / refines / extends / parallel / contradicts). v1.13 Phase 0+1+2: scan + advisory + enforcement. Phase 3 auto-propagates."
user-invocable: true
argument-hint: "preflight --new-spec <path> [--wiki=<path>] [--limit=10] [--include-archived] [--no-external] [--include-frozen-external] [--enforce] [--enforce-threshold=<float>] [--enforce-mode=strict|confirm]"
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

## Phase 0+1+2 — advisory scan + enforcement (current)

Scope:
- Scan kata-managed wiki pages whose frontmatter `type` is in `spec_types`
- Scan external sources from `.wiki-plugins.yaml` `external_sources:` block
  (default treatments `active` + `raw`; `--include-frozen-external` adds
  frozen sources)
- Score and rank candidates by relevance (title overlap, tag overlap,
  wikilink reference, hub score for kata pages, type match)
- External candidates flagged `writeable: false` — Phase 3 auto-propagation
  will skip them
- URI scheme `external://<source-name>/<path>` for external relationship
  targets
- **Phase 2 enforcement (v2.4.0+)**: with `--enforce` (or
  `spec_authoring.enforce_relationship_declaration: true` in SCHEMA.md),
  the script rejects ingest when any candidate scored at-or-above
  `enforcement_score_threshold` is not addressed in the new spec's
  `spec_relationships:` block. Exit codes: 0 = accept, 2 = reject (strict),
  1 = reject (confirm — agent should prompt for resolution).
- Do **not** auto-propagate (Phase 3)

## Phase 3+ (future)

| Phase | Adds |
|---|---|
| 3 | Auto-propagation: superseded specs get banner + tier flip + reverse-link |
| 4 | `wiki-graph --spec-history <topic>` coherence view |

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
# Basic: scan kata wiki + configured external sources
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec ~/.llm-wiki/myproject/raw/drafts/F017-new-spec.md

# Include archived (decisions/ pages often archived):
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec ~/work/F017-new-spec.md \
    --include-archived

# Cap the candidate list:
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec <path> --limit 5

# Skip external sources (kata-only):
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec <path> --no-external

# Also scan frozen-treatment sources (rare — retired-project corpora):
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec <path> --include-frozen-external

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

## External source configuration (Phase 1)

Phase 1 adds backfill from external markdown corpora — typically a
project's pre-kata SDD spec directory that the team wants to reference
without bulk-importing into kata. Configure in `.wiki-plugins.yaml`:

```yaml
external_sources:
  - name: sdd-specs                  # short slug, used in external://<name>/...
    type: directory                  # Phase 1 only supports directory
    root: ~/work/myproject/docs/specs  # absolute or ~-prefixed path
    treatment: raw                   # active | raw (default) | frozen
    description: "Pre-kata SDD spec corpus, May 2025 onward"
    discover:
      type_field: type               # frontmatter key holding the type
      exclude:                       # optional substring matches to skip
        - drafts/
        - archived/
```

The `treatment` flag controls visibility:

| Treatment | wiki-search default | spec preflight scan |
|---|---|---|
| `active` | Yes — co-equal with kata pages | Yes (always) |
| `raw` (default) | No — excluded from default search | Yes — surfaces for preflight only |
| `frozen` | No | Only with `--include-frozen-external` |

`raw` is the right choice for most adoption scenarios: the historical
corpus stays out of daily search noise but participates in spec preflight
when authoring new specs that might overlap with prior decisions.

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
  "tier_breakdown": {"active": 1, "archived": 12, "frozen": 0, "external": 3},
  "external_sources_scanned": [
    {"name": "sdd-specs", "treatment": "raw", "page_count": 42,
     "scored_count": 3, "elapsed_ms": 28.4}
  ],
  "external_skipped": [],
  "candidates_found": 7,
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
    },
    {
      "path": "external://sdd-specs/F011-merge-back.md",
      "fs_path": "/Users/me/work/myproject/docs/specs/F011-merge-back.md",
      "title": "F011 merge-back lane discipline",
      "type": "decisions",
      "tier": "external",
      "source": "sdd-specs",
      "source_treatment": "raw",
      "writeable": false,
      "score": 8.5,
      "signals": {
        "title_overlap": 0,
        "tag_overlap": 4,
        "link_reference": true,
        "hub_score": 0.0,
        "type_match": true,
        "external_penalty": -0.5
      }
    }
  ],
  "advisory": "Phase 0+1 (advisory): ... declare relationships ... `writeable: false` ...",
  "phase": 1
}
```

Key Phase 1 fields:

- `tier_breakdown.external`: count of external candidates that scored above
  zero (separate from active/archived/frozen which are kata-managed)
- `external_sources_scanned`: per-source diagnostic (page count, scored
  count, elapsed ms)
- `external_skipped`: sources excluded by treatment filter (e.g. frozen
  sources without `--include-frozen-external`)
- `candidates[].source` / `candidates[].source_treatment`: present only
  on external candidates
- `candidates[].writeable: false`: invariant for external candidates;
  Phase 3 auto-propagation will skip them and instead write an internal
  reverse-index file `decisions/.spec-reverse-index.md` (Phase 3 detail)

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

## Known limitations (Phase 0+1+2)

- **No auto-propagation** — Phase 3
- **No coherence view** (lineage tree) — Phase 4
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
