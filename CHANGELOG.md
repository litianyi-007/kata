# Changelog

All notable changes to Kata (previously `ak-wiki` — see v2.0.0 below) are
recorded here. The plugin follows [semver](https://semver.org/) — major
bumps signal a manifest or skill-API change.

## [2.7.0] — 2026-05-18 — v1.11 session-ingest MVP (Phase 1-5)

**The conversation-born knowledge channel.** Until v2.7.0 kata could
only ingest artifacts (URLs, files, pasted text). The reasoning trail
in a 2-hour debugging session — what was tried, what was rejected, why
the chosen fix won — was never captured unless the user remembered to
write it down. v1.11 closes that gap.

### Added

- **`wiki-session-ingest` skill** (`plugin/skills/wiki-session-ingest/SKILL.md`)
  - One user-facing entry point that works from inside any of six
    target CLIs without extra arguments
  - Five phases: detect CLI → write raw dump → extract knowledge-point
    candidates → multi-select → distill via `wiki-ingest`
  - Multi-select UX via AskUserQuestion (Claude Code native) +
    numbered-prompt fallback for terminal-only CLIs
  - Provenance: every distilled page carries `source_cli`,
    `session_id`, `cwd`, plus `evidence_anchors` pointing back into the
    raw dump via `session-msg-N` ids
  - Integration with `wiki-ingest` via the v2.6.0 hint flags
    (`--page-type`, `--proposed-path`, `--evidence-anchors`) — single
    source of truth for page-write; no duplicate ingest path

- **`plugin/scripts/session_ingest.py`** helper (~600 lines, stdlib-only)
  - **`detect`** subcommand — probes `$CLAUDECODE`, `$CODEX_SESSION_ID`,
    `~/.codex/sessions/{YYYY}/{MM}/{DD}/` rollouts (cwd-match against
    `session_meta.payload.cwd`), `$GEMINI_CLI` / `$COPILOT_CLI` /
    `$OPENCODE` / `$KIMI_CLI` sentinels, falls back to `unknown` +
    LLM-dump mode. Returns JSON with `cli`, `detection_mode`,
    `session_id`, `session_file`.
  - **`dump`** subcommand — parses Claude Code or Codex CLI JSONL into
    readable markdown body (filters decorative events, renders tool
    calls + outputs with head/tail truncation), wraps with frontmatter,
    writes to `{wiki}/raw/sessions/{cli}-{date}-{slug}-{short-id}.md`.
  - **`dump-llm`** subcommand — agent provides body via `--body` or
    stdin; script wraps with frontmatter for Gemini / Copilot /
    OpenCode / Kimi / unknown paths.
  - **`config show|get|set`** subcommands — reads/writes
    `~/.kata/session-ingest.yaml` (the per-machine
    `auto_trigger_on_session_end` flag, default false).
  - **Safety**: 50 MB session-size cap (exit code 2 + hint to narrow
    scope), read-only on `~/.claude/projects/` and
    `~/.codex/sessions/`, dirty-wiki guard documented in SKILL.

- **Decision tree CLI detection** (PRD §CLI detection):
  - Tier 1: `$CLAUDECODE == "1"` → Claude Code, JSONL adapter
  - Tier 2: `$CODEX_SESSION_ID` set OR rollout under
    `~/.codex/sessions/.../*` whose first-line
    `session_meta.payload.cwd` matches cwd → Codex CLI, JSONL adapter
    (cwd normalization handles Windows backslash + case)
  - Tier 3-6: `$GEMINI_CLI` / `$COPILOT_CLI` / `$OPENCODE` /
    `$KIMI_CLI` → LLM-dump mode
  - Tier 7: unknown → LLM-dump fallback; agent renders the body

- **Auto-trigger opt-in** at `~/.kata/session-ingest.yaml`
  (`auto_trigger_on_session_end: false` by default). Documented hook
  wiring for Claude Code's `Stop` hook + Codex equivalent; MVP does
  NOT auto-install (one-command install is a v1.12 polish). Even with
  the flag on, the multi-select step still runs — no silent writes.

- **Tests 23, 24, 25** in `tests/run_smoke.py`:
  - **Test 23**: Claude Code end-to-end — synthetic JSONL fixture with
    user/assistant/tool/decorative events; HOME-overridden detect
    finds the slug-of-cwd project dir; dump parses 4 messages, filters
    `file-history-snapshot`, preserves conclusion text and message
    anchors
  - **Test 24**: Codex CLI cwd-match — synthetic rollout with
    `session_meta.payload.cwd` matching fixture cwd; detect finds it
    via the cwd-match heuristic (CLAUDECODE explicitly unset in env
    overrides to prevent leak from parent Claude Code process); dump
    parses user/assistant/tool events
  - **Test 25**: LLM-dump path — agent-supplied body via `--body`
    wrapped with frontmatter; `~/.kata/session-ingest.yaml`
    show/set/get roundtrip on a tempdir HOME

### Changed

- Root `SKILL.md` frontmatter: "14 skills" → "15 skills (… spec /
  session-ingest)"; description mentions v1.11 MVP shipped + Claude
  Code + Codex adapters + LLM-dump fallback
- Plugin manifest + marketplace.json bumped 2.6.0 → 2.7.0

### Deferred to v1.12

- Sentinel-env detection for Gemini / Copilot / OpenCode / Kimi
  (LLM-dump remains the safe default until each is verified inside the
  respective CLI)
- Auto-wired CLI hooks (one-command install of Stop hook etc.) — MVP
  only documents the wiring per CLI
- Bulk historical session ingest (`--since=2026-05-01`)
- Cross-CLI session merge (two CLIs working on the same task)
- Token-budget-aware AI summarization for >200k-token sessions
- `--scrub-secrets` flag to redact API-key-shaped tokens before the
  raw dump is committed
- Interactive editing of a candidate before distilling (title /
  page_type / proposed_path tweak)

### Migration

None required. The new skill is purely additive; existing
`wiki-ingest` flows are unaffected. To opt in to auto-trigger:

```bash
py -3 plugin/scripts/session_ingest.py config set \
    auto_trigger_on_session_end true
```

