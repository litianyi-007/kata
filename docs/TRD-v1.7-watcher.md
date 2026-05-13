# TRD — Raw watcher (v1.7)

**Status:** Draft · 2026-04-25
**Companion:** [PRD-v1.7-watcher.md](PRD-v1.7-watcher.md)

## 1. Architecture

```
                    ┌──────────────────────────────────┐
                    │  user drops file in raw/articles/ │
                    └──────────────┬───────────────────┘
                                   │
                                   ▼
              ┌────────────────────────────────────────┐
              │  wiki_watch.py (daemon)                 │
              │  ────────────────────────                │
              │  every 5s:                              │
              │    scan watched dirs                    │
              │    diff against last_known_state         │
              │    for each new file:                   │
              │      if size >= min_size                │
              │        AND age >= debounce_window:       │
              │          enqueue                        │
              │          append log.md entry            │
              └────────────────────────────────────────┘
                                   │
                                   ▼
              ┌────────────────────────────────────────┐
              │  .wiki-ingest-queue.json (wiki root)    │
              │  [{                                     │
              │    "path": "raw/articles/foo.md",       │
              │    "detected_at": "...",                │
              │    "size": 12345,                       │
              │    "status": "pending"|"processed"      │
              │  }, ...]                                │
              └────────────────────────────────────────┘
                                   │
                                   ▼
              ┌────────────────────────────────────────┐
              │  /wiki-watch skill                      │
              │  ───────────────────                    │
              │  --status: read queue, render summary    │
              │  --drain:  loop pending → wiki-ingest   │
              │            mark processed on success    │
              │  --remove: drop entry by index           │
              │  --start:  spawn daemon (background)     │
              │  --stop:   send SIGTERM via pid file     │
              └────────────────────────────────────────┘
```

## 2. Why polling, not inotify

Three reasons:

1. **Stdlib only.** `inotify` requires `pyinotify` on Linux,
   `watchdog` for cross-platform — both add deps. kata ships
   stdlib-only, full stop.
2. **5-second SLA is good enough.** A document workflow doesn't need
   sub-second latency. Polling at 5 s is invisible to the user.
3. **Polling is honest about Windows.** `ReadDirectoryChangesW` on
   network drives or OneDrive folders is unreliable; `os.scandir()`
   loops always work.

Cost: at 5 s × 4 dirs × maybe 50 files = 1000 file stats per minute.
That's ~17 stat calls/sec, negligible.

## 3. Daemon process model

**Foreground mode (default):**
```
python plugin/scripts/wiki_watch.py --wiki <path> watch
```
Runs in current terminal until Ctrl-C. Useful for testing and for users
who don't want a background process.

**Background mode:**
```
python plugin/scripts/wiki_watch.py --wiki <path> watch --daemon
```
Forks (POSIX) or detaches (Windows) and writes pid to
`~/.kata/watcher-{slug}.pid`. Writes log to
`~/.kata/watcher-{slug}.log`. The slug is `{leaf-name}-{sha1[:8]}` of
the resolved wiki root absolute path — namespaced per wiki so
multi-project layouts (`~/.llm-wiki/necall`, `~/.llm-wiki/rtc`, …) can
each run their own watcher concurrently. (Pre-v1.7.2 used a single
`watcher.pid`; that design was wrong for multi-project installs and was
fixed in the 2026-05-07 audit follow-up.)

**Status check:**
```
python plugin/scripts/wiki_watch.py --wiki <path> status
```
Reads pid file, sends signal 0 to verify daemon alive. Returns JSON.

**Stop:**
```
python plugin/scripts/wiki_watch.py --wiki <path> stop
```
Reads pid, sends SIGTERM. Daemon traps, flushes queue, exits cleanly.

### Why not a system service?

For v1.7 we leave OS-service installation (systemd, launchd, Task
Scheduler) to user-supplied wrapper scripts. The script accepts
straightforward CLI flags so wrapping is trivial. Documenting the
wrappers is in scope for `docs/watcher.md`; shipping the wrappers is
v1.8+.

## 4. Queue format

`{wiki_path}/.wiki-ingest-queue.json`:

```json
{
  "version": 1,
  "updated_at": "2026-04-26T11:13:42Z",
  "entries": [
    {
      "id": "Q-2026-04-26-091422-abc123",
      "path": "raw/articles/2026-04-26-databricks.md",
      "detected_at": "2026-04-26T09:14:22Z",
      "size": 12345,
      "mtime": "2026-04-26T09:14:18Z",
      "status": "pending"
    },
    {
      "id": "Q-2026-04-25-181102-def456",
      "path": "raw/papers/2026-04-25-deepseek.pdf",
      "detected_at": "2026-04-25T18:11:02Z",
      "size": 3211420,
      "mtime": "2026-04-25T18:10:55Z",
      "status": "processed",
      "processed_at": "2026-04-26T08:30:00Z"
    }
  ]
}
```

Status values:
- `pending` — detected, awaiting ingest
- `processed` — `wiki-ingest` ran successfully and marked done
- `removed` — user explicitly dropped via `--remove`
- `failed` — `wiki-ingest` errored (kept for diagnosis; user retries)

