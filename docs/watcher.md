# Raw watcher

Detect new files in `raw/{articles,papers,transcripts,external}/` and
queue them for ingestion. The watcher never invokes `wiki-ingest`
itself — the agent does that on `/wiki-watch --drain`. Detection is
filesystem-only; no chat session, no external service.

## Why this exists

The wiki's "compiled once, kept current" property requires the human
to remember to run `wiki-ingest` shortly after each new source lands.
In practice that's where the loop breaks — files pile up, then ingestion
becomes a chore. v1.7 closes the gap by making "what's pending?" a
one-line question.

## Quick start

```bash
# Start the daemon (5-second polling, runs until --stop)
/kata:wiki-watch --start

# Drop a file in raw/articles/ — Web Clipper, curl, drag-and-drop, anything

# Check status (does not require daemon)
/kata:wiki-watch --status

# Process all pending files in one go
/kata:wiki-watch --drain

# Stop the daemon when done
/kata:wiki-watch --stop
```

## Architecture

```
                  ┌─────────────────────────────────┐
                  │ user drops file in raw/articles/ │
                  └────────────────┬────────────────┘
                                   ▼
                ┌──────────────────────────────────┐
                │ wiki_watch.py daemon (polling)    │
                │  - 5s poll, 5s debounce          │
                │  - skip files < 100 bytes        │
                │  - skip files not in (.md, .txt, │
                │    .html, .pdf)                  │
                └────────────────┬─────────────────┘
                                 ▼
                ┌──────────────────────────────────┐
                │ .wiki-ingest-queue.json          │
                │   pending → processed / failed / │
                │             removed              │
                └────────────────┬─────────────────┘
                                 ▼
                ┌──────────────────────────────────┐
                │ /wiki-watch --drain (skill)      │
                │   loops pending → wiki-ingest    │
                │   marks each queue entry         │
                │   appends 1 log.md entry         │
                └──────────────────────────────────┘
```

## Queue lifecycle

Every file the watcher has ever seen lives in
`{wiki_path}/.wiki-ingest-queue.json`. Status transitions:

- `pending` — detected, awaiting `wiki-ingest`
- `processed` — `wiki-ingest` succeeded; can be pruned
- `failed` — `wiki-ingest` errored; review and retry
- `removed` — user explicitly dropped via `--remove`

Entries are never silently deleted. Run `queue prune --older-than 30`
periodically to clean up entries with non-`pending` status older than
30 days.

## Configuration

### Polling and debounce

```bash
# Faster polling (more responsive, more I/O)
/kata:wiki-watch --start --poll 1 --debounce 2

# Slower polling (lighter, suitable for batched workflows)
/kata:wiki-watch --start --poll 30 --debounce 10
```

Defaults (5/5) are calibrated for Obsidian Web Clipper's multi-pass
save behavior. Files with rapidly-changing size or mtime get held in
debounce until they stabilize.

### What's watched

Hardcoded in v1.7: `raw/articles/`, `raw/papers/`, `raw/transcripts/`,
`raw/external/`. Not configurable from SCHEMA.md (yet — feedback during
dogfood will tell us if this should be exposed). `raw/imported/` and
`raw/assets/` are deliberately not watched (handled by import workflow
and ingest-time download respectively).

### What's filtered

- Files smaller than `--min-size` (default 100 bytes) — likely scratch
- File extensions other than `.md`, `.txt`, `.html`, `.pdf`
- Files with active size/mtime changes (debouncing)

## Daemonization

The script's `--daemon` flag detaches the process. PID and log files
are **per-wiki**: a daemon for `~/.llm-wiki/necall` writes
`~/.kata/watcher-necall-<sha1[:8]>.pid` and a paired
`watcher-necall-<sha1[:8]>.log`. The slug is `{leaf-name}-{abs-path-hash}`,
so two unrelated wikis with identical leaf names don't collide and
multiple project wikis can each run their own watcher concurrently
(`--status` / `--stop` only touch the daemon for the resolved wiki path).
This is enough for terminal users.

For users who want OS-supervised lifecycle (auto-restart, boot-time
start), wrap the script in your platform's service framework.

### Linux — systemd user unit

`~/.config/systemd/user/kata-watch.service`:

```ini
[Unit]
Description=kata raw watcher
After=default.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /path/to/plugin/scripts/wiki_watch.py \
    --wiki %h/wiki watch --heartbeat
Restart=on-failure

[Install]
WantedBy=default.target
```

Enable:
```bash
systemctl --user enable --now kata-watch
journalctl --user -u kata-watch -f   # follow logs
```

### macOS — launchd

`~/Library/LaunchAgents/com.kata.watcher.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>           <string>com.kata.watcher</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/path/to/plugin/scripts/wiki_watch.py</string>
    <string>--wiki</string>
    <string>/Users/you/wiki</string>
    <string>watch</string>
    <string>--heartbeat</string>
  </array>
  <key>RunAtLoad</key>       <true/>
  <key>KeepAlive</key>       <true/>
  <key>StandardOutPath</key> <string>/tmp/kata-watcher.log</string>
  <key>StandardErrorPath</key><string>/tmp/kata-watcher.err</string>
</dict>
</plist>
```

Load:
```bash
launchctl load ~/Library/LaunchAgents/com.kata.watcher.plist
```

### Windows — Task Scheduler

```powershell
$action = New-ScheduledTaskAction `
    -Execute "python.exe" `
    -Argument "C:\path\to\plugin\scripts\wiki_watch.py --wiki C:\Users\you\wiki watch --heartbeat"

$trigger = New-ScheduledTaskTrigger -AtLogOn

Register-ScheduledTask -TaskName "kata-watcher" `
    -Action $action -Trigger $trigger `
    -Description "kata raw/ watcher"
```

### Cron alternative — single-pass scan

If you don't want a long-running daemon, run a one-shot scan every
minute via cron:

```cron
* * * * * /usr/bin/python3 /path/to/plugin/scripts/wiki_watch.py \
    --wiki /home/you/wiki watch --max-iterations 1
```

The watcher's debounce logic still applies — files that haven't been
stable for `debounce` seconds won't be enqueued. Increase `--max-iterations`
if you want longer per-cron-tick scanning.

## Recovery from crashes

If the daemon crashes (kernel oom-killer, hard reboot), the pid file
is stale. `--start` detects this:

```
$ /kata:wiki-watch --start
Stale pid file removed (pid 12340 not running). Starting fresh daemon (pid 12567)…
```

The queue file is independent — its entries persist regardless. After
a crash, run `--status` to see what's still pending.

## What it isn't

- **Not autonomous.** Drain is always explicit. There's no `--auto-drain`
  in v1.7. A misconfigured watcher can never silently mutate wiki pages.
- **Not modification-tracking.** Only NEW files trigger enqueue. Editing
  an existing raw file doesn't re-trigger. (We could add this in v1.8 if
  there's demand.)
- **Not a session listener.** The watcher reads filesystem state and
  nothing else. Drop a file, walk away — when you come back, the queue
  remembers.

## See also

- [PRD-v1.7-watcher.md](PRD-v1.7-watcher.md) — product requirements
- [TRD-v1.7-watcher.md](TRD-v1.7-watcher.md) — technical design
- `plugin/skills/wiki-watch/SKILL.md` — full skill reference
- `plugin/scripts/wiki_watch.py` — implementation