Then wire a Claude Code `Stop` hook per the SKILL.md example, or the
Codex CLI equivalent.

---

## [2.6.0] — 2026-05-17 — v1.11 session-ingest Phase 0 (wiki-ingest hint flags)

**Companion change** to unblock v1.11 `wiki-session-ingest` (Phase 1-5
shipping in v2.7.0). Three strictly-additive optional flags on the
`wiki-ingest` skill let an upstream caller hand off structured hints
rather than re-deriving them.

### Added

- **`--page-type=<type>`** — strong default for new-page type
  (`decision` / `feature` / `bug` / `lesson` / `concept` / `prd` /
  `rfc` / `adr` / `task-spec` / etc; must be SCHEMA.md-declared). Agent
  follows the hint unless SCHEMA.md analysis reveals a clear mismatch,
  in which case it overrides and notes the override in the report.
- **`--proposed-path=<wiki-relative>`** — preferred destination path
  for the new page. Treated as a hint, not a command:
  - Free path → used as-is
  - Existing page → standard "create vs update" policy applies
    (default: update with diff preview)
  - SCHEMA.md category conflict → fall back to inference, note override
- **`--evidence-anchors=<comma-separated>`** — opaque tokens preserved
  verbatim in the new page's frontmatter under `evidence_anchors:`.
  Typical: `session-msg-142,session-msg-167` from v1.11
  session-ingest. Field omitted entirely when flag unset.

All three flags are documented in `plugin/skills/wiki-ingest/SKILL.md`
under new sub-step **④b** (between page-write and cross-reference).
Existing `wiki-ingest <url|file|text>` invocation shape is unchanged;
all hints are optional.

### Why

v1.11 `wiki-session-ingest` (Draft v2 locked PRD) needs to invoke
`wiki-ingest` per knowledge-point candidate during its Phase 5 distill
loop, with structured hints so each candidate lands at the right path
under the right type with provenance anchors preserved. Without Phase 0,
`wiki-session-ingest` would have to either re-implement page-write logic
(violating single-source-of-truth) or hand off without structured hints
(losing precision).

### Migration

None required. All three flags are additive; existing wiki-ingest flows
are unaffected.

---

## [2.5.0] — 2026-05-17 — v1.13 SHM Phase 1 removed (external_sources)

**Removes a feature shipped in v2.3.0 the previous day** because the
abstraction broke kata's self-closing principle. v2.4.0 Phase 2
enforcement stays — it's purely kata-internal and unaffected.

### Removed

- `external_sources` array from `schema/wiki-schema.json` + the
  `$defs/external_source` definition
- `_load_external_sources()` / `_enumerate_external_pages()` helpers
  from `plugin/scripts/spec_preflight.py`
- CLI flags `--no-external` and `--include-frozen-external`
- External-candidate scoring loop in `spec_preflight.main()`
- `external://<source>/<path>` URI normalization branch in
  `_candidate_match_keys()` (Phase 2 was kata-internal; URI branch
  was a leftover from Phase 1)
- Output fields `external_sources_scanned`, `external_skipped`,
  `tier_breakdown.external`, and the per-candidate `source` /
  `source_treatment` / `writeable` / `fs_path` fields
- `tests/run_smoke.py` Test 21 (Phase 1 end-to-end fixture)
- `plugin/skills/wiki-spec/SKILL.md` Phase 1 documentation,
  external-source configuration table, and Phase 1 output sample

### Why

Three reasons compounding:

1. **`wiki-import` already covers human-curated bulk ingest**. A team
   with a legacy SDD spec corpus can run
   `wiki-import <corpus> --priority=recency --per-file-prompt` and get
   exactly the curated import external_sources was trying to avoid. The
   "avoid bulk-import" framing was solving a non-problem.
2. **Authority + self-closing violation**. `external_sources` reached
   outside `{wiki_path}/` to enumerate, score, and surface third-party
   markdown files. That breaks the kata invariant that the wiki is a
   compiled artifact under one root. To make it work we'd have had to
   invent an entire lifecycle (transit → graduation → blocklist → TTL)
   — and the fact that we needed to invent a lifecycle to make the
   abstraction behave is itself a sign the abstraction was wrong.
3. **Federation is the right architecture for cross-source**. Two
   self-closing kata wikis cooperating at the `wiki-query` ↔
   `wiki-query` layer (planned for v1.12) preserves both sides'
   authority. Reaching into raw markdown dirs does not.

Empirical motivation: a NECallKit test (363 historical specs/docs)
returned `page_count: 0` for both external sources, because 95%+ of the
legacy corpus had no YAML frontmatter — and a path-pattern type
inference patch to fix it would have been a sunk-cost workaround for an
abstraction that needed removal, not extension. Full architectural
reasoning in
`~/.llm-wiki/kata/decisions/2026-05-17-external-sources-removed.md`
(kata self-meta wiki ADR, also intended as essay seed material).

### Migration

- Wikis that adopted `external_sources` in v2.3.0 (window: 2026-05-16 →
  2026-05-17, very few users): remove the `external_sources:` block
  from `.wiki-plugins.yaml`. If the historical corpus is still needed,
  run `wiki-import <corpus_path>` instead — it produces real kata pages
  with proper frontmatter, full graph participation, and tier lifecycle.
- v2.4.0 Phase 2 enforcement (`--enforce`, `enforce_relationship_declaration`,
  threshold + mode CLI) is unchanged.
- v2.2.0 Phase 0 advisory preflight is unchanged.

### Validation

All 21 smoke tests pass after Test 21 removal (the deleted test was the
only one that exercised external_sources). Pre-commit hook clean.

---

## [2.4.0] — 2026-05-16 — v1.13 SHM Phase 2: relationship declaration enforcement

**Closes the loop** the v1.13 problem statement called out: until Phase 2,
preflight surfaced related prior specs but the author was free to ignore
them. With Phase 2, a wiki opting in via SCHEMA.md gets an ingest-time
gate that rejects new specs whose `spec_relationships:` block does not
address every above-threshold preflight candidate. This is the
spec-drift fix that motivated v1.13.

### New

