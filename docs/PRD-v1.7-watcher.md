# PRD — Raw watcher (v1.7)

**Status:** Draft · 2026-04-25
**Targets:** kata v1.7
**Companion:** [TRD-v1.7-watcher.md](TRD-v1.7-watcher.md)

## 1. Problem

The wiki's compounding loop assumes the user runs `/wiki-ingest` shortly
after a source lands in `raw/`. In practice:

- Obsidian Web Clipper saves an article to `raw/articles/` → user closes
  browser → forgets to switch to Claude Code → file sits unprocessed
- `curl > raw/external/foo.md` drops a file → user moves on → forgets
- Bulk drag-and-drop into `raw/papers/` produces 5 files that get
  ingested 0–3 of by the time the user remembers

The "compiled once, kept current" promise breaks at "kept current"
because the human has to remember to invoke ingestion. v1.7 closes
that gap by detecting raw-tree changes and prompting the user to
process them — without ever silently mutating wiki pages.

## 2. Goal & non-goals

**Goal:** A user can drop files into `raw/articles/` (or any raw
category) at any time, and on their next Claude Code session,
`/wiki-watch --status` shows them exactly which files need ingestion,
ready to process in one command.

**Non-goals:**
- **Auto-trigger of `wiki-ingest`** without user confirmation — too easy
  for a misconfigured watcher to ingest a half-downloaded file or a
  spam clip. v1.7 is detection + queue, not autonomous execution.
- Watching for file modifications (only new files in v1.7).
- Cross-platform service installation (systemd / launchd / Task Scheduler
  scripts). v1.7 documents the cron pattern; OS-service wrapping is v1.8+.
- Watching `raw/imported/` (handled by `wiki-import` workflow, not the
  daily-loop watcher).

## 3. User stories

| # | Story |
|---|-------|
| US-1 | _As a user, I save an Obsidian Web Clipper output to `raw/articles/`. Tomorrow morning, `/wiki-watch --status` tells me there's 1 pending file._ |
| US-2 | _As a user with 5 pending files, I run `/wiki-watch --drain` and the agent ingests them in order, showing me what was created/updated for each._ |
| US-3 | _As a power user, I want `wiki-watch --start` to run as a background daemon so the queue is always current; I'll trigger `--drain` when I have time._ |
| US-4 | _As a user who dropped a file by accident, I want `/wiki-watch --remove <file>` to take it out of the queue without ingesting._ |

## 4. Success metrics

**Quantitative:**
- File detection latency p99 ≤ 10 s (polling interval 5 s + debounce 5 s)
- Zero spurious queue entries from file mod / rename / delete events
- Zero false-positive `--drain` ingestions (every ingest triggered by drain
  has a queue entry that points to a real file)

**Qualitative (4-week dogfood):**
- ≥ 80% of new files in raw/ get ingested within 24 h (vs. the
  pre-watcher baseline where this is closer to 30%)
- User reports "I forgot to ingest" zero times during the window
- No accidental ingestions of WIP/temp files

## 5. Scope

### In scope (v1.7)
- Polling-based watcher (stdlib only, no inotify / watchfiles dep)
- 5-second poll, 5-second debounce per file
- Queue persisted to `.wiki-ingest-queue.json` in wiki root
- `wiki-watch` skill with `--start`, `--status`, `--drain`, `--remove`, `--stop`
- Categories watched: `raw/articles/`, `raw/papers/`, `raw/transcripts/`,
  `raw/external/`
- Notification log appended to `log.md` on each enqueue
- Cron-pattern documentation for headless operation

### Out of scope (v1.7 — explicitly deferred)
- `inotify` / `kqueue` / `ReadDirectoryChangesW` event watching (poll-based suffices for the 5s SLA)
- Auto-trigger ingest (`--auto-drain` may land in v1.8)
- File-modification tracking (re-ingestion of edited raw files)
- `raw/assets/` watching (those are downloaded by `wiki-ingest`, not user-curated)
- OS-level desktop notifications

## 6. UX

### Status

