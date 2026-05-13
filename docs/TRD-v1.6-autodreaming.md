# TRD — Auto-dreaming v0 (LLM Application Innovation domain)

**Status:** Draft · 2026-04-25
**Companion:** [PRD-v1.6-autodreaming.md](PRD-v1.6-autodreaming.md)

## 1. Architecture

```
                    ┌──────────────────────────┐
                    │  log.md (since watermark) │
                    │  + git diff of wiki pages │
                    │  + frozen/archived pool   │
                    └────────────┬──────────────┘
                                 │ read-only
                                 ▼
              ┌──────────────────────────────────────┐
              │  plugin/scripts/wiki_dream.py        │
              │  ───────────────────────────────     │
              │  1. parse increment → entity set E   │
              │  2. parse increment → tag set T      │
              │  3. for each frozen/archived page p: │
              │       score = w_e·entity_overlap(p,E) │
              │             + w_t·tag_resurgence(p,T) │
              │             + w_c·citation_hit(p,…)   │
              │  4. emit candidates score≥threshold   │
              └────────────┬─────────────────────────┘
                           │ JSON
                           ▼
              ┌──────────────────────────────────────┐
              │  wiki-dream skill (thin wrapper)      │
              │  ───────────────────────────────      │
              │  - shows candidates with explanations │
              │  - dry-run by default                  │
              │  - --apply writes tier_override:active │
              │  - logs reject signals to feedback.log │
              └────────────┬─────────────────────────┘
                           │
                           ▼
              ┌──────────────────────────────────────┐
              │  Wiki state changes:                  │
              │  - dreaming/{YYYY-MM-DD}.md            │
              │  - tier_override frontmatter on apply │
              │  - log.md: ## [date] dream | run      │
              │    (also serves as next watermark)    │
              │  - dreaming-feedback.log (rejects)    │
              └──────────────────────────────────────┘
```

## 2. Data flow — concrete

**Watermark.** Each `wiki-dream` run appends to `log.md`:

```markdown
## [2026-04-25] dream | weekly run
- Window: 2026-04-18 to 2026-04-25 (7 days)
- Candidates emitted: 4
- Applied (tier_override): 0 (dry-run)
- Rejected: 0
- Watermark: 2026-04-25T23:01:00Z
```

Next run reads the most recent `## [date] dream | run` entry's
watermark line and only considers log entries newer than it.

**Increment extraction:**

```python
since = read_watermark(log_md) or (today - 30 days)

new_log_entries = [e for e in parse_log(log_md) if e.date > since]

# Entities from new wiki pages and updated pages
new_or_updated = git_diff_or_mtime(wiki_root, since)
entities_in_increment = union(extract_wikilinks(p.body) for p in new_or_updated)
tags_in_increment = union(p.frontmatter.tags for p in new_or_updated)

# Tag resurgence: a tag that appears in the increment more than k times
# but had been dormant (no occurrences in the previous Δ window)
resurgent_tags = compute_resurgence(tags_in_increment, log_md,
                                    dormancy_window=180, min_count=3)
```

## 3. Scoring algorithm

```python
def score(page, increment):
    s = 0.0
    reasons = []

    # Entity overlap: page's wikilinks ∪ page's title appears in increment entities
    page_entities = set(page.out_links) | {page.title.lower()}
    overlap = page_entities & increment.entities
    if overlap:
        s += W_ENTITY * min(len(overlap) / 3, 1.0)
        reasons.append(f"shares entities {overlap} with new ingests")

    # Tag resurgence: any of page's tags resurged
    page_tags = set(page.frontmatter.get("tags") or [])
    resurged = page_tags & increment.resurgent_tags
    if resurged:
        s += W_TAG * min(len(resurged) / 2, 1.0)
        reasons.append(f"tags {resurged} resurged this period")

    # Citation hit: a new page has a [[wikilink]] directly to this page
    direct_links = increment.direct_inbound_links_to(page)
    if direct_links:
        s += W_CITATION * min(len(direct_links) / 2, 1.0)
        reasons.append(f"directly linked from new pages {direct_links}")

    return s, reasons


W_ENTITY    = 0.5    # primary signal
W_TAG       = 0.2    # supporting signal — resurgence is rarer but weaker
W_CITATION  = 0.4    # strong but rare — direct citation
THRESHOLD   = 0.6    # below this, not a candidate
```

