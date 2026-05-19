---
spec_relationships:
  - kind: extends
    target: docs/PRD-v1.10-external-searchable-sources.md
    note: |
      v1.10 introduced .wiki-plugins.yaml as a query-fallback mechanism
      (local-miss → external CLI → save-to-raw → ingest). v1.13 keeps
      that pipeline intact and adds two things on top: (1) a `treatment`
      flag per source (raw | frozen | active) controlling how aggressively
      the source is surfaced in default queries; (2) wires external
      sources into spec preflight so that a kata adoption can scan a
      pre-existing SDD corpus without bulk-importing it first. v1.10
      remains a valid PRD; v1.13 Phase 1 is strictly additive.
  - kind: refines
    target: docs/PRD-v1.11-session-ingest.md
    note: |
      Both PRDs address "the agent at authoring time should see something
      it currently doesn't." v1.11 focuses on what was learned in a CLI
      session; v1.13 focuses on what was decided in prior specs. They are
      complementary, not overlapping. v1.11 Phase 0 (the three hint flags
      on wiki-ingest) is still in flight and unaffected by this PRD.
  - kind: references
    target: docs/idea-coverage-matrix-dreamer.md
    note: |
      Coverage-matrix dreamer surfaces gap candidates (absent cells in
      a stack × platform implicit grid). v1.13 Phase 3 auto-propagation
      provides reject signals (this old spec was just superseded → don't
      resurface it as a dream candidate). The two integrate naturally as
      Phase 3 + future dreamer-v2 work.
  - kind: extends
    target: docs/PRD-v1.6-autodreaming.md
    note: |
      v1.6 dreamer's accept primitive (--apply tier-bump) does not match
      the actual accept channel (--pin permanent override) observed in
      the NECallKit Week 1 dogfood — see docs/dogfood-v1.6.md Week 1
      surprises. v1.13 Phase 3 introduces a more targeted reject channel
      ("this spec was superseded") that lets the dreamer learn from
      explicit lifecycle events rather than inferring relevance from
      co-occurrence alone.
---

# PRD v1.13 — Spec History Management

Status: Draft v1 — Phase 3 is PREVIEW in shipped v2.13.x
Date: 2026-05-16 (last updated 2026-05-19 after codex audit task-mpci827r-1prafp)
Author: surebeli

> **Status update — 2026-05-19**: Phases 0, 2, 4 ship as `ship-with-caveats`.
> Phase 3 (auto-propagation) is **opt-in preview** — the v2.13.x implementation
> is append-only and cannot reverse banner / `spec_superseded_by` / tier flip
> when the source spec is later edited to drop the `supersedes` declaration.
> Stale propagated state thus becomes a new drift source — exactly the failure
> mode v1.13 set out to prevent. The transactional reland with reconcile /
> rollback semantics is tracked in
> `docs/PRD-v1.14-spec-propagation-reconcile.md`. Until then,
> `auto_propagation.enabled` defaults to `false` and must be the literal
> `true` (string `"false"` no longer coerces). See
> "Phase 3 PREVIEW caveat" in `plugin/skills/wiki-spec/SKILL.md`.

## Context

LLM-driven spec-driven-development workflows (SDD / superpowers / similar
plugins) make it cheap to generate well-structured specs. A team adopting
these workflows produces dozens of spec documents per quarter — PRDs,
design docs, RFCs, ADRs, task-level specs. Each spec, in isolation, is
good.

Over time, the spec corpus develops a structural problem. New specs
overlap with, refine, or sometimes overturn older specs. But when the new
spec is being authored, the agent has no mechanism that forces it to
**answer for** the existence of the older overlapping specs. The new
spec may declare a contradictory invariant, propose a redesign that
silently obsoletes a prior decision, or repeat a design exploration that
was already settled three months ago.

After 6-12 months, the spec corpus drifts from a coherent decision
record into a pile of related-but-disconnected pages. Readers can't tell
which spec is canonical for a given topic. New engineers waste effort
re-deriving decisions. Old specs that should be archived stay surfaced;
new specs that should explicitly supersede old ones don't say so.

