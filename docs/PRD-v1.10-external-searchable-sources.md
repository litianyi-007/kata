# PRD v1.10 — External Searchable Sources (federated search)

Status: Draft
Date: 2026-05-11
Author: surebeli

> **Related work (2026-05-16):** v1.13 SHM extends this PRD's
> `.wiki-plugins.yaml` mechanism with a `treatment: raw|frozen|active`
> flag and wires external sources into spec preflight (so a mid-project
> kata adoption can scan a historical SDD spec corpus without bulk-
> importing). v1.13 does **not** supersede v1.10 — v1.10's query-fallback
> behavior is preserved as `treatment: active` default. See
> [`PRD-v1.13-spec-history-management.md`](PRD-v1.13-spec-history-management.md).

## Context

Existing `.wiki-plugins.yaml` solves a specific case: when `wiki-query` returns
0 hits locally, fall back to an external CLI, save stdout to `raw/external/`,
ingest, and grow the wiki. This is **ETL** — knowledge flows from external
into the wiki once, and lives in the wiki thereafter.

Real projects also have **active document sources that should not be ingested
yet** — a target repo's `docs/` and `specs/` directories that are still being
written, a Notion or Confluence space owned by another team, or a sibling
ongoing project. The user wants to drop these into kata as
**searchable references**: `wiki-search` can optionally look inside them
without forcing an `ingest`, and the wiki page distilled later still treats
its own `raw/` as the canonical evidence.

Concretely from the NECallKit dogfood: today's `docs/2026-04-16-web-ios-singlecall-api-alignment.md`
got ingested once, but the file keeps being edited. The user wants to query
"newest enableOffline behavior" without re-running ingest every time the
upstream doc changes.

This is **federated search** — not ETL.

## Goals

- Let a wiki declare multiple **external sources** in `SCHEMA.md` (or a
  sibling registry file), each with its own type, priority, and distillation
  hint.
- Extend `wiki-search` with a `--include-external` flag (default off) that
  scores external hits alongside local hits and labels them clearly.
- Keep the wiki's `raw/` and `wiki page` content authoritative; external hits
  are advisory, not canonical.
- Track external-source hit frequency so the wiki can recommend distilling
  high-traffic external content into `raw/` + wiki pages.
- Support per-project scenarios where a sibling code repo's `docs/` /
  `specs/` is registered as an external source.

## Non-goals

- **No remote source types in MVP** — only `local-directory` and `wiki-vault`
  are supported. Git ref / HTTP / Notion / Confluence are reserved interface
  points and deferred to v1.11+.
- **No `wiki-query` federation by default**, ever. wiki-query never reads
  from external sources unless an explicit `--include-external` flag is passed
  at call time. No global setting can flip this default to on.
- No replacement for `wiki-import` / `wiki-ingest`. External sources do not
  bypass the ingest pipeline; they make "I haven't ingested it yet" cheaper.
- No automatic ingest from external sources, ever. kata only observes,
  counts, and suggests; every `wiki-ingest` must be user-initiated after a
  closed validation loop (§Validation loop before ingest).
- No mutation of external sources. kata reads them; never writes.
- No transitive federation. External sources cannot themselves declare their
  own external sources.

## Personas / user stories

- **Maintainer on an ongoing project** — registers the target repo's `docs/`
  as an external source. `wiki-search --include-external` shows hits from both
  local distilled pages and the live source tree.
- **Cross-team consumer** — registers a sibling team's specs directory under
  `~/team-shared/specs/`. Reads it via search; ingests only the conclusions
  that matter for their wiki.
- **Onboarding agent** — opens a wiki for the first time. Sees `[external]`
  results pointing at the source repo, follows them, distills the high-value
  ones via curated `wiki-ingest`.
- **Multi-wiki maintainer** — owns two project wikis on the same machine.
  Registers wiki B as wiki A's `wiki-vault` source so cross-project queries
  don't lose context, while each wiki keeps its own canonical `raw/` and
  synthesis.

## Data Model

### `SCHEMA.md` `## External sources` block

