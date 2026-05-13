# Tasks — v1.5 + v1.6

Sequenced. Each task has acceptance criteria. v1.5 is mechanical; v1.6
starts at a confirmation gate.

Companion docs: [PRD](PRD-v1.6-autodreaming.md) · [TRD](TRD-v1.6-autodreaming.md)

---

## Phase v1.5 — Foundation closing (no decisions needed)

### v1.5-1 — Wire skills to scripts

**Files:** `plugin/skills/wiki-graph/SKILL.md`, `plugin/skills/wiki-tier/SKILL.md`, `plugin/skills/wiki-import/SKILL.md`

Add an `## Implementation` section to each, with concrete `Bash:` invocations of the matching script. Skill body keeps the algorithmic prose for context but routes execution through the script.

**Acceptance:**
- Each of the 3 SKILL.md has a section starting `## Implementation`.
- The section names the script path and shows ≥ 2 example argv.
- A short note "the script is the source of truth; this prose explains its behavior" appears.

### v1.5-2 — GitHub Actions CI

**Files:** `.github/workflows/test.yml` (new)

Run `tests/run_smoke.py` on push and PR against main. Matrix on Python 3.10, 3.11, 3.12, 3.13.

**Acceptance:**
- Workflow file is valid YAML.
- Runs only on `*.py`, `*.md`, `tests/**`, `plugin/scripts/**`, `schema/**` changes.
- Passes locally via `act` or visibly in CI on push.

### v1.5-3 — Schema cross-field validation

**Files:** `plugin/scripts/schema_validate.py`, `tests/run_smoke.py`

Add 5 cross-field rules:
1. `memory_tiers.active_days < memory_tiers.archived_days`
2. `custom_dimensions[*].name` unique
3. `custom_dimensions[*].applies_to` items must reference declared categories
4. `dreaming.weights.*` ≥ 0 (when block exists)
5. `dreaming.confidence_threshold` ∈ [0, 1] (when block exists)

**Acceptance:**
- New tests in run_smoke.py prove each rule fires when violated and passes when satisfied.
- Existing tests still green.

### v1.5-4 — Image-handling script

**Files:** `plugin/scripts/ingest_images.py` (new), tests/run_smoke.py

Stdlib `urllib` for downloads (no `requests` dep). For each `![](url)` in the input file:
- If `url` is remote (http/https): download to `raw/assets/{source-stem}-{n}.{ext}`, replace with relative path.
- If `url` is already local: leave unchanged.
- Cap each download at 10 MiB; cap total per source at 50 MiB.
- Strip query strings from filenames.

