---
name: wiki-lint
description: "Health-check the wiki: structural checks (orphans, broken links, frontmatter, stale content, tier consistency, custom-dimension completeness), content gaps with web-search suggestions, and taxonomy evolution proposals for SCHEMA.md."
user-invocable: true
argument-hint: "[--fix] [--report-only] [--check=orphans|links|frontmatter|stale|index|tags|size|gaps|schema|tiers|dimensions]"
---

# wiki-lint

Health-check the wiki and report issues by severity. Runs **two kinds** of checks:

1. **Structural checks** — orphans, broken links, frontmatter, index completeness,
   page size, tag drift (the "is the wiki well-formed?" layer)
2. **Content / evolution checks** — content gaps the LLM can spot, web-search
   suggestions to fill them, and SCHEMA.md evolution proposals based on observed
   patterns (the "is the wiki *growing well*?" layer)

The second layer is what makes this a useful LLM task, not just a formatter.
Karpathy's original:
> "data gaps that could be filled with a web search. The LLM is good at suggesting
> new questions to investigate and new sources to look for."

`--fix` applies safe automated fixes. `--report-only` prints findings without any
changes (default).

## When to use

- User asks to "lint", "audit", "health-check", or "clean up" the wiki
- After a large batch ingest
- When `wiki-digest` flagged orphans or coverage gaps
- Periodically (suggested: every 50 ingests or monthly)

## Implementation

Structural checks live in `plugin/scripts/lint_naive.py` — broken links,
orphans, missing required frontmatter, tag drift, stale content, page
size, custom-dimension completeness. **Use the script for these.** It
returns deterministic JSON; the skill formats by severity and decides
which to surface first.

```bash
# Run all structural checks
python {plugin_root}/scripts/lint_naive.py --wiki {wiki_path} --check all

# Subset
python {plugin_root}/scripts/lint_naive.py --wiki {wiki_path} \
    --check links,orphans,frontmatter

# Filter by severity
python {plugin_root}/scripts/lint_naive.py --wiki {wiki_path} \
    --check all --severity HIGH

# Custom stale threshold
python {plugin_root}/scripts/lint_naive.py --wiki {wiki_path} \
    --check stale --stale-days 365
```

**The script does NOT do** — these stay LLM tasks for this skill:

- **Content gaps** — "this entity is mentioned in 3+ pages but has no
  entity page" requires reading bodies and judging significance.
- **SCHEMA.md evolution proposals** — "you've used this tag 8 times,
  add to taxonomy?" requires noticing patterns.
- **Web-search suggestions** — "for this gap, query X" requires synthesis.

So the skill flow is: **call script → present structural findings →
read pages mentioned in findings → reason about content gaps → propose
schema updates**. The script handles the cheap mechanical pass; the
agent does the expensive judgmental pass.

## Pre-flight

Always read orientation files first:
```
read_file {wiki_path}/SCHEMA.md
read_file {wiki_path}/index.md
read_file {wiki_path}/log.md
```

## Structural checks

### 1. Orphan pages
Wiki pages with no inbound `[[wikilinks]]` from any other page.
- Severity: **MEDIUM** for active-tier orphans — they are invisible and often stale
- Severity: **LOW** for archived/frozen orphans — expected as content ages out;
  surface only if the user runs `--check=orphans --tier=all`
- Fix: suggest adding a link from the most semantically related page

### 2. Broken wikilinks
`[[links]]` pointing to files that don't exist.
- Severity: **HIGH** — broken links degrade navigation
- `--fix`: either create a stub page, remove the brackets, or ask the user

### 3. Index completeness
Every file under wiki category directories should appear in `index.md`.
- `missing` = filesystem pages not in index → add to index
- `ghost` = index entries with no corresponding file → remove from index
- Severity: **HIGH** (missing) / **MEDIUM** (ghost)
- `--fix`: automatic