```yaml
external_sources:
  defaults:
    enabled: true                  # global on/off; default true once any source declared
    always_on: auto                # auto | true | false. "auto" = true iff decay != none.
    priority: lower-than-local     # local-first | external-first | equal
    distillation_hint: 5           # per-source default unless overridden
    decay: half-monthly            # half-monthly | none. Halves all hit counts on the 1st of each month when enabled.
  sources:
    - name: necallkit-active-docs
      type: local-directory
      path: <workspace>/project/NECallKit/docs
      glob: "**/*.md"
      priority: lower-than-local
      distillation_hint: 3
      description: "Active NECallKit docs (still being written, ingest selectively)"
    - name: necallkit-specs
      type: local-directory
      path: <workspace>/project/NECallKit/specs
      glob: "**/*.md"
      priority: equal
      description: "NECallKit specs trees (PRD / data-model / research / tasks)"
    - name: shared-team-wiki
      type: wiki-vault
      path: ~/.llm-wiki/SharedPlatform     # default path; ~ expanded per-machine
      paths:                                # optional per-machine overrides
        - machine_id: litianyi-mbp-mac-7b52f6
          path: ~/wiki-shared/wikis/SharedPlatform
        - machine_id: desktop-ab12-win-9e3a1c
          path: D:/Notes/llm-wiki/SharedPlatform
      priority: equal
      distillation_hint: 5
      description: "Sibling team's distilled wiki; reuse their knowledge without merging vaults"
```

