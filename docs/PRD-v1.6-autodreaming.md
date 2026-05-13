# PRD — Auto-dreaming v0 (LLM Application Innovation domain)

**Status:** Draft · 2026-04-25
**Author:** litianyi
**Targets:** kata v1.6
**Owner:** kata maintainer

## 1. Problem

An LLM application-innovation wiki accumulates hundreds of pages over
time: products, frameworks, patterns, companies, model releases that
shape apps, research briefs, and discussion notes. After 12–24 months,
many pages drop into the `archived` / `frozen` tier — out of sight by
default. But the AI/LLM application market is **non-linear**:

- An old company gets acquired and matters again (Mosaic → Databricks)
- An "obsolete" architecture gets revived (MoE in 2024)
- A 2-year-old paper becomes the basis for a hot new technique
- A dormant tag (`#multimodal`) suddenly gets 6 new ingests in a week

Without dreaming, the user must **manually remember** that these old
pages exist. That's exactly the maintenance burden Karpathy says LLMs
should absorb. Auto-dreaming fills the gap: while the user sleeps, the
agent re-evaluates which frozen pages have become relevant again.

## 2. Goal & non-goals

**Goal:** Ship a usable auto-dreamer for one first domain (LLM
application innovation) that hits **precision ≥ 0.7** and **recall ≥
0.5** on a benchmark fixture, and that the maintainer can dogfood on a
real AI / large-model application-innovation wiki for ≥ 4 weeks without
subjective failure ("the candidates are mostly noise").

**Non-goals:**
- Personal/journal/fiction domains (v1.8+).
- Auto-applying re-promotions without human review (v0 is dry-run by default).
- Pruning or deleting frozen content (never automatic; this is a separate v2 feature called "auto-pruning").
- Cross-wiki dreaming (v2.0).
- Session-history-based dreaming. The wiki remains a function of files only.

## 3. Personas & user stories

**Primary persona — LLM application researcher / builder (P1).** Tracks
model releases when they affect applications, product launches,
framework shifts, adoption patterns, source digests, and reusable
discussion conclusions. Wiki has 200–800 pages, ingests 3–10 sources per
week, and files selected session outputs back into `briefs/` and
`discussions/`.

**User stories:**

| # | Story |
|---|-------|
| US-1 | _As P1, after my Sunday-evening ingest batch, I want to see "5 frozen app-innovation pages might matter again — here's why" so I can spot patterns I'd missed._ |
| US-2 | _As P1, when DeepSeek-V3 drops, I want the dreamer to remind me my MoE/Switch-Transformer pages are relevant context for writing about it — without me having to remember they exist._ |
| US-3 | _As P1, I want to reject a re-promotion suggestion and have that signal improve future suggestions, not be silently lost._ |
| US-4 | _As P1, I want to understand WHY a page was suggested — "co-occurs with X in this week's ingest" not "score 0.73"._ |
| US-5 | _As P1, I want research briefs and filed-back discussions to affect future dreaming once they are saved as wiki pages._ |
| US-6 | _As P1, I want to run the dreamer manually OR have it run weekly without me, my choice._ |

## 4. Success metrics

**Quantitative (CI gate):**
- Benchmark fixture precision ≥ **0.7** (of pages dreamer suggested, ≥ 70% are correct re-promotes per ground truth)
- Benchmark fixture recall ≥ **0.5** (of pages that should be re-promoted, dreamer catches ≥ 50%)
- Runtime ≤ **30 s** on a 500-page fixture (p99)

**Qualitative (4-week dogfood):**
- ≥ 60% of suggested re-promotions accepted by maintainer
- ≤ 10 candidates per weekly run on a 500-page wiki (no spam)
- Zero false `--apply` write to wrong page (correctness over recall)

**Anti-metrics (intentionally NOT optimized):**
- Number of re-promotions per week. More is not better.
- Coverage of frozen pages. Dreamer is allowed to ignore most of them.

## 5. Scope

### In scope (v1.6)
- One strategy: `co-occurrence + tag-resurgence` (hybrid).
- One domain template: LLM application innovation under the existing
  `market_research` template id (products/frameworks/patterns/companies/
  models/launches/trends/comparisons/benchmarks/briefs/discussions/queries).