- **`spec_preflight.py --enforce` flag** — parses the new spec's
  `spec_relationships:` block from frontmatter, compares declared
  targets against the full (unbounded by `--limit`) ranked candidate
  list, and rejects on uncovered above-threshold candidates.
- **`--enforce-threshold <float>`** — per-invocation override of the
  schema's `enforcement_score_threshold`. Useful for tighter or looser
  one-shot runs without editing SCHEMA.md.
- **`--enforce-mode strict|confirm`** — per-invocation override of the
  schema's `enforcement_mode`. strict → exit code 2 on uncovered;
  confirm → exit code 1 so the caller can prompt the user before
  rejecting.
- **Target normalization** — declared targets accept any of:
  - Wiki-relative path: `decisions/F100-foo.md`
  - Path without `.md`: `decisions/F100-foo`
  - Bare stem: `F100-foo`
  - Wikilink form: `[[F100-foo]]` or `[[F100-foo|display alias]]`
  - External URI: `external://sdd-specs/F011-bar.md`
  Match is case-insensitive on both full key and bare stem.
- **`enforcement` block in JSON output** — when enforcement is active:
  - `enabled`, `mode`, `threshold`
  - `declared_relationships` (kind, target, note for each)
  - `declared_count`, `above_threshold_count`, `covered_count`,
    `uncovered_count`
  - `uncovered`: array of {path, title, type, tier, score} for each
    above-threshold candidate not covered by declarations
  - `decision`: `accept` or `reject`
- **Schema additions** in `spec_authoring`:
  - `enforcement_score_threshold: 5.0` (default; tune per-wiki)
  - `enforcement_mode: strict` (default; `confirm` opt-in)
  - existing `enforce_relationship_declaration: false` remains the
    master toggle
- **`wiki-ingest` SKILL** — step ②b documents the Phase 2 gate: when
  `enforce_relationship_declaration: true`, re-run preflight with
  `--enforce` after the author has had a chance to add declarations;
  abort ingest on exit code 2 / 1 with the structured `enforcement`
  report.

### Changed

- **`wiki-spec` SKILL** — Phase scope updated (Phase 0+1+2 → scan +
  advisory + enforcement); CLI examples include the new flags; the
  Known-limitations section now flags Phase 3+ (auto-propagation,
  lineage view) as the remaining work
- **Root `SKILL.md` frontmatter** — description: "Phase 0+1" → "Phase
  0+1+2 — wiki + external-source backfill + relationship-declaration
  enforcement on ingest"
- **`run_smoke.py` `run()` helper** — `allowed_exit_codes` parameter
  added (defaults to `{0, 1}`, backwards compatible). Test 22 passes
  `{0, 2}` to allow the strict-mode rejection path.

### Validation

`tests/run_smoke.py` Test 22 covers all five enforcement paths:
- Run 1: schema enables enforcement, no declarations → exit 2, decision
  `reject`, F100 surfaces in `uncovered`
- Run 2: add `spec_relationships: [{kind: supersedes, target:
  decisions/F100-payment-flow.md}]` → exit 0, decision `accept`,
  `covered_count: 1`, `uncovered_count: 0`
- Run 3: schema is strict, `--enforce-mode confirm` overrides → exit 1
  on reject (caller-prompts path)
- Run 4: `--enforce-threshold 999.0` raises bar above any candidate
  score → `above_threshold_count: 0`, decision `accept`
- Run 5: declaration uses `[[wikilink]]` form (stem only) → normalization
  matches it to the full-path candidate, decision `accept`

All 22 smoke tests pass on Windows + Linux + macOS.

### Migration

- Existing wikis with `spec_authoring.enabled: false` (default for new
  wikis): nothing changes.
- Existing wikis with Phase 0+1 enabled but no enforcement set: nothing
  changes. `spec_preflight` continues to run in advisory mode.
- To opt in: add to SCHEMA.md `spec_authoring:` block:
  ```yaml
  enforce_relationship_declaration: true
  enforcement_score_threshold: 5.0     # adjust after observing
  enforcement_mode: strict             # or confirm for caller-prompts
  ```
  Then run a manual preflight on a few existing specs to calibrate
  the threshold before turning the gate on for live ingest.

---

## [2.3.0] — 2026-05-16 — v1.13 SHM Phase 1: external source backfill

**Extends Phase 0** (v2.2.0) so a kata adoption in the middle of an
existing SDD-style project can scan a pre-existing spec corpus without
bulk-importing every old spec. The historical corpus stays on disk
where it is; kata enumerates it for preflight only.

### New

- **`.wiki-plugins.yaml` `external_sources:` array** — separate from
  v1.10's `external_plugins:` (which executes CLI tools for query
  fallback). Each `external_sources` entry has:
  - `name`: identifier for the URI scheme (`external://<name>/<path>`)
  - `type`: `directory` (Phase 1 only; future phases may add git-remote)
  - `root`: absolute or `~`-prefixed path to the directory
  - `treatment`: `active | raw | frozen` (default `raw`)
  - `description`: optional human-readable label
  - `discover.type_field`: frontmatter key holding the type (default
    `type`; override for corpora using `category` or `doc_type`)
  - `discover.exclude`: substring patterns to skip (e.g. `drafts/`)
- **Treatment semantics**:
  - `active` — participates in default wiki-search + spec preflight
  - `raw` — excluded from default search, included in spec preflight
    (the right choice for most historical-corpus adoptions)
  - `frozen` — excluded everywhere unless `--include-frozen-external`
- **URI scheme `external://<source>/<path>`** for cross-source
  references in `spec_relationships:` targets. Phase 3 auto-propagation
  will skip these (kata cannot edit external pages); Phase 3 will
  instead write a kata-internal reverse-index file.
- **`plugin/scripts/spec_preflight.py`** extended with:
  - `_load_external_sources(wiki_root)` — reads
    `.wiki-plugins.yaml`'s `external_sources` block
  - `_enumerate_external_pages(source, spec_types_set)` — walks the
    source's `root` directory, filters by frontmatter type, returns
    page records (path, uri, title, type, tags, body, source, treatment)
  - External-candidate scoring loop in `main()` (uses the same
    heuristics as kata-side: title overlap, tag overlap, wikilink
    reference, type match; sets `hub_score=0` and adds `-0.5`
    authority penalty for external)
