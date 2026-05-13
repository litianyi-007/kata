---
name: wiki-watch
description: "Watch raw/{articles,papers,transcripts,external}/ for new files, queue them, and let the user drain the queue with one command. Closes the 'I dropped a file but forgot to ingest' gap. NEVER auto-runs wiki-ingest — drain is always explicit."
user-invocable: true
argument-hint: "[--start [--poll N --debounce N]] [--stop] [--status] [--drain [--pages 1,2,3]] [--remove <id>]"
---

# wiki-watch

Detect new sources in `raw/` and surface them for ingestion. The watcher
runs as a polling daemon (5 s default), debounces in-progress writes,
and writes detected files to `.wiki-ingest-queue.json`. **The agent —
not the daemon — invokes `wiki-ingest`** when the user drains the queue.
This separation keeps the watcher dumb (always safe to run) and ingest
deliberate (always reviewed).

> If a file appears in raw/ but you don't want to ingest it (e.g. WIP),
> use `wiki-watch --remove <id>` to drop it from the queue without
> processing.

## Implementation

`plugin/scripts/wiki_watch.py` owns the daemon, queue IO, and detection
logic. **The script is the source of truth; the prose below explains
its behavior.** This skill calls the script for state mutation and
status reads, then orchestrates `wiki-ingest` invocations during drain.

```bash
# Foreground watch (testing) — Ctrl-C to stop
python {plugin_root}/scripts/wiki_watch.py --wiki {wiki_path} watch

# Background daemon
python {plugin_root}/scripts/wiki_watch.py --wiki {wiki_path} watch --daemon

# Status: daemon liveness + queue summary
python {plugin_root}/scripts/wiki_watch.py --wiki {wiki_path} status

# Stop the daemon (clean SIGTERM)
python {plugin_root}/scripts/wiki_watch.py --wiki {wiki_path} stop

# Read queue (optionally filtered by status)
python {plugin_root}/scripts/wiki_watch.py --wiki {wiki_path} queue list \\
    [--status pending|processed|failed|removed]

# Mark an entry's status (used during drain)
python {plugin_root}/scripts/wiki_watch.py --wiki {wiki_path} \\
    queue mark <id> processed|failed|removed

# Drop entry without ingesting
python {plugin_root}/scripts/wiki_watch.py --wiki {wiki_path} \\
    queue remove <id>

# Prune old processed/failed/removed entries (default 30 days)
python {plugin_root}/scripts/wiki_watch.py --wiki {wiki_path} \\
    queue prune --older-than 30
```

`{plugin_root}` resolves to the directory containing `.claude-plugin/`.

## Modes

### `--start`

Spawn the daemon. Default poll 5 s, debounce 5 s, min file size 100 B.

```
$ /kata:wiki-watch --start
Daemon started (pid 12340). Polling every 5s.
Logs at ~/.kata/watcher-{project-slug}.log.
```

PID and log files are namespaced per-wiki (`watcher-{leaf-name}-{hash}.pid`)
so multiple project wikis (`~/.llm-wiki/necall`, `~/.llm-wiki/rtc`, …) can
each run their own watcher concurrently. `--status` and `--stop` only
affect the daemon for the resolved wiki path.

If a daemon is already running for **this** wiki, return its info and exit
nonzero — never spawn a second one for the same wiki.

### `--status` (default when no flag passed)

Show daemon liveness + pending count. If daemon is down but queue has
pending entries, suggest `--drain` (drain works regardless of daemon).

```
$ /kata:wiki-watch --status

[Daemon] running (pid 12340, started 2026-04-25 23:00:14Z)
[Queue]  3 pending, 12 processed, 0 failed, 1 removed

[Pending]
1. raw/articles/2026-04-26-databricks-acquires-mosaic.md
   detected: 2 hours ago | size: 12 KB
2. raw/papers/2026-04-26-deepseek-v3.pdf
   detected: 1 hour 30 min ago | size: 3.2 MB
3. raw/external/deepwiki-cli/2026-04-26-auth.md
   detected: 1 hour ago | size: 8 KB

[Suggested next]
→ /kata:wiki-watch --drain
→ /kata:wiki-watch --remove 3   (to skip a file)
```

### `--drain` — the central skill action

For each `pending` entry in detection order:

1. Verify the file still exists; if missing, mark `failed` with reason.
2. Invoke `/kata:wiki-ingest <path>` (the existing skill).
3. On success, run `queue mark <id> processed`.
4. On failure, run `queue mark <id> failed` and capture the error.
5. After the loop, append a single `## [date] watch | drained N files`
   entry to log.md.

`--drain --pages 1,3` processes only the listed indices (1-based, in the
order shown by `--status`).

### `--remove <id>` / `--remove <index>`

Mark an entry as `removed` without processing. Accept either the
internal queue id or the 1-based index from `--status`.

### `--stop`

Send SIGTERM to the daemon. The script handles cross-platform signal
delivery (Windows uses TerminateProcess via `os.kill`).

## When NOT to use

- For one-off ingestion of a known file → just run `/wiki-ingest <path>`
  directly. The watcher is for the steady-state "I drop files, you
  remind me to ingest" workflow.
- For bulk import of an existing folder → use `wiki-import`, not the
  watcher. The watcher is for incremental drips, not migrations.

## Safety properties

- **Never auto-ingests.** Drain is always explicit. A misconfigured
  watcher can't pollute the wiki because it doesn't write wiki pages.
- **Debounced.** Files must have stable size + mtime for ≥ 5 s before
  enqueueing — catches multi-pass writes from Web Clipper or in-progress
  downloads.
- **Atomic queue writes.** Daemon and skill share the queue file via
  rename atomicity; no fcntl/lockfile.
- **Audit trail preserved.** Removed and processed entries stay in the
  queue (status flag flipped) so `--status` history is complete. Use
  `queue prune` to reclaim space periodically.

## Headless operation

For users who don't want a long-running daemon, use cron / Task Scheduler
to run a single-pass scan every minute:

```bash
# crontab entry — scan once, exit, no daemon
* * * * * python /path/to/plugin/scripts/wiki_watch.py \\
    --wiki ~/wiki watch --max-iterations 1
```

Then run `/wiki-watch --drain` interactively when you have time.
`docs/watcher.md` has full systemd / launchd / Task Scheduler recipes.

## Notes for the agent

- During `--drain`, surface what each `wiki-ingest` invocation produced
  (created/updated pages). Don't just say "3 files processed".
- If `--drain` is invoked and the queue is empty, suggest `--start` if
  the daemon is also down.
- The watcher and dreamer are independent. They share `log.md` (each
  writes its own action lines) but otherwise don't interact. Don't
  conflate "schedule the dreamer" with "schedule the watcher" — they
  use different cadence patterns (dreamer weekly, watcher continuous).