```
$ /kata:wiki-watch --status

[Queue] 3 pending files
1. raw/articles/2026-04-26-databricks-acquires-mosaic.md
   detected: 2026-04-26 09:14:22 (2h ago)
   size: 12 KB

2. raw/papers/2026-04-26-deepseek-v3.pdf
   detected: 2026-04-26 09:42:01 (1h 30m ago)
   size: 3.2 MB

3. raw/external/deepwiki-cli/2026-04-26-auth-middleware.md
   detected: 2026-04-26 10:01:18 (1h 12m ago)
   size: 8 KB

[Daemon] running (pid 12340, started 2026-04-25 23:00)

[Suggested next]
→ /kata:wiki-watch --drain          (process all 3)
→ /kata:wiki-watch --drain --pages=1,2  (process selected)
→ /kata:wiki-watch --remove 3       (drop without ingesting)
```

### Drain

```
$ /kata:wiki-watch --drain

Processing 3 queued files…

[1/3] raw/articles/2026-04-26-databricks-acquires-mosaic.md
  → invoking wiki-ingest…
  → Created: companies/mosaic.md (updated), models/mpt-7b.md (re-activated)
  → Queue: marked as processed

[2/3] raw/papers/2026-04-26-deepseek-v3.pdf
  → invoking wiki-ingest…
  → Created: models/deepseek-v3.md, papers/deepseek-v3-paper.md
  → Queue: marked as processed

[3/3] raw/external/deepwiki-cli/2026-04-26-auth-middleware.md
  → invoking wiki-ingest…
  → Created: concepts/auth-middleware.md
  → Queue: marked as processed

[Summary] 3 files ingested, 8 wiki pages touched.
[Queue] empty
```

### Daemon lifecycle

```
$ /kata:wiki-watch --start
Daemon started (pid 12340). Polling every 5s.
Output: ~/.kata/watcher-{leaf}-{sha1[:8]}.log

$ /kata:wiki-watch --stop
Daemon stopped (pid 12340).
```

> **v1.7.2 update.** PID and log paths are namespaced per wiki:
> `watcher-{leaf}-{sha1[:8]}.{pid,log}`, where `leaf` is the wiki root's
> directory name (sanitized) and `sha1[:8]` is the first 8 hex chars of
> SHA-1 over the absolute path. Two unrelated wikis with the same leaf
> name (e.g. two different `common/` dirs) don't collide. Multiple
> project wikis (`~/.llm-wiki/necall`, `~/.llm-wiki/rtc`, …) each run
> their own watcher concurrently. `--status` / `--stop` operate on the
> daemon for the resolved wiki path only.

## 7. Open decisions (non-blocking)

These have reasonable defaults; user override is fine.

1. **Polling interval** — default 5 s. Lower = faster detection + more I/O; higher = laggy. Acceptable range 1–60 s.
2. **Debounce window** — default 5 s. Files smaller than this duration's
   write activity are considered "still being written"; we wait until they
   stabilize before enqueueing. Catches Web Clipper's multi-step saves.
3. **Min file size** — default 100 bytes. Files smaller than this are
   ignored (likely scratch / lock files).
4. **Daemon storage** — pid + state in `~/.kata/watcher.{pid,log}`,
   wiki-local queue in `{wiki_path}/.wiki-ingest-queue.json`.

## 8. Risks

| Risk | Mitigation |
|------|-----------|
| Daemon crash leaves queue stale | `--start` checks pid file, removes stale entries (>24h since detection without daemon running) |
| Half-written file detected | Debounce: file must have stable mtime + size for `debounce_window` seconds before enqueue |
| User runs `--drain` when daemon is down | Drain works regardless of daemon state — it just processes the queue |
| Multiple daemons spawn (user runs `--start` twice) | pid file with flock; second `--start` reports "already running" |
| Wiki path moves and daemon points at old path | Daemon reads `WIKI_PATH` at start; document this in README |

## 9. Dependencies

- v1.6 must be shipped (it is — committed `f42b8e5`).
- No external Python deps; stdlib only.
- The `wiki-ingest` skill must exist and accept a path argument (it does).

## 10. Parallelism with v1.6 dogfood

Per [v1.6 dogfood obligation](../) memory: v1.7 development is **explicitly
parallel** with the dogfood window. Watcher is code-isolated from dreamer
(no shared files except `log.md` for unrelated entries). The watcher does
NOT depend on dreamer state and the dreamer does NOT consume queue state.

What stays gated on dogfood completion:
- v1.7 **public release / marketing** — wait until v1.6 dogfood validates
- Any v1.6 algorithm tuning — separate from v1.7 work

What is NOT gated:
- v1.7 PRD / TRD / code / test / merge to main — all OK during dogfood
