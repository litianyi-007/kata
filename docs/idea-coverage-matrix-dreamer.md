# Idea: Coverage-matrix dreamer (v1.7+ proposal)

Status: idea / pre-PRD. Recorded 2026-05-14 from the NECallKit dogfood
wiki-search natural experiment (see
[`dogfood-necallkit-hn-essay.md`](dogfood-necallkit-hn-essay.md) →
"2026-05-14 — wiki-search natural experiment").

## Problem the v1.6 strategy cannot see

The v1.6 dreamer scores frozen and archived pages by **co-occurrence**
with recent ingests: entity overlap, tag resurgence, citation backlinks
([`dreaming.md`](dreaming.md) §"How scoring works"). It is a
**resurrection** strategy — it brings back pages that already exist.

A different class of useful candidates is **never an existing page in
the first place**. When a wiki has dense coverage of one combination of
attributes but a structural hole in a neighboring combination, no
existing page can be resurrected to fill the hole — the dreamer is
blind to it.

### Concrete example (NECallKit, 2026-05-14)

A Codex session asked the wiki to inform a spec for **Electron + Vue2
UIKit reuse**. Three wiki-search queries returned 30 hits across 28
archived pages and 2 active pages. The wiki had:

| Stack | Web | Electron |
|---|---|---|
| React | covered (active + archived) | covered (active + archived) |
| Vue3 | covered (active + archived) | covered (active + archived) |
| **Vue2** | **partial (demo only)** | **empty** |

The agent inferred the Vue2 × Electron hole only by noticing every
top-ranked hit was archived and none mentioned Vue2 in an
Electron-reuse context — a manual O(N) scan. The v1.6 dreamer **could
not have surfaced this**: there is no `vue2-electron-uikit-reuse.md`
to resurface.

## What a coverage-matrix dreamer does

Treat a small set of frontmatter dimensions as an implicit grid. Pages
populate cells. Empty cells whose row and column neighbors are dense
become **gap candidates**: "consider creating an active page for
{row} × {column}."

Pseudocode sketch:

```python
# Configurable dimensions per wiki, declared in SCHEMA.md.
dimensions = schema["dreaming"]["coverage_axes"]
# e.g. [{"name": "stack", "tag_prefix": "stack-"},
#       {"name": "platform", "tag_prefix": "platform-"}]

# For each axis, extract value-set from tag prefixes on active pages.
values_by_axis = {ax["name"]: collect_tag_values(pages_active, ax) for ax in dimensions}

# Build the full cartesian grid of cells, count active pages per cell.
grid = Counter()
for p in pages_active:
    cell = tuple(extract_value(p, ax) for ax in dimensions)
    if all(cell):
        grid[cell] += 1

# A cell is a gap candidate if:
#   - it has 0 active pages
#   - each of its row and column has ≥ N populated cells
#   - aggregate active pages in its row + column ≥ M
#   - it has been "queried-around": archived hits or recent log mentions
#     within last K days for either coordinate
gap_candidates = []
for cell in cartesian_product(values_by_axis):
    if grid[cell] > 0:
        continue
    if row_density(cell) >= N and col_density(cell) >= N:
        if cross_density(cell) >= M and recently_queried(cell, days=K):
            gap_candidates.append(cell)
```

A gap candidate emits a `dreaming/{date}.md` entry of a different
shape than v1.6's "resurface this page":

```markdown
### Gap candidate: stack=Vue2 × platform=Electron

- Row density (Vue2 across platforms): 1 active page
- Column density (Electron across stacks): 6 active pages
- Cross-density: 7
- Recent log mentions touching either coordinate: 4 entries since 2026-05-08
- Adjacent populated cells:
  - stack=Vue3 × platform=Electron — see `Electron/vue3-uikit` cluster
  - stack=Vue2 × platform=Web — see `Web/basic-vue2` cluster
- Suggested action: draft an active page describing the Vue2 ×
  Electron reuse path, or explicitly mark it as out-of-scope in
  SCHEMA.md so future gap-scans skip it.
```

