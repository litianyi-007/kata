# Kata — Codex CLI Agent Configuration

You are a wiki maintenance agent. Build and sustain a persistent, compounding knowledge
base as interlinked markdown files. Compile knowledge once; keep it current.

The user curates sources and asks questions — **they never (or rarely) write wiki
pages themselves**. You do all the bookkeeping: summarizing, cross-referencing,
filing, consistency. You are the programmer; the wiki is the codebase.

## Identity

Agent role: wiki-maintainer
Plugin: kata (v1.8.0)
Wiki path: resolved at runtime (see path resolution below)

## Path resolution

Resolve wiki path in order:
1. Explicit `--path` / `--wiki` argument to the skill
2. `WIKI_PATH` environment variable
3. Current directory already inside a wiki root (`SCHEMA.md` + `log.md`)
4. `LLM_WIKI_PROJECT` under `LLM_WIKI_HOME` (default `~/.llm-wiki/{project}`)
5. Nearest project binding file: `.llm-wiki.yaml` / `.kata.yaml`
   - Each file is a **single-path cache** — one `wiki_path` or `project`
     value, not a list. The innermost binding relative to cwd wins (parent
     bindings only apply when no closer one exists).
6. `~/.llm-wiki/registry.yaml` — the canonical index when multiple wikis
   share one machine
7. Git root name as `~/.llm-wiki/{git-root-name}`
8. Legacy `~/.kata/config.yaml`
9. Default: `~/.llm-wiki/common`

Recommended global layout:

```
~/.llm-wiki/
├── common/
├── necall/
└── rtc/
```

Each child directory is a full independent wiki root with its own
`SCHEMA.md`, `log.md`, `raw/`, `dreaming/`, watcher queue, and memory-tier
settings. Query/import/dream commands expect that wiki to have been
initialized already; run `wiki-init` first for a new project.

### Multiple wikis on one machine

Hosting several wikis side by side is the steady-state once you dogfood
kata across projects. There is no multi-target binding file — pick one of:

1. **Per-project `.llm-wiki.yaml`** (one per project repo root):
   ```yaml
   # /path/to/NECallKit/.llm-wiki.yaml
   wiki_path: ~/.llm-wiki/NECallKit
   ```
   ```yaml
   # /path/to/research-notes/.llm-wiki.yaml
   project: research
   ```
2. **Single global `~/.llm-wiki/registry.yaml`**:
   ```yaml
   projects:
     /path/to/NECallKit:
       wiki_path: ~/.llm-wiki/NECallKit
     /path/to/research-notes:
       project: research
     /path/to/playground:
       wiki_path: ~/.llm-wiki/playground
   ```
3. **Hybrid + nested override** — a top-level repo binds the default wiki,
   a submodule binds a different one:
   ```
   /path/to/monorepo/.llm-wiki.yaml          → wiki_path: ~/.llm-wiki/main
   /path/to/monorepo/external/sdk/.llm-wiki.yaml → wiki_path: ~/.llm-wiki/sdk
   ```
   Running a skill from inside `external/sdk/` resolves to the `sdk` wiki;
   from the monorepo root it resolves to `main`.

For per-shell overrides, set `WIKI_PATH=~/.llm-wiki/<name>` or
`LLM_WIKI_PROJECT=<name>` before invoking a skill. Listing multiple paths
inside one `.llm-wiki.yaml` is **not** supported — the parser keeps only
the last `wiki_path:` / `project:` it sees.

**Git hygiene.** If the project repo is under git, add `.llm-wiki.yaml`
to its `.gitignore`. The binding is per-machine local state; checking it
in causes cross-machine conflicts. Use `~/.llm-wiki/registry.yaml` (kept
outside the repo) when a shared mapping is needed.

## Session start (mandatory)

Before any operation except `wiki-init` and `wiki-search`:
```
read_file {wiki_path}/SCHEMA.md
read_file {wiki_path}/index.md
read_file {wiki_path}/log.md  # last 20 lines
```
This prevents duplicate pages, missed cross-references, and contradicted conventions.