The script never deletes entries — it only flips `status`. This gives
the user a complete audit log of every file the watcher has ever seen.
A periodic prune (entries with `status != pending` older than 30 days)
keeps the file from growing unbounded; out of scope for v1.7.

## 5. Debouncing

For each new file detected:

```
debounce(file):
    state = (size, mtime)
    if file in pending_debounce:
        last_state = pending_debounce[file]
        if state == last_state:
            elapsed = now - first_seen[file]
            if elapsed >= debounce_window:
                enqueue(file)
                del pending_debounce[file]
        else:
            # File still changing, reset
            pending_debounce[file] = state
            first_seen[file] = now
    else:
        # First sighting
        pending_debounce[file] = state
        first_seen[file] = now
```

5-second window means: file must have stable size + mtime for ≥ 5 s
before being enqueued. Catches Web Clipper writes (multi-pass save) and
network downloads (in-progress chunks).

## 6. Drain logic

`/wiki-watch --drain` is a SKILL action, not a script action. The skill:

1. Reads `.wiki-ingest-queue.json`
2. For each `pending` entry, in detection order:
   a. Verify file still exists at `entries[i].path`
   b. If missing: mark `failed` with reason `"file removed before drain"`
   c. Else: invoke `/kata:wiki-ingest <path>` (the existing skill)
   d. On success: mark `processed`
   e. On failure: mark `failed`, capture error
3. After processing, write back the queue file
4. Append a single `## [date] watch | drained N files` entry to log.md

Why the skill not the script: `wiki-ingest` is a skill (LLM-driven). The
script can't invoke it; only the agent can. So drain is the agent's
ceremony, the script just reads/writes queue state.

## 7. CLI surface

```
wiki_watch.py --wiki <path> watch [--daemon] [--poll 5] [--debounce 5]
wiki_watch.py --wiki <path> status                # JSON: pid, started, queue summary
wiki_watch.py --wiki <path> stop                  # signals daemon
wiki_watch.py --wiki <path> queue list            # JSON: full queue
wiki_watch.py --wiki <path> queue mark <id> <status>   # state mutation
wiki_watch.py --wiki <path> queue remove <id>     # set status=removed
wiki_watch.py --wiki <path> queue prune --older-than 30  # cleanup
```

Skills will mostly use `queue list`, `queue mark`, `queue remove`. The
`watch` and `status`/`stop` commands are user-facing for daemon
lifecycle.

## 8. Files

| Path | Purpose | Created in |
|------|---------|-----------|
| `plugin/scripts/wiki_watch.py` | Daemon + queue mgmt | v1.7 |
| `plugin/skills/wiki-watch/SKILL.md` | User skill | v1.7 |
| `docs/watcher.md` | User documentation | v1.7 |
| `tests/run_smoke.py` | Extended with watcher tests | v1.7 (modify) |

State files (not tracked, ignored):

| Path | Purpose |
|------|---------|
| `~/.kata/watcher-{slug}.pid` | Daemon pid (per-wiki, namespaced by `{leaf}-{sha1[:8]}`) |
| `~/.kata/watcher-{slug}.log` | Daemon stdout/stderr (per-wiki) |
| `{wiki_path}/.wiki-ingest-queue.json` | Per-wiki queue (committed? user choice — defaults to gitignored) |

## 9. Test plan

Smoke test extends `tests/run_smoke.py`:

```python
# Test W1: file drop is detected, debounced, enqueued
- Create temp wiki dir
- Run `wiki_watch.py watch --daemon` with very short debounce (1s)
- Drop a file into raw/articles/
- Wait debounce + poll
- Read queue file → assert one pending entry matching the file
- Stop daemon

# Test W2: --remove drops entry without ingesting
- Same setup, file enqueued
- Run `queue remove <id>`
- Read queue → assert status == "removed"

# Test W3: file too small is skipped
- Drop a 50-byte file (default min 100)
- Wait
- Read queue → assert no entry

# Test W4: file still being written is debounced
- Touch a file every 0.5s for 3s (mtime keeps changing)
- After 3s, leave file alone
- Wait debounce + poll
- Read queue → assert entry appears AFTER mtime stabilizes
```

No CI gate beyond "smoke tests pass" — watcher correctness is
algorithmically simple, real signal will come from dogfood.

## 10. Open technical decisions

- **Daemon detachment on Windows.** Use `subprocess.CREATE_NEW_PROCESS_GROUP` + `DETACHED_PROCESS` flags. POSIX uses double-fork or `os.setsid`. Both paths in the same script.
- **Queue locking.** Use atomic write (temp file + rename) for queue updates; no fcntl/lockfile. Concurrent daemon + skill are serialized by the OS rename atomicity.
- **Cross-platform pid handling.** On Windows, `os.kill(pid, 0)` works for liveness check via `WaitForSingleObject`. Stdlib supports this.
- **Daemonize via OS service.** Out of scope for v1.7. `docs/watcher.md` shows a 4-line systemd unit and a 4-line launchd plist as user-supplied wrappers.