Scores are bounded to ~1.0 in the common case; theoretical max ≈ 1.1.
The threshold 0.6 means a strong single signal (entity overlap of 3+
items) qualifies, but a single weak signal does not.

## 4. Schema additions

`SCHEMA.md` gains a `dreaming:` block. JSON-Schema in `schema/wiki-schema.json`
extended:

```yaml
dreaming:
  enabled: true
  strategy: co-occurrence       # only valid value in v1.6
  cadence: weekly               # weekly | daily | manual
  max_repromote_per_run: 10
  confidence_threshold: 0.6
  weights:
    entity: 0.5
    tag: 0.2
    citation: 0.4
  resurgence:
    dormancy_window_days: 90     # dogfood preset for fast LLM app cycles
    min_count: 2
  watermark_field: dream         # log.md action name to use as watermark
```

`schema_validate.py` adds:

- `dreaming.strategy` must be `co-occurrence` in v1.6
- `dreaming.confidence_threshold` ∈ [0, 1]
- `dreaming.max_repromote_per_run` ≥ 1
- weights are floats ≥ 0

## 5. Components & file inventory

| Path | Purpose | New / changed |
|------|---------|---------------|
| `plugin/scripts/wiki_dream.py` | dreamer entry point | NEW |
| `plugin/scripts/wiki_lib.py` | page discovery, log parser | EXTENDED (parse_log_entries, watermark IO) |
| `plugin/skills/wiki-dream/SKILL.md` | user-invokable skill | NEW |
| `schema/wiki-schema.json` | dreaming block validation | EXTENDED |
| `tests/dreaming_fixtures/market_research/` | fixture wiki + ground truth | NEW |
| `tests/dreaming_fixtures/market_research/expected.json` | ground truth | NEW |
| `tests/build_dreaming_fixture.py` | fixture builder | NEW |
| `tests/run_dreaming_eval.py` | benchmark runner; computes precision/recall | NEW |
| `templates/market_research/SCHEMA.md` | starter template wiki-init can copy; content targets LLM application innovation | NEW |
| `templates/market_research/index.md` | starter index for the dogfood wiki | NEW |
| `.github/workflows/test.yml` | CI runs both smoke + dreaming eval | EXTENDED |

## 6. Algorithm details

### 6.1 Log parser

`log.md` is append-only with `## [date] action | subject` headers.
Parser yields `(date, action, subject, body_lines)` tuples in order.

### 6.2 Increment extraction

- **Source 1:** new entries in log.md after watermark (mostly ingest events; their `Created:` and `Linked to:` lines list new pages and references)
- **Source 2:** wiki page mtime > watermark (catches manual edits)
- Union → set of "fresh" pages
- For each fresh page: extract title, frontmatter tags, body wikilinks
- Aggregate to `(entities, tags)` over the whole increment

### 6.3 Resurgence detection

A tag is "resurgent" if:
- Count of pages with this tag among `dormancy_window_days` ago→now is ≥ `min_count`
- AND count of pages with this tag in the equivalent window before that was 0

Computed by walking page frontmatter once with date-binning. O(n) over all wiki pages.

### 6.4 Candidate selection

- For each frozen + archived page (skip active — already on hot surface):
  - Compute score per §3
  - If score ≥ threshold → candidate
- Sort candidates by score descending
- Cap at `max_repromote_per_run`
- Emit JSON: `[{page, score, reasons, current_tier}, ...]`

### 6.5 Apply path

`wiki-dream --apply --pages 1,2` writes:

```yaml
# in candidate page's frontmatter
tier_override: active
tier_override_reason: "auto-dream 2026-04-25: shares entities {...}"
tier_override_set_at: 2026-04-25
```

And appends to `log.md`:

```markdown
## [2026-04-25] dream | applied 2 candidates
- Promoted: [[mixture-of-experts]], [[mosaic]]
- Reason: weekly co-occurrence dreamer (run 2026-04-25)
```

### 6.6 Reject signal

`wiki-dream --reject 3,4` (or interactive UI) appends to `dreaming-feedback.log`:

```
2026-04-25T23:05:12Z reject  switch-transformer  score=0.61  reasons=[...]
2026-04-25T23:05:14Z reject  constitutional-ai   score=0.58  reasons=[...]
```

This file is **logged but not consumed** by v0 algorithm. It exists so v1.7+ can replay rejects and adjust weights. Format chosen for grep-ability and append-only safety.

## 7. Performance

