---
name: wiki-digest
description: "Generate a digest of the wiki: recent activity summary, key themes by cluster, tier distribution (active/archived/frozen), coverage gaps, cross-cutting synthesis, stale custom dimensions, and suggested next actions. The weekly health report for your knowledge base."
user-invocable: true
argument-hint: "[--since=7d] [--focus=<topic>] [--format=brief|full] [--tier=active|all|archived|frozen]"
---

# wiki-digest

Generate a structured digest of the wiki's current state. Unlike `wiki-query` (which
answers a specific question) and `wiki-lint` (which checks structural health),
`wiki-digest` provides a **high-level synthesis**: what has been compiled, how it
clusters, what is missing, and what connections are worth exploring.

Think of it as the weekly editorial meeting for your knowledge base.

## When to use

- User asks "what's in the wiki?", "summarize what we know", "give me an overview"
- After a batch ingest to see what the new sources added
- Periodically to guide what to ingest next
- When starting a new session and wanting to orient quickly

## Implementation

`plugin/scripts/digest.py` produces the mechanical inputs — activity
counts from log.md, inventory by type/tag, tier distribution, recently
updated list, top hubs, stale custom dimensions. **Use the script for
these.** The skill's job is to add narrative layer: theme clustering,
coverage gaps, cross-cutting synthesis, suggested next actions.

```bash
# Default 7-day window
python {plugin_root}/scripts/digest.py --wiki {wiki_path}

# Longer window
python {plugin_root}/scripts/digest.py --wiki {wiki_path} --since 30d

# Focus on a single tag
python {plugin_root}/scripts/digest.py --wiki {wiki_path} --focus moe
```

What the script does NOT do — these stay this skill's job:

- **Theme clustering** — group recently updated pages by topic, identify
  the cluster anchor, assess depth.
- **Coverage gaps** — "missing synthesis pages, uncompared entities,
  unfiled queries" requires reading bodies and judging.
- **Cross-cutting synthesis** — entities spanning clusters, latent
  contradictions.
- **Suggested next actions** with specific skill invocations.

So the flow: **call script → digest the JSON → read top hubs and recent
pages → reason about themes and gaps → produce the narrative report**.

## Pre-flight (orientation guard)

Always read orientation files before running:
```
read_file {wiki_path}/SCHEMA.md
read_file {wiki_path}/index.md
read_file {wiki_path}/log.md
```

## Steps

① **Parse arguments:**
   - `--since=Nd` or `--since=YYYY-MM-DD` — scope to recent activity (default: all time)
   - `--focus=<topic>` — narrow digest to a specific theme or tag
   - `--format=brief` — 1-page summary; `full` — full analysis with all sections (default)
   - `--tier=<tier>` — default `active`; also `all`, `archived`, `frozen`.
     When tiers are enabled in SCHEMA.md, the inventory/cluster/gap sections
     restrict to the chosen tier. Tier distribution is always reported
     regardless of filter.

② **Activity summary** (from log.md):
   Parse log.md entries in the time window. Count by action type:
   ```
   ## [YYYY-MM-DD] ingest | Article Title
   ## [YYYY-MM-DD] query | Question asked
   ## [YYYY-MM-DD] lint | N issues found
   ```
   Build a timeline: what was added, when, in what order.

③ **Inventory scan** (from index.md + script):
   - Total pages by type (entities, concepts, comparisons, queries)
   - **Newly created** pages since `--since` — `digest.py` returns
     `recently_created` (driven by `created` frontmatter)
   - **Recently updated** pages since `--since` — `digest.py` returns
     `recently_updated` (driven by `updated` frontmatter); these may
     overlap with `recently_created` for genuinely new pages
   - Most-linked pages (hub pages — `top_hubs` from the script)
   - Orphan pages (pages with no inbound links from index scan)

④ **Theme clustering:**
   Group pages by shared tags from SCHEMA.md taxonomy. For each cluster:
   - Name the cluster (the dominant tag)
   - List member pages
   - Identify the "anchor page" (most linked-to within the cluster)
   - Note if the cluster is well-developed (3+ pages) or sparse (1–2 pages)

