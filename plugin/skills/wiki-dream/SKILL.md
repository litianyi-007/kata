---
name: wiki-dream
description: "Auto-dreaming: re-evaluate frozen and archived pages against recent activity, surface candidates whose relevance has resurfaced, optionally promote them back to the active tier. Reads only the wiki filesystem (log.md + page frontmatter dates ingested_at/updated); never reads chat sessions or file mtimes. Designed for market-research wikis but the strategy is pluggable."
user-invocable: true
argument-hint: "[--since YYYY-MM-DD] [--strategy co-occurrence] [--apply --pages 1,2,3] [--explain <page>] [--out <file>]"
---

# wiki-dream

While you sleep, the wiki re-evaluates which old pages have become relevant
again. The dreamer reads new ingest entries from `log.md` since the last
dream watermark, identifies entities/tags/citations they bring up, and scores
every frozen/archived page against that signal. Pages above the threshold
become **candidates** — surfaced for your review, never auto-promoted by
default.

> Auto-dreaming is the only thing in kata that runs without you. It is
> intentionally conservative: dry-run by default, capped at 10 candidates
> per run, and silently rejecting bad suggestions costs nothing — they
> just don't appear next time.

## Implementation

The algorithm is in `plugin/scripts/wiki_dream.py`. **The script is the
source of truth; the prose below explains its behavior.** The skill calls
the script and renders the result.

```bash
# Default — read watermark from log.md, write candidates to dreaming/{date}.md
python {plugin_root}/scripts/wiki_dream.py --wiki {wiki_path}

# Override window — dream over a specific period
python {plugin_root}/scripts/wiki_dream.py --wiki {wiki_path} \
    --since 2026-04-01

# Explain why one specific page did or didn't qualify
python {plugin_root}/scripts/wiki_dream.py --wiki {wiki_path} \
    --explain mosaic

# Apply — write tier_override:active to selected candidates
python {plugin_root}/scripts/wiki_dream.py --wiki {wiki_path} \
    --apply --pages 1,2,3
```

The candidate file is written to `dreaming/{YYYY-MM-DD}.md` (one per run,
preserved historically). The skill should also surface the JSON to the user.

## Inputs the dreamer reads (and ignores)

**Reads (only):**
- `log.md` entries since the last `## [date] dream | ...` watermark
- Wiki pages with `ingested_at` or `updated` ≥ that watermark
- Frozen and archived pages (the candidate pool)
- `SCHEMA.md` `dreaming:` config block

**Does NOT read:**
- Claude Code session history
- External APIs, embeddings, web
- Anything outside `{wiki_path}`

If a user expects "dream from what we just talked about" — explain that the
dreamer is filesystem-only by design (architecture, not bug). To get
session content into the dreamer's view, file it back to the wiki via
`/wiki-query --file` first.

## Modes

### Default: dream

```
$ /kata:wiki-dream

[Dreaming] since 2026-04-21 (last weekly run)

Candidate pool: 36 (archived + frozen)
Fresh pages this period: 8
Resurgent tags: trend

Found 9 candidates above threshold 0.6:

1. [[mixture-of-experts]]   (frozen, score 0.90)
   - shares entities ['glam', 'moe-foundational-paper'] with new ingests
   - directly linked from new pages ['queries/deepseek-v3-paper-released.md']

2. [[mosaic]]                (archived, score 0.90)
   - shares entities ['mosaic', 'mpt-7b'] with new ingests
   - directly linked from new pages ['queries/databricks-acquires-mosaic.md']

... etc

[Suggested next]
→ /kata:wiki-dream --apply --pages 1,2,4    (promote selected)
→ /kata:wiki-dream --explain mosaic          (full scoring breakdown)
```

### `--apply --pages <list>`

Writes `tier_override: active` to the selected candidates' frontmatter,
plus a reason and timestamp. Appends a `## [date] dream | applied N
candidates` log entry advancing the watermark. **Never auto-runs** — must
be invoked explicitly with `--apply`.

### `--explain <page>`

Re-scores one specific page (regardless of whether it crossed the
threshold), printing each component (entity / tag / citation), the reason
strings, and the increment summary that drove it. Useful for debugging "why
didn't X get promoted?"

## Scheduled runs

Recommended weekly cadence. Set up via Claude Code `/schedule`:

```bash
claude /schedule "0 23 * * 0" "/kata:wiki-dream"
```

The wiki-init skill writes this cron line during interactive setup if the
user enables dreaming. The candidates land in `dreaming/{date}.md` for
review the next morning; nothing is applied without explicit user action.

## Configuration

All knobs live in SCHEMA.md `dreaming:`:

| Key | Default | Effect |
|-----|---------|--------|
| `enabled` | true | Set false to disable entirely |
| `strategy` | co-occurrence | Only `co-occurrence` in v1.6 |
| `cadence` | weekly | Drives the cron line |
| `confidence_threshold` | 0.6 | Lower for more candidates, higher for less noise |
| `max_repromote_per_run` | 10 | Hard cap |
| `weights.entity` | 0.5 | Weight for entity overlap |
| `weights.tag` | 0.2 | Weight for tag resurgence |
| `weights.citation` | 0.4 | Weight for direct inbound link from a fresh page |
| `resurgence.dormancy_window_days` | 180 | Tag must be silent this long before counting as resurgent |
| `resurgence.min_count` | 3 | Tag must appear in ≥ N fresh pages to count |

Tune via `/wiki-config --set dreaming.confidence_threshold 0.55`.

## Failure modes / no-op cases

- **No watermark in log.md** → dreamer looks back 30 days as a fallback.
- **No fresh pages since watermark** → emits 0 candidates with explanation;
  log entry still advances the watermark.
- **Wiki has no frozen/archived pages** → candidate_pool_size is 0;
  candidates is empty. Explain to the user: tier system needs to be
  enabled and pages need to age out for dreaming to have anything to do.

## Notes for the agent

- Always show BOTH the candidate list AND a 1-line summary of why
  dreaming had this signal (the increment summary). Without context the
  candidates look arbitrary.
- When the user says "yes promote X" — translate to `--apply --pages N`,
  not direct frontmatter edit. The script handles log entry + reason
  capture.
- Reject signals are not stored anywhere v1.6; the user just doesn't
  apply candidates they don't want. v1.7+ may add a feedback loop.
