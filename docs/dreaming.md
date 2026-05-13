# Auto-dreaming

> The wiki maintains itself between sessions.

Auto-dreaming periodically re-evaluates **frozen and archived pages**
against the wiki's recent activity and surfaces those whose relevance has
resurfaced. It runs without you (cron, weekly by default), produces a
review file in `dreaming/{YYYY-MM-DD}.md`, and **never auto-promotes**
without your explicit `--apply`.

This is the only kata feature that runs without a human in the loop.
Designed conservatively: dry-run by default, capped at 10 candidates per
run, silently ignored rejections cost nothing.

## What it solves

Any wiki you run for more than 18 months ends up with hundreds of pages
in the archived/frozen tier. The market doesn't know about your tier
system — old companies get acquired, dead architectures get revived, an
old paper becomes hot again. Without dreaming, **you have to remember
manually** that those old pages exist. Karpathy says LLMs absorb
maintenance work; this is the most valuable maintenance work that has
no other automation pathway.

## Inputs (filesystem-only)

The dreamer reads exactly three things, all from your wiki directory:

1. `log.md` entries since the last `## [date] dream | …` watermark
2. Wiki pages with `ingested_at` or `updated` ≥ that watermark
3. The frozen + archived pool — the candidates to evaluate

It does **not** read:
- Claude Code session history. _Architecturally rejected:_ the wiki is a
  function of files only, so `git clone` reproduces the dreamer's output
  on any machine. Session-coupled dreaming would break that.
- External APIs, embeddings, or web data
- Anything outside `{wiki_path}/`

If you want session content to influence dreaming, file it back to the
wiki via `/wiki-query --file` first. That's the existing path for
"sessions become wiki pages."

## How scoring works (co-occurrence strategy, v1.6)

For each frozen/archived page _p_, compute a score in [0, ~1.1]:

```
score(p) =   weights.entity   · min(|p_entities ∩ fresh_entities| / 2,  1)
           + weights.tag      · min(|p_tags ∩ resurgent_tags|     / 1,  1)
           + weights.citation · min(|fresh_pages_linking_to_p|    / 1,  1)
```

A page is a **candidate** if `score >= confidence_threshold` (default 0.6),
sorted by score descending, capped at `max_repromote_per_run` (default 10).

**Three signals, in priority order:**
- **Entity overlap.** A fresh ingest mentions the page's title, stem, or
  any of its own outbound links. Strongest signal — a new article about
  Mosaic gives mosaic.md instant priority.
- **Citation hit.** A fresh page contains `[[wikilink]]` directly to the
  candidate. This is "the agent that ingested last week's news judged
  this connection worth a link" — that's high-quality signal.
- **Tag resurgence.** A tag appears ≥ `min_count` times in the increment,
  AND was absent from the prior `dormancy_window_days` window. Captures
  trend revivals (e.g. `#multimodal` going dormant for 6 months then
  showing up in 4 ingests in one week).

Default weights `0.5 / 0.2 / 0.4` mean: a single citation alone (0.4) is
not enough; entity overlap + citation (0.65) just clears the threshold;
two of three signals always crosses; all three signals push above 0.9.

## Configuration

```yaml
# SCHEMA.md
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
    dormancy_window_days: 180
    min_count: 3
```

Tune via `wiki-config`:

```bash
/wiki-config --set dreaming.confidence_threshold 0.55
/wiki-config --set dreaming.weights.citation 0.5
/wiki-config --explain dreaming.confidence_threshold
```

## Disabling

```bash
/wiki-config --set dreaming.enabled false
# or remove dreaming: from SCHEMA.md by hand
```

When disabled, `wiki-dream` exits 0 with a notice. No state is touched.

## Cadence

Weekly is the right default for market research and most slow-moving
domains. Daily makes sense for fast news domains (where the increment
density is high enough to benefit from finer windows). Manual is fine
when you don't want it on a cron.

For the v1.6 dogfood scenario — AI / large-model application innovation
research — the weekly cadence stays, but the resurgence window is
shorter: `dormancy_window_days: 90`, `min_count: 2`. Application
patterns and frameworks cycle in months, not half-years.

`wiki-init` writes a recommended `claude /schedule` line based on the
chosen cadence — you confirm before it runs.

```bash
# Weekly Sunday 23:00
claude /schedule "0 23 * * 0" "/kata:wiki-dream"

# Daily 06:00
claude /schedule "0 6 * * *" "/kata:wiki-dream"
```

## Domain support

| Domain | Status | Strategy |
|--------|--------|----------|
| LLM application innovation (products, frameworks, patterns, briefs, discussions) | **Dogfooding in v1.6** | co-occurrence |
| Market research (broader AI tech / companies / papers) | Planned v1.8 | co-occurrence + temporal |
| Research papers (arxiv-driven academic wikis) | Planned v1.8 | citational |
| Code knowledge bases | Planned v1.8 | structural (call-graph) |
| Personal / journal | Deferred — ground truth too fuzzy | temporal-pattern |

Each strategy has its own benchmark fixture under
`tests/dreaming_fixtures/<domain>/` with a `precision >= 0.7,
recall >= 0.5` CI gate. Picking the wrong strategy for your domain just
means "not many useful candidates" — never "wrong candidates aggressively
applied."

## Security and privacy

- **No network calls.** The dreamer is purely local file IO.
- **No frontmatter mutation without `--apply`.** Default is dry-run; the
  candidate file goes to `dreaming/{date}.md` for human review.
- **`--apply` is per-page selective.** `--apply --pages 1,3` promotes only
  candidates 1 and 3 from the most recent run; others are silently
  rejected and won't re-appear unless their score recomputes ≥ threshold
  on a future run.
- **Reverts available via git.** Every promotion is a frontmatter edit
  + a log.md entry. `git revert` undoes both.

## Reject signals (v1.6: passive)

If a candidate is suggested and you don't `--apply` it, that's a passive
reject. v1.6 does not consume reject signals back into the algorithm —
the same page may be suggested again next run if its score still clears
the threshold. v1.7+ will add `dreaming-feedback.log` consumption to
suppress repeat-rejected candidates.

## Why not just embeddings?

A vector-search dreamer would ask "which old pages are semantically near
this week's ingests?" That trades precision for recall — embeddings
hallucinate "similar" pages that share surface keywords but not actual
relevance. Co-occurrence is **what the wiki agent actually wrote** as
links, in pages that survived an explicit ingest pass. That's a much
higher-quality signal than vector cosine.

We may add embeddings as a tie-breaker for low-confidence candidates in
v1.8+, gated behind a strategy flag. The default will remain
co-occurrence.

## See also

- [PRD](PRD-v1.6-autodreaming.md) — product requirements + success metrics
- [TRD](TRD-v1.6-autodreaming.md) — technical design + algorithm details
- `tests/dreaming_fixtures/market_research/` — benchmark fixture and ground truth
- `plugin/scripts/wiki_dream.py` — implementation
