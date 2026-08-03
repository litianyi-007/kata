# Kata

**Project memory for AI-paired engineering — compiled once and kept current; humans ask, AI maintains.**

[![tests](https://github.com/litianyi-007/kata/actions/workflows/test.yml/badge.svg)](https://github.com/litianyi-007/kata/actions/workflows/test.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-22d3ee.svg)](LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude_Code-plugin-22d3ee.svg)](#quick-install)

![Kata — compile business semantics for AI-paired engineering. An AI-maintained wiki for project memory.](docs/assets/readme/kata-hero-banner.svg)

> 🇨🇳 [中文](README.md) (default) · 🇯🇵 [日本語](README.ja.md)

## What problem this solves

The judgment calls a project accumulates — why this threshold is this number,
why the last proposal got rejected — end up scattered across chat logs and
documents nobody reopens anymore. Every time you switch to a new agent
session, that context has to be relearned from scratch, or it just isn't, and
the same mistake gets made again.

kata is an **AI-maintained, human-queried wiki**: it builds on
[Karpathy's LLM-Wiki concept](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) —
*"unlike RAG... the wiki is compiled once and then kept up to date"*, *"you
curate sources and ask good questions, the LLM does the rest"*. kata adds one
self-closing loop on top of that: ingest → cross-link → a question worth
keeping gets filed as a hub page → the next session reads the hub before it
does anything.

One real measurement: over a 4-week dogfood on NECallKit (multi-platform
Electron + native SDK), one filed query grew the wiki by **+17 edges** —
versus an average of 5 edges per page from a plain import. Three real bugs
(B066/B070/B074), one wiki. Details in the
[Essay #1 draft](docs/essay-drafts/2026-05-13-essay1-code-quality-vs-business-DRAFT.md).

![One filed query, +17 edges. Imports averaged 5 edges per page. The wiki grows when you ask it questions, not when you load it.](docs/assets/essay/V1-wiki-compounding.svg)

### How this differs from neighbors

|                        | kata                             | Obsidian Copilot / Smart Connections | MCP memory servers | RAG / vector DB       |
|------------------------|-----------------------------------|---------------------------------------|---------------------|-----------------------|
| Source of truth        | Your markdown files               | Your markdown files                   | Server-side store    | Embedding index        |
| Compiled or per-query? | Compiled once, kept current       | Per-query retrieval                   | Per-query retrieval  | Per-query retrieval    |
| Cross-references       | Written into pages on ingest       | Computed from embeddings              | None or schema-typed | None                   |
| Works offline          | Yes (no embedding model needed)    | Embedding model required               | Server required       | Embedding model required |

kata bakes synthesis into the wiki itself; RAG and chat memory rebuild it on
every query — fine for fluid retrieval, but the cross-references never get
written down, so they never compound.

## Quick install

Prerequisites: Git ≥ 2.20 (needed for the v1.8 sync custom merge driver);
Python 3.10+ (pure stdlib — scripts under `plugin/scripts/` need no
`pip install`).

kata has **four parallel install paths** — pick the one that matches your LLM
tooling. All four produce the **same 18 skills** and the **same wiki
filesystem layout**; the wiki content itself always lives separately at
`~/.llm-wiki/<project>/`, independent of which install path you pick.

| Path | Tool | Install location | Scope |
|---|---|---|---|
| A | Claude Code (recommended) | `~/.claude/plugins/` (managed by `claude /plugin install`) | Global |
| B | Codex CLI | `~/.codex/skills/` + `~/kata/` (generated skills + env var) | Global |
| C | Standalone (any LLM) | Pasted into the session as a system prompt | Per-session |
| D | GitHub Copilot CLI (v2.15.2+) | `~/.config/github-copilot/copilot-cli/` (managed by `copilot plugin install`) | Global |

**Path A — Claude Code:**

```bash
claude /plugin marketplace add litianyi-007/kata
claude /plugin install kata@kata
```

Hacking on a local clone: `claude /plugin marketplace add .`, then edits under
`./plugin/skills/` take effect without a reinstall. Update / uninstall:
`claude /plugin update kata` / `claude /plugin uninstall kata` (wiki content
is unaffected).

**Path B — Codex CLI** (Codex has no plugin marketplace, so it relies on
generating skills into a discovery directory):

```bash
git clone https://github.com/litianyi-007/kata ~/kata
echo 'export KATA_HOME="$HOME/kata"' >> ~/.zshrc   # or ~/.bashrc
python ~/kata/scripts/install_codex_skills.py
```

Restart Codex after installing/updating — only then does a new session load
it. `plugin/AGENTS.md` is **not** Codex's skill registry — it's the shared
instructions the installer injects into every generated skill. Want kata in
just one project? add `--dest <project>/.codex/skills`.

**Path C — Standalone (any LLM):**

```bash
cat SKILL.md | pbcopy   # macOS; use xclip on Linux, clip on Windows
```

`SKILL.md` is self-contained — every skill's instructions, every guard, every
known limitation. It produces the same schema and wiki layout as A/B, at the
cost of no deterministic Python scripts (the LLM has to recompute
ranking/graph queries on every call) and no `wiki-sync` auto-merge driver.

**Path D — GitHub Copilot CLI:**

```bash
copilot plugin install litianyi-007/kata
```

Copilot CLI reads the repo-root `plugin.json` (added in v2.15.2 — Copilot
only looks at top-level manifests, it doesn't recurse into subdirectories),
which points at `plugin/skills/` — the same SKILL.md files Claude Code uses.

### Quick start

```bash
# 1. Initialize — interactive: asks about your domain, proposes categories that fit
/kata:wiki-init --path=~/.llm-wiki/my-project --domain="Electron + native SDK"

# 2. Ingest your first source — images auto-downloaded to raw/assets/, cross-references written in
/kata:wiki-ingest docs/ARCHITECTURE.md

# 3. See what was compiled — pages created, edges added, suggested next ingests
/kata:wiki-digest

# 4. Ask a real maintainer-decision question — the answer files back as a hub page
#    future agents read before they write code
/kata:wiki-query "what's our IPC topology between Electron renderer and native SDK?"

# 5. Explore the graph (BFS over [[wikilinks]])
/kata:wiki-graph --neighbors attention --depth=2 --format=mermaid

# 6. Periodic health check
/kata:wiki-lint
```

## Skills

18 skills, from bootstrapping a wiki to federating across them.

| Skill | Invocation | One-liner |
|---|---|---|
| wiki-init | `/kata:wiki-init` | Interactive bootstrap: asks your domain, proposes categories, writes SCHEMA.md, creates index.md/log.md |
| wiki-import | `/kata:wiki-import <path>` | Bulk-import an existing doc system (Obsidian/Notion/Confluence/folder) — dedup, checkpoint/resume, 5 phases |
| wiki-ingest | `/kata:wiki-ingest <source>` | Ingest a single source: save raw text + images, create/update pages per SCHEMA.md, update index.md and log.md |
| wiki-search | `/kata:wiki-search <query>` | Ranked keyword/tag/type search, active-tier only by default, scales to qmd/MCP |
| wiki-graph | `/kata:wiki-graph [mode]` | Query the wiki as a graph: neighbor traversal, shortest path, hub/orphan detection, frontmatter filters — no graph database maintained |
| wiki-tier | `/kata:wiki-tier` | View/adjust the active-archived-frozen memory-tier thresholds, manual pin overrides |
| wiki-digest | `/kata:wiki-digest` | Weekly health check: activity, tier distribution, coverage gaps, cross-cluster synthesis, suggested next steps |
| wiki-query | `/kata:wiki-query <question>` | Answer with citations, report explicit confidence, file back as a page, fall back to external plugins on a local miss |
| wiki-lint | `/kata:wiki-lint` | Structural checks (orphans/broken links/frontmatter/staleness/tiers/dimension completeness) + content gaps + SCHEMA.md evolution proposals |
| wiki-config | `/kata:wiki-config` | Unified read/write for SCHEMA.md — `--show`/`--get`/`--set`/`--explain`/`--validate`, operating by path |
| wiki-dream | `/kata:wiki-dream` | auto-dreaming: re-evaluates frozen/archived pages, suggests reviving ones whose relevance has resurfaced, filesystem-only |
| wiki-watch | `/kata:wiki-watch` | Watches `raw/` for new files and queues them; only draining actually ingests — it never invokes `wiki-ingest` itself |
| wiki-sync | `/kata:wiki-sync` | Multi-machine git sync: custom merge driver for log.md + local lock + force-push detection + wiki_id identity check |
| wiki-spec | `/kata:wiki-spec preflight <path>` | Before drafting a new spec, scans for related prior specs so the author can declare relationships — keeps the spec corpus from fighting itself |
| wiki-session-ingest | `/kata:wiki-session-ingest` | Pulls the insights out of the current AI CLI session and distills them into the wiki (incremental — only new messages since the last capture) |
| wiki-mcp-server | `/kata:wiki-mcp-server` | Runs this wiki as a read-only MCP server, so other MCP clients — or another kata doing federation — can query it |
| wiki-federate | `/kata:wiki-federate search <query>` | Cross-wiki federated query: read-only queries against the peer katas listed in `.federation.yaml`, results merged with provenance |
| wiki-skill-create | `/kata:wiki-skill-create` | Generates a project-local skill that wires kata's query/ingest into this project's actual code-edit/test/verify pipeline |

How these fit together day to day (four loops, not four standalone commands):

- **Daily loop** — drop a source in `raw/` → `wiki-ingest` → glance at `wiki-digest --since=1d`.
- **Question loop** — `wiki-search` (or `wiki-graph --neighbors`) to scope → `wiki-query` to answer;
  substantive answers file back automatically as `queries/*.md` and become new nodes in the graph.
- **Exploration loop** — `wiki-graph --shortest-path A,B` surfaces bridge concepts between two entities
  you didn't realize were connected.
- **Weekly loop** — `wiki-digest` for the overall state, `wiki-lint` for structure/content gaps and
  schema-evolution proposals.

## What it can't do / the real boundaries

This section isn't a disclaimer — every line below is either a boundary
that's already shipped and holds (a selling point), or an honest limitation.

**Boundaries that already hold:**

- **Federated queries are read-only across the boundary** — kata never writes
  to a peer wiki. `wiki-mcp-server` only exposes the read-only subset of
  `wiki-search` / `wiki-graph` / `wiki-spec-preflight` (candidates only,
  `--enforce` is never exposed); `wiki-ingest`, `wiki-import`,
  `wiki-tier --pin`, and `wiki-dream --apply` are never exposed over MCP.
- **`wiki-watch` never invokes `wiki-ingest` itself** (straight from the
  source comment) — draining is always an explicit human step, so a
  misconfigured watcher cannot silently mutate wiki pages.
- **External fallback plugins refuse `command_template:` and shell
  metacharacters** — since v1.4 only `argv:` token arrays are accepted, never
  through a shell; `auto_run` defaults to requiring human confirmation before
  it executes anything.
- **`wiki-sync` aborts the instant `wiki_id` doesn't match**, refuses to run
  while an import is in progress, and detects force-pushes (it never silently
  swallows a history rewrite).
- **Spec auto-propagation (Phase 3) is an opt-in preview, off by default** —
  because it still can't automatically reverse itself if the source spec is
  later edited to drop the supersession.

**Honest limitations (no gloss):**

- **Wiki-root resolution has no ceiling.** Whether it's walking up looking
  for an ancestor directory carrying `SCHEMA.md` + `log.md`, or looking for a
  `.llm-wiki.yaml` / `.kata.yaml` binding file, the implementation in
  `plugin/scripts/wiki_lib.py` is `for cur in (start, *start.parents)` — it
  walks all the way to the filesystem root, with no ceiling comparable to
  git's `GIT_CEILING_DIRECTORIES`. A binding file left in the wrong place
  will silently redirect a deeply nested project to a different wiki. This
  is **not a bug but depended-on behavior** — the nested-override pattern
  under "Multiple wikis on one machine" relies on exactly this to find a
  monorepo-root binding from an arbitrarily deep subdirectory, so this round
  didn't add a ceiling, and only logged it in
  [`docs/ISSUE-project-binding-unbounded-ancestor-walk.md`](docs/ISSUE-project-binding-unbounded-ancestor-walk.md).
  The cost is real: kata's own test suite couldn't finish on any machine with
  kata installed (before v2.16.0) because of exactly this, and the fix was to
  move the test fixture out of the project's ancestor chain rather than put
  a ceiling on the resolver.
- **Dogfood retrospectives have never been backfilled.** The retrospective,
  cumulative-metrics, and GA-decision sections in `docs/dogfood-v1.6.md` /
  `docs/dogfood-v1.8.md` are still unfilled template placeholders, from v1.6
  all the way through v2.15.5. There's a dogfood record, but don't read it as
  a GA conclusion.

## Core concepts

### The layered model

| Layer | What it is |
|---|---|
| **Base** | [Karpathy's LLM-Wiki concept](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — compiled once, kept current; humans curate, LLMs maintain; everything optional and modular. |
| **Core** | A **self-evolving knowledge system** built on the base: (1) a self-closing loop — ingest → cross-link → filed-query → compounding pages; (2) auto-dreaming — frozen pages resurface when their relevance returns. |
| **Phase 1** *(current)* | **AI-paired engineering.** Use the core wiki to compile project business semantics — thresholds, lifecycle invariants, domain conventions — so AI agents read project conventions before they write code. v1.4 → v1.13 ship this reach. |
| **Phase 1+** *(shipped)* | **Spec History Management (v1.13)** and **Work-Loop Bridge (v1.15)** — see "Wiring it into your workflow" below. |
| **Phase 2** *(designed, not yet implemented)* | **Team spec authoring + dispute resolution.** So future decisions don't re-litigate a fight that already happened. |
| **Phase 3+** | Open. The core keeps extending its boundary as we learn what compounds. |

The **product** is the Core plus each Phase's reach; Phase 1 is only the
first concrete boundary, not kata's definition.

### SCHEMA.md is the sole authoritative config

All conventions — page types, frontmatter fields, tag taxonomy, page
creation policy, cross-reference policy, page size limits, log rotation,
**custom dimensions**, and **memory-tier thresholds** — live in
`{wiki_path}/SCHEMA.md`. The plugin reads and enforces SCHEMA.md rather than
hardcoding opinions into the code.

```text
{wiki_path}/
├── SCHEMA.md          # conventions + dimensions + tier policy (user-editable)
├── index.md           # content catalog, one-line summaries
├── log.md             # append-only action log
├── raw/                # immutable source material (articles/papers/transcripts/assets/imported/external)
└── {categories}/       # defined by SCHEMA.md, fits your domain
                        # Research: entities/ concepts/ comparisons/ queries/
                        # Business: people/ projects/ decisions/ meetings/
```

`wiki-config` is its general-purpose read/write interface (`show`/
`get --path`/`set --path --value`/`explain --path`/`validate`), doing only
surgical replacement of existing scalar keys with automatic rollback on
schema-validation failure; adding a new key or a new YAML block still
requires hand-editing SCHEMA.md or rerunning `wiki-init`. `wiki-tier` and
`wiki-init` still keep their own domain-specific shortcuts —
`wiki-config` covers the long tail.

### Memory tiers (active / archived / frozen)

Raw content ages. The wiki distinguishes three tiers to keep queries
focused:

| Tier | Default window | Behavior |
|------|---------------|----------|
| **active** | < 1 year | Default query surface — all skills return active-tier results |
| **archived** | 1–2 years | Accessible via `--tier=archived` or `--tier=all` |
| **frozen** | > 2 years | Cold storage — auto-dreaming revisits it periodically |

Tiers are computed **on the fly** from `published_at` (fallback
`ingested_at`) — never stored in frontmatter, so threshold changes take
effect instantly. A page's tier is the most-recent tier across the sources
it cites. Manual `tier_override:` pins are supported.

```bash
/kata:wiki-tier --show
/kata:wiki-tier --preview --set-active=540d
/kata:wiki-tier --pin=concepts/attention.md:active
```

### Custom frontmatter dimensions

SCHEMA.md's `custom_dimensions:` block lets you declare domain-specific
frontmatter fields — `version:` for software, `venue:` for research papers.
Each dimension has a type, a description, and a `refresh_on` schedule that
controls when the agent prompts you for the value:

```yaml
custom_dimensions:
  - name: version
    type: string
    required: true
    refresh_on: [ingest, import]
```

`wiki-ingest`/`wiki-import` prompt per the `refresh_on` schedule
(`--set key=value` skips the prompt); `wiki-digest` surfaces stale values;
`wiki-lint` validates completeness and enum range; `wiki-graph --query` /
Obsidian Dataview query them like any other frontmatter.

### Auto-dreaming: what the wiki does while you sleep

Frozen content doesn't have to stay frozen forever — an acquired company, a
revived architecture, a classic paper being cited again. `wiki-dream` runs
on a cadence (weekly, or whatever rhythm you set), reading only `log.md` +
page frontmatter dates (`ingested_at`/`updated`) — **never** file mtimes or
chat sessions — so `git clone` onto any machine reproduces the same dreamer
behavior. v1.6 ships the `co-occurrence` strategy, gated in CI at
precision ≥ 0.7 / recall ≥ 0.5. Other strategies (citational/structural/
temporal) are left to v1.8+. There's a dogfood record at
`docs/dogfood-v1.6.md`, but its retrospective section has never been
backfilled — see "What it can't do" above.

```bash
/kata:wiki-dream                          # lands in dreaming/{date}.md
/kata:wiki-dream --apply --pages 1,3,5    # revive selected candidates
```

### External fallback plugins

When `wiki-query` can't find a local answer, it can call an external tool
registered in `.wiki-plugins.yaml`:

```yaml
plugins:
  - name: deepwiki-cli
    trigger: on_empty
    auto_run: false          # shows argv and asks for confirmation by default
    argv: ["deepwiki-cli", "search", "--repo={repo_path}", "--query={query}"]
```

Flow: query miss → plugin command → stdout saved to `raw/external/` →
`wiki-ingest` processes it → wiki pages grow → future queries hit local
first. Full manifest spec: see [`plugin/PLUGINS.md`](plugin/PLUGINS.md).

### Design lineage: what this project adds on top of Karpathy

| Extension | What it adds |
|-----------|---------------|
| **SCHEMA.md as authoritative config** | All conventions in one file; the agent reads and enforces it instead of hardcoding opinions |
| **Interactive domain-specific init** | `wiki-init` proposes categories per domain (research/book/business/personal) |
| **Bulk import** (`wiki-import`) | 5-phase migration from Obsidian/Notion/Confluence/folders, checkpoint/resume |
| **Structured graph queries** (`wiki-graph`) | Frontmatter filters, BFS neighbors, shortest-path, hubs/orphans — no persistent graph DB |
| **Three-tier memory aging** | active/archived/frozen, computed on the fly from source dates |
| **External fallback plugins** | Any CLI tool registered as a `wiki-query` fallback, through a closed-loop ingest |
| **Multi-format query output** | markdown / table / slides (Marp) / chart (matplotlib) / canvas (Obsidian) |

Deliberately not done: a **persistent graph database** (the filesystem is
the graph; scanning a few hundred pages takes milliseconds); **auto-pruning
of frozen content** (frozen = parked, not deleted); **embedding-based
semantic search** (deferred to qmd; the built-in 3-pass scan covers
Karpathy's ~100-source sweet spot); **multi-user access control** (the wiki
is just a git repo — use branches and PRs to collaborate).

## Wiring it into your workflow

kata's documentation loop (ingest → cross-link → query → file-back) closes
on its own, but three extensions each address a different "what's still
missing outside the loop" problem.

### Don't let insights rot in the chat log (wiki-session-ingest)

After two hours of debugging, the stuff actually worth keeping — the real
root cause, the rejected alternatives, the decision boundary — is all
sitting in the session transcript, and by the time you remember to write any
of it down, half of it is already gone. `wiki-session-ingest` reads the
current session, ranks candidate knowledge points by confidence, lets you
multi-select the keepers, and distills each one through the standard
`wiki-ingest` pipeline.

```bash
/kata:wiki-session-ingest          # incremental: only new messages since the last capture (v2.14.0+)
/kata:wiki-session-ingest --full   # force a fresh sweep from message #1
```

Works with Claude Code / Codex CLI (automatic JSONL transcript adapters) as
well as Gemini / Copilot / OpenCode / Kimi and any other CLI (LLM-dump
fallback). The raw session dump is markdown living in the wiki repo — it
travels with `wiki-sync` — so eyeball it before syncing if the session
touched any secrets.

### Keep your spec corpus from drifting (wiki-spec)

Six months into spec-driven development, nobody can say which spec is
canonical for a given area anymore, new specs quietly overlap with old ones,
and specs that should have been archived are still being cited. `wiki-spec`
adds two checkpoints to the ingest flow:

```bash
/kata:wiki-spec preflight raw/new-spec.md   # Phase 0: scan for related prior specs, advisory
/kata:wiki-ingest raw/new-spec.md           # auto-runs preflight + Phase 2 enforcement
```

The author declares relationships in the new spec's frontmatter with a fixed
vocabulary — `supersedes`/`refines`/`extends`/`parallel`/`contradicts` — and
those relationships enter the queryable graph; `wiki-graph --mode
spec-history` renders the lineage as an ASCII tree/JSON/Mermaid graph.
**Phase 3 (auto-propagation) is an opt-in preview, off by default** — see
"What it can't do" above. Cross-wiki spec relationships can point at a
federation peer via `kata://<peer>/<path>` (see the next section).

### Wire kata into your actual code pipeline (wiki-skill-create)

kata's documentation loop closes on its own, but the **actual work** —
searching source, editing code, running tests, verifying the fix — happens
outside that loop, and whether to bring kata's knowledge back into it is
entirely up to individual discipline. `wiki-skill-create` generates a
**project-local skill** that welds kata's query/ingest onto this project's
real work pipeline:

```bash
/kata:wiki-skill-create
```

Four MVP patterns — pick whichever matches how work actually shapes up in
your project:

| Pattern | Encoded loop |
|---|---|
| `issue-fix` | Problem → kata query → source search → minimal edit → test → human verify → wiki-ingest |
| `feature-build` | Requirement → kata query → spec draft → `wiki-spec preflight` → implement → verify → file back learnings from both spec and implementation |
| `bug-debug` | Bug → reproduce → kata search (by symptom and by mechanism) → root cause → fix + regression test → file back a root-cause-first lesson |
| `custom` | Describe your own loop → kata wraps it with query / human-gate / file-back bookends |

**Where to look for supplementary information (v2.15.1).** When a project
workflow hits a question kata's local wiki can't answer,
`--supplement-action <source-search|web-search|doc-lookup|custom>` decides
where to look next: `source-search` searches the project's source code,
`web-search` searches the web, `doc-lookup` searches the project's docs,
`custom` requires `--var` to pass `CUSTOM_SUPPLEMENT_*` variables for its own
behavior. If you don't pass one, `suggested_supplement_action` heuristics
pick a default — detecting a programming-language stack suggests
`source-search`, a `docs/` directory suggests `doc-lookup`, a pure-markdown
project suggests `web-search`; if none of those match, nothing is
suggested and the user picks. This step lands at a different point in each
of the four patterns — the orchestrator calls it **Phase 2.5**: step 3 in
`issue-fix`, step 3.5 in `bug-debug`, step 2.5 in `feature-build` and
`custom` — usually wedged right after the kata query and right before
actually touching code.

The generated SKILL.md lands at `<project>/.claude/skills/<name>/SKILL.md`
(`--target codex` writes it to `~/.codex/skills/` instead), with the
auto-detected tech stack (npm/cargo/pytest/go test, etc.) and project name
baked into its 7-step loop. After rendering it runs **9 static checks**
(frontmatter parses, required fields present, name format, frontmatter
≤ 1024 chars, description starts with "Use when", third person, sentinel
comment present, no unresolved `{{VAR}}`, `argument-hint` present when
user-invocable) — a failed check doesn't auto-fix itself; the user sees
what's wrong and decides whether to regenerate.

## Multi-machine and cross-wiki

### One wiki, multiple machines (wiki-sync)

v1.8 added `wiki-sync`: a custom merge driver for `log.md` (union+sort, with
canonical-hash dedup), a local sync lock, force-push detection (comparing
`origin/<branch>` SHA ancestry before and after fetch), wiki identity
verification (`wiki_id` UUID mismatch aborts immediately), and per-machine
sync reports living outside the wiki repo (`~/.kata/sync-reports/`, so they
never self-conflict).

```bash
/kata:wiki-init --path ~/.llm-wiki/myproject --enable-sync
cd ~/.llm-wiki/myproject && git init -b main && git add . && git commit -m "wiki: init"
git remote add origin git@github.com:you/myproject-wiki.git && git push -u origin main

# second machine
git clone git@github.com:you/myproject-wiki.git ~/.llm-wiki/myproject

/kata:wiki-sync              # interactive: lock + driver + fetch + merge + push
/kata:wiki-sync --dry-run    # preview, no side effects
```

Design process: see [`docs/PRD-v1.8-sync.md`](docs/PRD-v1.8-sync.md) (v1
draft + v2–v7, six cross-LLM review rounds, 42 findings converged, MVP-ready
as of 2026-05-07). `dreaming/` still has no merge driver — if both machines
run `wiki-dream` on the same day you'll get a normal git conflict; avoid it
by only running the dream cron on one machine.

### Multiple wikis on one machine

```
~/.llm-wiki/
├── common/     # default catch-all
├── necall/     # project A
└── research/   # project B
```

Path resolution priority (highest to lowest): explicit `--path`/`--wiki` →
the `WIKI_PATH` env var → the current directory already sitting inside a
wiki root → `LLM_WIKI_PROJECT` → the nearest `.llm-wiki.yaml`/`.kata.yaml`
binding file walking up from the project root → the global
`~/.llm-wiki/registry.yaml` → git repo name fallback → legacy config →
`~/.llm-wiki/common`.

`.llm-wiki.yaml` is a **single-path cache** — one file binds exactly one
wiki root; writing multiple `wiki_path:` lines doesn't work, only the last
one is honored. To host several wikis side by side, use one of two
patterns: a `.llm-wiki.yaml` per project repo (in a monorepo-with-submodule
setup, the binding closer to cwd wins), or a single global
`~/.llm-wiki/registry.yaml`. `.llm-wiki.yaml` is per-machine local state — it
belongs in `.gitignore`; the same goes for `registry.yaml`, kept outside the
repo.

**This resolution chain has no ceiling** — see "What it can't do" above.

### Read-only cross-wiki federated query (federation)

v1.12 lets kata act as both an MCP server (`wiki-mcp-server`) and an MCP
client that queries other katas (`wiki-federate`). Each wiki declares its
peers at its own root:

```yaml
# {wiki_path}/.federation.yaml
peers:
  - name: necallkit
    wiki_id: 7b52f6df-d7cf-47ab-b980-6042cf3a675c
    endpoint: stdio
    command: ["py", "-3", "path/to/kata/plugin/scripts/mcp_server.py", "--wiki", "~/.llm-wiki/NECallKit"]
    enabled: true
    timeout_seconds: 5
```

```bash
/kata:wiki-federate search "F011 merge-back"   # runs locally first, then fans out to enabled peers in parallel
/kata:wiki-federate peers                       # list registered peers
/kata:wiki-federate resolve "kata://necallkit/decisions/F011.md"
```

Results are cited as `kata://<peer-name-or-wiki_id>/<path>` URIs — use the
name form day to day (readable), and the wiki_id form for long-lived
cross-machine references (e.g. inside `spec_relationships:`, since it
survives a peer rename). Safety boundary: **read-only across the
boundary** — a peer's MCP server only exposes the read-only subset of
`wiki-search`/`wiki-graph`/`wiki-spec-preflight`; no write skill is ever
exposed across federation. **Every connection is identity-checked** — if
the `wiki_id` a peer reports doesn't match what's registered in
`.federation.yaml`, that peer is rejected. **No transitive resolution** — if
A references B and B references C, A won't automatically follow through to
C; an unreachable/timed-out/mismatched peer never fails the local query, it
only shows up in the result's `federation` diagnostics block. Query content
is sent to every peer as-is — use `--no-federate` for sensitive queries.

## Reference

**Works with:** Claude Code (`.claude-plugin/`), Codex CLI (generated
skills), any LLM (`SKILL.md` as a system prompt), GitHub Copilot CLI
(root-level `plugin.json`), Obsidian (the wiki is just a vault:
`[[wikilinks]]`, Graph view, Dataview queries over frontmatter, Web Clipper
into `raw/articles/`, Marp rendering `wiki-query --format=slides`). The
wiki is a git repo by default — `wiki-init`'s last step suggests
`git init`.

**Scaling:** < 100 pages — the built-in `wiki-search`; 100–500 pages — run
`wiki-lint` often to keep `index.md` fresh; 500–2000 pages — install
[qmd](https://github.com/tobi/qmd) (BM25 + vector hybrid with LLM re-rank;
`wiki-search` auto-detects it and shells out); 2000+ pages — qmd's MCP
server mode.

**Docs index:**

- [`docs/PRD-v1.8-sync.md`](docs/PRD-v1.8-sync.md) — multi-machine sync design
- [`docs/PRD-v1.12-cross-wiki-federation.md`](docs/PRD-v1.12-cross-wiki-federation.md) — federation design
- [`docs/PRD-v1.13-spec-history-management.md`](docs/PRD-v1.13-spec-history-management.md),
  [`docs/PRD-v1.14-spec-propagation-reconcile.md`](docs/PRD-v1.14-spec-propagation-reconcile.md) — spec history management
- [`docs/PRD-v1.15-work-loop-bridge.md`](docs/PRD-v1.15-work-loop-bridge.md) — work-loop bridge
- [`docs/dreaming.md`](docs/dreaming.md), [`docs/watcher.md`](docs/watcher.md) — auto-dreaming / watcher design
- [`plugin/PLUGINS.md`](plugin/PLUGINS.md) — external fallback plugin manifest format
- Every skill's full behavior is defined by its own `plugin/skills/<name>/SKILL.md` — this README only covers positioning and common usage

**Contributing:**

```bash
git config --local core.hooksPath .githooks   # enable the pre-commit smoke test
python tests/run_smoke.py                      # run it manually, matches CI
python scripts/build_skill_md.py               # regenerate the SKILL.md summary table after adding a skill
```

## Origin

Concept by [Andrej Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
(May 2025). Plugin design pattern from [SpecTeam](https://github.com/litianyi-007/SpecTeam).

This plugin's goal is a **faithful, opinionated implementation** of
Karpathy's intentionally-open concept. Where the original says "everything
mentioned above is optional and modular," we made concrete choices
(SCHEMA.md as the single config, interactive domain-specific init,
three-tier memory aging) while keeping the core invariants: the filesystem
is the only source of truth, `raw/` is immutable, humans curate / AI
maintains, and knowledge compiles once and then compounds.

License: MIT. See [LICENSE](LICENSE).
