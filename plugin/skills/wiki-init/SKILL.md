---
name: wiki-init
description: "Interactive bootstrap for a new LLM wiki: ask about domain, propose categories that fit, write a customized SCHEMA.md, create index.md and log.md, and suggest git init."
user-invocable: true
argument-hint: "[--path=~/wiki] [--domain='AI research'] [--categories='a,b,c'] [--non-interactive] [--set-tags='a,b,c'] [--set-active-days=N] [--set-archived-days=N] [--set-driving-field=published_at|ingested_at] [--set-dimension='name:type:required:refresh_on'] [--enable-dreaming] [--enable-sync] [--refresh-id [--force]]"
---

# wiki-init

Bootstrap a new wiki from scratch — **interactively**. The wiki's shape depends on
the domain, so this skill does not hardcode categories. Instead it asks about the
user's domain, proposes a category set that fits, and lets the user edit. The
resulting SCHEMA.md is the authoritative config that all other skills read.

> "The exact directory structure, the schema conventions, the page formats, the
> tooling — all of that will depend on your domain, your preferences, and your
> LLM of choice." — Karpathy, LLM Wiki

## When to use

- User asks to create, start, or initialize a wiki or knowledge base
- No wiki exists yet at the configured path

## Non-interactive mode

For interactive setup, this skill does the LLM walkthrough. For
**scripted setup** (CI, automated provisioning, fresh-machine bootstrap),
shell out to `plugin/scripts/wiki_init.py` directly — it implements the
same final state without any LLM call.

```bash
# Bootstrap from scratch with explicit flags
python {plugin_root}/scripts/wiki_init.py \
    --path ~/research-wiki \
    --domain "AI research" \
    --categories entities,concepts,comparisons,queries \
    --set-tags model,paper,concept,reference \
    --set-active-days 365 --set-archived-days 730 \
    --set-driving-field published_at \
    --set-dimension "version:string:false:ingest"

# Or use a domain template (recommended)
python {plugin_root}/scripts/wiki_init.py \
    --path ~/market-wiki \
    --template market_research
```

Available templates:
- `market_research` — companies / models / papers / trends; auto-dreaming
  enabled by default with `co-occurrence` strategy.

The script writes `SCHEMA.md`, `index.md`, `log.md`, all category dirs,
and the `raw/{articles,papers,transcripts,assets}/` layout. Validates
the resulting SCHEMA.md against `plugin/schema/wiki-schema.json` before
exiting. No LLM involvement.

| Flag | Default if `--non-interactive` and unset | Effect |
|------|------------------------------------------|--------|
| `--domain` | `general` | Plain wiki without domain-specific prompts |
| `--categories` | `entities,concepts,comparisons,queries` | Comma list of category dirnames |
| `--set-tags` | `concept,reference,question` | Comma list of starter tag taxonomy |
| `--set-active-days` | `365` | Memory tier: active threshold in days |
| `--set-archived-days` | `730` | Memory tier: archived threshold |
| `--set-driving-field` | `published_at` | Memory tier: which date field drives age |
| `--set-dimension` | (none — repeatable) | One custom dimension per flag, format `name:type:required:refresh_on1+refresh_on2`. Example: `--set-dimension='version:string:true:ingest+import'` |