- Discovery: O(n) over wiki pages (already in `wiki_lib.discover_pages`)
- Log parse: O(L) where L = lines in log.md
- Scoring: O(F × E) where F = frozen+archived pages, E = entities in increment. For F=500, E=50: 25k operations. < 100 ms.
- Total budget: **< 30 s for 500-page wiki** (PRD success metric).

## 8. Benchmark fixture spec

`tests/dreaming_fixtures/market_research/` keeps the historical fixture
id, but the dogfood-facing template is narrowed to LLM application
innovation:

```
SCHEMA.md                       # LLM application innovation domain config
log.md                           # base log + planted recent ingests
index.md
companies/
  anthropic.md      (active, 2 mo)
  openai.md         (active, 1 mo)
  mosaic.md         (archived, 9 mo)        ← should re-promote
  cohere.md         (archived, 11 mo)
  ada.md            (frozen, 25 mo)         ← should NOT re-promote
  ...
models/
  gpt-4.md, claude-3.md (active, recent)
  mpt-7b.md          (archived, 9 mo)        ← should re-promote (Mosaic)
  switch-transformer (frozen, 20 mo)         ← should re-promote (DeepSeek)
  word2vec.md        (frozen, 30 mo)         ← should NOT re-promote
  ...
papers/
  attention-is-all-you-need.md (frozen, 28 mo) ← should NOT re-promote
  ...
trends/
  multimodal.md     (frozen, 15 mo)          ← should re-promote (tag resurgence)
briefs/
  application-innovation-map.md               ← research synthesis page
discussions/
  open-questions.md                           ← filed-back discussion page
  ...
queries/
raw/
  articles/_recent/
    2026-04-22-databricks-acquires-mosaic.md   ← planted recent ingest
    2026-04-23-deepseek-v3-paper.md            ← planted recent ingest
    2026-04-24-multimodal-roundup.md           ← planted recent ingest
    ... (5–8 total)
expected.json                   # ground truth
```

`expected.json`:

```json
{
  "as_of_watermark": "2026-04-21",
  "should_repromote": [
    {"page": "companies/mosaic.md", "min_score": 0.6, "reason_must_include": ["mpt-7b"]},
    {"page": "models/mpt-7b.md",     "min_score": 0.6},
    {"page": "models/switch-transformer.md", "min_score": 0.6,
     "reason_must_include": ["deepseek-v3"]},
    {"page": "trends/multimodal.md", "min_score": 0.5,
     "reason_must_include": ["resurged"]}
  ],
  "should_stay_frozen": [
    "companies/ada.md",
    "models/word2vec.md",
    "papers/attention-is-all-you-need.md",
    "..."
  ]
}
```

Total: ~80 pages, 5–8 planted recent ingests, ~20 ground-truth labels (mix of should/should-not).

## 9. Eval algorithm

```python
def eval_run(fixture_dir, dream_output):
    expected = load(fixture_dir / "expected.json")

    promoted = {c["page"] for c in dream_output["candidates"]}
    should = {x["page"] for x in expected["should_repromote"]}
    should_not = set(expected["should_stay_frozen"])

    true_positives  = promoted & should
    false_positives = promoted & should_not
    false_negatives = should - promoted

    precision = len(true_positives) / len(promoted) if promoted else 0
    recall    = len(true_positives) / len(should)   if should   else 0

    # Reason quality: each true positive's reasons must include the
    # required substrings from expected.json
    reason_quality = check_reasons(dream_output, expected)

    return {"precision": precision, "recall": recall,
            "reason_quality": reason_quality, ...}
```

## 10. CI integration

`.github/workflows/test.yml`:

```yaml
- name: Smoke tests
  run: python tests/run_smoke.py
- name: Dreaming benchmark — LLM application innovation
  run: python tests/run_dreaming_eval.py --fixture market_research --gate
  # --gate makes nonzero exit if precision < 0.7 or recall < 0.5
```

## 11. Open technical decisions (not blocking PRD signoff)

- **Log parser robustness.** `## [YYYY-MM-DD]` is the documented format but ad-hoc real wikis may drift. Be liberal in parsing, conservative in writing.
- **Watermark storage.** Currently in `log.md` itself (`Watermark:` line). Alternative: separate `.dream-state.json`. Going with log.md for human-readability and grep-ability.
- **Tier override expiry.** Auto-applied `tier_override: active` from dreamer should arguably expire after N weeks if no further activity, otherwise the wiki accumulates "permanently active" pages. Out of scope for v1.6; addressed in v1.7.