- **CLI flags**: `--no-external` (skip external entirely),
  `--include-frozen-external` (also scan frozen-treatment sources).
- **JSON output additions**:
  - `external_sources_scanned`: per-source diagnostic
    (name, treatment, page_count, scored_count, elapsed_ms)
  - `external_skipped`: sources excluded by treatment filter
  - `tier_breakdown.external`: count of external candidates
  - `candidates[].source` / `source_treatment` / `writeable: false` /
    `fs_path` on external candidates only

### Changed

- `wiki-spec` skill argument-hint extended with `--no-external` +
  `--include-frozen-external`
- `wiki-spec` SKILL.md Phase scope updated (Phase 0+1 → advisory;
  Phase 2 → enforcement; Phase 3 → auto-propagation)
- Root `SKILL.md` frontmatter description: "Phase 0" → "Phase 0+1 —
  wiki + external-source backfill via .wiki-plugins.yaml"
- `schema/wiki-schema.json`: new top-level array `external_sources`
  + new `$defs/external_source` definition

### Validation

`tests/run_smoke.py` Test 21 validates Phase 1 end-to-end:
- Builds fixture with 1 kata-managed spec + 2 external specs (and 1
  non-spec README that should be filtered out)
- Configures `.wiki-plugins.yaml` with `external_sources` entry,
  `treatment: raw`
- Runs preflight against a new draft that link-references the F011
  external spec and shares tags with both
- Asserts: phase=1, `external_sources_scanned` populated correctly,
  F011 surfaces as external candidate with `writeable: false`, URI
  scheme `external://sdd-specs/...`, signals correct
- Asserts: `--no-external` suppresses external enumeration entirely

### Migration

`external_sources` is additive. Existing `external_plugins` (v1.10
query-fallback CLI tools) continue to work unchanged — they're a
different array. Wikis without `external_sources` block behave
exactly as v2.2.0.

To enable Phase 1 backfill of a historical corpus:

```yaml
# In wiki's .wiki-plugins.yaml
external_sources:
  - name: legacy-specs
    type: directory
    root: ~/work/myproject/docs/specs
    treatment: raw
```

Then `wiki-spec preflight --new-spec <draft>` will surface candidates
from both the kata wiki AND the legacy directory.

## [2.2.0] — 2026-05-16 — v1.13 SHM (Spec History Management) Phase 0

**New optional skill: `wiki-spec`**. First phase of a multi-phase feature
that closes the spec-drift gap in SDD / superpowers-style workflows.
Phase 0 ships an advisory-only preflight scan; Phase 1+ extends to
external sources, enforces relationship declaration, and auto-propagates
supersession across the wiki. Off by default; opt-in per wiki via
`spec_authoring.enabled: true` in SCHEMA.md.

### Motivation

LLM-driven SDD / superpowers flows generate many specs over time. Each new
spec is authored fresh, often by a different session/agent, with no
mechanism that makes the new spec "answer for" the older specs whose scope
it overlaps. Result: spec corpora drift from "coherent decision record"
into "pile of disconnected pages". Kata's wedge has always been project
memory; spec history is a structured subset of that problem that needs
its own primitives.

### New

- **`plugin/scripts/spec_preflight.py`** — given a draft spec file (need
  not be in the wiki yet), scan wiki pages whose frontmatter `type` is in
  `spec_authoring.spec_types`, rank by relevance signals (title overlap,
  tag overlap, wikilink reference, hub score, type match), emit JSON.
  Default `spec_types` covers SDD-style (`prd`, `design`, `rfc`, `adr`,
  `task-spec`) and kata-native (`decisions`).
- **`plugin/skills/wiki-spec/SKILL.md`** — new skill exposing the
  `preflight` subcommand. Phase 0 surfaces candidates; the author / agent
  reads them and decides whether to declare relationships in the new
  spec's frontmatter. No enforcement yet.
- **`schema/wiki-schema.json`** — adds `spec_authoring` config block:
  `enabled`, `spec_types`, `preflight` (auto/manual/off),
  `relationship_kinds`, `enforce_relationship_declaration` (Phase 2
  toggle, off in Phase 0).
- **Convention** for per-spec frontmatter (Phase 0 manual, Phase 2
  enforced): `spec_relationships: [{kind, target, note}]` with kinds
  `supersedes | refines | extends | parallel | contradicts | references | custom`.

### Roadmap (subsequent phases, not in this release)

| Phase | Adds |
|---|---|
| 1 | Preflight reaches external sources via `.wiki-plugins.yaml` `treatment: raw\|frozen\|active` (supersedes v1.10 PRD) |
| 2 | Required `spec_relationships:` declaration; ingest rejects on missing |
| 3 | Auto-propagation: superseded specs get banner + tier flip + reverse-link; integrates with v1.6 dreamer reject-signal channel |
| 4 | `wiki-graph --spec-history <topic>` coherence view |

Forthcoming: `docs/PRD-v1.13-spec-history-management.md` (Day 3 of the
2026-05-16 cooldown roadmap will draft it formally; this CHANGELOG entry
is the minimum-viable design contract for now).

### Changed

- **Skill count**: 13 → 14 (Test 18 assert updated implicitly via `>= 13`).
- **Plugin manifest version**: 2.1.0 → 2.2.0 in both
  `.claude-plugin/marketplace.json` and `plugin/.claude-plugin/plugin.json`.

### Migration

No migration required. `spec_authoring` is opt-in:

```yaml
# In SCHEMA.md of any wiki that wants the feature:
spec_authoring:
  enabled: true
  spec_types: [decisions]   # narrow to your wiki's conventions
```

Wikis without this block continue to behave exactly as in v2.1.0.

### Validation

`tests/run_smoke.py` Test 20 validates Phase 0 end-to-end: builds a
fixture wiki with 2 prior decisions + 1 new draft spec, runs preflight,
verifies the link-referenced same-tagged candidate ranks first with the
correct signals (link_reference + type_match + tag_overlap ≥3) and that
advisory text is present.

