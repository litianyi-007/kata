---
name: wiki-ingest
description: "Ingest a source into the wiki: save raw content and referenced images, prompt the user for any custom frontmatter dimensions declared in SCHEMA.md, extract key information, create or update wiki pages per SCHEMA.md conventions, and update index.md and log.md."
user-invocable: true
argument-hint: "<url|file|text> [--batch] [--no-discuss] [--no-images] [--no-spec-preflight] [--set=key=value,...]"
---

# wiki-ingest

Integrate a new source into the wiki. A single ingest can touch **10–15 pages** —
this compounding effect is the whole point. Knowledge is compiled once, not
re-derived on every query.

## When to use

- User provides a URL, file path, or pasted text to add to the wiki
- User says "add this", "ingest this", "read this and update the wiki"

## Pre-flight (orientation guard)

Before ingesting, read orientation files if not done this session:
```
read_file {wiki_path}/SCHEMA.md     # ← conventions, tag taxonomy, policies
read_file {wiki_path}/index.md
read_file {wiki_path}/log.md         # last 20 lines
```

**SCHEMA.md is authoritative.** Read its page creation policy, required frontmatter
fields, tag taxonomy, and cross-reference policy — enforce those, not plugin defaults.

## Steps

### ① Capture raw source (+ images)

**Save the source text:**
- URL → fetch content as markdown, save to `raw/articles/{descriptive-name}.md`
- PDF → extract text, save to `raw/papers/{descriptive-name}.md`
- Pasted text → save to appropriate `raw/` subdirectory
- Name descriptively: `raw/articles/karpathy-llm-wiki-2026.md`
- Never overwrite existing raw files — append suffix if collision

**Extract and save referenced images** (unless `--no-images`):
- Scan the source for image references (markdown `![](url)`, HTML `<img>`, etc.)
- Download each image to `raw/assets/{source-stem}-{image-name}`
- Rewrite the saved raw source to reference local paths, not remote URLs
- URLs rot; local copies persist. This is one of the main benefits of the wiki
  layer over bookmark-style systems.

**Processing order for multimodal sources** (important):
> LLMs can't natively read markdown with inline images in one pass. Read the
> source **text first** (chunking if long), identify which images actually carry
> information (diagrams, charts, screenshots — not decorative), **then view
> those specific images separately** using the image-reading tool to gain
> additional context. Skip decorative images.

### ①b Prompt for custom dimensions

Read SCHEMA.md's `custom_dimensions:` block. For each dimension where
`refresh_on` includes `ingest`:

1. If the user passed `--set name=value` on the command line, use that value
   directly without prompting (automation-friendly)
2. Otherwise, prompt using the dimension's `description` as the question:
   > "{description} (type: {type}, {required|optional}, default: {default})"
3. For `type: enum`, list the allowed values and accept only one
4. For `type: date`, accept ISO 8601 or common shorthands (today, yesterday)
5. If the user skips a `required` dimension without supplying a default, warn
   and ask again — do not silently omit required fields

Store the collected values in a session map `{dim_name: value}`. These get
written to every page's frontmatter in step ④, subject to each dimension's
`applies_to` filter.

**Also capture the source dates** needed by the memory-tier system:
- `published_at` — if the source carries a publication date (from OpenGraph
  metadata, paper bibliography, article byline, etc.), extract it automatically.
  If not, prompt: "When was this source published? (ISO date or 'unknown')"
- `ingested_at` — always set to today's date automatically

These two dates are written to every new or updated page's frontmatter. The
tier system (SCHEMA.md `memory_tiers:`) uses `driving_field` to decide which
one drives the tier computation.

### ② Discuss takeaways

Unless `--no-discuss` or running in an automated context: surface 3–5 key insights
and ask the user what to emphasize **before** writing pages. This is Karpathy's
"stay involved" mode — the user guides the direction, you do the writing.

### ②b Spec preflight (if source is a spec-type page) — v1.13 SHM

**When this step runs**:

Read SCHEMA.md's `spec_authoring` block (skip if absent or `enabled: false`).
If the block is enabled AND `spec_authoring.preflight == "auto"` (default) AND
the captured raw source's frontmatter `type` is in `spec_authoring.spec_types`
(default includes `decisions`, `prd`, `design`, `rfc`, `adr`, `task-spec`),
run preflight before any wiki page is written:

```bash
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec {raw_source_path} \
    --include-archived
```

The script emits a JSON envelope with ranked candidate prior specs. Present
the top 5 to the user (or surface to the agent making authoring decisions)
along with the relevance signals (`title_overlap`, `tag_overlap`,
`link_reference`, `hub_score`, `type_match`).

**For each top candidate, the author decides** (Phase 0 is advisory — Phase 2
will enforce):

