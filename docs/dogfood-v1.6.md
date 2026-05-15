# v1.6 Dogfood — Auto-dreaming on LLM application innovation wiki

> Per PRD §4: ship-readiness gate is **4 weeks** of real-wiki use with
> ≥ 60% acceptance rate, ≤ 10 candidates/run, zero `--apply` to wrong
> page. This file is the running log.

## Status

**As of 2026-05-14: Running on NECallKit wiki (week 1, day 7 of 28).**

Window scope shifted: the original framing was an "LLM application
innovation" research wiki, but the actual v1.6 capability is being
exercised on `~/.llm-wiki/NECallKit` since 2026-05-08 in parallel
with the NECallKit HN-essay dogfood (see
[`dogfood-necallkit-hn-essay.md`](dogfood-necallkit-hn-essay.md)).
This is the real validation surface; the LLM-app-innovation wiki
remains un-bootstrapped.

- `~/.llm-wiki/NECallKit/SCHEMA.md` → `dreaming.enabled: true`
- `~/.llm-wiki/NECallKit/dreaming/` → 6 daily run files
  (2026-05-08 → 2026-05-13)
- Window: **2026-05-08 → ~2026-06-05** (28 days from enable date)
- Acceptance scoring (this file's weekly disposition tables): **not
  yet filled in** — see Week 1 below for the first real entry.

Tuning, v1.8 announcement, and v1.7 backlog remain gated on the
acceptance scoring completing — not on usage, which is happening.

> **Original framing notes (kept for context):** The text below was
> written when this doc was scoped to the LLM-app-innovation research
> wiki. The "Setup" / "Scenario" / "Frozen parameters" blocks still
> describe the *intended* config and the *frozen* dreamer parameters
> for the validation window. The "Action required from the maintainer"
> startup checklist is no longer the active path — NECallKit already
> bootstrapped via a different route. Weekly logs below use NECallKit
> as the real corpus.

> **v1.8 sync also Pending** — see `docs/dogfood-v1.8.md`. Recommended
> plan: **run both windows in parallel on the same wiki, same 4 weeks**.
> The cron line `wiki-sync --auto && wiki-dream` covers both. Combined
> dogfood lets us observe (1) dreaming candidate quality AND (2) sync
> churn / driver merge frequency on the same content stream — they
> share a single time investment instead of doubling it.

Action required from the maintainer (combined v1.6 + v1.8 startup):

1. Pick the live wiki path (recommended: `~/.llm-wiki/<project>` — the
   v1.7.2 multi-project layout). Same path on both machines.
2. Bootstrap the wiki with both flags on:
   - **Fresh wiki**: `python plugin/scripts/wiki_init.py --path ...
     --enable-dreaming --enable-sync` (or `--template market_research
     --enable-sync`; the template already ships dreaming on so
     `--enable-dreaming` is implicit there)
   - **Existing wiki**: `python plugin/scripts/wiki_init.py --refresh-id
     --path ...` (injects `wiki_id`, refreshes `.gitignore` /
     `.gitattributes`). Then hand-edit SCHEMA.md to add the `dreaming:`
     and `sync:` blocks (see "Frozen parameters" below for v1.6 dreaming
     and `dogfood-v1.8.md` for v1.8 sync), then
     `python plugin/scripts/schema_validate.py --wiki ...` to verify.
3. Configure git remote on machine A and clone on machine B (see
   `dogfood-v1.8.md` step 3-4 for exact commands).
4. Schedule weekly runs (staggered to reduce push race):
   - Machine A cron: `0 23 * * 0  cd ~/.llm-wiki/<project> &&
     wiki-sync --auto && wiki-dream`
   - Machine B cron: `30 23 * * 0  cd ~/.llm-wiki/<project> &&
     wiki-sync --auto && wiki-dream`
5. Fill the setup table below AND `dogfood-v1.8.md` setup table with
   day-1 numbers and the actual start date.

Once started, the 4-week clock runs forward — *do not tune frozen
parameters mid-window* (see "Frozen parameters" further down).

## Scenario

Scenario under review: research, information acquisition, synthesis, and
discussion around **AI / large-model application innovation**. This keeps
the v1.6 dogfood narrower than general AI market research: the primary
question is whether old application patterns, frameworks, products, and
discussion notes resurface at the right time when new sources arrive.

## Setup

| | |
|---|---|
| Wiki path | `~/.llm-wiki/NECallKit` (real corpus, ~110 pages as of 2026-05-12) |
| Dreaming enabled on | 2026-05-08 |
| Dogfood window | 4 weeks from enable = 2026-05-08 → ~2026-06-05 |
| Cadence | daily run cadence (see `dreaming/` files), not weekly |
| Scenario | NECallKit multi-platform SDK monorepo — Web/Electron/Mobile reuse, bugfix preflight, spec authoring |
| Initial config | `entity 0.5 / tag 0.2 / citation 0.4 / threshold 0.6 / dormancy 90d / resurgence min_count 2` (frozen) |
| Total wiki pages on day 1 | ~50 (grew to ~110 by 2026-05-12) |
| Tier distribution on day 1 | mostly active at start; archived layer grew as 2026-04-20 reuse work crystallized |
| Execution host | Codex CLI (Codex Desktop sessions) + Claude Code mixed |
| Schedule method | manual + cron on the NECallKit dogfood host |
| Execution guide | [dogfood-guide-v1.6.md](dogfood-guide-v1.6.md) |

## Scenario boundaries

**In this dogfood window:**

- Research pages: `briefs/`, `comparisons/`, `trends/`
- Information acquisition: `raw/articles/`, `raw/papers/`,
  `raw/transcripts/`, `raw/external/` drained through watcher / ingest.
  This includes exported Grok / external LLM sessions when they contain
  reusable research value.
- Discussion outputs: `discussions/` pages created from reusable session
  conclusions, hypotheses, and follow-up questions
- Application-innovation entities: `products/`, `frameworks/`,
  `patterns/`, `companies/`, `models/` when they affect application
  behavior or product strategy

**Out of this first window:**

- Core model research that is not tied to application behavior
- General tech market tracking
- Personal notes / journal behavior
- Auto-apply of any dream candidate

## Frozen parameters for the window

Do not tune these until the week-4 retrospective:

```yaml
dreaming:
  enabled: true
  strategy: co-occurrence
  cadence: weekly
  max_repromote_per_run: 10
  confidence_threshold: 0.6
  weights:
    entity: 0.5
    tag: 0.2
    citation: 0.4
  resurgence:
    dormancy_window_days: 90
    min_count: 2
```

Rationale: LLM app patterns cycle faster than broad market-research
entities, so tag dormancy is shorter and a two-source resurgence can be
meaningful. The threshold and weights stay conservative until real usage
proves otherwise.

## How to use this file

After each weekly run:

1. Open `dreaming/{YYYY-MM-DD}.md` produced by the run.
2. For each candidate, decide accept (`--apply --pages N`) / reject (do
   nothing) / unsure.
3. Fill in the week's section below — **especially the "surprises" and
   "tuning thoughts" bullets**, those are the v1.7 backlog.
4. Don't tune config mid-window. Let four weeks run on the same settings;
   tune at the retrospective.
5. File reusable research-session output into `briefs/` or
   `discussions/` before the next run; otherwise the dreamer cannot see
   the discussion.

## Weekly logs

### Week 1 — 2026-05-08 → 2026-05-14

**Run summary** (NECallKit corpus, daily dreaming runs)

- Daily run files: `dreaming/2026-05-08.md` through `dreaming/2026-05-14.md` (7 files, full Week 1 coverage)
- Wiki pages: ~50 day-1 → 119 by Week 1 end (+69, 1.4× scale)
- Trigger pattern: 6 of 7 days produced 0 candidates; 1 day (**2026-05-12**) produced a burst of 7 candidates
- The 2026-05-12 burst was triggered by the prior day's heavy ingest
  (F011 master-merge-back-preflight + offline-message contract +
  electron-android switchCallType update) plus same-day kata
  self-meta wiki multi-machine work
- **Cron cadence: clean** — 7/7 daily files present at expected
  timestamps (22:00 server time); automation has not missed a day

**Disposition** — 2026-05-12 burst, retroactive review at 2026-05-15

Effective acceptance signal across two channels:

- `wiki-dream --apply` (the dreamer's native action) — **0/7 invoked**
- `wiki-tier --pin` with `tier_override: active` (permanent override) —
  **1/7 effectively accepted** (candidate #4)

| # | Page | Score | Reasons (short) | Decision | Notes |
|---|------|-------|-----------------|----------|-------|
| 1 | `decisions/electron-switchcalltype-remediation-history.md` | 0.9 | Entity overlap with `electron-camera-switch-microphone-state-regression-bugfix-set` + `electron-web-api-reuse-and-merge-back-switch-contract` | ❌ | Silent reject; remains archived. Re-evaluate if a fresh switchCallType regression bug arrives. |
| 2 | `decisions/necallkit-docs-guides-electron-flutter-merge-review-checklist.md` | 0.9 | Linked from new F011 master-merge-back-preflight | ❌ | Silent reject; merge-review checklist is fresh-pull-only, doesn't need active surface. |
| 3 | `modules/002-electron-callkit-contracts-electron-node-nim-boundary.md` | 0.9 | Entity overlap + linked from `necallkit-docs-guides-electron-merge-impact-baseline` and `necallkit-offline-message-contract-and-electron-link-2026-05-11` | ❌ | Silent reject; the boundary contract is stable but the *active* surfaces are the page set already linked from it. |
| 4 | `modules/necallkit-architecture-overview.md` | 0.9 | Linked from new merge-impact-baseline | ✅ | **Accepted via `wiki-tier --pin` on 2026-05-14** (one of 4 architecture pages pinned). Note: pinned, NOT bumped via `--apply`. |
| 5 | `queries/002-electron-callkit-example-contract-boundary-query.md` | 0.9 | Entity overlap with node-nim-boundary + reuse-operating-boundary | ❌ | Silent reject; query page, not architecture invariant — natural fit for archived tier. |
| 6 | `queries/necallkit-electron-web-reuse-operating-boundary-query.md` | 0.9 | Entity overlap + linked from new switch-contract module | ❌ | Silent reject; same rationale as #5. |
| 7 | `features/002-electron-callkit-electron-reference-alignment-nim-uikit-electron.md` | 0.65 | Linked from offline-message contract | ❌ | Silent reject; reference-alignment is a one-time historical note, not a recurring touch point. |

**Effective accept rate**: 1/7 = **14%** (channel: `tier_override: active`).
**Native channel accept rate**: 0/7 = **0%** (channel: `--apply`).

PRD §4 acceptance gate is 60%. Week 1 is **below the gate on both channels**,
but the data calls into question whether `--apply` is the right primitive
for the acceptance signal at all (see Surprises below).

**Surprises** — pages I'd forgotten existed, or connections I hadn't seen:

- **wiki-search archived-tier signal is load-bearing.** Codex
  session 2026-05-14 (id `019e2234-61d2-7a13-ad96-bf0388531a42`) ran
  3 search queries for an Electron Vue2 reuse spec; 28/30 top hits
  were `archived`. The archived layer correctly gave the
  Web/Electron architecture boundary (`packages/` shared core +
  thin wrappers) that grounded the entire final spec
  recommendation. Detailed log in
  [`dogfood-necallkit-hn-essay.md`](dogfood-necallkit-hn-essay.md)
  under "2026-05-14 — wiki-search natural experiment".
- **Vue2 was a coverage gap the wiki never named.** The agent had to
  infer it from "all queries returned archived." A coverage-matrix
  dreamer (idea logged in `docs/idea-coverage-matrix-dreamer.md`)
  would have flagged stack=Vue2 × platform=Electron as an empty cell
  with surrounding active coverage on Vue3.
- **Channel mismatch — dreamer's accept primitive vs user's real
  action.** PRD §4 assumes the accept signal is `wiki-dream --apply`
  (one-shot tier bump). Across the only candidate-burst this Week 1
  (2026-05-12, 7 candidates), **0 `--apply` invocations** occurred,
  yet **1 candidate was meaningfully accepted** via
  `wiki-tier --pin` with `tier_override: active` — a permanent
  override, not a one-shot bump. The dreamer's UI offers `--apply`
  as the canonical accept action, but for the case the dogfood is
  actually exercising (stable architecture facts re-surfaced because
  fresh ingests link to them), the right action is permanent pin,
  not transient bump. v1.6 retrospective should either redefine the
  accept primitive or have the dreamer emit both options per
  candidate.
- **Algorithmic trigger is sparse but accurate when it fires.** 6/7
  days produced 0 candidates and 1/7 fired with 7 candidates at
  threshold ≥0.9. That's not a bug — co-occurrence requires
  multi-page fresh ingests to trigger, and most days only had
  single-page activity. When it fired, the architectural-overview
  page in the burst was independently confirmed via wiki-tier pin
  two days later. Algorithm correctly surfaced what mattered; the
  channel for "yes, accept this" was what missed.

**Tuning thoughts** — would I want a different threshold / weight if I
were running this for a year?

- **Do not change frozen parameters this window.** `entity 0.5 / tag 0.2 / citation 0.4 / threshold 0.6 / dormancy 90d / resurgence min_count 2` stay locked through 2026-06-05.
- Two ergonomic fixes to `search_naive.py` are queued (not
  dreamer-config changes, so within-window-safe):
  1. add `tier_breakdown` aggregate to JSON envelope
  2. fix `_excerpt()` body-bias — current output is heading-noise
- **v1.7+ idea** (post-window): coverage-matrix dream strategy as a
  second strategy alongside co-occurrence. Sketched at
  `docs/idea-coverage-matrix-dreamer.md`.

**Bugs / annoyances** — anything the script did that felt wrong:

- `search_naive.py` excerpt is title + section header, not body content
- no aggregate tier breakdown — agent must scan all results to see pattern
- no "low active coverage" hint when archived/active ratio is extreme

**Scenario fit** — did this help the NECallKit dogfood workflow?

- Research direction clarified: yes. Wiki architecture boundary
  framed the Vue2 spec recommendation; agent didn't need to
  re-derive it from scratch.
- Information acquisition improved: partial. Vue3 reuse covered;
  Vue2 gap forced source archeology (3 source files read after wiki
  miss).
- Discussion reuse improved: yes. Unified contract decision
  (`electron-web-unified-public-contract.md`) was picked up and
  carried into spec open questions.

### Week 2 — YYYY-MM-DD

(same template)

### Week 3 — YYYY-MM-DD

(same template)

### Week 4 — YYYY-MM-DD

(same template)

## Cumulative metrics (filled in at week 4)

| Metric | Target | Actual | Pass? |
|--------|--------|--------|-------|
| Total candidates emitted | — | __ | — |
| Total accepted | — | __ | — |
| Acceptance rate | ≥ 60% | __% | ☐ |
| Median candidates/run | ≤ 10 | __ | ☐ |
| Max candidates in a single run | ≤ 10 (cap) | __ | ☐ |
| `--apply` to wrong page (had to revert) | 0 | __ | ☐ |
| Genuinely useful "I'd forgotten" finds | qualitative | __ | — |

## Retrospective (week 4)

**What worked.**

-

**What didn't.**

-

**Scenario observations.** (Did the app-innovation workflow expose
false-positive patterns that aren't visible in the synthetic fixture?
Did source acquisition, synthesis, or discussion pages behave differently?)

-

## Decisions for v1.6 GA / v1.7 backlog

Tick what to do **after** the dogfood window:

- [ ] Adjust `confidence_threshold` from 0.6 to ___. Reason: _____
- [ ] Adjust weights to `entity __ / tag __ / citation __`. Reason: _____
- [ ] Update fixture `expected.json` to capture missed scenarios: _____
- [ ] Implement reject-signal feedback (consume `dreaming-feedback.log`)
  in v1.7 algorithm — yes / no / wait
- [ ] Add second strategy (`citational` / `temporal`) to address: _____
- [ ] File bugs as separate issues: _____
- [ ] Update `docs/dreaming.md` "limitations" section with what we
  learned: _____

## Notes for week-N me

- The fixture in CI is synthetic — guarantees the algorithm is
  internally consistent but says nothing about real-world fit. **This
  file is the only signal that matters for shipping v1.6 to others.**
- Don't expand to other domains (academic papers, code, personal) until
  LLM application innovation has cleared this gate. Adding a second
  strategy when the first hasn't dogfooded is how products end up
  shipping mediocre defaults.
- A run that produces 0 candidates is not a bug. It means the
  increment didn't shake any old pages loose. Note it but don't tune.
- `git log --grep='dream | applied'` shows exactly what was promoted
  over time — useful for spotting drift if `--apply` decisions feel
  arbitrary in retrospect.