## [2.1.0] — 2026-05-14 — wiki-search tier-aware ranking + coverage signal

**Backward-compatible additions** to `wiki-search`. No skill API changes,
no manifest changes. Pin behavior (`tier_override: active` in page
frontmatter) now actually surfaces pinned pages in top-N results.

### New

- **`tier_breakdown` field** in `search_naive.py` JSON envelope — aggregate
  tier distribution `{active, archived, frozen}` over the full unfiltered
  match set. Lets callers see coverage shape at a glance without scanning
  every result. Useful when a query has high archived hits but low active
  hits, signaling stale or mis-categorized content.
- **`low_active_coverage` hint** in `search_naive.py` JSON envelope — boolean,
  true when active hits < 20% of total matches and total matches ≥ 3. The
  threshold filters out tiny match sets to avoid false alarms.
- **`wiki-search` SKILL.md** documents how to use both new fields in
  summary lines and follow-up suggestions.

### Changed

- **Rank order** in `search_naive.py:rank_key` — `tier` is now a tiebreaker
  after `tag_match`, before `hub`. Active > archived > frozen. User-pinned
  pages bubble up above implicit hub centrality. Strong title/tag match
  still wins. Net effect on prior queries against a real wiki: pinned
  architecture pages went from absent in top-10 to top-1 / top-9 / top-10
  positions for the same query.
- **`_excerpt()`** in `search_naive.py` — strips H1/H2 heading lines
  before term-finding so excerpts contain body content instead of
  `"# Title  ## Section Header …"` noise. Falls back to original
  behavior if the query term appears only in headings.

### Motivation

Real dogfood session on 2026-05-14: an agent ran three wiki-search
queries and got 28/30 archived results. The agent correctly self-reported
the surface signal but had to scan all results to detect the pattern.
Investigating the cause revealed two design errors:

1. Tier semantics designed for research wikis (where archived = stale)
   mis-fired for architecture wikis (where archived = stable but
   unmaintained). Fix: per-page `tier_override:` was already supported
   in v1.6, but `tier_breakdown` + `low_active_coverage` make the
   mis-fire visible to callers.
2. `rank_key` did not consider tier as a ranking signal, so pinning a
   page kept it in the active pool but did not surface it in top-N.
   Fix: tier tiebreaker.

Full evidence chain in `docs/dogfood-necallkit-hn-essay.md` →
"2026-05-14 — wiki-search natural experiment". Pre-PRD design idea
spawned by the same session: `docs/idea-coverage-matrix-dreamer.md`.

### Migration

None required. All changes are additive or behavior fixes to
under-specified ordering. Existing wiki-search callers ignoring the new
fields work unchanged.

If you have pages whose architectural facts are stable but date-aged
into `archived` tier, pin them with frontmatter:

```yaml
tier_override: active
tier_reason: stable architecture fact, not subject to time decay
```

Next session's wiki-search will surface them in top results.

## [2.0.0] — 2026-05-13 — Rebrand to **Kata**

**⚠ BREAKING CHANGE for slash commands.** All commands previously invoked
as `/ak-wiki:wiki-*` are now `/kata:wiki-*`. Update your muscle memory and
any scripts. The 13 skill names themselves (wiki-init, wiki-ingest, etc.)
are unchanged — only the plugin prefix moved.

### Why rebrand

The previous name framed the project as "an implementation of Karpathy's
LLM-Wiki idea." Reality is the opposite: llm-wiki is one substrate, and
the product is a **workflow + project memory layer for AI-paired
engineering** that compiles business semantics, manages spec authoring +
disagreement, and lets each builder adapt the workflow to their own
project. The new name captures the **accept-adapt-transcend mastery
curve** at the heart of the product.

### Breaking changes

| Identifier | Old | New |
|---|---|---|
| Brand | AK LLM Wiki / ak-wiki | **Kata** |
| Plugin name | `ak-wiki` | `kata` |
| Slash command prefix | `/ak-wiki:*` | `/kata:*` |
| Marketplace name | `ak-llm-wiki` | `kata` |
| Env var | `AK_WIKI_HOME` | `KATA_HOME` |
| Project binding file (secondary, low-use) | `.ak-wiki.yaml` | `.kata.yaml` (`.llm-wiki.yaml` still primary) |
| Per-machine state dir | `~/.ak-wiki/` (sync-reports etc.) | `~/.kata/` |
| Stash tag pattern | `.ak-wiki-stash-tag` | `.kata-stash-tag` |
| Public repo URL | `surebeli/AK-llm-wiki` | `surebeli/kata` |

### Migration

For existing users (if any):

1. **Slash commands:** retrain. `/ak-wiki:wiki-init` → `/kata:wiki-init`.
2. **Env var:** rename `AK_WIKI_HOME` → `KATA_HOME` in shell profile.
3. **Per-machine state directory:** optional rename — if you depend on
   sync reports or stash tags, `mv ~/.ak-wiki ~/.kata`. Otherwise let the
   new state dir build fresh.
4. **Project binding files:** if you placed `.ak-wiki.yaml` in any
   project repo root, rename to `.kata.yaml` (or rely on `.llm-wiki.yaml`
   which is still the primary form).
5. **Repo URL:** GitHub redirects old URL `surebeli/AK-llm-wiki` to
   `surebeli/kata` for ~30 days. Update remotes:
   ```bash
   git remote set-url origin https://github.com/surebeli/kata.git
   ```
6. **Self-meta wiki on disk:** `~/.llm-wiki/ak-wiki/` is **not**
   auto-renamed. User decides whether to rename to `~/.llm-wiki/kata/`
   (no auto-migration of `wiki_id` in `SCHEMA.md` either way).

### What did NOT change

- 13 skill names (`wiki-init`, `wiki-ingest`, etc.) — they operate on the
  wiki artifact; the wiki is what Kata produces, so the noun stays.
- All algorithms / scripts / behavior.
- Wiki filesystem layout (`raw/`, `SCHEMA.md`, `index.md`, `log.md`).
- The `.llm-wiki.yaml` primary binding file (only the secondary
  `.ak-wiki.yaml` alias was renamed).

### Positioning shift in README + manifests