In non-interactive mode the skill skips git init (caller's responsibility)
and skips the conversational steps in ②, ③, ④, ④b, ④c — it goes straight
from path resolution to file generation using the flags above.

## Steps

### ① Resolve path

> **HARD RULE — read this before doing anything else.**
>
> A wiki **always** initializes under `~/.llm-wiki/<project>/`
> (Windows: `C:\Users\<user>\.llm-wiki\<project>\`). The wiki is a
> **separate artifact** from the project it describes — it never lives
> inside the project's source repo. This is the single most common
> AI-agent mistake during wiki-init, and `wiki_init.py` refuses
> non-standard paths without `--force`.
>
> When the user says "initialize a wiki for project X", default to:
>
> ```
> ~/.llm-wiki/<X>/
> ```
>
> Pick the project slug from: explicit user input → existing
> `~/.llm-wiki/registry.yaml` entry → the source repo's git root
> basename. Never use the project source path as the wiki path.

**Anti-pattern (refuse and re-propose):**

```text
❌ Wrong: --path <workspace>/project/NECallKit
❌ Wrong: --path ~/code/my-project
❌ Wrong: running wiki-init while cwd is inside the source repo with no --path

✅ Right: --path ~/.llm-wiki/NECallKit
✅ Right: --path ~/.llm-wiki/my-project
```

If the user already ran `wiki-init` against a source-repo path:

1. Stop. Do not continue ingesting into that wrong location.
2. Tell the user the wiki landed in the wrong place and propose the
   correct standard path.
3. Offer to move the wiki to `~/.llm-wiki/<project>/` (a directory
   rename plus, if a git remote was set up, a careful re-clone or
   `git mv` — coordinate with the user).
4. Update any `.llm-wiki.yaml` / registry entries to point at the
   new location. Notes:
   - `.llm-wiki.yaml` only caches one wiki per file — if this project
     also needs a different wiki, drop a separate `.llm-wiki.yaml` in
     that submodule / subdirectory, or add the mapping to
     `~/.llm-wiki/registry.yaml` instead.
   - When the project repo is git-managed, add `.llm-wiki.yaml` to its
     `.gitignore` — it is per-machine state and would otherwise conflict
     across maintainers / machines.

**Path-resolution chain (for `--path` omitted, in priority order):**

1. Explicit `--path` / `--wiki` flag (still validated against the
   standard layout by the script — non-standard paths require `--force`).
2. `WIKI_PATH` environment variable.
3. Current directory **if and only if** it is already an existing wiki
   root (has `SCHEMA.md` at its top). This case is for re-running
   wiki-init operations on an existing wiki; **it is not a way to
   bootstrap a new wiki in arbitrary cwd**.
4. `LLM_WIKI_PROJECT` env var under `LLM_WIKI_HOME` (default
   `~/.llm-wiki/{project}`).
5. Nearest `.llm-wiki.yaml` / `.kata.yaml` binding file pointing at
   a wiki root. **Single-path cache** — each file binds to exactly one
   wiki; the innermost binding relative to cwd wins. For multi-wiki
   coexistence, prefer step 6 or place separate bindings in each
   project / submodule root.
6. `~/.llm-wiki/registry.yaml` lookup.
7. Git root name as `~/.llm-wiki/{repo}` — derives a `~/.llm-wiki/`
   subpath from the project's git root basename. **Never returns the
   project's own source path.**
8. Default `~/.llm-wiki/common`.

Every step that does not produce a path under `~/.llm-wiki/` will be
rejected by `wiki_init.py` unless `--force` is passed.

**Recommended multi-project layout:**

```
~/.llm-wiki/                       ← shared parent, per machine
├── common/                        ← default catch-all
├── NECallKit/                     ← one wiki per project
├── kata/                       ← kata plugin's own self-meta wiki
└── registry.yaml                  ← optional name → path lookup
```

Each child directory is an independent wiki root with its own
`SCHEMA.md`, `log.md`, `raw/`, `dreaming/`, watcher queue, and
memory-tier settings.

If the resolved path already exists and is non-empty, warn the user and
ask before overwriting (the script refuses without `--force`).

### ② Ask about the domain

If `--domain` not provided, ask:
> "What domain will this wiki cover? Be specific. Examples:
>  - 'transformer ML research — papers and blog posts'
>  - 'reading the Lord of the Rings trilogy — characters, places, events'
>  - 'competitive analysis of SaaS observability tools'
>  - 'my personal health, psychology, self-improvement'
>  - 'internal team wiki — projects, decisions, customer calls'"

### ③ Propose categories that fit the domain

Based on the domain, propose a starter category set. Do **not** hardcode
`entities/concepts/comparisons/queries` — match the domain:

**Research / technical deep-dive:**
- `entities/` — people, labs, orgs, products, models
- `concepts/` — techniques, theories, ideas
- `comparisons/` — side-by-side analyses
- `queries/` — filed query results

**Reading a book / media / fiction:**
- `characters/`, `places/`, `events/`, `themes/`, `timeline/`, `chapters/`

**Personal / self-improvement:**
- `journal/`, `topics/` (health, psychology, career), `patterns/`, `queries/`

**Business / team:**
- `people/`, `projects/`, `customers/`, `decisions/`, `meetings/`, `queries/`

**Competitive analysis / market research:**
- `competitors/`, `features/`, `market/`, `comparisons/`, `queries/`

**Trip planning / hobby / custom:**
- Ask the user what fits, or propose 3–5 categories based on the domain keywords

Present the proposal:
> "For a {domain} wiki, I suggest these categories:
>  - {cat1}/ — {purpose}
>  - {cat2}/ — {purpose}
>  ...
>  Accept, edit, or replace?"

If `--categories` was provided, use them directly. Otherwise wait for user input.

### ④ Ask about conventions (defaults offered)

Walk through each policy briefly. **Offer defaults — don't force.** User can press
enter to accept each.

- **Frontmatter fields** — default: `title, created, updated, type, tags, sources,
  published_at, ingested_at`. The last two are required by the memory-tier system
  (step ④c) — keep them unless the user explicitly disables tiers.
- **Tag taxonomy** — propose 10–20 domain-specific tags. Show the list, accept edits.
- **Page creation policy** — default: "create a page when the subject is central to
  a source, or mentioned in 2+ sources". Alternatives: "central only" / "flexible"
- **Cross-reference policy** — default: "link to related pages wherever there's a
  genuine connection; no minimum". Alternatives: "≥1 link required" / "≥2 required"
- **Page size limit** — default: no limit (flag in lint only if user sets one)
- **Log rotation threshold** — default: no rotation (flag in lint only if set)

Each answer gets written verbatim into SCHEMA.md so future skill runs enforce the
user's actual preferences — not plugin defaults.

### ④b Ask about custom frontmatter dimensions

Beyond standard fields (title, tags, sources, dates), a wiki can declare **custom
dimensions** — extra frontmatter fields specific to the domain. Example: a software
project wiki typically wants `version:` on every page; a research-paper wiki might
want `venue:` or `citation_count:`; a personal journal might want `mood:`.

Ask:
> "Any custom frontmatter dimensions for this domain? These are extra fields the
> agent will ask you about every time it ingests a new source. Leave empty to skip.
>
> Example: `version` (string, required, asked on every ingest) — useful when the
> wiki tracks a thing that evolves (software, product, treaty)."

For each dimension the user names, capture:
- **name** — lowercase_snake_case field name
- **type** — one of `string | date | number | enum | list`
  - If `enum`, ask for the allowed values (comma-separated)
- **description** — short phrase used as the prompt text (e.g. "Which version of
  the product does this source describe?")
- **required** — yes / no (default yes)
- **default** — optional default value, or none
- **refresh_on** — when does the agent prompt for this field's value?
  - `ingest` — every `wiki-ingest` run asks
  - `import` — every `wiki-import` run asks (once for the whole batch by default)
  - `digest` — `wiki-digest` surfaces pages with stale values and offers to re-prompt
  - `manual` — never auto-prompts; user supplies via `--set version=X`
  - Default for string fields that describe evolving state: `[ingest, import]`
- **applies_to** — optional list of page types this field applies to (omit = all)

Write the dimensions into SCHEMA.md's `custom_dimensions:` block (step ⑥) so every
other skill can read and enforce them.

### ④c Ask about memory tier thresholds

The wiki distinguishes **three tiers** of raw content by age:
- **active** — recent enough that the wiki prioritizes it in all queries (default: < 1 year)
- **archived** — older, still accessible but not default (default: 1–2 years)
- **frozen** — old, read-mostly, candidate for future auto-dreaming (default: > 2 years)

Tiers are computed **on-the-fly** from a date field, not stored as frontmatter.
This means adjusting the thresholds is instant and can't drift.

Ask:
> "Memory tier thresholds (press enter for defaults):
>  - active window: [default 365 days]
>  - archived window: [default 730 days — anything older is frozen]
>  - driving date: [default `published_at` if present, else `ingested_at`]
>  
>  Wiki queries default to `--tier=active`. To disable tiers entirely, say 'off'."

If the user says "off", record `memory_tiers: disabled` in SCHEMA.md and skip the
rest of this step. Otherwise write the thresholds into SCHEMA.md's `memory_tiers:`
block (step ⑥). The thresholds can be changed later with `wiki-tier --set-thresholds`.

### ④cc Ask about multi-machine sync (v1.8+)

If the user is setting up across multiple machines (laptop + desktop, or
team), ask whether to enable wiki-sync:

> "Will this wiki be synced across multiple machines via git? Enabling
>  wiki-sync writes a `sync:` block to SCHEMA.md and generates a
>  `wiki_id` UUID for cross-machine identity check. You'll still need to
>  set up a git remote separately. (PRD-v1.8 docs/PRD-v1.8-sync.md)"

If yes, in non-interactive mode pass `--enable-sync`. The script:
- Generates a `wiki_id` UUID v4 and writes it to SCHEMA.md's `## Identity`
  section (top-level scalar, sync identity check parses it before any
  other config)
- Writes the `sync:` block (enabled / remote=origin / branch=main /
  on_conflict=report-and-exit / auto_chain_dream=false /
  auto_configure_drivers=true)
- Always writes per-machine `.gitignore` (`.wiki-ingest-queue.json` /
  `.wiki-import-checkpoint.json` / `.wiki-import-lock` /
  `.wiki-plugins.yaml`) regardless of `--enable-sync` — these state files
  should never sync.

### ④d Ask about auto-dreaming

If memory tiers are enabled, also ask whether to turn on auto-dreaming:

> "Enable auto-dreaming? It periodically re-evaluates frozen / archived pages
>  whose relevance returns based on this period's ingests, and surfaces a
>  candidate list for review (never auto-promotes).
>
>  - co-occurrence (only strategy in v1.6) — entity overlap + tag resurgence
>    + direct citation from fresh pages
>  - cadence: weekly | daily | manual (default: weekly)
>  - threshold 0.6, max 10 candidates / run, dormancy 180d, min_count 3
>
>  Enable? [y/n]"

If yes, write a default `dreaming:` block into SCHEMA.md (step ⑥) and **at
the end of init, surface the recommended schedule line** so the user can
copy-paste it without hunting through docs:

```
claude /schedule "0 23 * * 0" "/kata:wiki-dream"
```

The non-interactive script accepts `--enable-dreaming` to do the same end-state
without an LLM walkthrough. Domain templates that ship dreaming on
(`market_research`) include the block automatically — `wiki_init.py
--template market_research` always prints the schedule line in its output.

### ④e Existing-wiki upgrade: --refresh-id (v1.8+)

For wikis created before v1.8 that need to adopt sync:
`wiki_init.py --refresh-id --path <wiki>` inserts a fresh `wiki_id` UUID
into the existing SCHEMA.md without rebuilding directories. If a `wiki_id`
already exists, the command refuses unless `--force` is passed (overwriting
drops cross-machine identity — peer machines will see identity-mismatch
on next sync and need their own `--refresh-id` coordinated). Also re-runs
the gitignore merge so old wikis pick up the per-machine state patterns.

### ⑤ Create directory structure

```
{wiki_path}/
├── raw/articles/
├── raw/papers/
├── raw/transcripts/
├── raw/external/
├── raw/imported/
├── raw/assets/          # Images and attachments referenced by sources
├── {category-1}/        # from step ③
├── {category-2}/
├── ...
└── _archive/            # Superseded pages (removed from index, never deleted)
```

### ⑥ Write SCHEMA.md

Include:
- **Domain**: what this wiki covers (from step ②)
- **Categories**: the list from step ③ with one-line purpose for each
- **Conventions**: file naming, wikilinks syntax
- **Frontmatter template**: the fields chosen in step ④
- **Custom dimensions**: the fields chosen in step ④b — as a YAML block:
  ```yaml
  custom_dimensions:
    - name: version
      type: string
      description: "Which version of the product does this source describe?"
      required: true
      default: null
      refresh_on: [ingest, import]
      applies_to: null   # null = all page types
  ```
  If the user declared no custom dimensions, write `custom_dimensions: []`.
- **Memory tiers**: the thresholds chosen in step ④c — as a YAML block:
  ```yaml
  memory_tiers:
    enabled: true
    active_days: 365
    archived_days: 730
    driving_field: published_at   # fallback: ingested_at
  ```
  If the user said "off", write `memory_tiers: { enabled: false }`.
- **Tag taxonomy**: the tags chosen in step ④ (add new tags here BEFORE using them)
- **Page creation policy**: the rule chosen in step ④
- **Cross-reference policy**: the rule chosen in step ④
- **Page size limit**: the rule chosen in step ④ (or "no limit")
- **Log rotation**: the rule chosen in step ④ (or "no rotation")
- **Update policy** for contradictions: note both claims with dates, flag for review

Make it clear at the top: **this file is user-editable and co-evolves with the
wiki**. `wiki-lint` will propose updates over time.

### ⑦ Write index.md

Sectioned header with one section per category from step ③:
```markdown
# Wiki Index

> Content catalog. Every wiki page listed under its type with a one-line summary.
> Read this first to find relevant pages for any query.
> Last updated: {date} | Total pages: 0

## {Category 1}
## {Category 2}
...
```

### ⑧ Write log.md

```markdown
# Wiki Log

> Chronological record of all wiki actions. Append-only.
> Format: ## [YYYY-MM-DD] action | subject
> Tip: `grep "^## \[" log.md | tail -5` for the last 5 entries

## [YYYY-MM-DD] init | Wiki initialized
- Domain: {domain}
- Path: {wiki_path}
- Categories: {list}
- Structure created with SCHEMA.md, index.md, log.md
```

### ⑨ Suggest git init

At the end, suggest:
> "Your wiki is a git repo's worth of markdown — you get version history, branching,
> and collaboration for free with one command:
>
> ```bash
> cd {wiki_path} && git init && git add . && git commit -m 'wiki: init'
> ```
>
> Run it?"

Offer to run it if the user confirms.

### ⑩ Confirm and suggest first ingest

Report what was created, then suggest:
> "Wiki initialized at `{path}`. Drop a source into `raw/articles/` (or paste a URL)
> and run `kata:wiki-ingest <source>` to add your first document. A single
> source usually touches 10–15 pages — that's the compounding effect."

## Output

```
[Operation] wiki-init | {domain}

[Changes]
- Created: SCHEMA.md (with {N} categories, {M} tags, {policies})
- Created: index.md, log.md
- Created: {list of category dirs and raw/ subdirs}
- Git: {"initialized" | "skipped"}

[Summary]
Wiki initialized for "{domain}" at {path}. Categories: {list}. SCHEMA.md customized
with {N}-tag taxonomy. Ready to ingest first source.

[Suggested next]
→ kata:wiki-ingest <source>
```