**Acceptance:**
- Smoke test fixture gets a fake markdown with one local + one remote image; script rewrites the remote one and leaves the local one alone. (Use a `file://` URL for the "remote" so the test doesn't hit the network.)

### v1.5-5 — naive search script

**Files:** `plugin/scripts/search_naive.py` (new), tests/run_smoke.py

3-pass scan: index.md, frontmatter, body. Tier filter via `--tier`. Deterministic ranking: title-match > tag-match > body-match-count > recency. JSON output.

**Acceptance:**
- Smoke test runs `search_naive.py --query attention --wiki tests/fixture` and asserts top result has `attention` in title or tags.

### v1.5-6 — SKILL.md build script

**Files:** `scripts/build_skill_md.py` (new — note this is at repo root, not plugin/scripts)

Concatenates `plugin/skills/*/SKILL.md` into root `SKILL.md` with a generated header. Idempotent: running twice produces no diff.

**Acceptance:**
- After running once, `git diff SKILL.md` is non-empty (initial generation).
- After running twice in a row, second `git diff` is empty.
- Build script has a `--check` flag that exits nonzero if SKILL.md is out of date — wire into CI.

### v1.5-7 — Version bump + CHANGELOG

**Files:** `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `SKILL.md` frontmatter, `CHANGELOG.md`

Bump to `1.5.0`. Add CHANGELOG section: scripts wired, CI green, naive search, image handling, schema cross-field, single source of truth.

**Acceptance:**
- All four files agree on `1.5.0`.
- CHANGELOG entry uses the same format as 1.4.0.

---

## v1.6 GATE — Dogfood decisions confirmed

PRD §7 records the first dogfood decisions: LLM application innovation
scope, dated candidate outputs, `/schedule` documentation only, frozen
weights, and fast-cycle resurgence (`90d / min_count 2`).

Proceed with v1.6 tasks and dogfood without further product gate.

---

## Phase v1.6 — Auto-dreaming v0

### v1.6-1 — LLM application innovation domain template

**Files:** `templates/market_research/SCHEMA.md`, `templates/market_research/index.md`

Starter SCHEMA.md for the first dogfood domain: AI / large-model
application innovation. The template directory remains
`market_research` for compatibility, but the content is narrowed to
products, frameworks, patterns, research briefs, discussions, and
application-facing model signals. Includes categories, taxonomy, custom
dimensions (`launch_date`, `company_status`, `maturity`, `signal_type`,
`evidence_level`), and the dreaming block.

**Acceptance:**
- `schema_validate.py --file templates/market_research/SCHEMA.md` returns valid.
- Documented in README / docs as the v1.6 dogfood template.

### v1.6-2 — wiki_lib extensions

**Files:** `plugin/scripts/wiki_lib.py`

Add: log entry parser, watermark IO, increment extraction (entities + tags), resurgence detection.

**Acceptance:**
- New unit-test-style assertions in tests/run_smoke.py covering each function.
- Functions documented with docstrings.

### v1.6-3 — Build dreaming fixture

**Files:** `tests/build_dreaming_fixture.py`, `tests/dreaming_fixtures/market_research/expected.json`

~80 pages following the spec in TRD §8. 5–8 planted recent ingests. Hand-curated `expected.json`.

**Acceptance:**
- `python tests/build_dreaming_fixture.py --domain market_research` generates the fixture.
- Total pages ≥ 70, planted recent ingests ≥ 5.
- `expected.json` validates as JSON and has both `should_repromote` and `should_stay_frozen` populated.

### v1.6-4 — wiki_dream.py

**Files:** `plugin/scripts/wiki_dream.py` (new)

Implement scoring per TRD §3. CLI: `--wiki PATH [--since DATE] [--strategy co-occurrence] [--apply --pages 1,2] [--explain PAGE]`. JSON output.

**Acceptance:**
- Runs against the fixture and produces JSON.
- `--explain` mode prints reasons for one page even if it's not a top candidate.
- `--apply` writes `tier_override` and a log entry; without `--apply`, nothing is written.

### v1.6-5 — Eval runner + CI gate

**Files:** `tests/run_dreaming_eval.py` (new), `.github/workflows/test.yml` (extend)

Implement eval per TRD §9. CI step with `--gate` flag exits nonzero on threshold miss.

**Acceptance:**
- Eval prints precision, recall, reason-quality.
- `--gate` exits 1 if `precision < 0.7` or `recall < 0.5` (numbers from PRD §4).
- Initial run on the fixture should already pass these (prove the algorithm + fixture are coherent).

### v1.6-6 — wiki-dream skill

**Files:** `plugin/skills/wiki-dream/SKILL.md` (new)

User-invokable skill that calls `wiki_dream.py`. Implementation block exactly like v1.5-1.

**Acceptance:**
- Skill exposes `--apply`, `--explain`, `--pages`.
- README "Skills" table updated to 10 skills (was 9).

### v1.6-7 — Schema validation for dreaming block

**Files:** `schema/wiki-schema.json`, `plugin/scripts/schema_validate.py`

Add the `dreaming:` block schema per TRD §4. Cross-field rules from v1.5-3 (which can be implemented before this if order is convenient).

**Acceptance:**
- `schema_validate.py` rejects malformed dreaming blocks (negative weights, threshold > 1, unknown strategy).

### v1.6-8 — Dogfood loop bootstrap

**Not a code task — a setup task for the maintainer.**

Set up litianyi's actual LLM application innovation wiki with v1.6
dreaming enabled. Schedule weekly. Begin 4-week dogfood window before
announcing v1.6. The first scenario covers research, information
acquisition, synthesis, and discussion around AI / large-model
application innovation.

**Acceptance:**
- Real wiki has dreaming enabled in SCHEMA.md using the dogfood baseline:
  `entity 0.5 / tag 0.2 / citation 0.4 / threshold 0.6 / dormancy 90d / min_count 2`.
- Weekly execution method configured: Claude `/schedule`, cron /
  Task Scheduler, or explicit manual weekly run.
- Notes file `docs/dogfood-v1.6.md` started, capturing each week's accept/reject ratio and surprises.
- `docs/dogfood-guide-v1.6.md` exists as the maintainer execution guide.

### v1.6-9 — Documentation

**Files:** `README.md`, `docs/dreaming.md` (new)

README: add "Auto-dreaming" section between "Memory tiers" and "External fallback plugins". Tagline: "the wiki tends itself between sessions". Link to `docs/dreaming.md` for depth.

**Acceptance:**
- README has the new section.
- `docs/dreaming.md` covers: what it is, what it isn't (no session input, no auto-apply), how to configure, how to disable, how to write your own strategy.

### v1.6-10 — Version bump + CHANGELOG

**Files:** version files + CHANGELOG

Bump to `1.6.0`.

**Acceptance:**
- All version files agree.
- CHANGELOG entry covers the dreaming feature, the new fixture, the new CI gate, and links to PRD/TRD.

---

## After v1.6 ships

- Begin 4-week dogfood window. **Bug fixes only on v1.6 surfaces** during the window.
- v1.7 development (raw watcher) runs **in parallel** — code-isolated from dreamer.
- At week 4: review accept/reject log. Tuning, v1.8 strategies, and v1.7 public release all gate on this.

---

## Phase v1.7 — Raw watcher (parallel with v1.6 dogfood)

Companion: [PRD-v1.7-watcher.md](PRD-v1.7-watcher.md) · [TRD-v1.7-watcher.md](TRD-v1.7-watcher.md)

### v1.7-1 — wiki_watch.py daemon

**Files:** `plugin/scripts/wiki_watch.py` (new)

Stdlib polling daemon. Cross-platform daemon detachment. CLI surface per TRD §7.

**Acceptance:**
- Foreground `watch` mode runs and prints heartbeat every poll cycle.
- `--daemon` mode forks/detaches and writes pid file.
- `status` returns JSON with pid, started_at, queue summary.
- `stop` reads pid, sends SIGTERM, waits for clean exit.
- `queue list / mark / remove / prune` round-trip queue state.

### v1.7-2 — wiki-watch skill

**Files:** `plugin/skills/wiki-watch/SKILL.md` (new)

User-invokable skill. Modes: `--start`, `--stop`, `--status`, `--drain`,
`--remove <id>`. Implementation block with concrete bash invocations.

**Acceptance:**
- All five modes documented with example output.
- Drain logic specified: skill calls `wiki-ingest` per queued path,
  marks status, appends single log entry.
- Implementation block names `plugin/scripts/wiki_watch.py` as source of truth.

### v1.7-3 — Smoke test for watcher

**Files:** `tests/run_smoke.py` (extend)

Four assertions per TRD §9: detection, remove, min-size skip, debounce.

**Acceptance:**
- Smoke test grows from 22 to ~26 assertions.
- Tests use 1-second debounce for fast iteration.
- No flake (assertions stable across 5 consecutive runs).

### v1.7-4 — README + docs/watcher.md

**Files:** `README.md` (extend), `docs/watcher.md` (new)

README adds an "Auto-ingest from raw/" section between "Auto-dreaming"
and "External fallback plugins".

`docs/watcher.md` covers:
- Daemonization recipes for systemd / launchd / Windows Task Scheduler
- Cron pattern as alternative to long-running daemon
- Queue lifecycle (pending → processed / failed / removed)
- Why polling (no third-party deps)
- How to recover from a crashed daemon (delete pid file, re-start)

### v1.7-5 — Version bump 1.7.0 + CHANGELOG

**Files:** version files + CHANGELOG.md

**Acceptance:**
- `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `SKILL.md` all show `1.7.0`.
- CHANGELOG entry covers watcher daemon, queue, drain pattern.
- Skill table regenerates with `wiki-watch` (12 skills total).

---

## After v1.7 ships

- Continue v1.6 dogfood through week 4.
- v1.7 watcher is OK to merge to main but not to publicly announce — that's
  still gated on dogfood.
- v1.8 starts only after dogfood retrospective: more dreaming domains
  (citational, temporal) per the original plan.
