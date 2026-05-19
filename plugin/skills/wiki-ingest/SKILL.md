---
name: wiki-ingest
description: "Ingest a source into the wiki: save raw content and referenced images, prompt the user for any custom frontmatter dimensions declared in SCHEMA.md, extract key information, create or update wiki pages per SCHEMA.md conventions, and update index.md and log.md."
user-invocable: true
argument-hint: "<url|file|text> [--batch] [--no-discuss] [--no-images] [--no-spec-preflight] [--set=key=value,...] [--page-type=<type>] [--proposed-path=<dest-path>] [--evidence-anchors=<comma-separated>]"
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

**For each top candidate, the author decides**:

1. **Skip** — the candidate is unrelated despite the surface overlap. No
   action needed.
2. **Declare a relationship** — add to the new spec's frontmatter:

   ```yaml
   spec_relationships:
     - kind: supersedes | refines | extends | parallel | contradicts
       target: <wiki-path-of-old-spec>     # or kata://<peer>/<path> URI for federated targets
       note: "<one-line rationale>"
   ```

   `target` accepts: wiki-relative path, `[[wikilink]]`, bare stem
   (resolved by wiki-wide stem search), or `kata://<peer-or-uuid>/<path>`
   for a peer wiki registered in `.federation.yaml`. Absolute paths and
   `..` segments are rejected by Phase 3's path-traversal guard.

Phase 0 itself does **not** auto-update the old spec. Phase 3
(opt-in preview, off by default) adds banner + tier flip + reverse-link
on the target page when `auto_propagation.enabled: true`. See
`wiki-spec` skill for the Phase 3 PREVIEW caveat. If a relationship
clearly implies the old spec is dead and Phase 3 is off, the author may
manually run `wiki-tier --pin <old-spec>:archived` or add a
`tier_override:` line by hand.

**Phase 2 enforcement gate (v1.13, v2.4.0+)**:

If SCHEMA.md sets `spec_authoring.enforce_relationship_declaration: true`,
re-run preflight with `--enforce` immediately before step ④ (after the
author has had a chance to add `spec_relationships:` to the draft):

```bash
python {plugin_root}/scripts/spec_preflight.py \
    --new-spec {raw_source_path} \
    --include-archived \
    --enforce
```

Inspect the `enforcement` block in the JSON envelope:

- **exit code 0** → `decision: "accept"`. All above-threshold candidates are
  covered by the draft's `spec_relationships:` entries (or there are no
  above-threshold candidates). Proceed to ③.
- **exit code 2** → `decision: "reject"` (strict mode). Surface the
  `enforcement.uncovered` list to the user and **abort the ingest**. The
  author must either declare relationships for each uncovered candidate
  or explicitly lower the threshold / disable enforcement.
- **exit code 1** → `decision: "reject"` (confirm mode). Surface the
  `enforcement.uncovered` list and ask the user, per-candidate, whether
  to declare a relationship or mark as explicitly_unrelated, then re-run.

The script reports `enforcement.threshold` and `enforcement.mode` in the
envelope so the author can see which gate they tripped against.

**When to skip this step** (no preflight needed):

- `spec_authoring.enabled: false` (default for new wikis)
- `spec_authoring.preflight: off`
- Source's frontmatter `type` is not in spec_types
- User passes `--no-spec-preflight` (force-skip override — also bypasses
  enforcement; use only when the author has out-of-band justification)
- Wiki has fewer than 2 existing spec-type pages (no candidates possible)

**Configuration override**: if the source's frontmatter `type` is in
`spec_types` but the user explicitly wants to skip preflight for this
ingest, accept `--no-spec-preflight` and proceed straight to ③. Note this
in step ⑦ Report so the user knows preflight (and any enforcement) was
bypassed.

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

### ④b Optional hint flags from upstream skills (v1.11 Phase 0)

Three optional flags let an upstream skill (e.g. `wiki-session-ingest`) hand
off structured hints rather than re-deriving them. All three are strictly
additive — unset behavior matches the inference path described above.

- **`--page-type=<type>`** — strong default for page type. Use this value
  unless SCHEMA.md analysis reveals a clear mismatch (e.g. the source body
  is obviously a `lesson` but the upstream hinted `decision` — in that case,
  follow SCHEMA.md and note the override in the report). Common values:
  `decision`, `feature`, `bug`, `lesson`, `concept`, `prd`, `rfc`, `adr`,
  `task-spec`. Must be one SCHEMA.md actually declares.
- **`--proposed-path=<wiki-relative-path>`** — preferred wiki-relative
  destination (e.g. `decisions/F100-payment-rewrite.md`). Treat as a hint,
  not a command:
  - If the path is free, use it as-is
  - If a page already exists there, apply the standard "create vs update"
    policy from step ④ above (default: update existing with diff preview)
  - If the path conflicts with SCHEMA.md's category policy (e.g. hint says
    `decisions/foo.md` but `decisions` doesn't exist as a category), fall
    back to inference and note the override
- **`--evidence-anchors=<comma-separated>`** — opaque tokens the upstream
  skill wants preserved in the new page's frontmatter under
  `evidence_anchors:`. Write verbatim, no normalization. Typical values:
  `session-msg-142,session-msg-167` (session-ingest message indices), or
  any caller-defined token. The field is omitted entirely when the flag
  is unset.

Example invocation by `wiki-session-ingest` (Phase 5 distill loop):

```
wiki-ingest raw/sessions/claude-code-2026-05-17-foo-12434e19.md \
    --page-type=decision \
    --proposed-path=decisions/llm-wiki-yaml-single-path-cache.md \
    --evidence-anchors=session-msg-142,session-msg-167
```

Per step ⑦ Report, surface any hint that was overridden so the upstream
caller can audit what landed vs what was requested.

### ④c Auto-propagate spec_relationships (v1.13 Phase 3, v2.12.0+)

If the new page's frontmatter contains `spec_relationships:` AND
SCHEMA.md sets `spec_authoring.auto_propagation.enabled: true`, invoke
spec auto-propagation BEFORE cross-referencing (step ⑤) so the
modified target pages also get their cross-refs updated in the same
ingest:

```bash
python {plugin_root}/scripts/spec_propagate.py \
    --wiki {wiki_path} \
    --new-spec {wiki-relative-path-of-page-just-written}
```

For each `kind:` in `spec_authoring.auto_propagation.kinds_to_propagate`
(default: `[supersedes]`), the script applies three idempotent actions
to the target page:

1. **Banner**: prepends a `<!-- kata:spec-banner BEGIN/END -->` marker
   block warning the reader the page is superseded
2. **Reverse link**: appends `spec_superseded_by: [{path, date, note}]`
   to target's frontmatter (dedup by path on re-run)
3. **Tier flip**: sets `tier_override: archived` + `tier_reason:
   "Superseded by <stem> on <date>"` (unless author manually pinned
   the page — detected via tier_reason NOT starting with "Superseded by")

**Federation carve-out**: `kata://<peer>/<path>` targets DO NOT modify
the peer page (read-only federation contract from v1.12 D1.6). They
write to `{wiki_path}/.spec-reverse-index.yaml` which Phase 4 lineage
view (`wiki-graph --mode spec-history`) reads.

Surface the propagation result in step ⑦ Report: list each target
that got the banner / reverse-link / tier flip + any `kata://`
entries added to the reverse-index. The author needs to know that
their supersede declaration triggered other-page modifications.

**When to skip**:

- `spec_authoring.auto_propagation.enabled: false` (default — opt-in)
- The new page has no `spec_relationships:` block
- No relationship's `kind:` is in `kinds_to_propagate`

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
