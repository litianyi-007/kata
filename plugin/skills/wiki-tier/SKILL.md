---
name: wiki-tier
description: "Inspect and manage the memory-tier system: view the active/archived/frozen distribution, preview a threshold change before committing, update SCHEMA.md thresholds, and pin manual tier overrides on specific pages."
user-invocable: true
argument-hint: "[--show] [--set-active=Nd] [--set-archived=Nd] [--set-field=published_at|ingested_at] [--preview] [--pin=<page>:<tier>] [--unpin=<page>] [--list=<tier>] [--disable] [--enable]"
---

# wiki-tier

Manage the wiki's three-tier memory system. Raw content and wiki pages are
bucketed into `active | archived | frozen` by age, and most query skills
default to `--tier=active`. This skill is how you inspect that distribution,
adjust the thresholds, and pin individual pages that shouldn't follow the
automatic rule.

> **Why tiers:** old sources don't just become irrelevant — they become
> _noise_. Filtering them out of the default query surface is how the wiki
> keeps compounding without diluting. Frozen content is not deleted; it's
> just parked.

## Model

- Tiers are **computed on-the-fly** from a date field per `SCHEMA.md`
  `memory_tiers:` block. They are **not** stored as frontmatter — that would
  silently drift whenever a threshold changes. The filesystem is the only
  source of truth; the tiers are always in sync with the current config.
- **Driving field:** per SCHEMA.md, typically `published_at` with a fallback
  to `ingested_at` when `published_at` is missing.
- **Wiki-page inheritance:** a wiki page's tier is **the most recent tier
  across its cited sources** — any one active source pulls the whole page
  into active. This keeps synthesis pages on the hot path as long as fresh
  sources back them.
- **Manual override:** a page may set `tier_override: frozen` (or `active`,
  `archived`) in its frontmatter to bypass the automatic rule. Lint and
  digest respect pins.

## When to use

- "Show me the tier distribution"
- "Push the active window out to 2 years"
- "Pin this page to active — it's the canonical reference even though the
  source is old"
- "Which pages just aged out?"
- "Disable tiers — I don't want this right now"

## Implementation

Tier computation is in `plugin/scripts/tier_compute.py`. **The script is the
source of truth; the prose below explains its behavior.** Don't recompute
tiers by reading frontmatter dates yourself — shell out and format the JSON.

```bash
# Show config + distribution + pinned overrides (default mode)
python {plugin_root}/scripts/tier_compute.py --wiki {wiki_path} --show

# Preview a threshold change without writing SCHEMA.md
python {plugin_root}/scripts/tier_compute.py --wiki {wiki_path} \
    --preview --set-active 540 --set-archived 1095

# List every page in the frozen tier
python {plugin_root}/scripts/tier_compute.py --wiki {wiki_path} \
    --list frozen
```

**What the script does NOT do** — and the skill must:
- Apply confirmed threshold changes by editing `SCHEMA.md`'s `memory_tiers`
  block (the script previews; the skill writes when the user confirms).
- Pin/unpin individual pages by editing their frontmatter (`tier_override:`).
- Append to `log.md` after any change.

`{plugin_root}` resolves to the directory containing `.claude-plugin/`.

## Pre-flight

```
read_file {wiki_path}/SCHEMA.md    # for memory_tiers block
```

If `memory_tiers.enabled: false`, only `--enable` and `--show` are meaningful;
other flags emit a warning.

## Modes

### `--show` (default when no other flag is set)

Print the current tier configuration and distribution:

```
[Operation] wiki-tier | show

[Config]
enabled:        true
active_days:    365
archived_days:  730
driving_field:  published_at (fallback: ingested_at)

[Distribution]
Tier       Pages   Raw sources   Oldest            Newest
active       142           87   2025-04-12        2026-04-12
archived      53           41   2024-04-12        2025-04-11
frozen        19           22   2019-01-03        2024-04-11

[Pinned overrides]
entities/rope.md → tier_override: active  (pinned 2026-02-10 — canonical reference)
...

[Recently aged out]
Since last --show, 7 pages crossed active → archived:
  - entities/model-v1.md  (published_at: 2025-04-10)
  - concepts/early-rlhf.md
  ...
```

### `--set-active=Nd` / `--set-archived=Nd` / `--set-field=...`

Stage a threshold change and **preview the delta** before committing:

```
Proposed: active_days 365 → 540
This will:
  + 31 pages move archived → active
  − 0 pages move active → archived
  Net: +31 active, −31 archived

Apply to SCHEMA.md? [y/n]
```

Thresholds take effect immediately after write — there's no re-indexing step
because tiers are computed on-the-fly. Combine with `--preview` to print the
delta without asking to apply.

### `--preview`

Run a hypothetical threshold change without writing SCHEMA.md. Accepts the
same set flags and prints the would-be distribution + migration list:

```
kata:wiki-tier --preview --set-active=180d --set-archived=365d
```

Useful for "what would tighten look like" before committing.

### `--pin=<page>:<tier>` / `--unpin=<page>`

Write or clear a `tier_override:` field on a specific wiki page:

```
kata:wiki-tier --pin=entities/rope.md:active
kata:wiki-tier --unpin=entities/rope.md
```

Updates just that page's frontmatter and appends a log entry. Pins are the
escape hatch for "this page is canonical even though its source is old".

### `--list=<tier>`

List every page in a given tier. Useful for spot-checking:

```
kata:wiki-tier --list=frozen
# entities/early-transformer.md  (2019-01-03)
# concepts/word2vec.md            (2019-06-15)
# ...
```

Combine with `--focus=<tag>` to scope (e.g. "show me all frozen pages tagged
`deprecated`").

### `--disable` / `--enable`

Toggle the entire tier system. Writes `memory_tiers.enabled: false|true` to
SCHEMA.md. When disabled, all query skills stop filtering by tier and the
distribution section disappears from `wiki-digest`.

Disabling does **not** touch any page frontmatter — pins remain as recorded,
they just become no-ops until re-enabled.

## Log entry

Every tier change (threshold update, pin, unpin, enable, disable) writes a
log entry:
```
## [YYYY-MM-DD] tier | {action}
- Change: active_days 365 → 540
- Affected: 31 pages (archived → active)
```

## Notes for the agent

- Tier changes are **safe** — they're pure re-interpretations of existing
  dates, not mutations of the underlying content. The only files touched are
  SCHEMA.md (threshold changes) and individual pages (pin/unpin).
- Never auto-prune frozen content. The future plan is an **auto-dreaming**
  layer that revisits frozen sources periodically and re-promotes any that
  still matter; v1 of the plugin does not implement that. Frozen = parked,
  not deleted.
- If the user asks "what happens to frozen content?", answer: it stays
  queryable via `--tier=frozen` or `--tier=all`, but never appears in default
  searches. Think of it as cold storage with instant retrieval.
- Tier computation is cheap — a few hundred pages is milliseconds — so running
  `--show` as a warm-up at the start of a session is reasonable.

## Output

```
[Operation] wiki-tier | {mode}

[Changes]
- SCHEMA.md: {active_days: 365 → 540}
- Pinned: entities/rope.md → active
- ...

[Summary]
{1–2 sentence summary of the effect}

[Suggested next]
→ kata:wiki-digest             (to see post-change state)
→ kata:wiki-tier --list=frozen (to spot-check what got demoted)
```
