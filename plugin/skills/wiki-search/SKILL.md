---
name: wiki-search
description: "Search the wiki by keyword, tag, topic, or type. Returns ranked results with page summaries and matching excerpts. Defaults to active-tier content when memory tiers are enabled. No orientation required — runs directly against wiki files."
user-invocable: true
argument-hint: "<query> [--tag=<tag>] [--type=entity|concept|comparison|query] [--limit=10] [--tier=active|all|archived|frozen]"
---

# wiki-search

Fast, ranked search across compiled wiki pages. Unlike a raw file search, this
understands wiki structure — it searches frontmatter tags, page titles, content, and
cross-link density to return the most relevant results.

Does **not** require session orientation — can run cold.

## Path resolution (read this first)

`{wiki_path}` is resolved by `wiki_lib.find_wiki_root()` — the same 9-step
resolver every other skill uses (see `plugin/scripts/wiki_lib.py:482-568`):
explicit `--wiki` → `$WIKI_PATH` → cwd ancestor with `SCHEMA.md`+`log.md` →
`$LLM_WIKI_PROJECT` under `$LLM_WIKI_HOME` → nearest `.llm-wiki.yaml` /
`.kata.yaml` → `~/.llm-wiki/registry.yaml` → git-root-name as
`~/.llm-wiki/{repo}` → legacy `~/.kata/config.yaml` → default
`~/.llm-wiki/common`.

**Operational contract — do not violate:**

- **Delegate path resolution to `search_naive.py`.** Call it **without
  `--wiki`** by default; the script self-resolves via `find_wiki_root()`.
  Pass `--wiki <path>` only when the user explicitly supplies one in the
  skill args.
- **Do not** read `SCHEMA.md` / `index.md` / `log.md` as a precondition.
  Their absence in cwd is **not** evidence that the wiki is unavailable —
  the wiki very likely lives at `~/.llm-wiki/<project>/`, not in cwd. Those
  three files are `wiki-init` / `wiki-query`'s precondition, not yours.