### 4. Frontmatter validation
Every wiki page must have the fields **SCHEMA.md requires** (not plugin hardcoded).
Default: `title, created, updated, type, tags, sources`.
- `type` must be one of the categories SCHEMA.md defines
- `tags` must only contain values from SCHEMA.md's taxonomy
- Severity: **MEDIUM** (missing fields) / **LOW** (tag drift — see check 8)

### 5. Stale content
Two layers split between script and skill — be explicit which one fires:

**Mechanical (`lint_naive.py --check stale`):** pages whose `updated`
date is older than `--stale-days` (default 180). Pure threshold —
**no entity awareness**. This is what the script reliably flags.

**Semantic (LLM layer, this skill):** for the pages the script flagged,
optionally read the bodies and compare with newer sources mentioning
the same entities. If a freshly ingested source contradicts or
supersedes a flagged page's content, mark the page for refresh ingest.
This step is non-mechanical — it requires reading bodies and judging
relevance, which the script does not do.

- Severity: **LOW** — flag only, never auto-fix
- v1.8+ may promote the semantic check into the script if a deterministic
  heuristic emerges; for now keep the layer split honest in the report.

### 6. Contradiction flags
Pages with unresolved `contradictions:` frontmatter (flagged during ingest).
- Severity: **MEDIUM** — list them for user review

### 7. Page size
Pages over the limit SCHEMA.md specifies (default: no limit — skip this check).
- Severity: **LOW** — suggestion only, never enforce without SCHEMA.md saying so

### 8. Tag drift
Tags used across pages that aren't in SCHEMA.md's taxonomy. This overlaps with
check 11 (taxonomy evolution) — report here, propose there.

### 9. Log rotation
If SCHEMA.md specifies a log rotation threshold and log.md exceeds it, rotate:
rename `log.md` → `log-YYYY.md`, create fresh `log.md` with a rotation entry.
(Skip entirely if SCHEMA.md says "no rotation" — default.)

### 9b. Memory-tier consistency (if `memory_tiers.enabled: true`)
- **Missing driving-field dates**: pages with neither `published_at` nor
  `ingested_at` — can't compute tier. Severity: **MEDIUM**. `--fix`: set
  `ingested_at` to file mtime.
- **Invalid `tier_override:`**: frontmatter value not one of
  `active|archived|frozen`. Severity: **LOW**.
- **Aged-out active pages**: pages that just crossed active→archived since the
  last lint run. Severity: **INFO** — no fix needed, just surface the list for
  awareness. Suggest `wiki-tier --show` for full details.

### 9c. Custom-dimension completeness (if `custom_dimensions:` is non-empty)
For each dimension in SCHEMA.md:
- **Missing required dimension**: pages where a `required: true` dimension has
  no value and no default. Severity: **MEDIUM**. `--fix`: prompt for the value.
- **Enum value out of range**: a dimension with `type: enum` has a value not in
  the allowed set. Severity: **LOW**. `--fix`: prompt to correct.
- **Dimension on wrong page type**: a dimension with `applies_to: [X]` is
  present on a page of type Y. Severity: **LOW**. `--fix`: remove field.

---

## Content checks (the LLM layer)

### 10. Content gaps
Use the LLM's reading ability to find what's **missing**. Scan wiki page content for:

- **Implicit entities** — proper nouns / repeated terms that appear across 3+ pages
  but don't have their own entity page. Often these are the most connective nodes.