- README opening flipped from "A plugin... based on Karpathy" to "A
  workflow + project memory layer for AI-paired engineering." The
  Karpathy lineage table is preserved further down as `## Design
  lineage` — credit is intact; framing is product-first.
- `plugin.json` + `marketplace.json` descriptions rewritten with
  workflow framing. Keywords dropped `karpathy`, `rag-alternative`;
  added `workflow`, `ai-paired-engineering`, `builder`, `kata`,
  `project-memory`, `multi-llm`, `spec-management`.
- Essay style guide bumped to v1.2; new §2 Builder ethos sub-section
  formalizes the accept-adapt-transcend stance for all future essays.

## [Unreleased]

### Documentation

- Clarify that `.llm-wiki.yaml` is a **single-path cache** — one wiki per
  file, not a list. Document the recommended multi-wiki coexistence
  patterns (per-project bindings, global `registry.yaml`, hybrid with
  nested innermost-wins override) in README → "Multiple wikis on one
  machine"; cross-referenced from `plugin/CLAUDE.md`, `plugin/AGENTS.md`,
  `SKILL.md`, `plugin/skills/wiki-init/SKILL.md`, and the NECallKit
  multi-machine onboarding handbook.
- Recommend adding `.llm-wiki.yaml` to project `.gitignore` when the
  project repo is git-managed — the binding is per-machine local state
  (paths differ across OS and developers); shared mappings should live
  in `~/.llm-wiki/registry.yaml` outside the repo.

## [1.7.2] — 2026-05-07

Multi-project global-install patch. ak-wiki can now be installed once and
used from arbitrary engineering repositories while resolving each project
to its own independent wiki under `~/.llm-wiki/{project}`. If no project
is specified or detected, skills fall back to `~/.llm-wiki/common`.

### Added — multi-project resolver

- `wiki_lib.find_wiki_root()` now resolves in this order: explicit
  `--wiki` / `--path`, `WIKI_PATH`, current wiki root, `LLM_WIKI_PROJECT`
  under `LLM_WIKI_HOME`, project-local `.llm-wiki.yaml` / `.ak-wiki.yaml`,
  `~/.llm-wiki/registry.yaml`, git root name as `~/.llm-wiki/{repo}`,
  legacy `~/.ak-wiki/config.yaml`, then `~/.llm-wiki/common`.
- Project binding files can use either:
  `project: necall` or `wiki_path: ~/.llm-wiki/necall`.
- `LLM_WIKI_HOME` customizes the base directory; default remains
  `~/.llm-wiki`.

### Changed — init layout

- `wiki_init.py` now creates `raw/external/` and `raw/imported/` by
  default, matching the external fallback and bulk-import workflows.
- `wiki_init.py --path` is optional; when omitted it initializes the wiki
  selected by the resolver, so running it inside a git repo creates
  `~/.llm-wiki/{repo}` by default.
- Template initialization copies `templates/<name>/index.md` when present,
  instead of always rendering the generic index.

### Documentation

- README documents the `~/.llm-wiki/{project}` layout, `.llm-wiki.yaml`,
  environment variables, and full path resolution order.
- Claude/Codex operational docs and the standalone `SKILL.md` now describe
  the same resolver and raw directory layout.

### Tests

- Smoke tests cover project binding resolution, `LLM_WIKI_PROJECT`, and
  fallback to `~/.llm-wiki/common`.

## [1.7.1] — 2026-04-26

Polish patch shipped during the v1.6 dogfood window. No new product
features — closes the gap where four skills (lint, digest, search,
init) were still pure-prompt despite earlier roadmap intent. Each now
has a deterministic script backing the mechanical part; the LLM-only
parts (judgment, narrative synthesis, schema evolution) remain in the
skill prompt.

### Added — scripts that were promised but missing

- `plugin/scripts/lint_naive.py` — structural lint: broken wikilinks,
  index gaps, true orphans, missing required frontmatter, tag drift
  (vs SCHEMA.md taxonomy), stale pages by `updated`, page-size cap,
  tier override sanity, custom-dimension completeness. Returns JSON
  grouped by check + severity. **Content gaps and SCHEMA.md evolution
  remain LLM tasks** in the wiki-lint skill prompt.
- `plugin/scripts/digest.py` — activity counts from log.md, inventory
  by type/tag, tier distribution, recently updated list, top hubs by
  inbound link count, stale custom-dimension values. **Theme
  clustering and coverage gaps remain LLM tasks** in the wiki-digest
  skill prompt.
- `plugin/scripts/wiki_init.py` — actually implements `--non-interactive`
  (prior versions only documented it). Writes SCHEMA.md / index.md /
  log.md / category dirs / raw layout from CLI flags or a domain
  template (`--template market_research`). Auto-validates the resulting
  SCHEMA.md against schema/wiki-schema.json before exit.

### Changed — skills wired to existing scripts

- `wiki-search` SKILL.md gained an `## Implementation` block pointing
  at `plugin/scripts/search_naive.py` (the script existed in v1.5 but
  the skill never referenced it).
- `wiki-lint` SKILL.md gained an `## Implementation` block routing
  structural checks through `lint_naive.py` while keeping content gaps
  and schema-evolution proposals as LLM tasks.
- `wiki-digest` SKILL.md gained an `## Implementation` block routing
  inventory/activity through `digest.py` while keeping theme
  clustering as an LLM task.
- `wiki-init` SKILL.md non-interactive section now shells out to
  `wiki_init.py` instead of describing the flow in prose only.

### Added — git pre-commit hook

- `.githooks/pre-commit` runs `tests/run_smoke.py` and
  `scripts/build_skill_md.py --check` on every commit that touches
  scripts/skills/schema/tests. Opt-in via
  `git config --local core.hooksPath .githooks`. README has the
  enable command in a new "Contributing" section.

### Tests

- Smoke test grew from 26 to 29 assertions: lint findings (Test 14),
  digest output shape (Test 15), wiki_init bootstrap + schema_validate
  pipe (Test 16).

### Internal

- 12 skills total still; `templates/market_research/` reachable via
  `wiki_init.py --template market_research`.

## [1.7.0] — 2026-04-25