`defaults.always_on` and `defaults.decay` are configuration-only and have
no per-source override (they govern the whole wiki's external behavior).
All other `defaults.*` keys are inherited by every source unless the
source overrides them explicitly.

**`always_on: auto` semantics** (recommended default):

- When `decay != none` (e.g., `half-monthly`), "auto" resolves to **true**.
  Counts naturally fade, so federating by default does not produce hint
  fatigue.
- When `decay: none`, "auto" resolves to **false** — without decay,
  cumulative hit counts would grow unbounded under `always_on: true`, so
  the safe default reverts to per-call opt-in.
- Explicit `true` or `false` overrides the auto-derived value regardless
  of `decay`.

This pairing makes `always_on: true` and `decay: half-monthly` the
self-balancing default: federation is on, but old references fade.

### Source object fields

- `name`: stable short identifier. Appears in result labels as
  `[external:{name}]`. Required, unique within the wiki.
- `type`: source backend. MVP supports `local-directory` and `wiki-vault`.
  Reserved values: `git-repo` (with ref+path), `http-endpoint`, `cli-command`.
  Each non-MVP type is rejected with a clear error.
  - `local-directory`: scans `path` under `glob`. Does not enforce
    `.gitignore` but honors it if discoverable. Suitable for ongoing
    docs / specs trees in a sibling project.
  - `wiki-vault`: scans **another kata vault root**. Auto-restricts to
    the category directories declared in the target's `SCHEMA.md`
    (`features/`, `bugs/`, `decisions/`, `modules/`, `queries/`,
    `lessons/`, plus any custom categories). **Hard-skips** `raw/`
    (immutable source material is not searchable across vaults — distill
    inside its own vault first) and `dreaming/` (per-machine, not
    portable). Transitive federation is refused: a `wiki-vault` source's
    own `external_sources` are not followed.
- `path`: absolute local path (default for any machine when no
  `paths:` override matches). Required for `local-directory` and
  `wiki-vault`. `~` is expanded per-machine. Must exist and be readable;
  for `wiki-vault` must also contain a valid `SCHEMA.md` with `wiki_id`.
  Otherwise the source is marked `unhealthy` and skipped with a warning.
- `paths`: optional list of per-machine path overrides. Each entry has a
  `machine_id` (matched against `~/.kata/machine-id` of the current
  machine) and a `path`. Resolution order on every search:
  1. If a `paths` entry matches the current machine's `machine_id`, use
     that entry's `path`.
  2. Otherwise, fall back to the top-level `path` field with `~`
     expanded.
  3. If neither yields an existing readable directory, mark the source
     `unhealthy` and skip.
  This lets a wiki synced across heterogeneous machines (different OS,
  different mount points) carry a single SCHEMA.md while each machine
  resolves to its actual local checkout. See §Machine identity below.
- `glob`: glob filter applied under `path`. Default `**/*.md`. For
  `wiki-vault`, glob applies **after** the category restriction and the
  `raw/` + `dreaming/` skip — it cannot override those guards.
- `priority`: `lower-than-local` | `equal` | `higher-than-local`. Controls
  how external hits are ranked against local wiki hits with the same token
  score. Default from `defaults.priority`.
- `distillation_hint`: integer; if the same external file is hit ≥ this many
  times in a tracking window, `wiki-search` outputs a "consider ingesting"
  suggestion. Default from `defaults.distillation_hint`. `0` disables.
- `description`: human-readable purpose. Required to discourage anonymous
  registrations.
- `enabled`: optional per-source override (default `true`).

### Hit tracking file

`~/.kata/external-hits/{wiki-slug}.json` — per-machine, outside the wiki
repo (same reasoning as sync reports). Schema:

```json
{
  "version": 1,
  "wiki": "NECallKit",
  "hits": {
    "necallkit-active-docs": {
      "docs/2026-04-16-web-ios-singlecall-api-alignment.md": 4,
      "docs/prd/F011-master-low-coupling-sync/F011-master-merge-back-plan.md": 1
    }
  },
  "last_reset": "2026-05-11T00:00:00Z"
}
```

When a path crosses `distillation_hint`, the search output flags it. The user
can run a manual reset (drop the JSON) after acting on a suggestion.

### Machine identity

kata gives every machine a stable identifier so SCHEMA.md can declare
**per-machine path overrides** (§Source object fields `paths:`). This is
needed because `~/.llm-wiki/` is **not** a synced directory — only each
wiki's git repo content is synced. So a path declared in SCHEMA.md must
either work on every machine after `~`-expansion (the common case) or
specify per-machine overrides.

#### `machine-id` file

Per-machine, lives at:

```text
~/.kata/machine-id
```

Never enters any wiki repo (lives outside `~/.llm-wiki/`). Each machine
generates its own once.

#### Generation algorithm

On first invocation of any wiki command that needs machine identity
(initially: `wiki-search --include-external`, `wiki-config machine-id`),
kata checks for the file. If absent, it generates:

```text
machine_id = "{hostname_short}-{platform}-{home_hash}"

hostname_short = socket.gethostname() with .local / .lan / .localdomain
                 stripped, then truncated to ≤12 chars, lower-cased,
                 non-alphanumerics replaced with '-'.
platform       = "mac" | "win" | "linux"
home_hash      = SHA1(os.path.expanduser("~")) hex digest, first 6 chars
```

Examples (the same user across machines):

| hostname | platform | home | generated machine_id |
|---|---|---|---|
| `host-mbp.local` | mac | `/Users/<user>` | `host-mbp-mac-7b52f6` |
| `DESKTOP-AB12CDE` | win | `C:\Users\<user>` | `desktop-ab12-win-9e3a1c` |
| `DESKTOP-AB12CDE` (WSL) | linux | `/home/<user>` | `desktop-ab12-linux-4f8a2c` |

#### Privacy properties

- **Full absolute paths never enter the machine_id** — only a 6-hex SHA1
  digest of the home directory.
- The hostname is included, truncated to 12 chars. Users on shared
  hostnames can rename their machine_id any time.
- `machine-id` file is per-machine and lives outside any wiki repo, so
  it never sync-conflicts and never leaks across machines.

#### User-renamable

After auto-generation, kata shows the proposed id and lets the user
edit `~/.kata/machine-id` to a more human-readable form (e.g.,
`lty-mac-home`, `lty-win-corp`). The auto-generated form is the
fallback; user-renamed ids stay unless the user changes the file.

The first-run prompt looks like:

```text
kata: Generated machine-id for this machine:
    litianyi-mbp-mac-7b52f6
You can rename it to something more readable (e.g., 'lty-mac-home') by
editing ~/.kata/machine-id at any time. The id is used by
external-source per-machine path overrides; nothing else.
```

If the user never opens that file, the auto-id is used indefinitely.

#### Inspecting

```bash
/kata:wiki-config machine-id
# Prints the current machine's id. Use this to find the value you need
# to paste into another machine's SCHEMA.md `paths:` overrides.
```

No discovery / auto-sync mechanism in v1.10 MVP: copying machine_ids
between machines is manual. v1.11+ may add a `known-machines.json` that
wiki-sync co-distributes, but MVP keeps it explicit.

## User Workflows

### Register a source

User edits `SCHEMA.md` directly (consistent with how other v1.x configs were
added — sync block, tag taxonomy, custom dimensions). A future
`wiki-config external add` would be sugar but is not required for MVP.

After editing, no separate "activate" step. The next `wiki-search
--include-external` reads the new block.

### Search with external

```bash
# Local only (current behavior, unchanged)
/kata:wiki-search --query "enableOffline"

# Local + every enabled external source
/kata:wiki-search --query "enableOffline" --include-external

# Local + a specific source (others skipped this call)
/kata:wiki-search --query "enableOffline" --external-source=necallkit-active-docs

# External only (rare; debugging; requires --explicit-allow per §Safety Rules)
/kata:wiki-search --query "enableOffline" --external-source=necallkit-specs --no-local --explicit-allow

# Opt out for this one call when defaults.always_on=true
/kata:wiki-search --query "enableOffline" --local-only
```

When `external_sources.defaults.always_on` resolves to `true` (explicit
`true`, or `auto` with `decay != none`), the `--include-external` flag is
implied for every `wiki-search` call. `--local-only` overrides for the
current call only and never persists. This lets a user who always wants
federation rely on the auto-derived default while still being able to
diagnostically pull local-only results when needed.

`--local-only` and `--include-external` are mutually exclusive. Passing both
is a usage error.

Output shape — local and external are grouped, each labeled:

```text
=== local hits (3) ===
1. bugs/electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09.md  body=42
2. features/necallkit-offline-message-contract-and-electron-link-2026-05-11.md  body=18
3. log.md  body=4

=== external hits (2) ===
[external:necallkit-active-docs]
1. docs/2026-04-16-web-ios-singlecall-api-alignment.md  body=7  [ephemeral, not in wiki]
[external:necallkit-specs]
1. specs/001-nim-v10-upgrade/spec.md  body=5  [ephemeral, not in wiki]

=== distillation hints ===
- necallkit-active-docs / 2026-04-16-web-ios-singlecall-api-alignment.md
  has been hit 4 times (threshold 3). Consider:
    /kata:wiki-ingest <path>
```

### Distillation hint workflow

When a hit crosses `distillation_hint`, the search output appends a one-line
recommendation with the exact `wiki-ingest` command. User runs it (or
doesn't). After ingest the file naturally moves to local hits and the hint
stops firing.

### Health check

`wiki-lint` validates `external_sources`:

- `path` exists and is readable
- `name` is unique within the wiki
- `type` is supported (`local-directory` only in MVP)
- Sources marked `unhealthy` are skipped, not fatal

## Search Integration

### Scoring

External hits use the **same** token-frequency algorithm as `search_naive.py`
(no separate scoring backend in MVP). Each source becomes a virtual page
collection; its scores are then adjusted by `priority`:

- `lower-than-local`: multiply external score by 0.7 before ranking
- `equal`: no adjustment
- `higher-than-local`: multiply external score by 1.3

This is a simple proxy. v1.11+ may add explicit `tier` semantics. The
multipliers above are tunable but should be conservative — external content
should rarely outrank curated wiki pages by default.

### Output verbosity

Two output modes:

- **Grouped (default)**: local hits in one section, external hits in
  another (with per-source labels), distillation hints last. Visually
  reinforces "local is canonical, external is ephemeral" each time the
  user reads search output. This is the recommended mode and matches the
  example in §User Workflows above.
- **Interleaved (`--debug-interleave`)**: all hits sorted by adjusted score
  in a single list, each prefixed with `[local]` or `[external:{name}]`.
  **Debug only** — primary use case is tuning `priority` multipliers
  (verifying that a `higher-than-local` source actually outranks weak
  local hits after the ×1.3 multiplier applies). Not recommended for
  everyday search: with mixed sections it is easier to skim past
  `[ephemeral]` labels and inadvertently treat external content as
  canonical. The `--debug-` prefix is intentional — the flag should not
  appear in normal user-facing help suggestions, only in detailed help
  output or PRD/README sections about priority tuning.

The grouped mode is always available; `--debug-interleave` is an opt-in
escape hatch for priority debugging.

### Performance and rate limits

- MVP synchronously scans `local-directory` sources on every
  `--include-external` invocation. For directories under ~10k files this
  stays under 1s with `glob` filtering. Larger directories should be
  ingested instead.
- An in-process LRU cache (default 64 sources × 30s) avoids rescanning a
  source many times within one session.
- `wiki-search --include-external` runs all enabled sources sequentially.
  Future v1.11+ may parallelize, but MVP keeps deterministic ordering.

### Trust boundary

- Every external hit is labeled `[ephemeral, not in wiki]` in the output.
- `wiki-query` **never** calls external sources by default. There is no
  global setting that flips this on (the `always_on` flag governs
  `wiki-search` only). A future `wiki-query --include-external` flag may
  be added in v1.11+, but it must require explicit per-call invocation;
  kata never auto-federates query synthesis. Every cited external
  page (when explicitly federated in a future version) will carry an
  `[ephemeral, unverified]` footnote.
- `wiki-search` never writes to external sources.
- kata never auto-runs `wiki-ingest` based on external hits — see
  §Validation loop before ingest.

## Distillation: an optional pathway

External hits never become wiki content automatically. The wiki
**observes, counts, and notes** — it does not nudge. If an external file
gets referenced often, that's a data point; what to do with it is the
user's call. **"Keep using it as an external reference, never distill"
is a fully legitimate end state** — not a problem to solve.

kata's job for external sources is to make them findable, not to
push them toward `raw/`.

### Optional 3-step pathway (only if you decide to distill)

```text
1. Observe   — wiki-search returns external hit; counter increments
2. Validate  — *if* you choose to distill, first confirm the source is
                correct, current, and applicable. Specifically rule out:
                  - stale draft / superseded version
                  - deprecated rule the wiki already overwrote
                  - partial info that contradicts a wiki conclusion
                  - hallucinated or generated-but-unverified content
3. Distill   — run `/kata:wiki-ingest <path>` when ready. Not before.
```

There is no expectation that you reach step 3. Step 1 — with the counter
quietly incrementing across sessions — is the steady state for most
external files. The wiki is not waiting for you to ingest.

### External usage notes (canonical wording at threshold)

When a hit crosses its `distillation_hint` threshold, `wiki-search`
appends a quiet observation block. Wording is matter-of-fact, not a
recommendation:

```text
=== external usage notes ===

[external:necallkit-active-docs] docs/2026-04-16-web-ios-singlecall-api-alignment.md
  referenced 4 times across recent searches (threshold: 3)

  This file is being used as an external reference frequently enough to
  show up here. There is no requirement to distill it — using it
  long-term as an external reference is a fine end state.

  If you happen to want to bring it into the wiki, the command is:
    /kata:wiki-ingest <workspace>/project/NECallKit/docs/2026-04-16-web-ios-singlecall-api-alignment.md

  kata only ingests what you have checked for staleness,
  contradiction, and verified correctness. Validation is your call.

  This note will fade on its own: counts halve on the 1st of each
  month, so if you stop hitting the file, this block stops appearing.
```

Three deliberate features of this wording:

- **No verbs that imply obligation** (no "consider", "should",
  "recommend"). Just description of what happened.
- **"Long-term as an external reference is a fine end state"** —
  removes the implicit pressure that the threshold means "do something."
- **The decay sentence ends the note** — closes with "this will fade
  on its own," so the user does not feel they need to act to make the
  prompt stop.

### Why kata never auto-ingests

Even with this relaxed framing, kata still **never** auto-runs
`wiki-ingest`. Three reasons:

- An external source is by construction outside wiki curation. It can
  drift, get rewritten, or be deprecated without kata noticing.
- Auto-ingesting on threshold would let stale or contradictory content
  silently enter `raw/` and seed wrong conclusions for future agents.
- The wiki is the user's curated artifact. Automation should never
  decide what enters it.

This mirrors `knock-it-out` §3.5 distillation gate: facts only land in
the wiki when the user confirms them. Observation alone is not enough
to write — but observation alone is also not a problem to fix.

## Safety Rules

- `path` is resolved with `Path.resolve()` and compared against a hardcoded
  user-home ancestry. Paths under `/`, `C:\Windows`, `/etc`, `/usr` are
  refused.
- A source with `path` outside the user's home (or outside the wiki root for
  relative paths) emits a warning at lint time; user can override with
  `allow_outside_home: true` per source.
- External source content is **never** written into wiki pages by automation.
  Ingest is always an explicit `wiki-ingest` call with the user's review.
- Hit tracking lives in `~/.kata/`, not the wiki repo, so it never
  conflicts during sync.
- `wiki-search --no-local --external-source=X` requires `--explicit-allow`
  or it warns about "external-only mode is for debugging, not for answering"
  to prevent over-trusting external snapshots.
- `wiki-vault` source paths must contain a valid `SCHEMA.md` with a UUID
  `wiki_id`. Sources pointing at non-wiki directories are marked
  `unhealthy` and skipped (not fatal).
- `wiki-vault` scans hard-skip `raw/` and `dreaming/` of the target wiki
  **before** applying user-provided `glob`. The user cannot override these
  skips. This preserves the "no transitive ingest" rule: distilling
  another vault's `raw/` would conflate evidence chains across wikis.
- `~/.kata/machine-id` lives outside any wiki repo and is never synced.
  Even if a user puts a `paths:` override naming a stale `machine_id`,
  kata on a machine with a different id simply falls back to the
  top-level `path:`; no cross-machine leakage.
- `machine-id` file contents are limited to a single line ≤ 64 chars
  matching `^[A-Za-z0-9._-]+$`. Longer or malformed content is rejected
  at read time with a clear error.

## Interaction With Existing Skills

- `wiki-init`: optionally seeds an empty `external_sources:` block in
  SCHEMA.md with a comment explaining federation.
- `wiki-search`: gains `--include-external`, `--external-source`,
  `--local-only`, and `--debug-interleave` flags. When
  `external_sources.defaults.always_on` resolves to `true` (explicit or
  auto-derived from `decay != none`), `--include-external` is implied
  unless `--local-only` is passed for the current call. Output format
  extends with grouped sections, `[ephemeral]` labels, and external
  usage notes (see §Distillation: an optional pathway).
- `wiki-query`: **does not** call external sources, period. No global
  setting flips this. A future `wiki-query --include-external` flag may
  land in v1.11+ for explicit per-call federation, but it is not part of
  v1.10 and never becomes default-on.
- `wiki-ingest`: unchanged. Distillation hints from `wiki-search` produce
  ready-to-run `wiki-ingest` commands; the user runs them manually.
- `wiki-lint`: validates `external_sources` block, reports `unhealthy`
  sources and unknown `type` values.
- `wiki-config`: can list external sources, toggle `enabled`, and show
  the current machine's `machine-id` via `wiki-config machine-id`.
  Editing full source definitions still goes through SCHEMA.md; editing
  the local `machine-id` still goes through the file at
  `~/.kata/machine-id`.
- `wiki-sync`: treats `external_sources` block as normal versioned wiki
  metadata. `~/.kata/external-hits/` is per-machine and not synced.
- `wiki-watch`: unchanged. Watcher operates on `raw/`, not external sources.

## MVP Implementation Shape

1. Add schema validation for `external_sources` block in
   `plugin/scripts/schema_validate.py`. Reject unknown `type` values with
   a clear message naming the MVP set (`local-directory`, `wiki-vault`);
   require `description` and unique `name`; refuse `glob` overrides that
   would bypass `wiki-vault`'s `raw/` / `dreaming/` skip.
2. Add `external_sources.py` for parsing the block, validating paths,
   loading source content, and tracking hits. Implement two scanners:
   - `LocalDirectoryScanner`: reads files matching `glob` under `path`.
   - `WikiVaultScanner`: reads category directories declared in the
     target wiki's `SCHEMA.md`. Hard-skips `raw/` and `dreaming/` before
     applying any user `glob`. Refuses to follow the target's own
     `external_sources` (no transitive federation).
   Path resolution follows §Machine identity: try `paths:` overrides
   matching `~/.kata/machine-id` first, then top-level `path:` with
   `~` expansion.
2a. Add `machine_id.py` with two responsibilities:
    - Read `~/.kata/machine-id`; if absent, generate
      `{hostname_short}-{platform}-{home_hash}` (§Machine identity
      generation algorithm), write it, and print the first-run prompt
      to stderr.
    - Validate the file contents (single line, `^[A-Za-z0-9._-]+$`,
      ≤ 64 chars); reject malformed content.
3. Extend `search_naive.py` with `--include-external`, `--external-source`,
   `--local-only`, and `--debug-interleave` flags. Reuse the existing
   token-frequency scoring; apply `priority` multipliers before sorting.
   Resolve `defaults.always_on` per the auto-derivation rule (auto →
   true iff `decay != none`); when it resolves to `true`, treat
   `--include-external` as implied unless `--local-only` is passed for
   the current call. Grouped output is default; `--debug-interleave` produces
   the score-sorted list with inline labels.
4. Add hit-tracking persistence under `~/.kata/external-hits/{slug}.json`.
   Increment on every external hit returned to the user; flush at end of
   command. Implement half-monthly decay: on first invocation of any wiki
   command after the 1st of a new month, divide all counts by 2 (integer
   floor) and record the decay date. Decay is observable in the JSON
   (`last_decay` field) so manual inspection is auditable.
5. Implement external usage notes output using the canonical wording in
   §Distillation: an optional pathway. The note never auto-runs
   `wiki-ingest`; it names the command, prefills the path, lists the
   validation checklist (current / non-contradictory / closed loop), and
   closes with the decay sentence so the user knows the note will fade
   without action.
6. Extend `wiki-lint` to surface `unhealthy` sources, unknown `type`,
   duplicate `name`, paths outside home (with `allow_outside_home: true`
   override), `wiki-vault` sources pointing at non-wiki directories,
   and `paths:` entries with malformed or duplicate `machine_id`. Also
   warn (not fail) when a `paths:` entry's `machine_id` does not match
   any locally cached `known-machines` value, if such a cache exists.
6a. Extend `wiki-config` with `machine-id` subcommand: prints the
    current machine's id; if absent, triggers generation per
    §Machine identity.
7. Update README §External fallback plugins (clarify ETL vs federation)
   and add a new §External searchable sources section with examples
   covering both `local-directory` and `wiki-vault` types.
8. Add a starter `external_sources:` example block to a sample wiki
   fixture under `tests/`.

Approximate scope: 350-550 LOC across 5-6 files; reuse `search_naive`
core. The `wiki-vault` scanner adds ~50 LOC for category enumeration and
skip enforcement; half-monthly decay adds ~30 LOC; `always_on` /
`--local-only` plumbing adds ~20 LOC; `machine_id.py` + `paths:`
resolution adds ~80 LOC.

## Dogfood Acceptance Criteria

Acceptance requires running federation against the live NECallKit wiki on
this machine:

- Register `<workspace>/project/NECallKit/docs` as a `local-directory`
  source with `priority: lower-than-local`, `distillation_hint: 3`.
- Register `<workspace>/project/NECallKit/specs` as a second source with
  `priority: equal`.
- Register a sibling wiki vault (a small test fixture, or another local
  `~/.llm-wiki/<project>/`) as a `wiki-vault` source. Verify that the
  target's category pages are searchable but its `raw/` and `dreaming/`
  are never reached.
- `wiki-search --query "enableOffline" --include-external` returns both
  local wiki pages and at least the
  `2026-04-16-web-ios-singlecall-api-alignment.md` external hit, labeled
  and grouped.
- Same query 3 times surfaces an external usage note that:
  - reports the count and threshold as data, not as a recommendation,
  - names the exact `wiki-ingest` command and the validation checklist
    (current / non-contradictory / closed loop),
  - explicitly frames "keep using as external reference" as a
    legitimate end state,
  - closes with the decay sentence ("counts halve on the 1st of each
    month").
  The note never auto-executes. The user may ignore it forever; that is
  a supported outcome, not a deferred TODO.
- With `defaults.always_on: auto` and `defaults.decay: half-monthly`,
  `wiki-search` includes external by default (auto-derived true);
  `--local-only` opts out for one call. Switching to `decay: none` with
  `always_on: auto` flips the behavior back to per-call opt-in. Setting
  `always_on: false` explicitly always disables auto-inclusion regardless
  of decay.
- `wiki-search` without `--include-external` and without `always_on`
  behaves identically to v1.9 — no regression in local-only flow.
- `wiki-sync` round-trips the `external_sources` block via normal git;
  per-machine hit tracking JSON under `~/.kata/` is untouched.
- `wiki-lint` flags broken sources (`path` does not exist, or
  `wiki-vault` pointing at a directory without `SCHEMA.md`) as
  `unhealthy` without failing the whole lint.
- Setting the system clock past the 1st of a month and running any wiki
  command halves all hit counts and updates the decay timestamp in
  `~/.kata/external-hits/{slug}.json`.
- On a fresh machine, the first invocation of `wiki-search
  --include-external` generates `~/.kata/machine-id`, prints the
  proposed id to stderr, and uses it. Subsequent invocations read the
  file without prompting.
- `wiki-config machine-id` prints the current id. Manually editing the
  file changes the id; the next `wiki-search --include-external` uses
  the new id without restart.
- A `paths:` override with `machine_id` matching the current machine
  takes priority over the top-level `path:`. A non-matching `paths:`
  entry falls back to top-level `path:`. A non-existent resolved path
  marks the source `unhealthy`, not fatal.
- The `--debug-interleave` flag produces the score-sorted list with
  `[local]` / `[external:{name}]` labels inline; the same query without
  `--debug-interleave` produces the grouped view. The flag's help text
  identifies it as debug-only.

## Open Questions

All v1.10-blocking questions are closed below; remaining items are
deferred to v1.11+ and recorded for traceability.

### Closed (decided in this PRD)

1. ~~**Hit tracking window**~~ → **Half-monthly decay** (every 1st of
   month, integer-floor halve, recorded in
   `~/.kata/external-hits/{slug}.json`). Cumulative + manual reset
   rejected as it produces hint fatigue.
2. ~~**Output verbosity**~~ → **Grouped by default** (local section
   first, external section labeled `[ephemeral]`, distillation hints
   last). `--debug-interleave` added as debug-only escape hatch with inline
   `[local]` / `[external:{name}]` labels.
3. ~~**`wiki-query --include-external`**~~ → **Never on by default,
   ever.** No global setting flips this. A future `--include-external`
   flag in v1.11+ may add explicit per-call federation for
   `wiki-query`; nothing else.
4. ~~**Globally enabled vs per-call opt-in**~~ → **`defaults.always_on: auto`**
   three-state field (`auto | true | false`). "Auto" resolves to `true`
   iff `decay != none`, so federation is on by default whenever decay
   protects against hit fatigue. When `decay: none`, "auto" resolves to
   `false` for safety. Explicit `true`/`false` overrides regardless.
   This makes `always_on: auto` + `decay: half-monthly` the
   self-balancing recommended default.
5. ~~**Cross-wiki federation**~~ → **In MVP as `type: wiki-vault`.**
   Scans only the target wiki's category directories (declared in its
   `SCHEMA.md`); hard-skips `raw/` and `dreaming/`. Transitive federation
   refused — a `wiki-vault` source's own `external_sources` are not
   followed.
6. ~~**Auto-ingest after threshold**~~ → **Never.** External usage notes
   are matter-of-fact observations, not recommendations. They name the
   `wiki-ingest` command and a validation checklist, but explicitly
   frame "keep using as external reference forever" as a legitimate end
   state — no pressure to ingest. Wording is in §Distillation: an
   optional pathway.

### Still open (deferred to v1.11+)

- **`wiki-query --include-external` semantics** — citation badges,
  confidence-floor behavior when leaning partially on ephemeral content.
  Reopen after v1.10 dogfood gives the search-only loop real data.
- **Decay tuning** — half-monthly may be too aggressive for low-traffic
  wikis or too gentle for high-traffic ones. Consider exposing
  `defaults.decay` choices: `half-monthly` | `half-quarterly` | `none`.
  v1.10 hard-codes half-monthly; revisit only if dogfood shows it's wrong.
- **Hint upgrade tier** — surfacing "you are leaning hard on this
  external source because local is weak" was discussed and deliberately
  deferred. Add only if hint fatigue or local-thinness becomes a
  measurable problem during dogfood.
- **Remote source types** (`git-repo` with ref+path, `http-endpoint`,
  `cli-command`). Each is a separate v1.11+ slice with its own
  auth / cache / freshness design. MVP code already rejects them with
  a clear message naming the supported set.

## Forward compatibility

The `type` field is open by design. MVP supports `local-directory` and
`wiki-vault`. Adding `git-repo`, `http-endpoint`, or `cli-command` in
v1.11+ does not require schema migration; new sources just declare their
`type` and any type-specific fields. MVP code rejects unknown types with
a clear error message naming the supported set.

The `priority` enum is also extensible. v1.11 may introduce explicit
`tier: external-frozen` to align with the active/archived/frozen tier
system, mapping external sources into the same tier UI.

## Relationship to existing v1.x features

- **v1.4 external fallback plugins** (`.wiki-plugins.yaml`): orthogonal.
  Plugins do **fetch + ingest** on `on_empty`; v1.10 federation does
  **scan + label** on `--include-external`. Both can coexist; a future
  hybrid plugin type (`type: cli-command` external source) could merge them.
- **v1.7 raw/ watcher** (`wiki-watch`): unaffected. Watcher operates on
  `raw/`; external sources are explicitly outside `raw/`.
- **v1.8 sync**: `external_sources` block is versioned wiki metadata,
  merged via standard 3-way merge. Hit tracking is per-machine.
- **v1.9 branch-aware repository bindings**: complementary. v1.9 helps
  pages declare which branch they apply to; v1.10 helps the wiki *read*
  the branch's live source tree without ingesting. A future enhancement
  could auto-derive `external_sources` entries from `.wiki-repos.yaml`'s
  registered repos. The v1.10 `wiki-vault` type also pairs naturally with
  v1.9: in a multi-wiki setup where branches are partitioned across
  vaults, one vault can federate-search another without merging their
  `raw/`.