- **Open questions** — questions raised in page text ("why does X...?", "it's
  unclear whether...") that were never filed as query pages
- **Uncompared siblings** — two entities that appear together in 5+ pages but
  have no comparison page between them
- **Thin synthesis** — clusters of 5+ related pages with no overarching concept
  page tying them together

For each gap, propose a **specific action**:
```
• "flash-attention" mentioned in 6 pages but no entity page → create concepts/flash-attention.md
• Open question in entities/transformer.md:23 — "How does grouped-query attention change this?" → create queries/gqa-on-standard-transformer.md
• entities/claude-3.md and entities/gpt-4.md co-occur in 8 pages but no comparison → create comparisons/claude-3-vs-gpt-4.md
• 7 pages share the `fine-tuning` tag but no concept page → create concepts/fine-tuning.md synthesizing them
```

### 11. Web search suggestions
For identified content gaps (check 10), suggest **specific web searches** that
would fill them. This is where the LLM earns its keep:
```
• Gap: "No coverage on flash-attention variants beyond v1"
  → Suggested search: "flash attention v2 v3 hopper implementation"
• Gap: "transformer.md doesn't cover recent efficiency work"
  → Suggested search: "transformer efficient inference 2025 survey"
• Gap: "Missing data on Anthropic's training compute"
  → Suggested search: "Anthropic compute scale paper 2024"
```
If the environment has web search available, offer to run the search and stage
the results for `wiki-ingest`.

### 12. Taxonomy evolution (SCHEMA.md proposals)
Observe patterns that suggest SCHEMA.md should evolve, and **propose updates**:

- **New tags to add**: tags used in 3+ pages that aren't in SCHEMA.md's taxonomy
- **Tags to retire**: taxonomy tags that are never used on any page
- **New page type to add**: 5+ pages of a new kind filed under a catch-all
  category (e.g. 5 papers filed under `concepts/` that are really `papers/`)
- **Thresholds to adjust**: if "orphans" keeps flagging the same pages,
  SCHEMA.md's cross-reference policy may be too loose

Present each proposal as a diff:
```
Proposed SCHEMA.md changes:
  + tags: add "flash-attention", "rope", "mixture-of-experts"
  + categories: add "papers/" (currently 8 papers are filed under concepts/)
  - tags: retire "todo" (unused)

Apply? [y/edit/skip]
```

Apply approved changes to SCHEMA.md with `--fix` or on user confirmation.

---

## Report format

```
[Operation] wiki-lint | {wiki_path}

━━━ HIGH ━━━
Broken wikilinks ({N}):
  • entities/page-a.md:12 → [[missing-page]]
  → Fix: create stub, remove brackets, or rename

Index gaps ({N}):
  • entities/new-page.md — not in index.md
  → Fix (auto): add to index.md under Entities

━━━ MEDIUM ━━━
Orphan pages ({N}):
  • concepts/isolated-concept.md — no inbound links
  → Suggestion: link from [[related-page]]

Unresolved contradictions ({N}):
  • entities/model-x.md ↔ entities/model-y.md on "parameter count"
  → Needs user review

Content gaps ({N}):
  • "flash-attention" mentioned in 6 pages but no entity page exists
  → Create concepts/flash-attention.md, or run:
    kata:wiki-ingest <flash-attention-paper>

━━━ LOW ━━━
Tag drift ({N} unknown tags)
Stale content ({N} pages)
Oversized pages ({N}, per SCHEMA.md limit)

━━━ PROPOSALS (SCHEMA.md evolution) ━━━
  + add tag "flash-attention" (used in 4 pages, not in taxonomy)
  + add category "papers/" (8 concept pages are really papers)
  + web search: "flash attention v2 v3 hopper" (to fill content gap)

Apply proposals? [y/n/review-each]

━━━ Summary ━━━
Structural: {H} high, {M} medium, {L} low
Content:    {N} gaps, {M} web-search suggestions
Proposals:  {N} schema updates awaiting approval
Auto-fixable with --fix: {N}

[Changes]  (if --fix passed)
- Fixed: {list}
- Skipped: {list requiring manual action}

[Suggested next]
→ kata:wiki-ingest <source>   (fill a content gap)
→ kata:wiki-digest            (see post-lint state)
```

## Log entry

```
## [YYYY-MM-DD] lint | {N} issues, {M} gaps, {K} proposals
- High: N, Medium: M, Low: K
- Content gaps: list
- Schema proposals: list (applied: N, pending: M)
- Fixed: {auto-fix summary}
```
