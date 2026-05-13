# v1.6 Dogfood — Auto-dreaming on LLM application innovation wiki

> Per PRD §4: ship-readiness gate is **4 weeks** of real-wiki use with
> ≥ 60% acceptance rate, ≤ 10 candidates/run, zero `--apply` to wrong
> page. This file is the running log.

## Status

**As of 2026-05-07: Pending — dogfood window has not yet started.**

The setup table below still has placeholders. Until the wiki path,
"dreaming enabled on" date, and day-1 page counts are filled in, **no
weekly retrospective has comparable data**. Tuning, v1.8 announcement,
and any v1.7 backlog remain blocked by this.

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
| Wiki path | _<fill in: e.g. `~/llm-app-innovation-wiki`>_ |
| Dreaming enabled on | _<fill in: YYYY-MM-DD>_ |
| Dogfood window | 4 weekly runs from first scheduled run |
| Cadence | weekly · Sunday 23:00 |
| Scenario | LLM application innovation: research, source acquisition, synthesis, discussion |
| Initial config | `entity 0.5 / tag 0.2 / citation 0.4 / threshold 0.6 / dormancy 90d / resurgence min_count 2` |
| Total wiki pages on day 1 | _<fill in>_ |
| Tier distribution on day 1 | active __ / archived __ / frozen __ |
| Execution host | Claude Code / Codex CLI / standalone LLM / mixed |
| Schedule method | Claude `/schedule` / cron / Task Scheduler / manual weekly |
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

### Week 1 — YYYY-MM-DD

**Run summary**

- Candidates: __ / pool size __
- Fresh pages this period: __
- Resurgent tags: __
- New raw sources ingested: articles __ / papers __ / transcripts __ / external __
- New synthesis pages: briefs __ / comparisons __ / trends __
- New discussion pages: __
- Runtime: __

**Disposition**

| # | Page | Score | Reasons (short) | Decision | Notes |
|---|------|-------|-----------------|----------|-------|
| 1 |      |       |                 | ✅/❌    |       |
| 2 |      |       |                 | ✅/❌    |       |
| 3 |      |       |                 | ✅/❌    |       |

**Surprises** — pages I'd forgotten existed, or connections I hadn't seen:

-

**Tuning thoughts** — would I want a different threshold / weight if I
were running this for a year?

-

**Bugs / annoyances** — anything the script did that felt wrong:

-

**Scenario fit** — did this help the LLM app-innovation workflow?

- Research direction clarified: yes / no. Notes:
- Information acquisition improved: yes / no. Notes:
- Discussion reuse improved: yes / no. Notes:

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
