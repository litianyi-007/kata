#!/usr/bin/env python3
"""Multi-machine git sync orchestrator (PRD-v1.8 §6).

Pulls origin/<branch>, merges or fast-forwards, pushes back. Custom merge
drivers (merge_log.py for log.md) auto-handle the union/dedup cases.
Conflicts produce reports under ~/.kata/sync-reports/{slug}/.

Usage:
    wiki_sync.py [--wiki PATH] [--auto] [--dry-run]

State machine: try / finally with layered cleanup. Lock is always released.
Stash (if taken) is applied back IF working tree is clean afterwards.
Sync report is written for any non-trivial outcome.

Exit codes:
    0 — up-to-date / pushed / fast-forwarded / merged-clean
    1 — conflicts / force-push detected / identity mismatch / unrelated
        history / import in progress / merge in progress / lock held /
        push race exhausted / unexpected error
    2 — usage error
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wiki_lib import (  # noqa: E402
    emit,
    find_wiki_root,
    is_pid_alive,
    load_schema,
    wiki_slug,
)

PID_DIR = Path.home() / ".kata"
PLUGIN_ROOT = Path(__file__).resolve().parents[1]   # plugin/

PUSH_RETRY_BACKOFF = (1, 2, 4)

# Narrow race-marker patterns (review-2 MEDIUM-2). Earlier "any 'rejected'
# in stderr → race" was too loose; pre-receive hook reject / branch
# protection / permission denied also produce "rejected" but should NOT
# be retried. Only these specific git messages indicate non-fast-forward
# race that re-fetch+re-merge can solve.
#
# Git's wording varies across versions / platforms / protocols:
# - classic: "rejected (non-fast-forward)" / "non-fast-forward"
# - smart-protocol: "fetch first" / "stale info"
# - hint: "tip of your current branch is behind"
# - filesystem-protocol (Git for Windows local file remote, atomic push):
#   "cannot lock ref ... but expected ..." / "incorrect old value provided"
RACE_MARKERS = (
    "non-fast-forward",
    "non-fast forward",
    "fetch first",
    "stale info",
    "tip of your current branch is behind",
    "incorrect old value provided",
    "cannot lock ref",
)


def _is_push_race(stderr: str) -> bool:
    """True only for non-fast-forward race patterns. Hook decline,
    permission denied, etc. → False (caller treats as push-failed)."""
    s = stderr.lower()
    return any(m in s for m in RACE_MARKERS)


# ────────────────────── state ──────────────────────────

@dataclass
class SyncState:
    wiki_root: Path
    machine_slug: str
    remote: str = "origin"
    branch: str = "main"
    auto: bool = False
    dry_run: bool = False
    auto_configure_drivers: bool = True
    on_conflict: str = "report-and-exit"

    lock_path: Path | None = None
    lock_acquired: bool = False
    stash_sha: str | None = None
    stash_msg: str | None = None
    old_origin_sha: str | None = None
    new_origin_sha: str | None = None
    drivers_just_configured: bool = False

    local_wiki_id: str | None = None
    result: str = "unknown"
    unmerged_paths: list[str] = field(default_factory=list)
    report_lines: list[str] = field(default_factory=list)


# ────────────────────── git helpers ──────────────────────────

def _git(state: SyncState, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run a git command in the wiki root. Returns CompletedProcess.

    Force UTF-8 decoding — SCHEMA.md routinely has non-ASCII content (Chinese
    domain names, em-dashes) and Windows' default GBK codec corrupts
    `proc.stdout` to None when it can't decode. errors='replace' keeps us
    tolerant of any random byte that slips in (e.g. binary-ish raw/papers/).
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(state.wiki_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def _git_rev_parse(state: SyncState, ref: str) -> str | None:
    proc = _git(state, "rev-parse", "--verify", ref)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _is_ancestor(state: SyncState, ancestor: str, descendant: str) -> bool:
    proc = _git(state, "merge-base", "--is-ancestor", ancestor, descendant)
    return proc.returncode == 0


def _merge_base(state: SyncState, a: str, b: str) -> str | None:
    proc = _git(state, "merge-base", a, b)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


# ────────────────────── lock ──────────────────────────

def _lock_path_for(root: Path) -> Path:
    PID_DIR.mkdir(parents=True, exist_ok=True)
    return PID_DIR / f"sync-{wiki_slug(root)}.lock"


def acquire_lock(state: SyncState) -> bool:
    """Acquire local sync lock atomically (PRD §11.2 + review-1 LOW-1).

    Uses os.open with O_CREAT | O_EXCL — only one process can create the
    file. If the create fails because the file exists, read it and decide:
    stale (PID dead) → unlink and retry; live → caller exits friendly.

    Bounded retry on stale-cleanup race: at most 3 attempts to handle the
    case where two processes both see stale and both try to unlink.
    """
    state.lock_path = _lock_path_for(state.wiki_root)
    payload = {
        "pid": os.getpid(),
        "started_at": _iso_now(),
        "wiki": str(state.wiki_root),
    }
    payload_json = json.dumps(payload, indent=2)

    for attempt in range(3):
        try:
            # Atomic create — fails if path exists
            fd = os.open(str(state.lock_path),
                         os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            try:
                os.write(fd, payload_json.encode("utf-8"))
            finally:
                os.close(fd)
            state.lock_acquired = True
            return True
        except FileExistsError:
            # Read existing lock and decide
            try:
                existing = json.loads(
                    state.lock_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = {}
            existing_pid = existing.get("pid", 0) if isinstance(
                existing.get("pid"), int) else 0
            if existing_pid > 0 and existing_pid != os.getpid() \
                    and is_pid_alive(existing_pid):
                state.report_lines.append(
                    f"local sync lock held by pid {existing_pid} "
                    f"(started {existing.get('started_at', '?')}); "
                    f"exiting friendly")
                return False
            # Stale (or our own re-entry) — try to unlink and retry
            try:
                state.lock_path.unlink()
            except FileNotFoundError:
                pass  # another process already unlinked, retry the create
            # else: continue loop and try create again

    # Couldn't acquire after retries — treat as held to be safe
    state.report_lines.append(
        f"local sync lock could not be acquired after 3 stale-cleanup "
        f"retries; another process may be repeatedly racing")
    return False


def release_lock(state: SyncState) -> None:
    if state.lock_path and state.lock_path.exists():
        try:
            state.lock_path.unlink()
        except OSError as e:
            sys.stderr.write(
                f"[wiki-sync] failed to release lock {state.lock_path}: {e}\n")
    state.lock_acquired = False


# ────────────────────── stash ──────────────────────────

def _has_dirty_tracked(state: SyncState) -> bool:
    """Tracked-only dirty detection. Untracked files don't trigger stash
    (they're per-machine state by convention; gitignored or scratch).
    """
    proc = _git(state, "status", "--porcelain")
    if proc.returncode != 0:
        return False
    # Lines starting with '??' are untracked; ignore them.
    for line in proc.stdout.splitlines():
        if not line:
            continue
        if line[:2] == "??":
            continue
        return True
    return False


def stash_if_dirty(state: SyncState) -> bool:
    """Stash tracked changes BEFORE any operation that might touch the
    working tree (PRD §6.4 H3 round-2).

    Returns True on success or no-op. Captures stash SHA via
    `git rev-parse refs/stash` (PRD §6.4 H1b round-2).
    """
    if not _has_dirty_tracked(state):
        return True

    state.stash_msg = f"[kata sync] auto-stash {_iso_now()}"
    proc = _git(state, "stash", "push", "-m", state.stash_msg)
    if proc.returncode != 0:
        state.report_lines.append(
            f"git stash push failed: {proc.stderr.strip()[:300]}")
        return False

    sha = _git_rev_parse(state, "refs/stash")
    if sha:
        state.stash_sha = sha
    return True


def _find_stash_index_by_sha(state: SyncState, target_sha: str) -> int | None:
    """Locate stash@{n} whose commit SHA equals target_sha (H1b round-3)."""
    proc = _git(state, "stash", "list", "--format=%H")
    if proc.returncode != 0:
        return None
    for i, line in enumerate(proc.stdout.splitlines()):
        if line.strip() == target_sha:
            return i
    return None


def restore_stash(state: SyncState) -> None:
    """Apply stash by SHA and drop the corresponding stash@{n}.

    Only runs when working tree is clean (no unmerged paths). On conflict
    paths, the stash is intentionally left for the user to recover.
    """
    if not state.stash_sha:
        return
    if _has_unmerged_paths(state) or _has_dirty_tracked(state):
        state.report_lines.append(
            f"stash kept at commit {state.stash_sha[:8]} "
            f"(working tree not clean); recover with "
            f"`git stash apply {state.stash_sha}`")
        return

    proc = _git(state, "stash", "apply", state.stash_sha)
    if proc.returncode != 0:
        state.report_lines.append(
            f"`git stash apply {state.stash_sha[:8]}` failed: "
            f"{proc.stderr.strip()[:300]}; data preserved as commit, "
            f"recover manually")
        return

    idx = _find_stash_index_by_sha(state, state.stash_sha)
    if idx is not None:
        _git(state, "stash", "drop", f"stash@{{{idx}}}")
    # If not found in stash list (rare), no drop needed; commit SHA still
    # accessible via reflog if user wants.


# ────────────────────── preflight ──────────────────────────

def _has_unmerged_paths(state: SyncState) -> bool:
    proc = _git(state, "diff", "--name-only", "--diff-filter=U")
    if proc.returncode != 0:
        return False
    return bool(proc.stdout.strip())


def preflight(state: SyncState) -> tuple[bool, str | None]:
    """Pre-merge sanity checks. Returns (ok, reason) tuple.

    ok=False with reason → set state.result and exit 1.
    PRD §6.3.6: .git exists, origin configured, no MERGE/REBASE/CHERRY_PICK
    in progress, .wiki-import-lock check, .wiki-import-checkpoint.json check.
    """
    if not (state.wiki_root / ".git").exists():
        return False, "wiki has no .git directory; sync needs a git repo"

    proc = _git(state, "remote", "get-url", state.remote)
    if proc.returncode != 0:
        # PRD §11.7 friendly degrade
        state.result = "no-remote"
        return False, (f"no remote '{state.remote}' configured; "
                       f"sync skipped (this is friendly, not an error)")

    git_dir = state.wiki_root / ".git"
    for marker in ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD",
                   "rebase-merge", "rebase-apply"):
        if (git_dir / marker).exists():
            state.result = "merge-in-progress"
            return False, (f"{marker} present in .git/; finish the in-flight "
                           f"merge/rebase/cherry-pick first (`git merge "
                           f"--abort` or `git rebase --abort`)")

    # .wiki-import-lock check (PRD §11.8)
    import_lock = state.wiki_root / ".wiki-import-lock"
    if import_lock.exists():
        try:
            data = json.loads(import_lock.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        # Time-based staleness (24h default per import_checkpoint.py)
        started = data.get("started_at")
        is_stale = True
        if isinstance(started, str):
            try:
                t = datetime.strptime(started, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc)
                age_hours = (datetime.now(timezone.utc) - t).total_seconds() / 3600
                is_stale = age_hours > 24
            except (ValueError, TypeError):
                pass
        if not is_stale:
            state.result = "import-in-progress"
            return False, (f"wiki-import is in progress "
                           f"(source={data.get('source', '?')}, "
                           f"started={data.get('started_at', '?')}); "
                           f"rerun wiki-sync after it finishes")
        # Stale → auto-clean and continue
        try:
            import_lock.unlink()
            state.report_lines.append(
                f"removed stale .wiki-import-lock (started "
                f"{data.get('started_at', '?')}, > 24h ago)")
        except OSError:
            pass

    # .wiki-import-checkpoint.json check (PRD round-3 M2)
    cp = state.wiki_root / ".wiki-import-checkpoint.json"
    if cp.exists():
        state.result = "import-checkpoint-blocking"
        return False, (
            "wiki-import was interrupted; .wiki-import-checkpoint.json "
            "is present in working tree. Resume with `wiki-import "
            "--resume` or clean it up before sync (running sync now would "
            "merge against half-imported content)")

    return True, None


# ────────────────────── identity ──────────────────────────

def _extract_wiki_id(text: str) -> str | None:
    m = re.search(
        r"^\s*wiki_id\s*:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
        r"[0-9a-f]{4}-[0-9a-f]{12})", text, re.MULTILINE)
    return m.group(1) if m else None


def load_local_wiki_id(state: SyncState) -> tuple[bool, str | None]:
    schema_md = state.wiki_root / "SCHEMA.md"
    if not schema_md.exists():
        return False, "SCHEMA.md not found; cannot read wiki_id"
    text = schema_md.read_text(encoding="utf-8")
    wid = _extract_wiki_id(text)
    if not wid:
        return False, (
            "wiki_id missing from SCHEMA.md; sync requires a wiki_id "
            "for cross-machine identity check. Run `wiki-init "
            "--refresh-id --path <wiki>` to generate one")
    state.local_wiki_id = wid
    return True, None


def check_remote_identity(state: SyncState) -> tuple[bool, str | None]:
    """Compare remote SCHEMA.md's wiki_id to local. PRD §6.9 / §11.9."""
    proc = _git(state, "show", f"{state.remote}/{state.branch}:SCHEMA.md")
    if proc.returncode != 0:
        # Remote SCHEMA.md missing — warn but allow (legacy wiki upgrading)
        state.report_lines.append(
            f"remote SCHEMA.md not found at {state.remote}/{state.branch}; "
            f"identity check skipped (legacy wiki?)")
        return True, None
    remote_wid = _extract_wiki_id(proc.stdout)
    if not remote_wid:
        state.report_lines.append(
            f"remote SCHEMA.md has no wiki_id; identity check skipped "
            f"(legacy wiki?)")
        return True, None
    if remote_wid != state.local_wiki_id:
        state.result = "identity-mismatch"
        return False, (
            f"remote wiki_id={remote_wid} does NOT match local "
            f"wiki_id={state.local_wiki_id}. This means the remote is a "
            f"different wiki than the local one. Aborting sync to prevent "
            f"merging unrelated knowledge bases. If intentional, "
            f"reconfigure your git remote or run wiki-init --refresh-id")
    return True, None


# ────────────────────── driver registration ──────────────────────────

# Drivers we manage (PRD §8). Currently only merge_log; merge_index lands
# in v1.8 full version per §13 phasing.
def _driver_command(script_name: str) -> str:
    """Build the `git config merge.<name>.driver` command string.

    Use sys.executable (the running Python) so each clone resolves to the
    correct interpreter without depending on PATH.
    """
    py = sys.executable
    script = PLUGIN_ROOT / "scripts" / script_name
    return f'"{py}" "{script}" %A %O %B'


DRIVERS = {
    "akwiki-log": ("merge_log.py", "kata log union+sort merge"),
}


def ensure_drivers_registered(state: SyncState) -> None:
    """Auto-register merge drivers on first sync (PRD §8 Option A 三护栏).

    Guardrail 1: every sync verifies the configured path actually exists;
                 if not, rewrite (handles plugin-moved-since-last-sync).
    Guardrail 2: writes a one-line audit to state.report_lines (and the
                 sync report files this); not log.md (deferred to
                 wiki_lib follow-up if needed).
    Guardrail 3: respects sync.auto_configure_drivers=false to honor
                 manual `git config --unset`.
    """
    if not state.auto_configure_drivers:
        return

    for short_name, (script, friendly) in DRIVERS.items():
        cmd_key = f"merge.{short_name}.driver"
        name_key = f"merge.{short_name}.name"
        desired_cmd = _driver_command(script)
        existing_cmd = _git(state, "config", "--local", "--get",
                            cmd_key).stdout.strip()

        # Verify path inside existing command actually exists
        path_ok = False
        if existing_cmd:
            # Extract the script path (second quoted token)
            mp = re.findall(r'"([^"]+)"', existing_cmd)
            if len(mp) >= 2 and Path(mp[1]).exists():
                path_ok = True

        if existing_cmd == desired_cmd and path_ok:
            continue  # already correct

        # Either unset, stale path, or different command — rewrite
        _git(state, "config", "--local", cmd_key, desired_cmd)
        _git(state, "config", "--local", name_key, friendly)
        state.drivers_just_configured = True
        state.report_lines.append(
            f"configured git driver: merge.{short_name}.driver -> "
            f"{script} (path verified)")


# ────────────────────── main flow ──────────────────────────

def run_sync(state: SyncState) -> int:
    """Main sync flow per PRD §6 sections 6.3.x — 6.12."""

    # 6.3.2: read sync.* config (already loaded into state)

    # 6.3.3: validate local wiki_id
    ok, err = load_local_wiki_id(state)
    if not ok:
        state.result = "no-wiki-id"
        state.report_lines.append(err or "wiki_id missing")
        return 1

    # 6.3.4: dry-run fork (BEFORE any side effects)
    if state.dry_run:
        return _dry_run(state)

    # 6.3.5: acquire local sync lock
    if not acquire_lock(state):
        state.result = "lock-held"
        return 1

    # 6.3.6: preflight
    ok, err = preflight(state)
    if not ok:
        if state.result == "no-remote":
            # Friendly skip — exit 0
            return 0
        state.report_lines.append(err or "preflight failed")
        return 1

    # 6.3.7: register drivers
    ensure_drivers_registered(state)

    # 6.4: stash if dirty (BEFORE any tree-modifying operation)
    if not stash_if_dirty(state):
        state.result = "stash-failed"
        return 1

    # 6.5 / 6.6 / 6.7: record pre-fetch origin SHA, fetch, record post
    state.old_origin_sha = _git_rev_parse(
        state, f"{state.remote}/{state.branch}")
    fetch_proc = _git(state, "fetch", state.remote, state.branch)
    if fetch_proc.returncode != 0:
        state.result = "fetch-failed"
        state.report_lines.append(
            f"git fetch {state.remote} {state.branch} failed: "
            f"{fetch_proc.stderr.strip()[:300]}")
        return 1
    state.new_origin_sha = _git_rev_parse(
        state, f"{state.remote}/{state.branch}")
    if not state.new_origin_sha:
        state.result = "remote-branch-missing"
        state.report_lines.append(
            f"after fetch, {state.remote}/{state.branch} ref does not "
            f"exist; remote branch may have been deleted")
        return 1

    # 6.8: ancestry classification (5 cases)
    head = _git_rev_parse(state, "HEAD")
    if not head:
        state.result = "no-head"
        state.report_lines.append("HEAD ref missing; is this a fresh repo?")
        return 1

    classification = _classify_ancestry(state, head)
    if classification != "ok":
        state.result = classification
        return 1

    # 6.9: identity check (post-fetch)
    ok, err = check_remote_identity(state)
    if not ok:
        state.report_lines.append(err or "identity check failed")
        return 1

    # 6.11 + 6.12: converge HEAD with origin — merge + push, with race
    # retry that re-fetches and re-merges per PRD §6.12 (review-1 HIGH)
    rc = _converge_with_origin(state, head)
    return rc


def _classify_ancestry(state: SyncState, head: str) -> str:
    """Return 'ok' to continue or a result string to abort with.

    Cases (PRD §6.8):
      (i)   old_origin is None AND merge-base(HEAD, origin) exists → ok
      (ii)  old_origin is None AND no merge-base → unrelated-history
      (iii) old == new → no remote change → ok
      (iv)  old != new AND old is ancestor of new → ok (normal advance)
      (v)   old != new AND old NOT ancestor of new → force-push-detected
    """
    old = state.old_origin_sha
    new = state.new_origin_sha

    if old is None:
        # First fetch on this machine (or never had remote-tracking ref)
        mb = _merge_base(state, head, new)
        if not mb:
            # No common ancestor → unrelated histories
            return "unrelated-history"
        return "ok"

    if old == new:
        return "ok"

    # old != new — was the advance fast-forwardable?
    if _is_ancestor(state, old, new):
        return "ok"

    return "force-push-detected"


def _list_unmerged_paths(state: SyncState) -> list[str]:
    proc = _git(state, "diff", "--name-only", "--diff-filter=U")
    if proc.returncode != 0:
        return []
    return [p for p in proc.stdout.splitlines() if p.strip()]


def _converge_with_origin(state: SyncState, initial_head: str) -> int:
    """PRD §6.11 + §6.12: converge HEAD with origin/<branch>.

    On each iteration: classify HEAD vs origin (equal/ahead/behind/diverge);
    perform fast-forward, push, or merge+push as appropriate. On
    non-fast-forward push race, re-fetch and re-classify (which may produce
    a different category — e.g. what was "ahead" becomes "diverge" after
    origin advances).

    Bounded at len(PUSH_RETRY_BACKOFF)+1 attempts (4 total). Each retry
    backs off via the constant tuple. PRD §6.12 review-1 HIGH fix: prior
    version refused to re-merge inside the retry loop and went straight to
    race-exhausted. This version handles the diverge-after-race case the
    same way the first iteration handles a fresh diverge.
    """
    head = initial_head
    for attempt in range(len(PUSH_RETRY_BACKOFF) + 1):
        # Re-fetch and refresh ancestry on every retry. The first
        # iteration uses the fetch already done in run_sync.
        if attempt > 0:
            sleep_for = PUSH_RETRY_BACKOFF[attempt - 1]
            state.report_lines.append(
                f"push race; sleeping {sleep_for}s then re-fetching "
                f"and re-classifying (attempt {attempt + 1}/"
                f"{len(PUSH_RETRY_BACKOFF) + 1})")
            time.sleep(sleep_for)
            # review-2 MEDIUM-3: check fetch return code (was ignored)
            # and re-do force-push detect with pre-retry vs post-retry
            # origin SHA — remote could have been force-pushed during our
            # local merge attempt, in which case we should abort, not
            # silently merge against rewritten history.
            pre_retry_origin = state.new_origin_sha
            fetch_proc = _git(state, "fetch", state.remote, state.branch)
            if fetch_proc.returncode != 0:
                state.result = "fetch-failed"
                state.report_lines.append(
                    f"retry fetch failed: "
                    f"{fetch_proc.stderr.strip()[:300]}")
                return 1
            state.new_origin_sha = _git_rev_parse(
                state, f"{state.remote}/{state.branch}")
            if (pre_retry_origin and state.new_origin_sha
                    and pre_retry_origin != state.new_origin_sha
                    and not _is_ancestor(state, pre_retry_origin,
                                         state.new_origin_sha)):
                state.result = "force-push-detected"
                state.report_lines.append(
                    f"force-push during retry: "
                    f"pre={pre_retry_origin[:8]} → "
                    f"post={state.new_origin_sha[:8]}; abort")
                return 1
            head = _git_rev_parse(state, "HEAD") or head

        origin = state.new_origin_sha
        if not origin:
            state.result = "remote-branch-missing"
            return 1

        # equal — up-to-date
        if head == origin:
            state.result = "up-to-date"
            return 0

        head_in_origin = _is_ancestor(state, head, origin)
        origin_in_head = _is_ancestor(state, origin, head)

        if head_in_origin and not origin_in_head:
            # origin strictly ahead → fast-forward (no push needed)
            ff = _git(state, "merge", "--ff-only",
                      f"{state.remote}/{state.branch}")
            if ff.returncode != 0:
                state.result = "ff-failed"
                state.report_lines.append(
                    f"git merge --ff-only failed: "
                    f"{ff.stderr.strip()[:300]}")
                return 1
            state.result = "fast-forward"
            return 0

        if origin_in_head and not head_in_origin:
            # local strictly ahead → push directly
            push = _git(state, "push", state.remote, state.branch)
            if push.returncode == 0:
                if state.result == "unknown":
                    state.result = "pushed"
                return 0
            err = push.stderr.strip()
            if not _is_push_race(err):
                # Hook reject / permission / branch policy / etc. — not
                # a race; do NOT retry (review-2 MEDIUM-2)
                state.result = "push-failed"
                state.report_lines.append(
                    f"git push failed (non-race): {err[:400]}")
                return 1
            # Race — loop continues to retry (with re-fetch + re-classify)
            continue

        if not head_in_origin and not origin_in_head:
            # diverge — merge with driver, then push
            ts = _iso_now()
            commit_msg = (f"[kata sync] merge {state.remote}/"
                          f"{state.branch} at {ts}")
            # Clean up any stale merge state from a prior retry iteration
            if (state.wiki_root / ".git" / "MERGE_HEAD").exists():
                _git(state, "merge", "--abort")

            merge = _git(state, "merge", "--no-ff", "--no-commit",
                         "-m", commit_msg,
                         f"{state.remote}/{state.branch}")
            unmerged = _list_unmerged_paths(state)
            if unmerged:
                state.unmerged_paths = unmerged
                state.result = "conflicts"
                state.report_lines.append(
                    f"merge produced {len(unmerged)} unmerged path(s); "
                    f"resolve manually (.git/MERGE_HEAD preserved)")
                return 1

            cproc = _git(state, "commit", "--no-edit", "-m", commit_msg)
            if cproc.returncode != 0:
                combined = (cproc.stdout + cproc.stderr).lower()
                if "nothing to commit" in combined:
                    # Driver produced unchanged content; nothing actually
                    # diverged. Treat as up-to-date.
                    state.result = "merged-clean-nothing-to-commit"
                    return 0
                state.result = "commit-failed"
                state.report_lines.append(
                    f"git commit failed: {cproc.stderr.strip()[:300]}")
                return 1

            push = _git(state, "push", state.remote, state.branch)
            if push.returncode == 0:
                state.result = "merged"
                return 0
            err = push.stderr.strip()
            if not _is_push_race(err):
                state.result = "push-failed"
                state.report_lines.append(
                    f"git push failed after merge: {err[:400]}")
                return 1
            # Race after merge — loop will refetch+remerge
            continue

        # Both ancestry checks True means HEAD == origin, handled above.
        # If we reach here, ancestry is anomalous.
        state.result = "ancestry-anomaly"
        state.report_lines.append(
            f"unexpected ancestry: head={head[:8]} origin={origin[:8]} "
            f"head_in_origin={head_in_origin} "
            f"origin_in_head={origin_in_head}")
        return 1

    # Out of retries
    state.result = "race-exhausted"
    state.report_lines.append(
        f"failed to converge after "
        f"{len(PUSH_RETRY_BACKOFF) + 1} attempts; rerun wiki-sync")
    return 1


# ────────────────────── dry-run ──────────────────────────

def _dry_run(state: SyncState) -> int:
    """Read-only preview (PRD §6.4 / §11.5 M1).

    Does NOT acquire lock, NOT stash, NOT register drivers, NOT modify log.
    Allowed: git fetch (writes only to .git/refs/remotes/) + read-only
    git plumbing to compute classification.
    """
    if not (state.wiki_root / ".git").exists():
        state.result = "no-git"
        state.report_lines.append("(dry-run) no .git directory")
        return 1

    proc = _git(state, "remote", "get-url", state.remote)
    if proc.returncode != 0:
        state.result = "no-remote"
        state.report_lines.append("(dry-run) no remote configured")
        return 0

    state.old_origin_sha = _git_rev_parse(
        state, f"{state.remote}/{state.branch}")
    fetch_proc = _git(state, "fetch", state.remote, state.branch)
    if fetch_proc.returncode != 0:
        state.result = "fetch-failed"
        state.report_lines.append(
            f"(dry-run) fetch failed: {fetch_proc.stderr.strip()[:300]}")
        return 1
    state.new_origin_sha = _git_rev_parse(
        state, f"{state.remote}/{state.branch}")

    head = _git_rev_parse(state, "HEAD")
    classification = _classify_ancestry(state, head or "")
    if classification != "ok":
        state.result = classification
        state.report_lines.append(
            f"(dry-run) ancestry classification: {classification}")
        return 0  # dry-run reports without erroring

    if head == state.new_origin_sha:
        state.result = "up-to-date"
    elif _is_ancestor(state, head, state.new_origin_sha):
        state.result = "would-fast-forward"
    elif _is_ancestor(state, state.new_origin_sha, head):
        state.result = "would-push"
    else:
        state.result = "would-merge"
    state.report_lines.append(f"(dry-run) result: {state.result}")
    return 0


# ────────────────────── reports ──────────────────────────

RESULT_SUFFIX = {
    "up-to-date": None,             # don't write a report (T-sync-1)
    "pushed": "success",
    "fast-forward": "fast-forward",
    "merged": "success-with-driver",
    "conflicts": "conflicts",
    "force-push-detected": "force-push-detected",
    "unrelated-history": "unrelated-history",
    "identity-mismatch": "identity-mismatch",
    "import-in-progress": "aborted",
    "import-checkpoint-blocking": "aborted",
    "merge-in-progress": "aborted",
    "lock-held": "aborted",
    "no-remote": None,              # friendly skip, no report
    "race-exhausted": "race-exhausted",
    "stash-failed": "error",
    "fetch-failed": "error",
    "ff-failed": "error",
    "push-failed": "error",
    "commit-failed": "error",
    "no-wiki-id": "error",
    "no-head": "error",
    "no-git": "error",
    "remote-branch-missing": "error",
    "ancestry-anomaly": "error",
    "merged-clean-nothing-to-commit": "noop",
    "would-fast-forward": "dry-run",
    "would-push": "dry-run",
    "would-merge": "dry-run",
    "interrupted": "interrupted",
    "error": "error",
    "unknown": "error",
}


def write_sync_report(state: SyncState) -> Path | None:
    suffix = RESULT_SUFFIX.get(state.result, "error")
    if suffix is None:
        return None  # nothing to report (up-to-date / no-remote)

    # Local-only path (PRD §9.1 — never inside the wiki repo)
    report_dir = PID_DIR / "sync-reports" / state.machine_slug
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    report_path = report_dir / f"{ts}-{suffix}.md"

    lines = [f"# Sync · {ts}", ""]
    lines.append(f"- Wiki: {state.wiki_root}")
    if state.local_wiki_id:
        lines.append(f"- wiki_id: {state.local_wiki_id}")
    lines.append(f"- Machine slug: {state.machine_slug}")
    lines.append(f"- Remote: {state.remote} / branch: {state.branch}")
    lines.append(f"- Result: {state.result}")
    if state.dry_run:
        lines.append("- Mode: dry-run (no persistent changes)")
    if state.old_origin_sha:
        lines.append(
            f"- old origin SHA: {state.old_origin_sha[:8]}")
    if state.new_origin_sha:
        lines.append(
            f"- new origin SHA: {state.new_origin_sha[:8]}")
    if state.stash_sha:
        lines.append(f"- Stash: {state.stash_sha} ({state.stash_msg})")
    if state.drivers_just_configured:
        lines.append("- Auto-configured drivers: yes (this run)")

    if state.report_lines:
        lines.append("")
        lines.append("## Notes")
        for ln in state.report_lines:
            lines.append(f"- {ln}")

    if state.unmerged_paths:
        lines.append("")
        lines.append("## Unmerged paths (resolve manually)")
        for p in state.unmerged_paths:
            lines.append(f"- `{p}`")
        lines.append("")
        lines.append("## Recovery commands")
        lines.append("```bash")
        lines.append(f"cd {state.wiki_root}")
        lines.append("# Resolve conflicts in your editor, then:")
        lines.append("git add <files>")
        lines.append("git commit  # uses prepared message")
        lines.append("git push")
        if state.stash_sha:
            lines.append("# Restore stashed work after resolution (use SHA):")
            lines.append(f"git stash apply {state.stash_sha}")
            lines.append("git stash list --format='%gd %H'  "
                         "# find matching index")
            lines.append("git stash drop stash@{N}  # drop after apply")
        lines.append("# Or abort merge (keeps stash):")
        lines.append("git merge --abort")
        lines.append("```")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


# ────────────────────── cleanup ──────────────────────────

def cleanup(state: SyncState) -> Path | None:
    """Layered try/finally cleanup (PRD §6.2 H2 round-2).

    Each layer must not block the next:
    1. stash apply (best effort)
    2. report write (best effort)
    3. lock release (must always run if lock_acquired)

    Returns the report path if one was written.
    """
    # Layer 1: stash
    try:
        restore_stash(state)
    except Exception as e:
        sys.stderr.write(
            f"[wiki-sync] stash cleanup raised: {type(e).__name__}: {e}\n")

    # Layer 2: report
    report_path = None
    try:
        report_path = write_sync_report(state)
    except Exception as e:
        sys.stderr.write(
            f"[wiki-sync] failed to write sync report: {e}\n")
        sys.stderr.write(
            f"[wiki-sync] state summary: result={state.result}, "
            f"stash_sha={state.stash_sha}\n")

    # Layer 3: lock — must always run
    if state.lock_acquired:
        try:
            release_lock(state)
        except Exception as e:
            sys.stderr.write(
                f"[wiki-sync] failed to release lock: {e}; manually rm "
                f"{state.lock_path}\n")

    return report_path


# ────────────────────── helpers ──────────────────────────

def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ────────────────────── CLI ──────────────────────────

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wiki", default=None,
                   help="Wiki root path; uses kata resolver if omitted")
    p.add_argument("--auto", action="store_true",
                   help="Cron mode: any non-clean outcome exits non-zero")
    p.add_argument("--dry-run", action="store_true",
                   help="Read-only preview (no lock/stash/config/log writes)")
    args = p.parse_args()

    try:
        wiki_root = find_wiki_root(args.wiki)
    except Exception as e:
        emit({"error": f"could not resolve wiki root: {e}"})
        return 2

    if not wiki_root.exists():
        emit({"error": f"wiki root does not exist: {wiki_root}"})
        return 2

    schema = load_schema(wiki_root)
    sync_cfg = schema.get("sync") or {}
    if isinstance(sync_cfg, dict) and sync_cfg.get("enabled") is False:
        emit({
            "result": "sync-disabled",
            "wiki": str(wiki_root),
            "note": "sync.enabled is false in SCHEMA.md; nothing to do",
        })
        return 0

    state = SyncState(
        wiki_root=wiki_root,
        machine_slug=wiki_slug(wiki_root),
        remote=sync_cfg.get("remote", "origin")
        if isinstance(sync_cfg, dict) else "origin",
        branch=sync_cfg.get("branch", "main")
        if isinstance(sync_cfg, dict) else "main",
        on_conflict=sync_cfg.get("on_conflict", "report-and-exit")
        if isinstance(sync_cfg, dict) else "report-and-exit",
        auto_configure_drivers=sync_cfg.get("auto_configure_drivers", True)
        if isinstance(sync_cfg, dict) else True,
        auto=args.auto,
        dry_run=args.dry_run,
    )

    rc = 1
    try:
        rc = run_sync(state)
    except KeyboardInterrupt:
        state.result = "interrupted"
        state.report_lines.append("[interrupted by user]")
        rc = 130
    except Exception as e:
        import traceback
        state.result = "error"
        # Keep tail of traceback in the report for debugging without
        # spamming stdout; user can read the report file for full context
        state.report_lines.append(
            f"unexpected exception: {type(e).__name__}: {e}")
        state.report_lines.append("traceback (tail):\n"
                                  + traceback.format_exc()[-1500:])
        rc = 1
    finally:
        report_path = cleanup(state)

    payload = {
        "result": state.result,
        "wiki": str(state.wiki_root),
        "machine_slug": state.machine_slug,
        "remote": state.remote,
        "branch": state.branch,
    }
    if state.local_wiki_id:
        payload["wiki_id"] = state.local_wiki_id
    if state.old_origin_sha:
        payload["old_origin_sha"] = state.old_origin_sha[:8]
    if state.new_origin_sha:
        payload["new_origin_sha"] = state.new_origin_sha[:8]
    if state.stash_sha:
        payload["stash_sha"] = state.stash_sha[:8]
    if state.unmerged_paths:
        payload["unmerged_paths"] = state.unmerged_paths
    if state.report_lines:
        payload["notes"] = state.report_lines
    if "report_path" in dir() and report_path is not None:
        payload["report_path"] = str(report_path)
    emit(payload)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