- **Do not** invent fallbacks ("degrade to low confidence", "continue from
  source code", "wiki unavailable"). wiki-search is a hard query: either
  the script returns results, or path resolution fails and you report it
  with an actionable fix (see "When path resolution fails" below).

## When to use

- User asks "find pages about X", "search for Y", "what do we have on Z"
- During `wiki-ingest` to check existing coverage before creating pages
- During `wiki-query` to locate relevant pages before synthesizing an answer
- Any time the user wants to navigate the wiki by topic

## Implementation

`plugin/scripts/search_naive.py` is the source of truth for the 3-pass
scan + ranking. **Use it instead of re-implementing the algorithm.** The
script returns deterministic JSON; the skill formats it for the user.

```bash
# Default — omit --wiki and let the script self-resolve via find_wiki_root()
python {plugin_root}/scripts/search_naive.py \
    --query "attention mechanism"

# With tier and type filters
python {plugin_root}/scripts/search_naive.py \
    --query "RLHF" --tier all --type concept --limit 20

# Tag filter
python {plugin_root}/scripts/search_naive.py \
    --query "transformer" --tag architecture

# Only pass --wiki when the user supplied an explicit path in skill args
python {plugin_root}/scripts/search_naive.py --wiki {explicit_path} \
    --query "transformer"
```

Note: omitting `--wiki` is the default. The script calls `find_wiki_root()`
internally (see Path resolution above) and walks the full resolver chain.
Do **not** prefix the call with your own SCHEMA.md/log.md existence check.

The script handles tier-aware filtering, per-pass result merging, and
ranking (title > tag > body > recency). The skill's job after the call:

- Format each hit with title / type / tags / excerpt / related links
- If results are thin (`<3` hits) and tier filter was implicit, surface
  the script's `suppressed_other_tiers` count and recommend `--tier=all`
- Suggest follow-ups (`wiki-query` to synthesize, `wiki-graph --neighbors`
  to explore structure)

When `qmd` is in PATH, prefer it over this script (deferred — qmd
integration lands in v1.8+).

## Steps

⓪ **Resolve wiki path (delegated):**
   Call `search_naive.py` without `--wiki` (or with the user-supplied
   explicit path). The script runs `find_wiki_root()` internally and
   returns deterministic JSON. **Do not** read SCHEMA.md / index.md /
   log.md as an orientation precondition — wiki-search runs cold by
   design (see frontmatter description and "Path resolution" above).
   If the script exits non-zero, follow "When path resolution fails" at
   the end of this file — do not invent a "degrade / low confidence"
   fallback.

① **Parse the query:**
   - Extract search terms, any `--tag` filter, `--type` filter, `--limit` (default 10)
   - Identify if it's a keyword search, tag lookup, or conceptual question
   - `--tier` filter: default is `active` when SCHEMA.md has
     `memory_tiers.enabled: true`, otherwise `all`. Accept `active`, `all`,
     `archived`, `frozen`. If the user did not pass `--tier` and results are
     thin (<3 hits), **mention** in the summary that expanding to `--tier=all`
     might surface older matches (don't auto-expand — that's a surprise).

② **Search pass 1 — index.md scan:**
   Read `index.md` and find all entries whose one-line summary or title matches the
   query terms. This gives fast, broad results.

   ```bash
   # Pseudo-code
   read_file {wiki_path}/index.md
   # Find lines matching query terms (case-insensitive)
   ```

③ **Search pass 2 — frontmatter scan:**
   For pages not caught by index.md, scan frontmatter of wiki pages for tag matches:
   - Match `tags:` fields against `--tag` filter
   - Match `type:` field against `--type` filter
   - Match `title:` against query terms

   ```bash
   search_files "{query}" path="{wiki_path}" file_glob="**/*.md"
   # Exclude raw/ directory
   ```

④ **Search pass 3 — content scan** (if Pass 1+2 return < 3 results):
   Full-text search across wiki page bodies:
   ```bash
   search_files "{query}" path="{wiki_path}" file_glob="entities/**/*.md"
   search_files "{query}" path="{wiki_path}" file_glob="concepts/**/*.md"
   search_files "{query}" path="{wiki_path}" file_glob="comparisons/**/*.md"
   search_files "{query}" path="{wiki_path}" file_glob="queries/**/*.md"
   ```

⑤ **Filter by tier** (before ranking):
   - Compute each candidate's tier on-the-fly per SCHEMA.md `memory_tiers`
     (driving field → age → `active`/`archived`/`frozen`; honor
     `tier_override:` frontmatter pins)
   - Drop any page whose tier does not match the `--tier` filter
   - If tier filtering removes every candidate but there would be results at
     other tiers, surface that fact in step ⑦

⑥ **Rank results** by (higher wins at each level):
   1. Title-term match count
   2. Frontmatter tag-term match count
   3. **Hub centrality** — `|in_edges| + 0.5·|out_edges|`. At parity on
      title/tag, the page that is referenced more across the wiki sorts
      higher (matches the script's `hub_score`).
   4. Body match frequency
   5. Recency (`updated` date)
   6. Path (deterministic tiebreak)

⑦ **Format results** — for each result, show:
   - File path (relative to wiki root)
   - Title and type
   - Matching tags
   - One-line summary (from index.md if available, else first sentence of page)
   - Matching excerpt (3–5 lines around first content match)
   - Related pages (outbound wikilinks in the matching page)

⑧ **No results handling:**
   If no matches found: suggest alternative search terms, check spelling, and offer
   to run `wiki-lint` to verify index completeness. If the query had an active-tier
   filter (explicit or default) and there would be matches at other tiers, say so:
   > "No active-tier matches. 4 matches in archived, 2 in frozen. Re-run with
   > `--tier=all` to include them."

## When path resolution fails

Two failure modes — keep them distinct:

**1. Script exits non-zero / raises (wiki not resolvable).**

`find_wiki_root()` could not land on any path. Report a **hard failure**
with the actual candidates checked and an actionable fix. Example output:

> wiki-search: wiki path could not be resolved.
> Checked (in order): `$WIKI_PATH`, ancestors of cwd (for SCHEMA.md+log.md),
> `$LLM_WIKI_PROJECT` under `$LLM_WIKI_HOME`, nearest `.llm-wiki.yaml` /
> `.kata.yaml`, `~/.llm-wiki/registry.yaml`, `~/.llm-wiki/<git-root-name>`,
> legacy `~/.kata/config.yaml`, default `~/.llm-wiki/common`.
>
> Fix one of these:
> - Drop `wiki_path: ~/.llm-wiki/<project>` into a `.llm-wiki.yaml` at the
>   project root (and add it to `.gitignore` — per-machine state).
> - Add a `projects:` entry in `~/.llm-wiki/registry.yaml`.
> - Set `WIKI_PATH=~/.llm-wiki/<project>` in the environment.
> - Or `cd` into the wiki directory before re-running.

**2. Script exits 0 with `total: 0` and empty `results`.**

Wiki **was** resolved (path is fine) but no pages matched the query. This is
the normal "no results" case — go to Step ⑧ "No results handling". It is
**not** a path problem and must not be reported as one.

### Forbidden behavior (do not emit any of these)

Both failure modes above and the success path forbid the following — every
one was the source of a real bug where wiki-search misled the user:

- ❌ "Wiki unavailable / degrading to low confidence / 降级为不可用 / 低置信"
- ❌ "Continuing from source code instead" / "falling back to current sources"
- ❌ Treating missing SCHEMA.md / index.md / log.md **in cwd** as evidence
  that the wiki doesn't exist. The wiki almost always lives at
  `~/.llm-wiki/<project>/`, not in cwd.
- ❌ Inventing any "partial / degraded / best-effort" mode. wiki-search
  either resolves a wiki and returns results (possibly empty), or hard-fails
  with the resolver report above. There is no third state.

## Output

```
[Operation] wiki-search | "{query}"

[Results] {N} pages found

1. [{Title}](entities/title.md) — type: entity | tags: [tag1, tag2]
   {One-line summary}
   > "...{matching excerpt}..."
   Related: [[page-a]], [[page-b]]

2. [{Title}](concepts/title.md) — type: concept | tags: [tag3]
   ...

[Summary]
Found {N} pages matching "{query}". {Top result} is the most central page on this topic.

[Suggested next]
→ kata:wiki-query "{query}"  (to synthesize an answer from these pages)
```

---

## Scaling up

The built-in three-pass scan (index → frontmatter → content) works well at
**Karpathy's stated sweet spot: ~100 sources, a few hundred pages**. Beyond that
you'll want a proper search engine.

### Option A — [qmd](https://github.com/tobi/qmd) (recommended)

`qmd` is a local search engine for markdown files with **hybrid BM25 + vector
search and LLM re-ranking**, all on-device. Two integration modes:

- **CLI mode** — if `qmd` is in `PATH`, `wiki-search` shells out for Pass 2 and
  Pass 3 instead of doing its own full-text scan. Index `qmd index {wiki_path}`
  once, then `qmd search "{query}"` returns ranked results.
- **MCP server mode** — expose `qmd` as a native tool via its MCP server. The
  agent calls it directly like any other tool, bypassing the built-in scanner
  entirely. Best for wikis with 1000+ pages.

`wiki-search` auto-detects `qmd` at runtime. If found, it uses qmd; if not, it
falls back to the built-in scan. You get the same API regardless.

### Option B — custom script

For domain-specific needs (e.g. searching frontmatter dates for time-windowed
queries, or searching only within certain categories), vibe-code a small search
script. The built-in `search_files` tool is a fine base — Karpathy explicitly
suggests this:
> "You could also build something simpler yourself — the LLM can help you
> vibe-code a naive search script as the need arises."

### When to upgrade

| Wiki size | Tool |
|-----------|------|
| < 100 pages | Built-in 3-pass scan — the index is enough |
| 100–500 pages | Built-in scan, but run `wiki-lint` more often to keep index.md current |
| 500–2000 pages | Install `qmd`, use CLI mode |
| 2000+ pages | Install `qmd` with MCP server mode |

`wiki-search` falls back to the built-in scan if `qmd` is absent — no
external tool is ever required. (This is the *qmd vs. built-in* fallback,
unrelated to wiki-path resolution failure, which is always a hard error
per "When path resolution fails".)