The watcher release. Closes the gap where files dropped in `raw/` would
sit unprocessed because the user forgot to invoke `/wiki-ingest`. Built
in parallel with the v1.6 dogfood window — the watcher is code-isolated
from the dreamer (no shared state), so the two features ship without
blocking each other.

### Added — raw watcher daemon

- `plugin/scripts/wiki_watch.py` — polling daemon for `raw/articles/`,
  `raw/papers/`, `raw/transcripts/`, `raw/external/`. Stdlib only (no
  inotify/watchdog). 5-second poll, 5-second debounce against in-progress
  writes. Queue persisted to `.wiki-ingest-queue.json` with statuses
  `pending` / `processed` / `failed` / `removed`.
- `plugin/skills/wiki-watch/SKILL.md` — user-invokable skill. Modes:
  `--start`, `--stop`, `--status`, `--drain`, `--remove`. **Drain is
  always explicit** — the script never invokes `wiki-ingest` itself; the
  skill loops pending entries through `wiki-ingest` and marks each.
- Cross-platform daemonization: `subprocess.DETACHED_PROCESS` on
  Windows, `start_new_session=True` on POSIX.
- `docs/watcher.md` — full design + systemd/launchd/Task Scheduler
  recipes for headless deployment.

### Added — tests

- Smoke test grew from 22 to 26 assertions (Test 13: detection,
  debounce, min-size skip, queue remove, status without daemon).

### Documentation

- README adds an "Auto-ingest from raw/" section between "Quick start"
  and "Auto-dreaming".
- `docs/PRD-v1.7-watcher.md` and `docs/TRD-v1.7-watcher.md` document
  product + technical design.
- `docs/TASKS.md` extended with v1.7 phase and the parallelism note.

### Internal

- 12 skills total now (was 11 in v1.6).

## [1.6.0] — 2026-04-25

The auto-dreaming release. v1.6 ships the first feature that runs without
the user — a weekly job that re-evaluates frozen and archived pages
against recent activity and surfaces those whose relevance has resurfaced.
Strategy is benchmarked end-to-end with a CI precision/recall gate.

### Added — auto-dreaming

- `plugin/scripts/wiki_dream.py` — co-occurrence dreamer. Reads
  `log.md` + page mtime since the last watermark; scores frozen/archived
  pages on entity overlap, tag resurgence, and direct citation; emits
  candidates to `dreaming/{YYYY-MM-DD}.md` for review. **Filesystem-only
  by design** — never reads chat sessions.
- `plugin/skills/wiki-dream/SKILL.md` — user-invokable skill.
- `templates/market_research/SCHEMA.md` — domain template carrying the
  starter `dreaming:` block, custom dimensions (`launch_date`,
  `company_status`, `maturity`, `venue`), and the AI-market tag taxonomy.
- `tests/dreaming_fixtures/market_research/` — synthetic 92-page
  fixture with 8 planted recent ingests (Databricks-Mosaic acquisition,
  DeepSeek-V3 paper reviving MoE, multimodal tag resurgence) and
  hand-curated `expected.json` ground truth.
- `tests/run_dreaming_eval.py` — benchmark runner. `--gate` flag
  enforces `precision >= 0.7` and `recall >= 0.5` per PRD §4.

### Added — unified config interface

- `plugin/scripts/config_io.py` — surgical line-level edits to
  `SCHEMA.md` blocks. Validates after every write and reverts on
  failure. Logs each change to `log.md`.
- `plugin/skills/wiki-config/SKILL.md` — `--show / --get / --set /
  --explain / --validate`. Domain skills (`wiki-tier`, `wiki-init`)
  retain their UX shortcuts; `wiki-config` is the generic path-based
  alternative.

### Added — schema additions

- `schema/wiki-schema.json` gained the `dreaming:` block:
  `enabled`, `strategy`, `cadence`, `confidence_threshold`,
  `max_repromote_per_run`, `weights.{entity,tag,citation}`,
  `resurgence.{dormancy_window_days,min_count}`. Cross-field rules
  (already in v1.5) enforce ranges.
- `schema_validate.py` now handles `const` (needed for `if/then` blocks
  validating per-item conditional requirements like
  `custom_dimensions[*].type == "enum" → enum_values required`).

### Added — CI

- `.github/workflows/test.yml` runs `tests/run_dreaming_eval.py
  --fixture market_research --gate` after the smoke tests, blocking
  any PR that drops the dreamer's precision below 0.7 or recall below
  0.5 on the fixture.

### Tests

- Smoke test grew from 15 to 22 assertions covering wiki-config
  (show/get/set/revert/explain/log) and the dreaming gate.

### Documentation

- `docs/dreaming.md` — design depth, configuration, security model,
  reject-signal policy, why-not-embeddings.
- README adds an "Auto-dreaming" section between "Memory tiers" and
  "External fallback plugins".

### Internal

- `wiki_lib.py` gained: log parser, watermark IO, increment extraction,
  resurgence detection — pure stdlib, used by both the dreamer and
  any future strategy.

## [1.5.0] — 2026-04-25

Foundation release. No new features; closes the v1.4 gap between "scripts
exist" and "skills actually call them," adds CI, and prepares the schema
validator and search/image scripts for v1.6 (auto-dreaming).

### Changed — skills now invoke scripts

- `wiki-graph`, `wiki-tier`, `wiki-import` SKILL.md files gained an
  `## Implementation` block with the exact `Bash:` invocations of their
  matching script in `plugin/scripts/`. Skill prose still describes the
  algorithm for context, but the script is now declared as the source of
  truth — agents shell out instead of model-computing graph BFS or tier
  thresholds.

### Added — new scripts

- `plugin/scripts/ingest_images.py` — extracts `![](url)` references,
  downloads remote images to `raw/assets/`, rewrites paths in place. Per-
  download cap 10 MiB, per-source cap 50 MiB. Uses stdlib `urllib`; no
  third-party deps.
- `plugin/scripts/search_naive.py` — deterministic 3-pass search
  (index.md → frontmatter → body). Tier-filters by default, returns
  ranked JSON. Backs `wiki-search` when qmd is not installed.