1. **Skip** — the candidate is unrelated despite the surface overlap. No
   action needed.
2. **Declare a relationship** — add to the new spec's frontmatter:

   ```yaml
   spec_relationships:
     - kind: supersedes | refines | extends | parallel | contradicts
       target: <wiki-path-of-old-spec>
       note: "<one-line rationale>"
   ```

Phase 0 does **not** auto-update the old spec — `kind: supersedes` does NOT
trigger a banner / tier flip / reverse-link on the target page yet. Phase 3
will add that. If a relationship clearly implies the old spec is dead, the
author may also want to manually run `wiki-tier --pin <old-spec>:archived`
or add a `tier_override:` line by hand.

**When to skip this step** (no preflight needed):

- `spec_authoring.enabled: false` (default for new wikis)
- `spec_authoring.preflight: off`
- Source's frontmatter `type` is not in spec_types
- User passes `--no-spec-preflight` (force-skip override)
- Wiki has fewer than 2 existing spec-type pages (no candidates possible)

**Configuration override**: if the source's frontmatter `type` is in
`spec_types` but the user explicitly wants to skip preflight for this
ingest, accept `--no-spec-preflight` and proceed straight to ③. Note this
in step ⑦ Report so the user knows preflight was bypassed.

### ③ Check existing pages

Before creating anything new, find what already exists for every entity and concept
mentioned in the source:

```
run wiki-search internally for each key term
read index.md sections relevant to the source topic
```

Build a map: **existing (update)** vs. **new (create)**. The difference between a
growing wiki and a pile of duplicates.

### ④ Write or update wiki pages (per SCHEMA.md)

**Read SCHEMA.md's policies** and apply them:

- **Page creation policy** — only create a page if the subject meets SCHEMA.md's
  threshold (default: "central to this source OR mentioned in 2+ sources")
- **Required frontmatter** — use the fields SCHEMA.md specifies (default:
  `title, created, updated, type, tags, sources, published_at, ingested_at`)
- **Custom dimensions** — write every dimension from step ①b into the
  frontmatter, filtered by each dimension's `applies_to` (if set). Dimensions
  the user explicitly skipped are omitted; dimensions with `required: true`
  that have no value block the write.
- **Tags** — only use values from SCHEMA.md's taxonomy. If the source reveals a
  tag you want to use that isn't in the taxonomy, **pause** and propose adding
  it to SCHEMA.md rather than drifting (schema guard)
- **Cross-reference policy** — SCHEMA.md may specify a minimum link count, or
  "cross-reference when genuine" (default). Don't force fake links to meet quotas
- **Page type** — must be one of the categories SCHEMA.md defines; if the content
  doesn't fit any existing type, propose a new category rather than mis-filing

**New pages** — file name: lowercase-hyphens.md in the correct category directory.

**Existing pages** — add new information, update facts, bump `updated` date. When
new info conflicts with existing content: note both claims with dates, add a
`contradictions:` frontmatter field referencing the other page, and flag for user
review.

### ⑤ Cross-reference both ways

For every page created or updated, check that **at least one existing page links
back** when there's a genuine connection. Cross-reference is bidirectional — a
page that exists but is never linked to is invisible. (SCHEMA.md's cross-reference
policy is the final word here.)

### ⑥ Update navigation

- Add new pages to `index.md` under the correct section, alphabetically
- Update "Total pages" count and "Last updated" in the index header
- Append to `log.md`:
  ```
  ## [YYYY-MM-DD] ingest | {Source Title}
  - Source: raw/{path}
  - Images: {count downloaded to raw/assets/}
  - Created: {list of new pages}
  - Updated: {list of updated pages}
  ```

### ⑦ Report

List every file created and updated, note any schema-evolution proposals (new
tags, new page types) that need user approval.

---

## Batch ingest (`--batch`)

For multiple sources in one pass:
1. Read all sources first (text + relevant images)
2. Identify all entities/concepts across all sources
3. One search pass for all of them (not N passes)
4. Create/update pages in one pass
5. Update index.md once at the end
6. Write a single log entry covering the batch

For bulk-importing an **existing document system**, use `wiki-import` instead —
it handles directory traversal, schema mapping, and checkpoint/resume.

---

## Output

```
[Operation] wiki-ingest | {Source Title}

[Changes]
- Raw:       raw/articles/{filename}.md
- Images:    raw/assets/{N files downloaded}
- Created:   {list of new wiki pages}
- Updated:   {list of updated wiki pages}
- Schema:    {"no change" | "proposed: add tag X / add page type Y"}

[Summary]
Ingested "{title}". Created {N} new pages, updated {M} existing pages.
{Key insight or notable connection discovered.}
{Schema evolution proposal if any — needs user approval}

[Suggested next]
→ kata:wiki-digest   (to see the updated state of the wiki)
```
