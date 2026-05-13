#!/usr/bin/env python3
"""Polling watcher for raw/{articles,papers,transcripts,external}/.

Detects new files, debounces against in-progress writes, and enqueues
them for human-triggered ingestion via the wiki-watch skill. The script
NEVER invokes wiki-ingest itself — that's the skill's job (LLM-driven).

Stdlib only. No inotify / watchdog dependency.

Usage:
    wiki_watch.py --wiki <path> watch [--daemon] [--poll 5] [--debounce 5]
    wiki_watch.py --wiki <path> status
    wiki_watch.py --wiki <path> stop
    wiki_watch.py --wiki <path> queue list
    wiki_watch.py --wiki <path> queue mark <id> <status>
    wiki_watch.py --wiki <path> queue remove <id>
    wiki_watch.py --wiki <path> queue prune --older-than 30
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from wiki_lib import emit, find_wiki_root, is_pid_alive, wiki_slug

QUEUE_NAME = ".wiki-ingest-queue.json"
WATCHED_DIRS = ("raw/articles", "raw/papers", "raw/transcripts", "raw/external")
DEFAULT_POLL = 5
DEFAULT_DEBOUNCE = 5
DEFAULT_MIN_SIZE = 100
WATCHED_EXTS = (".md", ".txt", ".html", ".pdf")
PID_DIR = Path.home() / ".kata"


def pid_file_path(root: Path) -> Path:
    PID_DIR.mkdir(parents=True, exist_ok=True)
    return PID_DIR / f"watcher-{wiki_slug(root)}.pid"


def log_file_path(root: Path) -> Path:
    PID_DIR.mkdir(parents=True, exist_ok=True)
    return PID_DIR / f"watcher-{wiki_slug(root)}.log"


# ────────────────────── QUEUE IO ──────────────────────────

def queue_path(root: Path) -> Path:
    return root / QUEUE_NAME


def load_queue(root: Path) -> dict:
    qp = queue_path(root)
    if not qp.exists():
        return {"version": 1, "updated_at": _now_iso(), "entries": []}
    try:
        return json.loads(qp.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "updated_at": _now_iso(), "entries": []}


def save_queue(root: Path, data: dict) -> None:
    """Atomic write — temp file + rename."""
    qp = queue_path(root)
    data["updated_at"] = _now_iso()
    tmp = qp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(qp)


def enqueue(root: Path, rel_path: str, size: int, mtime: float) -> str:
    q = load_queue(root)
    # Skip if already queued (any status)
    for e in q["entries"]:
        if e["path"] == rel_path and e["status"] == "pending":
            return e["id"]
    entry_id = f"Q-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    q["entries"].append({
        "id": entry_id,
        "path": rel_path,
        "detected_at": _now_iso(),
        "size": size,
        "mtime": _ts_iso(mtime),
        "status": "pending",
    })
    save_queue(root, q)
    _append_log(root, "watch | enqueue", [
        f"- File: {rel_path}",
        f"- Size: {size} bytes",
        f"- Queue ID: {entry_id}",
    ])
    return entry_id


def mark_status(root: Path, entry_id: str, status: str,
                extra: dict | None = None) -> bool:
    q = load_queue(root)
    found = False
    for e in q["entries"]:
        if e["id"] == entry_id:
            e["status"] = status
            if status == "processed":
                e["processed_at"] = _now_iso()
            elif status == "failed":
                e["failed_at"] = _now_iso()
            if extra:
                e.update(extra)
            found = True
            break
    if found:
        save_queue(root, q)
    return found


def list_queue(root: Path, status_filter: str | None = None) -> list[dict]:
    q = load_queue(root)
    if status_filter:
        return [e for e in q["entries"] if e["status"] == status_filter]
    return q["entries"]


def prune_queue(root: Path, days: int) -> int:
    q = load_queue(root)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    before = len(q["entries"])
    q["entries"] = [
        e for e in q["entries"]
        if e["status"] == "pending"
        or _parse_iso(e.get("processed_at") or e.get("failed_at") or
                     e["detected_at"]) >= cutoff
    ]
    pruned = before - len(q["entries"])
    if pruned:
        save_queue(root, q)
    return pruned


# ────────────────────── WATCHER LOOP ──────────────────────────

def watch_loop(root: Path, poll: int, debounce: int, min_size: int,
               heartbeat: bool = False, max_iterations: int | None = None) -> None:
    """Main polling loop. Detects new files, debounces, enqueues."""
    pending_debounce: dict[str, tuple[int, float, float]] = {}
    # path -> (size, mtime, first_seen_ts)
    seen_processed: set[str] = set()  # paths we've already enqueued or skipped
    iteration = 0
    while True:
        iteration += 1
        try:
            _scan_once(root, pending_debounce, seen_processed,
                       debounce, min_size)
        except Exception as e:
            print(f"[watcher] error in scan: {e}", file=sys.stderr)
        if heartbeat:
            print(f"[watcher] poll #{iteration} ok", flush=True)
        if max_iterations and iteration >= max_iterations:
            return
        time.sleep(poll)


def _scan_once(root: Path, pending_debounce: dict, seen_processed: set,
               debounce: int, min_size: int) -> None:
    now = time.time()
    # Refresh the seen_processed set from queue so the daemon re-syncs
    # if the queue was modified externally
    queued_paths = {e["path"] for e in load_queue(root)["entries"]}
    seen_processed |= queued_paths

    for sub in WATCHED_DIRS:
        d = root / sub
        if not d.exists() or not d.is_dir():
            continue
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for entry in entries:
            if not entry.is_file():
                continue
            if not entry.name.lower().endswith(WATCHED_EXTS):
                continue
            rel = (Path(sub) / entry.name).as_posix()
            if rel in seen_processed:
                continue
            try:
                stat = entry.stat()
            except OSError:
                continue
            if stat.st_size < min_size:
                # Note: don't add to seen_processed — file may grow later
                continue

            state = (stat.st_size, stat.st_mtime)
            if rel in pending_debounce:
                last_size, last_mtime, first_seen = pending_debounce[rel]
                if state[:2] == (last_size, last_mtime):
                    if now - first_seen >= debounce:
                        # Stable — enqueue
                        enqueue(root, rel, stat.st_size, stat.st_mtime)
                        seen_processed.add(rel)
                        del pending_debounce[rel]
                else:
                    # Still changing, reset clock
                    pending_debounce[rel] = (state[0], state[1], now)
            else:
                # First sighting
                pending_debounce[rel] = (state[0], state[1], now)


# ────────────────────── DAEMON LIFECYCLE ──────────────────────────

def read_pid_file(root: Path) -> tuple[int, dict] | None:
    pf = pid_file_path(root)
    if not pf.exists():
        return None
    try:
        data = json.loads(pf.read_text(encoding="utf-8"))
        return data.get("pid", 0), data
    except (json.JSONDecodeError, OSError):
        return None


def write_pid_file(pid: int, root: Path) -> None:
    pid_file_path(root).write_text(json.dumps({
        "pid": pid,
        "wiki": str(root),
        "started_at": _now_iso(),
    }, indent=2), encoding="utf-8")


def remove_pid_file(root: Path) -> None:
    pf = pid_file_path(root)
    if pf.exists():
        pf.unlink()


def daemonize(root: Path, poll: int, debounce: int, min_size: int) -> int:
    """Spawn the watch loop as a background process. Returns child pid."""
    import subprocess
    log_file = log_file_path(root)
    creationflags = 0
    start_new_session = False
    if sys.platform == "win32":
        creationflags = (
            subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        )
    else:
        start_new_session = True

    cmd = [
        sys.executable, str(Path(__file__).resolve()),
        "--wiki", str(root),
        "watch",
        "--poll", str(poll),
        "--debounce", str(debounce),
        "--min-size", str(min_size),
        "--heartbeat",
    ]
    log_handle = log_file.open("a", encoding="utf-8")
    log_handle.write(f"\n=== daemon spawn {_now_iso()} ===\n")
    log_handle.flush()
    proc = subprocess.Popen(
        cmd, stdout=log_handle, stderr=log_handle, stdin=subprocess.DEVNULL,
        creationflags=creationflags, start_new_session=start_new_session,
        cwd=str(root),
    )
    write_pid_file(proc.pid, root)
    return proc.pid


def stop_daemon(root: Path) -> dict:
    info = read_pid_file(root)
    if not info:
        return {"stopped": False, "reason": "no pid file"}
    pid, data = info
    if not is_pid_alive(pid):
        remove_pid_file(root)
        return {"stopped": False, "reason": "stale pid file removed",
                "stale_pid": pid}
    try:
        if sys.platform == "win32":
            # Windows: signal.SIGTERM falls back to TerminateProcess
            os.kill(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError as e:
        return {"stopped": False, "reason": f"kill failed: {e}", "pid": pid}
    # Wait up to 5s for clean exit
    for _ in range(50):
        if not is_pid_alive(pid):
            break
        time.sleep(0.1)
    if is_pid_alive(pid):
        return {"stopped": False, "reason": "still alive after SIGTERM",
                "pid": pid}
    remove_pid_file(root)
    return {"stopped": True, "pid": pid, "data": data}


def status(root: Path) -> dict:
    info = read_pid_file(root)
    if not info:
        return {"running": False, "reason": "no pid file"}
    pid, data = info
    if not is_pid_alive(pid):
        return {"running": False, "reason": "stale pid file",
                "stale_pid": pid, "data": data}
    return {"running": True, "pid": pid, "data": data,
            "log_file": str(log_file_path(root))}


# ────────────────────── HELPERS ──────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc) - timedelta(days=365)  # treat as old


def _append_log(root: Path, action: str, lines: list[str]) -> None:
    log = root / "log.md"
    if not log.exists():
        return
    entry = f"\n## [{date.today().isoformat()}] {action}\n"
    for ln in lines:
        entry += ln + "\n"
    with log.open("a", encoding="utf-8") as f:
        f.write(entry)


# ────────────────────── CLI ──────────────────────────

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wiki", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("watch")
    w.add_argument("--daemon", action="store_true")
    w.add_argument("--poll", type=int, default=DEFAULT_POLL)
    w.add_argument("--debounce", type=int, default=DEFAULT_DEBOUNCE)
    w.add_argument("--min-size", type=int, default=DEFAULT_MIN_SIZE)
    w.add_argument("--heartbeat", action="store_true",
                   help="Print 'poll #N ok' lines for log file")
    w.add_argument("--max-iterations", type=int, default=None,
                   help="Exit after N polls (testing only)")

    sub.add_parser("status")
    sub.add_parser("stop")

    q = sub.add_parser("queue")
    qsub = q.add_subparsers(dest="qcmd", required=True)
    ql = qsub.add_parser("list")
    ql.add_argument("--status", default=None,
                    choices=["pending", "processed", "failed", "removed"])
    qm = qsub.add_parser("mark")
    qm.add_argument("entry_id")
    qm.add_argument("status",
                    choices=["pending", "processed", "failed", "removed"])
    qr = qsub.add_parser("remove")
    qr.add_argument("entry_id")
    qp = qsub.add_parser("prune")
    qp.add_argument("--older-than", type=int, default=30)

    args = p.parse_args()
    root = find_wiki_root(args.wiki)

    if args.cmd == "watch":
        if args.daemon:
            existing = read_pid_file(root)
            if existing and is_pid_alive(existing[0]):
                emit({"error": "daemon already running",
                      "pid": existing[0], "data": existing[1]})
                return 1
            pid = daemonize(root, args.poll, args.debounce, args.min_size)
            emit({"daemonized": True, "pid": pid, "wiki": str(root),
                  "log": str(log_file_path(root))})
            return 0
        # Foreground mode
        if not args.heartbeat:
            print(f"[watcher] watching {root} (poll={args.poll}s, "
                  f"debounce={args.debounce}s). Ctrl-C to stop.", flush=True)
        watch_loop(root, args.poll, args.debounce, args.min_size,
                   heartbeat=args.heartbeat,
                   max_iterations=args.max_iterations)
        return 0

    if args.cmd == "status":
        emit({**status(root),
              "wiki": str(root),
              "queue_summary": _queue_summary(root)})
        return 0

    if args.cmd == "stop":
        emit({**stop_daemon(root), "wiki": str(root)})
        return 0

    if args.cmd == "queue":
        if args.qcmd == "list":
            emit({"entries": list_queue(root, args.status)})
        elif args.qcmd == "mark":
            ok = mark_status(root, args.entry_id, args.status)
            emit({"marked": ok, "id": args.entry_id, "status": args.status})
        elif args.qcmd == "remove":
            ok = mark_status(root, args.entry_id, "removed")
            emit({"removed": ok, "id": args.entry_id})
        elif args.qcmd == "prune":
            n = prune_queue(root, args.older_than)
            emit({"pruned": n, "older_than_days": args.older_than})
        return 0

    return 0


def _queue_summary(root: Path) -> dict:
    entries = load_queue(root)["entries"]
    summary = {"pending": 0, "processed": 0, "failed": 0, "removed": 0}
    for e in entries:
        s = e["status"]
        summary[s] = summary.get(s, 0) + 1
    summary["total"] = len(entries)
    return summary


if __name__ == "__main__":
    sys.exit(main())