- `scripts/build_skill_md.py` — keeps the autogenerated skill-table block
  in root `SKILL.md` in sync with `plugin/skills/*/SKILL.md` frontmatter.
  `--check` mode exits nonzero on drift; CI uses it as a gate.

### Added — schema validation

- `schema_validate.py` now runs five cross-field rules after structural
  validation: `active_days < archived_days`, `custom_dimensions.name`
  uniqueness, `custom_dimensions.applies_to` references declared
  categories, `dreaming.weights.*` ≥ 0, `dreaming.confidence_threshold`
  ∈ [0, 1]. The dreaming rules are forward-compatible with v1.6.

### Added — CI

- `.github/workflows/test.yml` runs `tests/run_smoke.py` on push and PR
  against main, matrix on Python 3.10/3.11/3.12/3.13 × ubuntu/windows.
  Plus a schema-check job that compiles all `plugin/scripts/` and
  validates `schema/wiki-schema.json` is valid JSON.

### Added — tests

- Smoke test grew from 11 to 15 assertions (image rewrite, naive search
  determinism, three cross-field violations, well-formed dreaming block).

### Added — product planning

- `docs/PRD-v1.6-autodreaming.md` — product requirements for v1.6
  auto-dreaming, scoped to the market-research domain.
- `docs/TRD-v1.6-autodreaming.md` — technical design: data flow,
  scoring algorithm, fixture spec, eval CI gate.
- `docs/TASKS.md` — sequenced task list with acceptance criteria for
  v1.5 and v1.6.

## [1.4.0] — 2026-04-25

### Added — packaging fidelity

- `plugin/.claude-plugin/plugin.json` — required Claude Code plugin manifest
  (was missing in 1.3; install worked accidentally because the marketplace
  manifest carried the metadata).
- `tests/build_fixture.py` and `tests/run_smoke.py` — 50-page synthetic wiki
  plus 11 smoke tests covering graph, tier, schema validation, and external
  plugin security. Stdlib only.
- `CHANGELOG.md` (this file).

### Added — deterministic algorithms

- `plugin/scripts/wiki_lib.py` — shared library: page discovery, frontmatter
  parsing, indent-aware YAML subset parser, graph build, tier compute,
  shortest-path BFS, neighbor BFS, hub scoring.
- `plugin/scripts/graph_query.py` — backs `wiki-graph` for neighbors,
  shortest-path, hubs, orphans, cluster, and stats modes. Skill becomes a
  thin wrapper that calls the script and formats the JSON.
- `plugin/scripts/tier_compute.py` — backs `wiki-tier --show / --preview /
  --list` with deterministic distribution and delta computation.
- `plugin/scripts/schema_validate.py` — validates `SCHEMA.md` and
  `.wiki-plugins.yaml` against `schema/wiki-schema.json` (a real JSON Schema
  document, not a prompt rule).
- `plugin/scripts/import_checkpoint.py` — JSON checkpoint IO for
  `wiki-import --resume`. No more "agent self-discipline" persistence.
- `plugin/scripts/external_plugin_run.py` — secure runner for
  `.wiki-plugins.yaml` entries.

### Changed — security model for external plugins

**Breaking.** `command_template:` is removed; plugins now declare `argv:` as
a list of literal tokens. The runner uses `subprocess.run(argv, shell=False)`
— a shell never sees the substituted query. After substitution any token
containing `;`, `|`, `&`, `&&`, `||`, `` ` ``, `$(`, `<`, `>`, or newline is
refused. Output is sanitized for prompt-injection markers (`<system>`,
`<|im_start|>`, `IGNORE PREVIOUS`, `[[INST]]`) before landing in `raw/`.
Outputs are sized (`max_output_bytes`, default 1 MiB) and timeboxed
(`timeout_seconds`, default 60). Env passed to children is filtered to a
small allowlist.

Migration is documented in `plugin/PLUGINS.md`.

### Fixed — packaging consistency

- README install commands corrected: `claude /plugin marketplace add` +
  `claude /plugin install` (the previous `claude plugin install` was not the
  real CLI). All slash-command examples now show the `/` prefix that Claude
  Code actually accepts.
- Codex CLI section: removed the non-spec `.codex-plugin/plugin.json`. Codex
  CLI integration is now documented honestly as a copy-based flow (drop
  `AGENTS.md` + `skills/` + `scripts/` into the project root).
- Skill count unified to **9** (was inconsistently `10` in
  `marketplace.json`, the removed Codex manifest, and root `SKILL.md`).

### Added — README clarity

- "Two ways to use this" section: a 3-step path for the standalone prompt
  vs. the full plugin path.
- Comparison table vs. Obsidian Copilot, MCP memory servers, and
  RAG/vector DBs — clarifies what the wiki is *for* relative to neighbors.

## [1.3.0] — 2026-04-12

- External fallback plugins: `.wiki-plugins.yaml` registry and the
  `wiki-query` fallback flow (`on_empty` / `on_low_confidence` /
  `on_request`). _Note: 1.3 used `command_template:` which 1.4 removed._
- `wiki-graph` skill: structured frontmatter / neighbor / shortest-path /
  hubs / orphans / cluster modes, plus mermaid output.

## [1.2.0] — 2026-04-12

- Three-tier memory aging (`active` / `archived` / `frozen`), tier
  computation on-the-fly from `published_at`, `wiki-tier` skill for
  inspection and threshold management.

## [1.1.0] — 2026-04-12

- Custom frontmatter dimensions in SCHEMA.md, with `refresh_on` schedule
  driving when `wiki-ingest` / `wiki-import` / `wiki-digest` prompt for
  values.
- `wiki-import`: 5-phase bulk migration (Discovery → Mapping →
  Deduplication → Wave processing with checkpoint → Navigation update).
- Image handling in `wiki-ingest`: download referenced images to
  `raw/assets/` and rewrite source paths.

## [1.0.0] — 2026-04-12

- Initial release. 6 skills (init, ingest, search, digest, query, lint)
  implementing Karpathy's LLM Wiki concept as a Claude Code plugin.
- SCHEMA.md as the single authoritative config.
- `raw/` immutability, `index.md` + `log.md`, Karpathy-style log format.