⑤ **Coverage gap analysis:**
   For each cluster, check:
   - Is there a concept page synthesizing the cluster? If not, flag as gap.
   - Are there entities mentioned in multiple pages that lack their own page?
   - Are there comparison pages where two closely related entities exist but
     haven't been compared?
   - Are there questions in the log that were never filed as query pages?

⑥ **Cross-cutting synthesis** (full format only):
   Look across clusters for emergent connections:
   - Entities that appear in 3+ clusters
   - Concepts that contradict each other across clusters
   - Timelines or progressions implied by multiple pages
   - Open questions that span multiple areas

⑥b **Tier distribution** (if SCHEMA.md `memory_tiers.enabled: true`):
   Compute, for every wiki page, its tier from the driving-field date
   (default: `published_at` → fallback `ingested_at`). A page inherits the
   **most recent** tier across its cited sources — any active source pulls
   the page into active. Report:
   - Counts: `active: N | archived: M | frozen: K`
   - Pages that just crossed the archived threshold in the `--since` window
     ("aging out" list — these may deserve a refresh ingest)
   - Pages pinned with `tier_override:` (manual overrides are respected)
   When tiers are disabled, skip this section entirely.

⑥c **Stale custom dimensions** (if SCHEMA.md declares any):
   For each dimension where `refresh_on` includes `digest`, scan pages and
   find ones whose dimension value is **likely stale**:
   - Value still equals the initial import default
   - Value hasn't been updated since a newer source was ingested for the same
     entity
   - For `type: enum` fields: value is not the most recent valid option
     (e.g. `version: 1.0` when the latest ingested version is `2.3`)

   Offer to re-prompt for each stale page. This is non-blocking — the user can
   say "skip all" and digest continues. The point is a gentle reminder, not
   interruption.

⑦ **Suggested next actions:**
   Based on gaps and clusters, suggest specific actions:
   - "Ingest {X} to fill the gap in the {tag} cluster"
   - "Create a comparison page for {A} vs {B} — they share 5 pages but no comparison"
   - "Run wiki-lint — {N} orphan pages detected in the inventory"
   - "The {topic} cluster has grown to 8 pages — consider writing a synthesis concept page"

## Output (full format)

```
[Operation] wiki-digest | {scope}

━━━ Activity ({since} to {today}) ━━━
Ingests: {N} | Queries: {M} | Lints: {K}
Timeline: {chronological list of key events}

━━━ Inventory ━━━
Total pages: {N} (entities: {a}, concepts: {b}, comparisons: {c}, queries: {d})
New since {since}: {N} pages
Most-linked: [[{page1}]] ({N} links), [[{page2}]] ({M} links)
Orphans: {list or "none"}

━━━ Theme Clusters ━━━
{tag-name} ({N} pages) — anchor: [[{page}]]
  {list of pages with one-line summaries}
  Status: {well-developed | sparse | no synthesis page}

...

━━━ Coverage Gaps ━━━
• {Gap description and suggested action}
• ...

━━━ Cross-cutting Synthesis ━━━
{2–4 emergent connections or themes, with page citations}

━━━ Memory Tiers ━━━            (only if enabled in SCHEMA.md)
active:   {N} pages   (driving field: {field})
archived: {M} pages
frozen:   {K} pages
Aging out since {since}: {list of pages that just crossed active→archived}

━━━ Stale Custom Dimensions ━━━  (only if any dimension has refresh_on: digest)
{dimension-name}: {N} pages with potentially stale values
  • [[page-1]] — current: {val}, newer ingest suggests: {new-val}
  • ...
→ re-prompt? [y/n/later]

━━━ Suggested Next Actions ━━━
1. {action} → {skill invocation}
2. {action} → {skill invocation}
...

[Suggested next]
→ kata:wiki-ingest <source>  or  kata:wiki-lint
```

## Brief format (`--format=brief`)

Condensed to a single block:
```
[wiki-digest | brief | {date}]
{N} pages · {M} clusters · {K} new since {since}
Top themes: {tag1} ({N}), {tag2} ({M}), {tag3} ({K})
Gaps: {top 2 gaps}
Suggested: {top action}
```