This is the kata wedge applied to a specific corpus shape. Kata exists
to compile project memory; the spec sub-corpus is one of the highest-value
subsets of project memory because specs ARE decisions, not just notes.

## Goals

Primary:

1. **Make the new-spec author answer for prior overlapping specs.** Before
   a spec is ingested, the system surfaces specs whose tags, title, or
   referenced entities overlap and requires the author (human or agent)
   to declare relationships explicitly.

2. **Support mid-project kata adoption.** A team with 6 months of SDD
   specs in `docs/specs/` should be able to plug kata in without first
   bulk-importing every old spec. External-source backfill (via
   `.wiki-plugins.yaml`) lets the historical corpus participate in
   preflight without being kata-managed.

3. **Auto-propagate lifecycle events.** When the new spec declares
   `kind: supersedes`, the targeted old spec should automatically gain
   a banner, a reverse-link, and a tier flip — so future readers landing
   on the old spec see "this was replaced by X."

4. **Provide a lineage view.** Given a topic or spec, return the full
   chain of supersession / refinement / extension so a reader can
   reconstruct decision history without manual archaeology.

Secondary:

5. Feed v1.6 dreamer with explicit reject signals (this spec was
   superseded → don't resurface it on co-occurrence).

6. Match kata's principle that human curates, AI maintains — the author
   sees candidates, decides relationships; the system handles file
   updates.

## Non-goals

1. **Replacing SDD / superpowers / similar tools.** v1.13 is a layer
   above whatever spec-generation tool is in use. It does not generate
   spec content.

2. **Cross-organizational spec sharing.** v1.13 operates within a single
   kata wiki (Phase 1 external-sources backfill was tried and removed in
   v2.5.0 — see that Phase's section below). Cross-wiki federation
   (v1.12) is a separate PRD and now handles all cross-source needs.

3. **Resolving spec contradictions.** v1.13 surfaces the contradiction
   (kind: contradicts) and lets the author write a reconciliation note;
   it does not auto-merge or auto-resolve.

4. **Semantic equivalence detection.** Phase 0 uses lexical signals (tag
   overlap, title overlap, wikilink reference, hub score). It does not
   embed pages or compute semantic similarity. This is deferred to
   future work; the lexical signals are sufficient for the workflows
   v1.13 targets.

## Design overview

The feature ships as **4 phases**. Each phase has a self-contained user
value; subsequent phases compose on top.

```
Phase 0 (v2.2.0, shipped 2026-05-16)
  ├─ Advisory preflight against kata-managed pages
  ├─ JSON output for agent consumption
  └─ Manual relationship declaration in spec_relationships frontmatter

Phase 1
  ├─ External source preflight (via .wiki-plugins.yaml)
  ├─ Treatment flag (raw | frozen | active)
  └─ URI scheme for external relationships (external://<source>/<path>)

Phase 2
  ├─ Required relationship declaration
  └─ Ingest rejection for missing relationships above score threshold

Phase 3
  ├─ Auto-propagation: supersedes → banner + tier flip + reverse-link
  ├─ External-source supersession (kata cannot edit, but tracks reverse-index)
  └─ v1.6 dreamer reject-signal integration

Phase 4
  └─ wiki-graph --spec-history <topic>: lineage view (tree / mermaid)
```

## Core data model

### Schema-level config (`spec_authoring` block in SCHEMA.md)

```yaml
spec_authoring:
  enabled: true                          # opt-in per wiki
  spec_types:                            # frontmatter `type` values treated as specs
    - decisions                          # kata-native (default)
    - prd                                # SDD / superpowers convention
    - design
    - rfc
    - adr
    - task-spec
  preflight: auto                        # auto | manual | off
  relationship_kinds:                    # allowed `kind` values
    - supersedes
    - refines
    - extends
    - parallel
    - contradicts
    - references                         # weakest — "is aware of"
    - custom                             # free-form, requires note field
  enforce_relationship_declaration: false  # Phase 2 toggle
  enforcement_score_threshold: 5.0       # Phase 2: only candidates above
                                          # this score require declaration
  auto_propagation:                      # Phase 3 nested config
    enabled: false
    banner_template: |
      > **⚠ Superseded by [[{target_title}]]** on {date}.
      > Reason: {note}
      > This page is preserved for historical reference only.
    archive_on_supersede: true           # tier flip to archived
    reverse_index: true                  # write spec_superseded_by reverse link
```

### Per-spec frontmatter convention

Every spec-type page may have a `spec_relationships:` block:

```yaml
spec_relationships:
  - kind: supersedes
    target: decisions/F015-old-auth.md
    note: "Token-pair design replaces single-bearer-token in F015"
  - kind: extends
    target: external://sdd-specs/F011-merge-back.md
    note: "F011 lane discipline carries forward; F017 adds Vue2 specifics"
  - kind: contradicts
    target: decisions/F008-implicit-tenants.md
    note: |
      F008 assumed implicit tenant inference from session; F017 requires
      explicit tenant header. This is a deliberate reversal; F008 should
      not be archived because the reasoning is still useful as a
      cautionary tale.
```

Field constraints:

| Field | Required | Notes |
|---|---|---|
| `kind` | Yes | Must be in `spec_authoring.relationship_kinds` |
| `target` | Yes | Either a wiki-relative path OR `external://<source>/<path>` |
| `note` | Phase 2 enforces; Phase 0 optional | Free-form, recommended for `contradicts` |

### URI scheme for external relationships (DEPRECATED)

`external://<source-name>/<path>` was introduced for Phase 1 and removed
with Phase 1 in v2.5.0. Cross-source relationship targets are no longer
declared via URI; use `wiki-import` to bring legacy specs into the kata
wiki (then declare with a normal wiki-relative path), or wait for v1.12
cross-wiki federation.

## Phase 0 — advisory preflight (kata-only) — SHIPPED 2026-05-16

Status: shipped in v2.2.0 (commit `e19fafd` + `752b799`).

### What it does

`wiki-ingest <source>` checks the source's frontmatter `type`. If
`type` is in `spec_authoring.spec_types` AND
`spec_authoring.preflight == "auto"`, it invokes:

```bash
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec <raw_source_path> \
    --include-archived
```

The script:

1. Parses the new spec's frontmatter (`type`, `tags`, `wikilinks`)
2. Loads all wiki pages via `wiki_lib.discover_pages`
3. Filters to pages where `frontmatter.type ∈ spec_types`
4. Scores each candidate on:
   - title term overlap (weight 2.0)
   - tag overlap (weight 1.5)
   - explicit wikilink reference from new spec body (weight 3.0)
   - hub centrality (weight 0.5)
   - same-type bonus (+1.0)
5. Ranks descending, returns top N (default 10) as JSON

The agent / human reads the JSON, decides which candidates warrant a
relationship declaration, and adds entries to the new spec's
frontmatter `spec_relationships:` block before the page is written into
the wiki by step ④ of wiki-ingest.

### What it does NOT do

- No enforcement — author can ignore candidates entirely
- No auto-propagation — `supersedes` declarations do not touch the target
- No relationship suggestion — the script surfaces candidates but does
  not propose `kind` values

### Output format

See `plugin/scripts/spec_preflight.py` docstring + `plugin/skills/wiki-spec/SKILL.md`
"Output format" section.

### Validation

`tests/run_smoke.py` Test 20 validates Phase 0 end-to-end against a
2-spec fixture wiki + 1 new draft spec. Asserts:

- Correct candidate count
- Linked + tag-overlapping spec ranks first
- Signal fields populated correctly (link_reference, type_match,
  tag_overlap ≥ 3)
- Advisory text present
- Tier breakdown computed

## Phase 1 — external source backfill (REMOVED 2026-05-17)

**Status**: shipped in v2.3.0 on 2026-05-16, removed in v2.5.0 on
2026-05-17. The slot is intentionally vacated, not filled. See ADR
`~/.llm-wiki/kata/decisions/2026-05-17-external-sources-removed.md`
and CHANGELOG `[2.5.0]` for the full architectural reasoning.

### Why removed

Three converging reasons, each fatal on its own:

1. **`wiki-import` already covers the use case.** Human-curated bulk
   ingest of a legacy markdown corpus is exactly what `wiki-import` was
   built for (folder traversal, schema mapping, checkpoint/resume,
   per-file prompt). The "avoid bulk-import" framing was solving a
   non-problem.

2. **Self-closing violation.** The `external_sources` block reached
   outside `{wiki_path}/` to enumerate + score + surface third-party
   markdown files. To make it behave correctly we had to invent a
   lifecycle (transit zone → graduation → blocklist → TTL) — the fact
   that we needed to invent a lifecycle to make the abstraction work
   is itself the signal the abstraction was wrong. Kata's invariant is
   that the wiki is a compiled artifact under one root; `external_sources`
   leaked that boundary.

3. **Federation is the right architecture for cross-source.** Two
   self-closing kata wikis cooperating at the `wiki-query` ↔
   `wiki-query` layer (planned for v1.12) preserves both sides'
   authority. Reaching into raw markdown dirs does not.

### What the slot does now

- **Mid-adoption legacy corpus** → run `wiki-import <corpus>` with
  `--priority=recency --per-file-prompt`. The historical specs become
  real kata pages with proper frontmatter, full graph participation,
  and tier lifecycle. Phase 0 preflight + Phase 2 enforcement then
  cover them the same way they cover any kata-managed spec.
- **Live cross-project cooperation** → punt to v1.12 cross-wiki
  federation (separate PRD).
- **Lightweight reference (don't want to ingest, don't need federation)**
  → just use a wikilink to a path that doesn't resolve; the link
  preserves intent for humans, kata won't score it as a candidate, no
  ambiguity about ownership.

### Empirical motivation for removal

Tested against NECallKit (real project, 363 historical spec/doc files
in `specs/` + `docs/`). With both directories mounted as
`external_sources`, preflight returned `page_count: 0` on both — 95%+
of the legacy corpus had no YAML frontmatter, so the `discover.type_field`
filter silently dropped everything. The path-pattern type-inference
patch that would have fixed it was a sunk-cost workaround for an
abstraction the team decided to remove instead of extend.

## Phase 2 — relationship declaration enforcement

### Trigger

`spec_authoring.enforce_relationship_declaration: true` flips Phase 2 on
per-wiki. Two enforcement modes via `spec_authoring.enforcement_mode`:

- `strict` *(default when enabled)*: every preflight candidate above
  `enforcement_score_threshold` (default 5.0) must appear in
  `spec_relationships`. Ingest rejected otherwise.
- `confirm`: ingest proceeds but pauses for user "yes / no" confirmation
  per uncovered candidate.

### Rejection mechanism

`wiki-ingest` step ②b is extended:

1. Run preflight (same as Phase 0)
2. For each candidate where `score >= enforcement_score_threshold`:
   - If the candidate's path is in `spec_relationships[*].target`,
     mark as covered.
   - Otherwise, mark as uncovered.
3. If `enforcement_mode == strict` AND uncovered count > 0:
   - Emit a structured rejection report listing uncovered candidates
   - Exit with non-zero code; wiki-ingest aborts
   - Author must add relationship entries before retry
4. If `enforcement_mode == confirm`:
   - For each uncovered candidate, ask user yes/no (related?)
   - Yes → require kind / note
   - No → mark as "explicitly_unrelated" in an internal log (not
     written to frontmatter; just records the decision so retries
     don't re-ask)

### Bypass

`--no-spec-preflight` flag on wiki-ingest forces skip. Logged in the
report. Intended for one-off cases where the author has already
manually verified.

### Test plan

- Fixture: 1 active spec + 1 new draft that overlaps strongly (tag+title)
  but does NOT declare a relationship
- Enable enforce_relationship_declaration
- Assert: wiki-ingest rejects with exit code 2 + structured report
- Add relationship declaration to new draft
- Assert: wiki-ingest now succeeds

## Phase 3 — auto-propagation

### What it does

When a newly-ingested spec contains:

```yaml
spec_relationships:
  - kind: supersedes
    target: decisions/F015-old.md
    note: "F015's design is fully replaced by F017"
```

kata performs three actions on `decisions/F015-old.md`:

1. **Banner**: prepend a markdown block (template configurable in
   `spec_authoring.auto_propagation.banner_template`) pointing at the
   superseding spec:

   ```markdown
   > **⚠ Superseded by [[F017-new]] on 2026-05-16.**
   > Reason: F015's design is fully replaced by F017
   > This page is preserved for historical reference only.

   # F015 Old Auth Design
   ...
   ```

2. **Reverse link**: add `spec_superseded_by:` to F015's frontmatter:

   ```yaml
   spec_superseded_by:
     - path: decisions/F017-new.md
       date: 2026-05-16
       note: "F015's design is fully replaced by F017"
   ```

3. **Tier flip**: add `tier_override: archived` if not already set, and
   `tier_reason: "Superseded by F017 on 2026-05-16"`.

### Idempotency

Re-ingesting F017 (e.g. after editing) does not duplicate the banner /
reverse-link / tier override on F015. The propagation step checks for
existing entries and updates only if changed.

### Cross-wiki target carve-out

`kind: supersedes` with `target: kata://<peer>/<path>` does NOT trigger
file-modification on the peer wiki (v1.12 federation contract is
read-only). Instead, kata writes an **internal reverse-index** to a
kata-managed file at the local wiki root:

```yaml
# {wiki_path}/.spec-reverse-index.yaml (kata-internal)
external_supersessions:
  - external_target: kata://sdd-specs/decisions/F011-merge-back
    superseded_by: decisions/F017-new.md
    date: 2026-05-16
    note: "F011 lane discipline absorbed into F017"
```

Phase 4 lineage view reads this index alongside in-wiki reverse-links.

### Dreamer integration

v1.6 dreamer's co-occurrence strategy can mistakenly resurface a
superseded spec when a new fresh page mentions it. Phase 3 emits an
explicit reject signal to the dreamer:

- A page with `spec_superseded_by:` non-empty is **never** a dreamer
  candidate (regardless of score).
- A page with `tier_override: archived` AND `tier_reason` starting with
  "Superseded by" is also auto-excluded.

This addresses one of the v1.6 dogfood Week 1 findings (channel
mismatch — `--apply` is rarely used; `--pin` is the real accept channel).
The new reject channel is even more targeted: "this old spec is dead by
explicit declaration, not by inference."

## Phase 4 — coherence view

### Trigger

```bash
claude /kata:wiki-graph --spec-history <topic-or-page-id>
```

Or as a programmatic call:

```bash
python {plugin_root}/scripts/graph_query.py --spec-history <topic>
```

### Output

A tree showing supersession + refinement chain:

```
F017 (current, 2026-05-16)
  refines→ F011 (active, 2026-04-15)
  supersedes→ F015 (archived, 2026-03-02)
                 supersedes→ F008 (archived, 2026-01-12)
  references→ external://sdd-specs/initial-auth-rfc.md (raw)
```

Formats supported (per existing `wiki-graph --format`):

- `text` (default): the tree above
- `json`: structured for programmatic consumption
- `mermaid`: graph-style for embedding in markdown / Obsidian

### Implementation notes

`wiki-graph` already has graph-traversal primitives (BFS neighbors,
shortest path). Phase 4 adds a `spec-history` subcommand that:

1. Resolves the seed to a spec page
2. Walks `spec_relationships` outbound (this page → others)
3. Walks `spec_superseded_by` inbound (this page ← others)
4. Reads the kata-internal `external_supersessions` index for external links
5. Returns the merged tree

## Schema changes

`schema/wiki-schema.json` gains the `spec_authoring` block (shipped
Phase 0). Subsequent phases extend:

| Field added | Phase | Notes |
|---|---|---|
| `spec_authoring` (top-level) | 0 | shipped |
| `spec_authoring.enforcement_score_threshold` | 2 | numeric, default 5.0 |
| `spec_authoring.enforcement_mode` | 2 | enum: strict\|confirm |
| `spec_authoring.auto_propagation.*` | 3 | nested object |
| `.wiki-plugins.yaml` `treatment` field | 1 | enum: active\|raw\|frozen |
| `.wiki-plugins.yaml` `discover.type_field` | 1 | string, default "type" |

## Script / skill changes

| Item | Phase | Status |
|---|---|---|
| `plugin/scripts/spec_preflight.py` | 0 | shipped |
| `plugin/skills/wiki-spec/SKILL.md` (new skill) | 0 | shipped |
| `plugin/skills/wiki-ingest/SKILL.md` step ②b | 0 | shipped |
| `plugin/scripts/spec_preflight.py` external support | 1 | not started |
| `.wiki-plugins.yaml` treatment plumbing in external_plugin_run.py | 1 | not started |
| `plugin/scripts/spec_enforce.py` (Phase 2 rejection helper) | 2 | not started |
| `plugin/scripts/spec_propagate.py` (banner + tier + reverse-link) | 3 | not started |
| `plugin/scripts/graph_query.py` --spec-history subcommand | 4 | not started |
| `plugin/scripts/wiki_dream.py` reject-signal hook | 3 | not started |

## Test plan

| Phase | Test | Status |
|---|---|---|
| 0 | `tests/run_smoke.py` Test 20: preflight ranks correctly | shipped |
| 1 | Test 21: external source preflight with treatment flag | future |
| 2 | Test 22: rejection on missing relationship | future |
| 3 | Test 23: auto-propagation banner + tier flip + idempotency | future |
| 3 | Test 24: external supersession reverse-index | future |
| 3 | Test 25: dreamer skips superseded specs | future |
| 4 | Test 26: spec-history tree rendering | future |

All tests use fixture wikis under `tests/fixture/_spec_*/` to avoid
polluting the main fixture.

## Migration

### From v2.1.0 → v2.2.0 (Phase 0, current)

No migration required. `spec_authoring` is opt-in via SCHEMA.md:

```yaml
spec_authoring:
  enabled: true
  spec_types: [decisions]   # narrow to wiki's conventions
```

Wikis without the block behave exactly as v2.1.0.

### From v1.10 → v1.13 Phase 1 (future)

`.wiki-plugins.yaml` entries gain a `treatment` field, defaulting to
`active` (preserves v1.10 behavior). Users wanting spec-preflight-only
backfill set `treatment: raw` for their historical spec sources.

### From any phase → Phase 2 enforcement

Enabling `enforce_relationship_declaration: true` may cause the next
ingest of a spec-type page to reject. Recommended migration:

1. Run preflight manually (`wiki-spec preflight`) on each draft spec
   before flipping enforcement on, to surface what would be rejected
2. Add `spec_relationships:` entries to current draft specs
3. Flip enforcement to `confirm` mode first; promote to `strict` after
   1-2 weeks of confirm-mode signal

### From Phase 2 → Phase 3 auto-propagation

Enabling `auto_propagation.enabled: true` may cause the next ingest with
a `supersedes` declaration to modify old wiki pages. Recommended:

1. Audit existing `spec_relationships:` blocks (e.g. `wiki-graph --query
   "spec_relationships.kind=supersedes"`)
2. Dry-run propagation: `wiki-spec propagate --dry-run` (future skill
   subcommand)
3. Enable.

## Decision log (open questions resolved during 2026-05-16 design)

### Q1 — default value for external source `treatment`

**Resolved**: `raw`.

Reasoning: Most users adopting kata mid-project want their historical
spec corpus visible to preflight but not in default search. `active`
would cause noise in `wiki-search` results; `frozen` would hide the
corpus too completely.

### Q2 — preflight trigger: auto-detect vs explicit `--spec-mode`

**Resolved**: auto-detect based on frontmatter `type`, with SCHEMA.md
override (`spec_authoring.preflight: auto|manual|off`).

Reasoning: most authoring flows shouldn't require an extra flag. Manual
opt-in for edge cases (e.g. an SDD `prd` file the author specifically
doesn't want preflighted).

### Q3 — external relationship target format

**Resolved**: URI scheme `external://<source-name>/<path-within-source>`.

Reasoning: distinct namespace from wiki paths; resolves cleanly via
`.wiki-plugins.yaml` registration; future Phase 4 can render external
targets distinctly (dashed lines in mermaid, etc.).

### Q4 — Phase 3 dreamer integration

**Resolved**: in scope. `spec_superseded_by:` reverse links become
explicit reject signals to the dreamer. v1.6 dreamer code change is
small (a few lines in the candidate-filter pass).

Reasoning: the v1.6 dogfood Week 1 surprise was that the dreamer's
implicit reject channel (`tier_override: archived` via user pin) was
working but invisible. Phase 3 introduces an explicit channel that
ties to a real lifecycle event ("this spec was superseded"), making
the signal usable by other future strategies (coverage-matrix, etc.).

## Open questions (not yet resolved)

### O1 — Phase 2 enforcement threshold default

`enforcement_score_threshold: 5.0` is a heuristic. The Phase 0 fixture
test gets scores 5-15 for genuine matches and 0-3 for unrelated pages,
so 5.0 has good signal-to-noise on the test corpus. But real wikis may
need calibration. Possible resolutions:

- Calibrate against NECallKit wiki dogfood data when Phase 2 lands
- Make threshold adaptive (e.g. "top N candidates" instead of "score ≥ X")

### O2 — Phase 3 banner template per-relationship-kind

The banner template currently only handles `kind: supersedes`. Should
`kind: contradicts` also get a banner? Probably yes ("⚠ Contradicted by
F017") but with different verbiage. Phase 3 design TBD.

### O3 — External source as both query-fallback AND spec-preflight backfill

`.wiki-plugins.yaml` originally a v1.10 query-fallback config; v1.13
adds preflight scope. Should `treatment: raw` automatically remove the
source from `wiki-query` fallback, or are these two orthogonal axes?

Tentative: orthogonal. `treatment` controls preflight scope. v1.10
`when_to_call` controls query-fallback. A source can be `treatment: raw`
+ `when_to_call: on_empty` simultaneously.

### O4 — File-system performance at scale

Phase 0 reads every wiki page on every preflight. For a 1000-page wiki,
this is ~50-200ms. For 5000+ pages, may need indexing. Defer until
real users hit it; reuse v1.7+ qmd integration if needed.

## Cross-phase risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Phase 2 enforcement rejects too aggressively → user disables feature | Medium | `enforcement_mode: confirm` mode + threshold tuning |
| Phase 3 auto-propagation damages well-loved old specs → user reverts | Medium | Idempotent updates, dry-run mode, comprehensive test |
| External source paths change → URI breaks | Medium | `.wiki-plugins.yaml` re-discovery on miss; warn in preflight report |
| Phase 4 lineage view becomes complex tree, hard to read at scale | Low | Cap depth; collapse old archived branches |
| Dreamer reject-signal misclassifies non-superseded as superseded | Low | Only triggers on explicit `spec_superseded_by:` (not heuristic) |

## See also

- `plugin/scripts/spec_preflight.py` — Phase 0 implementation
- `plugin/skills/wiki-spec/SKILL.md` — skill contract
- `plugin/skills/wiki-ingest/SKILL.md` step ②b — auto-invocation
- `tests/run_smoke.py` Test 20 — Phase 0 validation
- `docs/PRD-v1.10-external-searchable-sources.md` — v1.13 Phase 1 builds on this
- `docs/PRD-v1.11-session-ingest.md` — complementary, not overlapping
- `docs/idea-coverage-matrix-dreamer.md` — Phase 3 + dreamer integration touchpoint
- `docs/dogfood-v1.6.md` Week 1 — channel-mismatch finding that motivates Phase 3 reject-signal
- v1.6 PRD, v1.7 PRD, v1.8 PRD — prior phase work this rests on

## Changelog (this PRD)

- 2026-05-16 — Draft v1 written. Phase 0 already shipped in v2.2.0
  (commit `e19fafd` + `752b799` integration). Phases 1-4 not yet
  started.