- Manual + scheduled execution paths.
- Dry-run by default; explicit `--apply` to write `tier_override`.
- Reject signal captured in `dreaming-feedback.log` (read by future tuning, not used in v0).
- CI benchmark with synthetic fixture.

### Out of scope (v1.6)
- Other strategies (citational, structural, temporal).
- Other domains.
- LLM-judge evaluation (v1 is rule-based scoring).
- Auto-`--apply` mode.
- Reject-signal feedback loop into algorithm (logged but not consumed).

## 6. UX

### Default flow

```
$ /kata:wiki-dream

[Dreaming] since 2026-04-18 (last run)

Found 4 candidates:

1. [[mixture-of-experts]]  (frozen, 18 mo)
   Why: linked from new ingest [[deepseek-v3]] AND [[deepseek-v3]] cites
        switch-transformer; tag #moe had 3 new ingests this week
   Confidence: 0.82
   ↑ promote to active   ↓ keep frozen   ✎ explain more

2. [[mosaic]]  (archived, 8 mo)
   Why: appears in new ingest "Databricks acquires MosaicML"; co-occurs
        with [[mpt-7b]] which was active this week
   Confidence: 0.75
   ↑ promote   ↓ keep   ✎ explain more

3. [[switch-transformer]]  (frozen, 20 mo)
   Why: co-occurs with mixture-of-experts (HIGH-confidence candidate above)
   Confidence: 0.61
   ↑ promote   ↓ keep   ✎ explain more

4. [[constitutional-ai]]  (archived, 11 mo)
   Why: tag #alignment had 4 new ingests this week
   Confidence: 0.58
   ↑ promote   ↓ keep   ✎ explain more

[Suggested next]
→ /kata:wiki-dream --apply --pages 1,2   (promote selected)
→ /kata:wiki-dream --explain mixture-of-experts
```

### Scheduled flow

`claude /schedule "0 23 * * 0" "/kata:wiki-dream"` → every Sunday 23:00.
Output written to `dreaming/{YYYY-MM-DD}.md` in wiki root; user reviews
Monday morning.

### Failure modes
- Wiki has no frozen pages → "Nothing to dream about. Try ingest more sources."
- Watermark not found (first run) → look back 30 days
- log.md missing → exit with error pointing at SCHEMA setup

## 7. Dogfood decisions

Confirmed for the first 4-week dogfood window:

1. **Fixture entity names.** Use realistic AI / LLM application entities
   where helpful, but fixtures and dogfood notes must not be presented as
   market recommendations.
2. **CI thresholds.** Keep precision ≥ 0.7 and recall ≥ 0.5.
3. **Candidate output format.** Use dated `dreaming/{YYYY-MM-DD}.md` so
   weekly review history is preserved.
4. **Cron integration.** Document the `/schedule` recipe; do not
   auto-write schedules during dogfood.
5. **Co-occurrence weights.** Freeze dogfood defaults at entity 0.5, tag
   0.2, citation 0.4, threshold 0.6.
6. **Fast-cycle resurgence.** For LLM application innovation, use
   `dormancy_window_days: 90` and `min_count: 2` during dogfood. Tune
   only after week 4.

## 8. Risks

| Risk | Mitigation |
|------|-----------|
| Algorithm doesn't reach precision 0.7 on fixture | v0 falls back to `--strategy=conservative` (entity-only, no tag-resurgence). CI threshold drops to 0.5; ship with caveat. |
| Fixture is too easy (gives 0.95 precision but real wiki gives 0.4) | Run dogfood eval in parallel; weekly subjective review |
| Dreamer suggests too many candidates, becomes noise | Hard cap `max_repromote_per_run` (default 10). Confidence threshold raises if user rejects 5 in a row |
| Maintainer doesn't dogfood for 4 weeks, can't validate qualitative goals | Build dreaming into the maintainer's actual workflow before announcing v1.6 to users |

## 9. Dependencies

- v1.5 must ship first (skills→scripts wiring, naive search, image handling). Dreamer relies on `wiki_lib.py` page discovery and graph build.
- No external services. Pure stdlib + the existing scripts.
