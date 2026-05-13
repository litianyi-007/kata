---
name: wiki-sync
description: "Multi-machine git sync for the wiki: pull, merge with custom drivers (log.md union+sort), push. Local sync lock + force-push detect + identity check + per-machine sync reports under ~/.kata/sync-reports/. Hard stops on import-in-progress, merge-in-progress, identity mismatch, force-push detected, unrelated histories. NEVER touches anything in the wiki repo without committing it first; reports go to ~/.kata/ to avoid self-conflict."
user-invocable: true
argument-hint: "[--auto] [--dry-run]"
---

# wiki-sync

Pull-merge-push your wiki across machines. Designed for the v1.7.2
multi-project layout (`~/.llm-wiki/{project}`), one git remote per project.
Each machine's lock and sync reports are namespaced by wiki slug, so you
can run wiki-sync on multiple project wikis concurrently.

> The cron friend of `wiki-dream`. Recommended chain: `wiki-sync --auto
> && wiki-dream`. If sync fails or stops on a conflict, dream doesn't run
> — that's by design (PRD-v1.8 §11.6).

## When to use

- Multi-machine workflow: laptop ingests on Wed, desktop on Sat, you
  want a single coherent wiki on Sunday morning
- Returning from a trip: one `wiki-sync` brings everything that the
  other machine pushed since you left
- Cron-driven weekly: `0 23 * * 0  wiki-sync --auto && wiki-dream`
- Pre-flight before starting work: `wiki-sync --dry-run` shows what
  *would* happen

## When NOT to use

- Single-machine wiki without a remote — `sync.enabled: false` in
  SCHEMA.md or just don't add a `sync:` block; wiki-sync becomes a no-op
- During an active `wiki-import` — preflight refuses to operate while
  `.wiki-import-lock` is fresh or `.wiki-import-checkpoint.json` is
  present (signals: "import was interrupted, resume or clean before sync")
- During an active `git merge` / `git rebase` / `git cherry-pick` —
  preflight refuses; finish the in-flight git operation first

## Implementation

`plugin/scripts/wiki_sync.py` owns the entire orchestration: lock /
stash with SHA tracking / fetch / ancestry classification / merge with
custom drivers / push retry / cleanup. The matching custom driver
`plugin/scripts/merge_log.py` handles `log.md` union+sort with
canonical hash dedup.

```bash
# Interactive run (cron mode disabled, lock + drivers configured if needed)
python {plugin_root}/scripts/wiki_sync.py --wiki {wiki_path}

# Cron mode: any non-clean outcome exits non-zero so the chain breaks
python {plugin_root}/scripts/wiki_sync.py --wiki {wiki_path} --auto

# Read-only preview: fetches but does not lock / stash / register driver
# / modify log; emits would-* result
python {plugin_root}/scripts/wiki_sync.py --wiki {wiki_path} --dry-run
```

`{plugin_root}` resolves to the directory containing `.claude-plugin/`.
`{wiki_path}` resolves via the standard wiki-root resolver — explicit
`--wiki`, then `WIKI_PATH`, then ancestor wiki, then `LLM_WIKI_PROJECT`,
etc. (CLAUDE.md path resolution).

## Behavior

### Default (interactive)

1. Resolve wiki, read `sync:` config from SCHEMA.md
2. Validate local `wiki_id` (UUID v4 in SCHEMA.md `## Identity` block)
3. Acquire local sync lock at `~/.kata/sync-{slug}.lock` (per-machine
   re-entry guard; cross-machine race goes through git push rejection
   and bounded retry)
4. Preflight: `.git` exists, remote configured, no merge/rebase in
   progress, no fresh `.wiki-import-lock`, no `.wiki-import-checkpoint.json`
5. Auto-register merge drivers if needed (Option A three guardrails:
   verify path, log audit, respect manual `--unset` via
   `sync.auto_configure_drivers: false`)
6. Stash dirty tree (tracked changes only) and capture stash commit SHA
7. Record `origin/<branch>` SHA, fetch, record new SHA
8. Ancestry classification (5 cases): `unrelated-history` /
   `force-push-detected` / normal advance
9. Identity check: read `wiki_id` from `git show origin/main:SCHEMA.md`,
   abort on mismatch
10. Compare HEAD vs origin: `up-to-date` / fast-forward / push /
    diverge-merge
11. On diverge: `git merge --no-ff` invokes the registered driver(s),
    check for unmerged paths, commit if clean
12. Push with bounded retry (3 × 1/2/4s backoff)
13. Cleanup in finally: stash apply (use SHA, not stash@{0}) → write
    sync report → release lock. Each layer fails independently.

### `--auto` (cron)