## Why not just lint?

`wiki-lint` could detect missing-page patterns today via a hand-coded
rule. The reason this belongs in the dreamer:

- **Same review surface.** Maintainer already opens
  `dreaming/{date}.md` weekly to triage resurfacing candidates.
  Adding gap candidates to that same file means zero new habit.
- **Same `--apply` flow.** `wiki-dream --apply` already promotes one
  candidate at a time; "promoting" a gap candidate means stubbing a
  new active page and registering it in `index.md`. Same friction
  budget.
- **Same conservatism guarantees.** The dreamer's design rule
  ([`dreaming.md`](dreaming.md) §"Security and privacy") is "never
  auto-promote without explicit `--apply`." Gap candidates inherit
  that for free.

## Open questions

1. **Axis declaration.** v1.6 has no formal axis concept. Adding
   `coverage_axes:` to SCHEMA.md is the cheapest path; alternative is
   to infer axes from tag-prefix frequency. SCHEMA.md is more honest
   — the wiki author already knows which dimensions matter.
2. **Density thresholds.** N (per-axis density) and M (cross-density)
   are domain-specific. Defaults probably want N=3, M=5 for a
   bootstrap wiki; tune at retrospective.
3. **False positives.** Many empty cells are *correctly* empty (e.g.
   stack=COBOL × platform=Electron). The "recently_queried" gate is
   the only thing keeping noise down; without it the dreamer would
   emit cartesian-product nonsense. **This means a gap dreamer is
   inherently demand-driven** — it only surfaces gaps that something
   in the wiki actually points at.
4. **Interaction with v1.6 co-occurrence.** They are
   complementary, not competing: co-occurrence resurfaces existing
   pages, gap-matrix proposes new ones. A run could emit both
   categories under separate headers in the same `dreaming/` file.
5. **Apply semantics for gap candidates.** Resurrection's `--apply`
   bumps `tier_override` or adjusts metadata. Gap `--apply` would
   create a page stub — which means it has to ask for at least a
   short description from the maintainer. That breaks the "fully
   non-interactive" property of v1.6 cron runs.

## Why this is v1.7+, not v1.6 tuning

v1.6's frozen-parameter rule
([`dogfood-v1.6.md`](dogfood-v1.6.md) §"Frozen parameters")
forbids changing dreamer weights/thresholds mid-window. This idea
adds a **second strategy**, not a tuning of the first, so it lives
outside the rule. But it also depends on what the v1.6 retrospective
reveals: if the co-occurrence strategy already produces high
acceptance rates on the NECallKit corpus, gap-matrix may be
deferrable. If it doesn't, gap-matrix becomes the natural v1.7
direction over a third co-occurrence variant.

## Decision dependencies

Block on:

- v1.6 retrospective (~2026-06-05) — does co-occurrence hit ≥60%
  acceptance? If yes, low pressure for a second strategy. If no,
  gap-matrix becomes a candidate to fill the gap.
- v1.7 watcher PRD ([`PRD-v1.7-watcher.md`](PRD-v1.7-watcher.md)) —
  watcher is the leading v1.7 candidate; gap-matrix is a peer
  proposal, not a replacement.

Do not block:

- Continued v1.6 dogfood on NECallKit (this idea changes nothing
  about the current window)
- Essay #1 (this idea is future scope, not in scope of the published
  thesis)

## See also

- [`dreaming.md`](dreaming.md) — current dreamer architecture and v1.6 strategy
- [`PRD-v1.6-autodreaming.md`](PRD-v1.6-autodreaming.md) — v1.6 PRD with frozen parameters
- [`dogfood-v1.6.md`](dogfood-v1.6.md) — v1.6 dogfood log with Week 1 entry
- [`dogfood-necallkit-hn-essay.md`](dogfood-necallkit-hn-essay.md) §"2026-05-14 — wiki-search natural experiment" — source observation
