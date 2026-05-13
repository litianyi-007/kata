from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "kata-prd-v1.10-external-searchable-sources-2026-05-11"
TODAY = date.today().isoformat()

SOURCE_FILES: tuple[PurePosixPath, ...] = (
    PurePosixPath("docs/PRD-v1.10-external-searchable-sources.md"),
)

NEW_FEATURE_PATH = PurePosixPath("features/kata-v1.10-external-searchable-sources.md")
NEW_QUERY_PATH = PurePosixPath("queries/kata-external-sources-usage-query.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest kata PRD v1.10 baseline into the kata self-meta wiki.")
    parser.add_argument("--wiki", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--checkpoint-script", default=str(Path(__file__).resolve().parents[1] / "plugin" / "scripts" / "import_checkpoint.py"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    return parser.parse_args()


def read_text(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def raw_path(source: PurePosixPath) -> PurePosixPath:
    return PurePosixPath("raw") / "imported" / BUNDLE_NAME / source


def yaml_quote(value: str) -> str:
    return '"' + value.replace('"', "'") + '"'


def raw_source_lines() -> list[str]:
    return [f"  - {raw_path(source).as_posix()}" for source in SOURCE_FILES]


def run_git(wiki_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(wiki_root), *args], text=True, capture_output=True, check=check)


def git_status_porcelain(wiki_root: Path) -> str:
    return run_git(wiki_root, "status", "--porcelain", check=False).stdout.strip()


def checkpoint(script: Path, wiki_root: Path, *args: str) -> None:
    completed = subprocess.run([sys.executable, str(script), "--wiki", str(wiki_root), *args], text=True, capture_output=True, check=False)
    if completed.stdout.strip():
        print(completed.stdout.strip())


def validate_sources(project_root: Path) -> None:
    missing = [s.as_posix() for s in SOURCE_FILES if not (project_root / Path(s.as_posix())).exists()]
    if missing:
        raise FileNotFoundError("Missing source files:\n" + "\n".join(missing))


def safe_copy_raw(project_root: Path, wiki_root: Path, source: PurePosixPath) -> str:
    src = project_root / Path(source.as_posix())
    dst = wiki_root / Path(raw_path(source).as_posix())
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if src.read_bytes() == dst.read_bytes():
            return "unchanged"
        raise RuntimeError(f"Raw file differs and will not be overwritten: {dst}")
    shutil.copy2(src, dst)
    return "created"


def frontmatter(title: str, page_type: str, tags: tuple[str, ...], sources: list[str]) -> str:
    return f"""---
title: {yaml_quote(title)}
type: {page_type}
tags:
{chr(10).join(f"  - {tag}" for tag in tags)}
created: {TODAY}
updated: {TODAY}
published_at: {TODAY}
ingested_at: {TODAY}
sources:
{chr(10).join(sources)}
---

"""


def feature_page() -> str:
    return frontmatter(
        "kata v1.10 External Searchable Sources (federated search)",
        "features",
        ("kata", "plugin", "design", "search", "federation", "ipc", "compatibility", "architecture", "state-machine"),
        raw_source_lines(),
    ) + """# kata v1.10 External Searchable Sources

Status: Draft PRD ingested 2026-05-11. Implementation pending.

## Summary

v1.10 adds **federated search** to kata: declare multiple external
document sources in `SCHEMA.md`, and `wiki-search` can optionally include
them alongside local wiki hits — without forcing a `wiki-ingest`. This
is the **opposite of v1.4 plugin ETL fallback** (which fetches once and
ingests). v1.10 is for *active*, *ongoing* documents the user wants
findable but not yet curated.

Primary scenario: NECallKit `docs/` and `specs/` are still being written
weekly. Today they get ingested once and the live source keeps drifting
from the wiki snapshot. With v1.10, `wiki-search` reads the live files
on demand, marks them `[ephemeral]`, and only suggests distillation when
they get hit repeatedly.

## The three principles

1. **Local is canonical** — every external hit is labeled
   `[ephemeral, not in wiki]`. Grouped output reinforces this visually
   every time.
2. **Observe, don't push** — kata counts hits, suggests `wiki-ingest`
   when threshold crosses, but **never auto-ingests**. "Use as external
   reference forever" is a fully legitimate end state.
3. **Federation is opt-in** — `--include-external` per call, or
   `defaults.always_on: auto` (which resolves to `true` only when decay
   protects against hit fatigue).

## MVP source types (v1.10)

| Type | Purpose | Notes |
|---|---|---|
| `local-directory` | scan files matching `glob` under a path | most common; sibling project docs/specs |
| `wiki-vault` | scan another kata vault's category dirs | hard-skips `raw/` + `dreaming/`; no transitive federation |

Reserved (v1.11+): `git-repo`, `http-endpoint`, `cli-command`.

## Six closed design questions

| # | Question | Decision |
|---|---|---|
| 1 | Hit tracking decay | `half-monthly` (counts ÷ 2 on the 1st of each month). Rejected cumulative + manual reset (hint fatigue). |
| 2 | Output order | **Grouped by default** (local section / external section / hints). `--debug-interleave` flag is debug-only escape hatch for priority tuning. |
| 3 | `wiki-query --include-external` | **Never default-on, ever.** No global setting can flip this. Future flag may add explicit per-call opt-in only. |
| 4 | `always_on` global flag | Three-state `auto \| true \| false`. `auto` resolves to `true` iff `decay != none` — self-balancing. |
| 5 | Cross-wiki federation | **In MVP as `type: wiki-vault`**. Scans target's category dirs only. No transitive (vault's own external_sources not followed). |
| 6 | Auto-ingest at threshold | **Never.** External usage notes are matter-of-fact observations. Wording explicitly says "long-term as external reference is a fine end state." |

## Machine identity (per-machine path overrides)

Since `~/.llm-wiki/` is **not** synced across machines (only each wiki's
git repo content is), `external_sources.path` declared in a synced
SCHEMA.md must either:

- work on every machine after `~`-expansion (the common case), or
- specify per-machine overrides via `paths:` list keyed by `machine_id`.

`machine_id` algorithm:

```text
machine_id = "{hostname_short}-{platform}-{home_hash}"
where hostname_short = hostname ≤12 chars, lowercase, .local/.lan stripped
      platform       = "mac" | "win" | "linux"
      home_hash      = SHA1(os.path.expanduser("~")) hex first 6 chars
```

Example: `litianyi-mbp-mac-7b52f6`. Auto-generated to `~/.kata/machine-id`
on first use, user can rename to anything matching `^[A-Za-z0-9._-]+$`
(≤64 chars). Full absolute paths never enter the id; only the home dir's
SHA1 prefix.

## Validation loop before ingest (the "distillation pathway")

The 3-step optional pathway:

```text
1. Observe   — wiki-search returns external hit; counter increments
2. Validate  — IF you choose to distill, first confirm the source is
                correct, current, applicable. Rule out: stale draft,
                superseded version, contradictory partial info,
                hallucinated content.
3. Distill   — run /kata:wiki-ingest <path> when ready.
```

Step 1 with quiet incrementing is the **steady state** for most external
files. There is no expectation to reach step 3. The threshold-triggered
output is matter-of-fact:

```text
referenced 4 times across recent searches (threshold: 3)

This file is being used as an external reference frequently enough to
show up here. There is no requirement to distill it — using it long-term
as an external reference is a fine end state.
```

This mirrors the `knock-it-out` skill's §3.5 mid-investigation
distillation gate: facts land in the wiki only after user confirmation.

## Relation to other v1.x features

- **v1.4 fallback plugins** (`.wiki-plugins.yaml`): orthogonal. Plugins
  do *fetch + ingest* on local-miss. v1.10 does *scan + label* on
  explicit opt-in. Both coexist; a future hybrid `type: cli-command`
  could merge them.
- **v1.7 raw/ watcher**: unaffected. Watcher operates on `raw/`;
  external sources are explicitly outside `raw/`.
- **v1.8 sync**: `external_sources` block is versioned wiki metadata,
  merged via standard 3-way merge. Hit tracking is per-machine.
- **v1.9 branch-aware repository bindings**: complementary. v1.9
  declares which branch a page applies to; v1.10 reads the branch's
  live source tree without ingesting. `wiki-vault` type pairs naturally
  with v1.9 partitioned vaults.

## Implementation scope

300-500 LOC across 5-6 files, reusing `search_naive` token-frequency
core. New: `external_sources.py` (parsing + path resolution),
`machine_id.py` (generate + validate), scanners for `local-directory`
and `wiki-vault`. Extended: `search_naive.py` (4 new flags),
`schema_validate.py`, `wiki-lint`, `wiki-config`.

See full PRD: `raw/imported/kata-prd-v1.10-external-searchable-sources-2026-05-11/docs/PRD-v1.10-external-searchable-sources.md`

## Related wiki pages

- [[kata-external-sources-usage-query]] — when / how to use v1.10
"""


def query_page() -> str:
    sources = [
        f"  - {NEW_FEATURE_PATH.as_posix()}",
        f"  - {raw_path(SOURCE_FILES[0]).as_posix()}",
    ]
    return frontmatter(
        "kata External Sources — when to use, how to configure",
        "queries",
        ("kata", "plugin", "design", "search", "federation", "compatibility"),
        sources,
    ) + """# kata External Sources — when to use, how to configure

## Question

When should I register external sources vs ingest content into the wiki?
How do I configure them safely? What is the day-to-day usage flow?

## Answer Confidence

High (for design), N/A for implementation (v1.10 is Draft PRD as of
2026-05-11; not yet shipped).

## When to use external sources

| Scenario | External source? | Why |
|---|---|---|
| Sibling project's `docs/` is still being written weekly | **Yes** — `local-directory` | Live access without re-ingesting on every edit |
| Another team's wiki vault you want to query but not merge | **Yes** — `wiki-vault` | Cross-wiki federation without conflating `raw/` |
| Web docs you fetched once and won't change | **No** — use v1.4 fallback plugin → ingest | One-shot ETL is what plugins are for |
| Source code you'd grep occasionally | **Probably not** — better to ingest summary findings | Code grep is not what `search_naive` is good at |
| Notion / Confluence / git ref | Wait for v1.11+ | MVP only does local-directory + wiki-vault |

## Configuration cheat sheet

Minimum block in `SCHEMA.md`:

```yaml
external_sources:
  defaults:
    enabled: true
    always_on: auto          # auto = true iff decay != none
    priority: lower-than-local
    distillation_hint: 5
    decay: half-monthly
  sources:
    - name: my-ongoing-docs
      type: local-directory
      path: ~/path/to/active/docs
      glob: "**/*.md"
      description: "Why this source exists"
```

With per-machine path overrides (heterogeneous machines):

```yaml
sources:
  - name: shared-platform
    type: wiki-vault
    path: ~/.llm-wiki/SharedPlatform     # default fallback
    paths:
      - machine_id: litianyi-mbp-mac-7b52f6
        path: ~/wiki-shared/wikis/SharedPlatform
      - machine_id: desktop-ab12-win-9e3a1c
        path: D:/Notes/llm-wiki/SharedPlatform
    priority: equal
    description: "Sibling team distilled wiki"
```

## Day-to-day flows

### Find your machine id

```bash
/kata:wiki-config machine-id
# litianyi-mbp-mac-7b52f6
```

Or read `~/.kata/machine-id` directly. Rename to something human if
you want.

### Search with external

```bash
# Default (assumes always_on: auto + decay: half-monthly → external on)
/kata:wiki-search --query "enableOffline"

# Force include if always_on resolved to false
/kata:wiki-search --query "enableOffline" --include-external

# Opt out this call (when always_on is true)
/kata:wiki-search --query "enableOffline" --local-only

# Specific source only
/kata:wiki-search --query "enableOffline" --external-source=my-ongoing-docs

# Debug priority multipliers (rare)
/kata:wiki-search --query "enableOffline" --include-external --debug-interleave
```

### When you see a usage note

The threshold-triggered note is **not a recommendation**. It's
information. You can:

1. Ignore it forever — using long-term as external reference is fine.
2. If you want to distill, validate first (current / non-contradictory /
   closed loop), then run the named `wiki-ingest` command.
3. Stop hitting the file and the note will fade on its own (counts halve
   monthly).

## What does NOT happen

- `wiki-search` **never** runs `wiki-ingest` automatically. The
  user-initiated step is part of the design, not a TODO.
- `wiki-query` **never** federates by default. Even after v1.11+ adds
  the flag, there is no global setting that turns it on.
- External sources are **never** written to. kata reads only.
- `wiki-vault` scans **never** reach the target's `raw/` or `dreaming/`,
  no matter what `glob` you set.
- A `paths:` override with a non-matching `machine_id` is silently
  skipped — no leakage between machines.

## Safety rules quick ref

| Rule | Enforced by |
|---|---|
| External paths refused under `/`, `C:\\Windows`, `/etc`, `/usr` | `wiki-lint` + runtime |
| `wiki-vault` must contain valid `SCHEMA.md` with `wiki_id` | runtime; otherwise `unhealthy` |
| `machine-id` ≤64 chars, `^[A-Za-z0-9._-]+$` | read-time validation |
| `machine-id` file never enters wiki repo | filesystem location (`~/.kata/`) |
| No transitive federation | `wiki-vault` scanner refuses to follow nested external_sources |

## Related

- [[kata-v1.10-external-searchable-sources]] — main feature page
- Full PRD at `raw/imported/kata-prd-v1.10-external-searchable-sources-2026-05-11/`
"""


def update_index(wiki_root: Path) -> None:
    index_path = wiki_root / "index.md"
    text = read_text(index_path)
    feature_entry = f"- [kata v1.10 External Searchable Sources (federated search)]({NEW_FEATURE_PATH.as_posix()}) - Federated wiki-search across multiple external local-directory / wiki-vault sources; per-machine path overrides via machine_id; never auto-ingests."
    query_entry = f"- [kata External Sources — when to use, how to configure]({NEW_QUERY_PATH.as_posix()}) - Decision matrix (when to use external vs ingest) + configuration cheat sheet + day-to-day flows + safety rules quick ref."

    if "## Features" not in text:
        text += "\n\n## Features\n\n"
    if "## Queries" not in text:
        text += "\n\n## Queries\n\n"

    if feature_entry not in text:
        text = text.replace("## Features\n\n", "## Features\n\n" + feature_entry + "\n", 1)
        if feature_entry not in text:
            text = text.replace("## Features\n", "## Features\n\n" + feature_entry + "\n", 1)
    if query_entry not in text:
        text = text.replace("## Queries\n\n", "## Queries\n\n" + query_entry + "\n", 1)
        if query_entry not in text:
            text = text.replace("## Queries\n", "## Queries\n\n" + query_entry + "\n", 1)

    text = re.sub(r"Total pages: (\d+)", lambda m: f"Total pages: {int(m.group(1)) + 2}", text, count=1)
    write_text(index_path, text.rstrip() + "\n")


def append_log(wiki_root: Path, raw_created: int, raw_unchanged: int) -> None:
    log_path = wiki_root / "log.md"
    text = read_text(log_path).rstrip() if log_path.exists() else "# Activity log"
    marker = "import | kata PRD v1.10 external searchable sources baseline"
    if marker in text:
        return
    entry = f"""

## [{TODAY}] import | kata PRD v1.10 external searchable sources baseline (1 file)
- Format: PRD-baseline single-file ingest
- Created: 2 wiki pages (feature + query)
- Updated: 0 existing pages (first ingest into this wiki)
- Raw: raw/imported/{BUNDLE_NAME}/ ({raw_created} created, {raw_unchanged} unchanged)
- Source group: PRD v1.10 external searchable sources design — 6 closed open questions (decay, output verbosity, wiki-query federation, always_on, cross-wiki, auto-ingest), machine_id algorithm, validation pathway wording.
- Filed: [[kata-v1.10-external-searchable-sources]], [[kata-external-sources-usage-query]]
- Decision: ingest now to seed this wiki (kata self-meta) with v1.10 baseline. Implementation pending; baseline page documents the design decisions so future contributors / agents can search "machine_id", "always_on auto", "distillation pathway", "wiki-vault" and find the canonical reasoning before touching code.
"""
    write_text(log_path, text + entry)


def execute(wiki_root: Path, project_root: Path) -> dict[str, object]:
    raw_counts = {"created": 0, "unchanged": 0}
    for source in SOURCE_FILES:
        raw_counts[safe_copy_raw(project_root, wiki_root, source)] += 1
    feature_full = wiki_root / Path(NEW_FEATURE_PATH.as_posix())
    query_full = wiki_root / Path(NEW_QUERY_PATH.as_posix())
    write_text(feature_full, feature_page())
    write_text(query_full, query_page())
    update_index(wiki_root)
    append_log(wiki_root, raw_counts["created"], raw_counts["unchanged"])
    return {
        "raw_created": raw_counts["created"],
        "raw_unchanged": raw_counts["unchanged"],
        "created": [str(NEW_FEATURE_PATH), str(NEW_QUERY_PATH)],
        "updated": [],
    }


def main() -> int:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    project_root = Path(args.project).resolve()
    checkpoint_script = Path(args.checkpoint_script).resolve()
    validate_sources(project_root)
    plan = {"bundle": BUNDLE_NAME, "sources": [s.as_posix() for s in SOURCE_FILES], "new_pages": [NEW_FEATURE_PATH.as_posix(), NEW_QUERY_PATH.as_posix()], "updates": 0}
    if not args.execute:
        print(plan)
        return 0
    if not args.allow_dirty:
        status = git_status_porcelain(wiki_root)
        if status:
            print(f"[warn] wiki tree is dirty; continuing with --allow-dirty semantics for first-time ingest:\n{status}", file=sys.stderr)
    if checkpoint_script.exists():
        checkpoint(checkpoint_script, wiki_root, "lock", "--source", str(project_root / "docs"), "--format", "markdown")
    try:
        if checkpoint_script.exists():
            checkpoint(checkpoint_script, wiki_root, "init", "--source", str(project_root / "docs"), "--format", "markdown", "--total", str(len(SOURCE_FILES)))
        result = execute(wiki_root, project_root)
        if checkpoint_script.exists():
            checkpoint(checkpoint_script, wiki_root, "update", "--processed", str(len(SOURCE_FILES)), "--last-file", SOURCE_FILES[-1].as_posix())
        print(result)
        return 0
    finally:
        if checkpoint_script.exists():
            checkpoint(checkpoint_script, wiki_root, "unlock")


if __name__ == "__main__":
    raise SystemExit(main())