Same flow, but any non-clean outcome (conflicts, force-push, identity
mismatch, etc.) exits non-zero so a chained `&& wiki-dream` doesn't run.
PRD-v1.8 §11.6 — failed sync is *safer* than partial dream over a
half-merged tree.

### `--dry-run`

Forks BEFORE side effects (PRD §6.4 / §11.5):
- No lock acquired
- No stash
- No driver registration
- No log mutation
- Only `git fetch origin <branch>` runs (writes only to
  `.git/refs/remotes/`, which is read-only side effect)

Result is one of `up-to-date` / `would-fast-forward` / `would-push` /
`would-merge` / `unrelated-history` / `force-push-detected`. Always
exits 0 (or 1 only for serious errors like missing wiki_id).

## Sync reports

Reports go to `~/.kata/sync-reports/{slug}/` — **outside the wiki
repo** (PRD §9.1 B1). Filename: `{ISO-timestamp}-{result}.md`.

Result suffixes:
- `success` — pushed cleanly
- `success-with-driver` — merged with driver, pushed cleanly
- `fast-forward` — origin advanced, local fast-forwarded
- `conflicts` — unmerged paths after driver merge; report includes
  recovery commands using the stash SHA
- `force-push-detected` / `unrelated-history` / `identity-mismatch` —
  hard stops with explanation
- `aborted` — preflight refused (import lock / merge in progress /
  lock held / etc.)
- `dry-run` — preview only
- `error` / `interrupted` — unexpected

`up-to-date` syncs and `no-remote` skips don't write a report (reduce
noise). The report directory grows over time; clean periodically with
`rm -r ~/.kata/sync-reports/{slug}/` if needed (rollback rule §16).

## Conflict handling

When the merge driver can't auto-merge, or when a non-managed file
diverges, the merge produces unmerged paths. wiki-sync:
1. Stops before push (commit not made)
2. Leaves `.git/MERGE_HEAD` and conflict markers in the unmerged files
   for the user to resolve in their editor
3. Writes a `conflicts` report with paths + recovery commands using
   the stash SHA (not stash@{0}, which can drift)

Recovery shape:
```bash
# 1. Resolve conflicts in editor
git add <resolved-files>
git commit  # uses prepared message
git push

# 2. Restore stashed work (use SHA, not stash@{0})
git stash apply <sha-from-report>
git stash list --format='%gd %H'    # find which stash@{n} matches
git stash drop stash@{N}             # clean up after apply

# Or abort the whole merge attempt:
git merge --abort
git stash apply <sha-from-report>    # restore working tree
```

For the `AKWIKI-SEMANTIC-CONFLICT` markers written by `merge_log.py`
on driver failure (parse error, etc.), the marker block contains
ours/base/theirs originals for the user to compose a resolution from.

## Cross-references

- **`wiki-import`** must complete (or fail and be cleaned) before sync —
  preflight enforces via `.wiki-import-lock` and
  `.wiki-import-checkpoint.json`. wiki-import's phase 5 deletes the
  checkpoint after `git commit` (regardless of push outcome) so
  commit-OK / push-fail doesn't block subsequent sync.
- **`wiki-dream`** chains after wiki-sync via cron (`wiki-sync --auto
  && wiki-dream`). Dream is filesystem-only; sync brings remote state
  in first, then dream operates on the merged result.
- **`wiki-watch`** is independent — its queue is per-machine
  (`.wiki-ingest-queue.json` is gitignored), no interaction with sync.

## Limitations (v1.8 MVP)

- Only `merge_log.py` driver is implemented. `merge_index.py`
  (section-aware union of `index.md`) lands in v1.8-full per PRD §13
  phasing — until then index.md uses git's default 3-way merge and
  conflicts go through standard manual resolution.
- Push race retry: bounded at 4 total attempts (1s/2s/4s backoff).
  Each retry re-fetches and re-classifies (origin may have advanced
  during our merge), and re-merges with the driver if still divergent.
  Out-of-retries → `race-exhausted` and asks user to rerun.
- Hard kill (SIGKILL / Windows TerminateProcess) skips Python's
  `finally` — next sync detects stale lock by PID liveness and
  auto-cleans, but stash is left for the user (`git stash list` will
  show it). T-sync-17b in PRD §14.

## Recommended cron line

```bash
# Sunday 23:00 — sync first, then dream if sync was clean
0 23 * * 0  cd ~/.llm-wiki/<project> && /kata:wiki-sync --auto && /kata:wiki-dream
```

For multi-project setups, give each project its own cron line with a
different `cd` target. Stagger times across machines (e.g., A at 23:00
B at 23:30) to reduce push race incidence — see PRD §15 dream cron
timing note.