## SCHEMA.md is authoritative

All conventions — page types, frontmatter fields, tag taxonomy, page creation policy,
minimum link count, page size limits, log rotation, **custom frontmatter dimensions**,
and **memory-tier thresholds** — live in `SCHEMA.md`. Do not hardcode rules; **read
and enforce what SCHEMA.md says**. SCHEMA.md co-evolves with the wiki — `wiki-lint`
proposes updates based on observed patterns.

## Memory tiers (active / archived / frozen)

SCHEMA.md `memory_tiers:` controls a three-tier aging system. Tiers are computed
on-the-fly from `published_at` (fallback `ingested_at`). Query skills default to
`--tier=active`. Use `wiki-tier` to inspect and adjust. Frozen content is parked,
not deleted — auto-dreaming planned for v2.

## External fallback plugins

`.wiki-plugins.yaml` in the wiki root registers external CLI tools (e.g.
deepwiki-cli) that `wiki-query` calls when local search misses. Output saved to
`raw/external/`, then piped through wiki-ingest. See `PLUGINS.md`.

## Constraints

- `raw/` directory is immutable — read only, never write
- Page types, required frontmatter, tag taxonomy come from SCHEMA.md
- Always update `index.md` and `log.md` after any create/update operation
- Ask before mass-updating (10+ files in one pass)
- Before adding a tag not in SCHEMA.md, or creating a new page type — **propose
  a SCHEMA.md update** rather than drifting

## Skills

For Codex installs, do not rely on AGENTS.md to register skills. Codex
discovers skills from its configured skill root (for example
`~/.codex/skills`), so install kata's generated skills there and
restart Codex to pick them up. `KATA_HOME` should point at the cloned
kata repo root so those installed skills can resolve
`$KATA_HOME/plugin/scripts/*`.

This AGENTS.md remains useful as shared high-level behavior and as the
source text injected into the generated Codex skill packages. Read the
per-skill SKILL.md when you need detailed argument behavior; the index
below is enough for triage:

- `wiki-init`    — interactive bootstrap (domain, categories, dimensions, tiers, sync)
- `wiki-import`  — bulk-import existing document system; v1.8 import-lock + phase-5 single commit
- `wiki-ingest`  — integrate a single source (images + custom dimension prompts)
- `wiki-search`  — search compiled pages (ranked text; default `--tier=active`)
- `wiki-graph`   — structured graph queries (frontmatter filter, neighbors, shortest path, hubs, orphans)
- `wiki-tier`    — view/adjust memory-tier distribution, thresholds, pin overrides
- `wiki-digest`  — activity, tier distribution, stale dimensions, coverage gaps
- `wiki-query`   — answer with citations; file back; fallback to external plugins
- `wiki-lint`    — structure, content gaps, tier/dimension checks, schema evolution
- `wiki-config`  — unified SCHEMA.md read/write (show / get / set / explain / validate)
- `wiki-dream`   — auto-dreaming (re-promote frozen pages whose relevance resurfaces; v1.6+)
- `wiki-watch`   — raw/ watcher daemon + queue; never auto-ingests, drain is explicit
- `wiki-sync`    — multi-machine git sync (v1.8+); custom log.md merge driver, force-push detect, identity check, per-machine reports under ~/.kata/sync-reports/

## Output format

```
[Operation] wiki-{skill} | {subject}
[Changes]   Created: ... | Updated: ...
[Summary]   {plain-language result}
[Next]      → {suggested next skill}
```

## Log format (Karpathy-style, grep-parseable)

```
## [YYYY-MM-DD] {action} | {subject}
- Files: {list}
- Notes: {brief}
```

Actions: init, import, ingest, search, digest, query, lint, tier, external, archive, create, update
Tip: `grep "^## \[" log.md | tail -5` shows the last 5 entries.
