#!/usr/bin/env python3
"""Checkpoint + lock IO for wiki-import.

Skill calls this for state mutation rather than self-discipline. Two
related concerns live here:

1. **Checkpoint** (`.wiki-import-checkpoint.json`) — durable progress
   state for resume after crash. Cleared on phase 5 commit success
   (PRD-v1.8 §13 / round-5 fix M6).
2. **Lock** (`.wiki-import-lock`) — per-machine signal to wiki-sync
   that an import is in progress; sync preflight checks this and refuses
   to operate on a half-imported tree. PRD-v1.8 §10/§11 safety rail #8.

The lock has a `pid` field for informational symmetry with watcher
PID lock, but staleness is **time-based** (not PID-liveness-based) since
LLM-orchestrated wiki-import doesn't have a single long-running process.
A lock older than `--stale-hours` (default 24) is considered stale.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wiki_lib import find_wiki_root, is_pid_alive

CHECKPOINT_NAME = ".wiki-import-checkpoint.json"
LOCK_NAME = ".wiki-import-lock"
DEFAULT_STALE_HOURS = 24


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wiki", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("read")
    sub.add_parser("clear")

    init = sub.add_parser("init")
    init.add_argument("--source", required=True)
    init.add_argument("--format", required=True)
    init.add_argument("--total", type=int, required=True)

    update = sub.add_parser("update")
    update.add_argument("--processed", type=int, required=True)
    update.add_argument("--last-file", required=True)

    skip = sub.add_parser("skip")
    skip.add_argument("--file", required=True)
    skip.add_argument("--reason", default="")

    err = sub.add_parser("error")
    err.add_argument("--file", required=True)
    err.add_argument("--message", required=True)

    # Lock subcommands (PRD-v1.8 §10 / §11.8)
    lock = sub.add_parser("lock",
                          help="Create .wiki-import-lock to signal "
                               "wiki-sync that import is in progress")
    lock.add_argument("--source", required=True)
    lock.add_argument("--format", required=True)

    sub.add_parser("unlock",
                   help="Delete .wiki-import-lock (idempotent)")

    check_lock = sub.add_parser("check-lock",
                                help="Inspect .wiki-import-lock; emit JSON "
                                     "with status=missing|alive|stale")
    check_lock.add_argument("--stale-hours", type=int,
                            default=DEFAULT_STALE_HOURS,
                            help="Lock older than this is stale "
                                 f"(default {DEFAULT_STALE_HOURS}h)")

    args = p.parse_args()
    root = find_wiki_root(args.wiki)
    cp_path = root / CHECKPOINT_NAME
    lock_path = root / LOCK_NAME

    # ---- Lock subcommands ----
    if args.cmd == "lock":
        return _cmd_lock(lock_path, args.source, args.format)

    if args.cmd == "unlock":
        return _cmd_unlock(lock_path)

    if args.cmd == "check-lock":
        return _cmd_check_lock(lock_path, args.stale_hours)

    # ---- Checkpoint subcommands ----
    if args.cmd == "read":
        if not cp_path.exists():
            print(json.dumps({"exists": False}))
            return 0
        print(cp_path.read_text(encoding="utf-8"))
        return 0

    if args.cmd == "clear":
        if cp_path.exists():
            cp_path.unlink()
        print(json.dumps({"cleared": True}))
        return 0

    state = {}
    if cp_path.exists():
        try:
            state = json.loads(cp_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}

    if args.cmd == "init":
        state = {
            "source_path": args.source,
            "format": args.format,
            "total_files": args.total,
            "processed": 0,
            "last_file": None,
            "timestamp": _now(),
            "skipped": [],
            "errors": [],
        }
    elif args.cmd == "update":
        state["processed"] = args.processed
        state["last_file"] = args.last_file
        state["timestamp"] = _now()
    elif args.cmd == "skip":
        state.setdefault("skipped", []).append(
            {"file": args.file, "reason": args.reason})
        state["timestamp"] = _now()
    elif args.cmd == "error":
        state.setdefault("errors", []).append(
            {"file": args.file, "message": args.message})
        state["timestamp"] = _now()

    cp_path.write_text(json.dumps(state, indent=2, ensure_ascii=False),
                       encoding="utf-8")
    print(json.dumps(state, indent=2, ensure_ascii=False))
    return 0


# ────────────────────── LOCK IO ──────────────────────────

def _cmd_lock(lock_path: Path, source: str, format_: str) -> int:
    """Create the import lock. Refuse if a non-stale lock exists."""
    if lock_path.exists():
        try:
            existing = json.loads(lock_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
        # If existing lock is fresh, refuse (concurrent import).
        # Time-based staleness: file mtime / started_at.
        started = _parse_iso(existing.get("started_at"))
        if started and (datetime.now(timezone.utc) - started
                        < timedelta(hours=DEFAULT_STALE_HOURS)):
            print(json.dumps({
                "error": "import lock exists and is fresh; another import "
                         "may be in progress",
                "lock": existing,
            }))
            return 1
        # Stale lock: warn and overwrite
        print(json.dumps({
            "warning": "stale lock cleared",
            "previous_lock": existing,
        }), end="\n")  # caller can ignore but we surface it

    payload = {
        "pid": os.getpid(),  # informational only — process exits immediately
        "started_at": _now(),
        "source": source,
        "format": format_,
    }
    lock_path.write_text(json.dumps(payload, indent=2,
                                    ensure_ascii=False),
                         encoding="utf-8")
    print(json.dumps({"locked": True, **payload}))
    return 0


def _cmd_unlock(lock_path: Path) -> int:
    """Delete the import lock. Idempotent — no error if missing."""
    if lock_path.exists():
        lock_path.unlink()
        print(json.dumps({"unlocked": True}))
    else:
        print(json.dumps({"unlocked": False, "reason": "no lock file"}))
    return 0


def _cmd_check_lock(lock_path: Path, stale_hours: int) -> int:
    """Inspect lock; emit JSON status. Used by wiki-sync preflight.

    Status:
      - "missing": no lock file → sync may proceed
      - "alive":   lock fresh (within stale_hours) → sync should friendly-exit
      - "stale":   lock older than stale_hours → sync may clear and proceed
    """
    if not lock_path.exists():
        print(json.dumps({"status": "missing"}))
        return 0
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Corrupt lock file — treat as stale
        print(json.dumps({"status": "stale", "reason": "corrupt lock JSON"}))
        return 0

    started = _parse_iso(data.get("started_at"))
    pid = data.get("pid", 0) if isinstance(data.get("pid"), int) else 0

    # Time-based staleness is the source of truth (LLM-orchestrated import
    # has no stable PID). PID liveness is informational.
    age_hours = None
    if started:
        age_hours = (datetime.now(timezone.utc) - started).total_seconds() / 3600
    is_stale = (age_hours is None) or (age_hours > stale_hours)

    print(json.dumps({
        "status": "stale" if is_stale else "alive",
        "lock": data,
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "stale_threshold_hours": stale_hours,
        "pid_alive_hint": is_pid_alive(pid),  # informational
    }))
    return 0


# ────────────────────── HELPERS ──────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s) -> datetime | None:
    if not isinstance(s, str):
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
