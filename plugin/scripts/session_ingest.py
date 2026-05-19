#!/usr/bin/env python3
"""Session-ingest helper — v1.11 Phase 1-5 + v2.14.0 incremental dumps.

Mechanical work for `wiki-session-ingest` skill: CLI detection,
JSONL parsing (Claude Code + Codex CLI), raw-dump writing with
provenance frontmatter, and auto-trigger config file read/write.

v2.14.0: `dump` defaults to **incremental** — same session re-invoked
appends only new messages to the existing dump (filename stable across
days). `--full` reparses from msg #1 and overwrites. State is tracked
in `{wiki}/raw/sessions/.session-ingest-state.yaml` keyed by session_id
(or session_file path when session_id is unknown).

The agent in the skill orchestrates the user-facing flow (extract
knowledge points, multi-select, distill via wiki-ingest). This script
covers the deterministic file-and-env parts.

Subcommands:

    session_ingest.py detect
        Probe environment + filesystem to identify the active CLI.
        Stdout: JSON envelope with cli, session_file, session_id, mode.

    session_ingest.py dump --wiki <path> [--cli <name>] [--session-file <path>]
                           [--session-id <id>] [--max-tool-output-lines N]
                           [--full]
        Run detect (or use overrides), parse the session JSONL into
        readable markdown, write to {wiki}/raw/sessions/{cli}-{date}-{slug}-{id}.md.
        Default mode is incremental — only messages with idx >
        state.last_msg_idx are appended to the existing dump (filename
        reused from state). `--full` forces a fresh reparse from msg #1
        and overwrites the dump (filename uses today's date if no state
        entry exists, otherwise the previously-recorded filename).

    session_ingest.py dump-llm --wiki <path> --cli <name> [--session-id <id>]
                               [--title <slug>] [--body-stdin]
        LLM-dump fallback: the agent provides the body (read from stdin
        or `--body <text>`); this script wraps with frontmatter and writes
        to raw/sessions/. Used for CLIs where we don't have a JSONL
        adapter. Always full-write (no stable msg_idx to do incremental
        against — agent decides what body content to provide).

    session_ingest.py state show [--session-id <id>]
        Print the contents of {wiki}/raw/sessions/.session-ingest-state.yaml.
        With --session-id, print just that session's entry.

    session_ingest.py state forget --session-id <id> [--wiki <path>]
        Remove a session entry from state. The next dump for that session
        will start fresh (full write). Does NOT delete the dump file
        itself.

    session_ingest.py config show
    session_ingest.py config get <key>
    session_ingest.py config set <key> <value>
        Read/write ~/.kata/session-ingest.yaml. MVP keys:
        - auto_trigger_on_session_end (bool, default false)

Exit codes:
    0 — success
    1 — invalid input or expected failure
    2 — session file too large (>50 MB; PRD §Safety)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from wiki_lib import emit


MAX_SESSION_BYTES = 50 * 1024 * 1024  # 50 MB safety guard (PRD §Safety)
DEFAULT_MAX_TOOL_OUTPUT_LINES = 30  # head 20 + tail 10 default
CONFIG_PATH = Path.home() / ".kata" / "session-ingest.yaml"

# State file lives inside the wiki so it ships with wiki-sync. Path is
# wiki-relative so machines that share the same wiki agree on what was
# already ingested. Keyed by session_id (or by session_file path when
# session_id is unknown, with `path:` prefix to avoid collision).
STATE_FILE_REL = "raw/sessions/.session-ingest-state.yaml"


@dataclass
class MessagePart:
    """One parsed message section ready to render as markdown."""
    idx: int
    role: str
    text: str  # full markdown section including heading + anchor + body


# ---------------------------------------------------------------------------
# CLI detection (PRD §CLI detection decision tree)
# ---------------------------------------------------------------------------

def _slug_path(cwd: str) -> str:
    """Convert an absolute path to the Claude Code project-dir slug form.

    Rules (empirically derived from ~/.claude/projects/ on Windows + posix):
    - Drive colon `:` → `-`
    - Path separators `\\` and `/` → `-`
    - Result: `F:\\workspace\\ai\\AK-llm-wiki` → `F--workspace-ai-AK-llm-wiki`
              `/home/user/project`            → `-home-user-project`
    """
    s = cwd.replace(":", "-").replace("\\", "-").replace("/", "-")
    return s


def _find_claude_session(cwd: str, session_id: str | None) -> Path | None:
    """Locate the Claude Code JSONL file for this cwd + optional session id."""
    base = Path.home() / ".claude" / "projects"
    if not base.is_dir():
        return None
    # Try the canonical slug first
    candidates = [base / _slug_path(cwd)]
    # Fallback: scan all project dirs for one whose name matches cwd
    # (in case the slug rule has an edge case we missed)
    cwd_norm = cwd.replace("\\", "/").lower()
    for d in base.iterdir():
        if d.is_dir():
            # Decode the slug back: replace `-` with `/` and try matching tail
            unslug = d.name.replace("-", "/").lower()
            if cwd_norm.endswith(unslug.rstrip("/")) or unslug.endswith(cwd_norm):
                if d not in candidates:
                    candidates.append(d)
    for d in candidates:
        if not d.is_dir():
            continue
        if session_id:
            target = d / f"{session_id}.jsonl"
            if target.is_file():
                return target
        # No session id → pick most recent .jsonl
        jsonls = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if jsonls:
            return jsonls[0]
    return None


def _find_codex_session(cwd: str, session_id: str | None) -> Path | None:
    """Locate the Codex CLI rollout JSONL via env var or cwd-match heuristic.

    PRD §Session-id resolution: prefer `$CODEX_SESSION_ID`; else scan today
    + yesterday under `~/.codex/sessions/YYYY/MM/DD/` for the most-recent
    rollout whose first-line `session_meta.payload.cwd` matches cwd.
    """
    base = Path.home() / ".codex" / "sessions"
    if not base.is_dir():
        return None

    cwd_norm = cwd.replace("\\", "/").lower().rstrip("/")

    # Walk today + yesterday folders
    today = datetime.now()
    candidates: list[Path] = []
    for delta in (0, 1, 2):  # today, yesterday, day before (cheap, robust)
        d = today.replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            import datetime as _dt
            d = d - _dt.timedelta(days=delta)
        except Exception:
            pass
        day_dir = base / f"{d.year:04d}" / f"{d.month:02d}" / f"{d.day:02d}"
        if not day_dir.is_dir():
            continue
        for f in day_dir.glob("rollout-*.jsonl"):
            candidates.append(f)

    if session_id:
        for f in candidates:
            if session_id in f.name:
                return f
        # session_id given but no filename match — fall through to cwd match

    # Cwd-match: read first line of each, compare session_meta.payload.cwd
    best: tuple[float, Path] | None = None
    for f in candidates:
        try:
            with f.open("r", encoding="utf-8", errors="replace") as fh:
                first = fh.readline()
        except OSError:
            continue
        try:
            obj = json.loads(first)
        except json.JSONDecodeError:
            continue
        meta_cwd = (
            obj.get("session_meta", {}).get("payload", {}).get("cwd")
            or obj.get("payload", {}).get("cwd")
            or ""
        )
        meta_norm = str(meta_cwd).replace("\\", "/").lower().rstrip("/")
        if meta_norm == cwd_norm:
            mt = f.stat().st_mtime
            if best is None or mt > best[0]:
                best = (mt, f)
    return best[1] if best else None


def cmd_detect(args) -> int:
    """Probe environment + filesystem to identify active CLI."""
    cwd = args.cwd or os.getcwd()

    # 1. Claude Code
    if os.environ.get("CLAUDECODE") == "1":
        sid = os.environ.get("CLAUDE_CODE_SESSION_ID") or args.session_id
        path = _find_claude_session(cwd, sid)
        emit({
            "cli": "claude-code",
            "detection_mode": "jsonl-read",
            "session_id": sid,
            "session_file": str(path) if path else None,
            "cwd": cwd,
        })
        return 0

    # 2. Codex CLI (env OR rollout cwd-match)
    codex_sid = os.environ.get("CODEX_SESSION_ID") or args.session_id
    codex_path = _find_codex_session(cwd, codex_sid)
    if codex_path:
        emit({
            "cli": "codex-cli",
            "detection_mode": "jsonl-read",
            "session_id": codex_sid,
            "session_file": str(codex_path),
            "cwd": cwd,
        })
        return 0

    # 3-6. Other CLIs (sentinel env probe — implementation-time verification)
    for env_var, cli_name in [
        ("GEMINI_CLI", "gemini-cli"),
        ("COPILOT_CLI", "copilot-cli"),
        ("OPENCODE", "opencode"),
        ("KIMI_CLI", "kimi-cli"),
    ]:
        if os.environ.get(env_var):
            emit({
                "cli": cli_name,
                "detection_mode": "llm-dump",
                "session_id": None,
                "session_file": None,
                "cwd": cwd,
            })
            return 0

    # 7. Unknown — LLM-dump fallback
    emit({
        "cli": "unknown",
        "detection_mode": "llm-dump",
        "session_id": None,
        "session_file": None,
        "cwd": cwd,
    })
    return 0


# ---------------------------------------------------------------------------
# JSONL parsers (Claude Code + Codex CLI)
# ---------------------------------------------------------------------------

def _truncate_tool_output(text: str, max_lines: int) -> str:
    """Head 20 + tail 10 truncation pattern (PRD §Raw session dump body)."""
    if not text:
        return ""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    head_n = max(int(max_lines * 2 / 3), 1)
    tail_n = max(max_lines - head_n, 1)
    return (
        "\n".join(lines[:head_n])
        + f"\n... [{len(lines) - head_n - tail_n} lines truncated] ...\n"
        + "\n".join(lines[-tail_n:])
    )


def _parse_claude_jsonl(path: Path, max_tool_output_lines: int
                         ) -> tuple[list[MessagePart], dict]:
    """Parse Claude Code session JSONL → list of MessagePart + metadata.

    Returns (parts, meta) where meta has: event_count, message_count,
    session_start, session_end, role_counts. Parts are 1-indexed via
    `MessagePart.idx`; idx is stable across re-parses of the same JSONL
    (the basis for incremental dump tracking).
    """
    parts_out: list[MessagePart] = []
    msg_idx = 0
    events = 0
    first_ts: str | None = None
    last_ts: str | None = None
    role_counts: dict[str, int] = {"user": 0, "assistant": 0, "tool": 0}

    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            events += 1

            # Filter decorative events
            ev_type = ev.get("type", "")
            if ev_type in ("file-history-snapshot", "permission-mode", "system"):
                continue

            ts = ev.get("timestamp") or ev.get("ts")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

            role = ev.get("role") or ev.get("message", {}).get("role") or ev_type
            msg = ev.get("message", {}) if isinstance(ev.get("message"), dict) else ev
            content = msg.get("content")

            # Content can be a string OR a list of content blocks
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                block_parts: list[str] = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        block_parts.append(block.get("text", ""))
                    elif btype == "tool_use":
                        name = block.get("name", "?")
                        block_parts.append(f"\n_[tool: `{name}`]_\n")
                    elif btype == "tool_result":
                        out = block.get("content", "")
                        if isinstance(out, list):
                            out = "\n".join(
                                b.get("text", "")
                                for b in out
                                if isinstance(b, dict)
                            )
                        truncated = _truncate_tool_output(str(out), max_tool_output_lines)
                        block_parts.append(f"\n```\n{truncated}\n```\n")
                text = "\n".join(p for p in block_parts if p)
            else:
                text = ""

            if not text.strip():
                continue

            msg_idx += 1
            heading = {"user": "User", "assistant": "Assistant"}.get(role, role.title())
            anchor = f"session-msg-{msg_idx}"
            section = (
                f"\n### {heading} (msg #{msg_idx}) <a id=\"{anchor}\"></a>\n"
                + text.rstrip()
                + "\n"
            )
            parts_out.append(MessagePart(idx=msg_idx, role=role, text=section))

            if role in role_counts:
                role_counts[role] += 1

    return parts_out, {
        "event_count": events,
        "message_count": msg_idx,
        "session_start": first_ts,
        "session_end": last_ts,
        "role_counts": role_counts,
    }


def _parse_codex_jsonl(path: Path, max_tool_output_lines: int
                        ) -> tuple[list[MessagePart], dict]:
    """Parse Codex CLI rollout JSONL → list of MessagePart + metadata.

    Codex rollout shape differs from Claude Code; events are typed
    (session_meta / user_message / assistant_message / tool_call / tool_result).
    Same `MessagePart.idx`-stable contract as the Claude parser.
    """
    parts_out: list[MessagePart] = []
    msg_idx = 0
    events = 0
    first_ts: str | None = None
    last_ts: str | None = None
    role_counts: dict[str, int] = {"user": 0, "assistant": 0, "tool": 0}

    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            events += 1

            ev_type = ev.get("type") or ev.get("kind") or ""
            ts = ev.get("timestamp") or ev.get("ts")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

            payload = ev.get("payload") or ev
            text = ""
            heading: str | None = None
            role = ev_type

            if ev_type in ("user_message", "user_turn"):
                heading = "User"
                text = str(payload.get("content") or payload.get("text") or "")
                role = "user"
                role_counts["user"] += 1
            elif ev_type in ("assistant_message", "assistant_turn"):
                heading = "Assistant"
                text = str(payload.get("content") or payload.get("text") or "")
                role = "assistant"
                role_counts["assistant"] += 1
            elif ev_type in ("tool_call", "function_call"):
                heading = "Tool"
                name = payload.get("name", "?")
                args = payload.get("arguments") or payload.get("args") or ""
                text = f"_[tool: `{name}`]_\n```\n{args}\n```"
                role = "tool"
                role_counts["tool"] += 1
            elif ev_type in ("tool_result", "function_call_output"):
                heading = "Tool result"
                out = payload.get("output") or payload.get("content") or ""
                if isinstance(out, (dict, list)):
                    out = json.dumps(out, ensure_ascii=False)
                text = "```\n" + _truncate_tool_output(str(out), max_tool_output_lines) + "\n```"
                role = "tool"
            elif ev_type == "session_meta":
                continue  # skip metadata event
            else:
                # Unknown event — keep but mark
                heading = ev_type.title() or "Event"
                text = json.dumps(payload, ensure_ascii=False)[:800]
                role = ev_type or "event"

            if not text.strip():
                continue
            msg_idx += 1
            anchor = f"session-msg-{msg_idx}"
            section = (
                f"\n### {heading} (msg #{msg_idx}) <a id=\"{anchor}\"></a>\n"
                + text.rstrip()
                + "\n"
            )
            parts_out.append(MessagePart(idx=msg_idx, role=role, text=section))

    return parts_out, {
        "event_count": events,
        "message_count": msg_idx,
        "session_start": first_ts,
        "session_end": last_ts,
        "role_counts": role_counts,
    }


def _render_parts(parts: list[MessagePart]) -> str:
    """Join parts into a single markdown body string."""
    return "\n".join(p.text for p in parts)


# ---------------------------------------------------------------------------
# State file (v2.14.0 incremental tracking)
# ---------------------------------------------------------------------------

def _state_path(wiki: Path) -> Path:
    return wiki / STATE_FILE_REL


def _state_key(session_id: str | None, session_file: Path | None) -> str:
    """Stable key for a session in the state map.

    Prefer the session_id (UUID — globally unique across machines).
    Fall back to `path:<absolute-session-file>` when session_id is
    unknown (LLM-dump CLIs, or detection that couldn't recover the id).
    A `path:` prefix avoids collision with a literal session_id that
    happens to look like a filesystem path.
    """
    if session_id:
        return str(session_id)
    if session_file:
        return "path:" + str(Path(session_file).resolve()).replace("\\", "/")
    return "path:unknown"


def _read_state(wiki: Path) -> dict:
    """Read state file. Return empty state on missing / unreadable.

    Schema:

        sessions:
          <session_id_or_pathkey>:
            dump_path: raw/sessions/<file>.md      # wiki-relative
            last_msg_idx: 142
            last_run_at: 2026-05-19T18:00:00Z
            cli: claude-code
            session_file: C:/Users/.../<id>.jsonl
    """
    sp = _state_path(wiki)
    empty = {"sessions": {}}
    if not sp.is_file():
        return empty
    try:
        text = sp.read_text(encoding="utf-8")
    except OSError:
        return empty
    # Minimal YAML reader — flat `sessions:` map with per-session
    # indented scalar children. Mirrors the format _write_state emits.
    state: dict = {"sessions": {}}
    current_key: str | None = None
    in_sessions = False
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.rstrip() == "sessions:":
            in_sessions = True
            continue
        if not in_sessions:
            continue
        # 2-space indent → session key; 4-space → child scalar
        stripped = raw_line.rstrip()
        if stripped.startswith("  ") and not stripped.startswith("    "):
            # New session entry: "  <key>:"
            content = stripped[2:].rstrip(":")
            current_key = content
            state["sessions"][current_key] = {}
        elif stripped.startswith("    ") and current_key:
            # Child scalar: "    key: value"
            kv = stripped.strip()
            if ":" not in kv:
                continue
            k, v = kv.split(":", 1)
            v = v.strip()
            if v.isdigit():
                state["sessions"][current_key][k.strip()] = int(v)
            else:
                state["sessions"][current_key][k.strip()] = v
    return state


def _write_state(wiki: Path, state: dict) -> None:
    """Write state file. Renders the flat schema readable by _read_state."""
    sp = _state_path(wiki)
    sp.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# kata wiki-session-ingest incremental tracking (v2.14.0+)",
        "# Edited automatically by session_ingest.py — do not hand-edit",
        "# unless you also delete the corresponding dump file in raw/sessions/.",
        "sessions:",
    ]
    for key, entry in sorted(state.get("sessions", {}).items()):
        lines.append(f"  {key}:")
        for k in ("dump_path", "cli", "session_file", "last_run_at",
                  "last_msg_idx"):
            if k in entry:
                lines.append(f"    {k}: {entry[k]}")
    sp.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _now_iso() -> str:
    """UTC timestamp in ISO 8601 with 'Z' suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_incremental_to_dump(dump_path: Path, new_body: str,
                                 new_total_msgs: int, msg_idx_start: int,
                                 msg_idx_end: int, run_at: str) -> None:
    """Append a new section to an existing dump file.

    Updates frontmatter `message_count` and the `incremental_runs:` list.
    Preserves all other frontmatter (including `distilled_pages:` that
    wiki-ingest may have appended in Phase 5).
    """
    text = dump_path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    delimiter = (
        f"\n<!-- kata:session-ingest INCREMENTAL "
        f"run_at={run_at} msg_start={msg_idx_start} msg_end={msg_idx_end} -->\n"
    )

    if not m:
        # No frontmatter (unexpected for a kata-written dump) — just append.
        dump_path.write_text(
            text.rstrip() + "\n" + delimiter + new_body + "\n",
            encoding="utf-8",
        )
        return

    fm_text = m.group(1)
    body_existing = text[m.end():]

    # Update message_count + append to incremental_runs in-place.
    fm_lines = fm_text.splitlines()
    other_lines: list[str] = []
    runs_lines: list[str] = []
    saw_message_count = False
    in_incremental_runs = False
    for line in fm_lines:
        stripped = line.lstrip()
        if line and not line[0].isspace():
            # Top-level key
            in_incremental_runs = False
            if stripped.startswith("message_count:"):
                other_lines.append(f"message_count: {new_total_msgs}")
                saw_message_count = True
                continue
            if stripped.rstrip() == "incremental_runs:" or \
                    stripped.startswith("incremental_runs:"):
                in_incremental_runs = True
                runs_lines.append("incremental_runs:")
                continue
            other_lines.append(line)
        else:
            # Indented (child of last top-level)
            if in_incremental_runs:
                runs_lines.append(line)
            else:
                other_lines.append(line)

    if not saw_message_count:
        other_lines.append(f"message_count: {new_total_msgs}")
    if not runs_lines:
        runs_lines = ["incremental_runs:"]
    runs_lines.append(f"  - run_at: {run_at}")
    runs_lines.append(f"    msg_idx_start: {msg_idx_start}")
    runs_lines.append(f"    msg_idx_end: {msg_idx_end}")
    runs_lines.append(
        f"    new_message_count: {msg_idx_end - msg_idx_start + 1}"
    )

    new_fm = "\n".join(other_lines + runs_lines)
    dump_path.write_text(
        "---\n" + new_fm + "\n---\n"
        + body_existing.rstrip() + "\n"
        + delimiter + new_body + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Raw-dump writer
# ---------------------------------------------------------------------------

def _slug_from_cwd(cwd: str) -> str:
    """Short, filesystem-safe slug from cwd's last segment."""
    p = Path(cwd).name or "wiki"
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", p).strip("-").lower()[:40] or "session"


def _short_session_id(sid: str | None) -> str:
    if not sid:
        return ""
    s = str(sid).replace("-", "")
    return s[:8]


def _write_dump(wiki: Path, cli: str, session_file: Path | None,
                session_id: str | None, body: str, meta: dict,
                detection_mode: str, cwd: str,
                dump_path: Path | None = None,
                msg_idx_start: int = 1, msg_idx_end: int | None = None,
                run_at: str | None = None) -> Path:
    """Write a fresh raw session dump (full mode).

    When `dump_path` is provided, reuse that path (typical when a state
    entry already pointed at an existing dump for this session and the
    user is doing a `--full` re-write). Otherwise compute a fresh
    {cli}-{today}-{slug}-{short_id}.md path.
    """
    sessions_dir = wiki / "raw" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    if dump_path is None:
        slug = _slug_from_cwd(cwd)
        short_id = _short_session_id(session_id) or "anon"
        fname = f"{cli}-{today}-{slug}-{short_id}.md"
        out = sessions_dir / fname
    else:
        out = dump_path

    run_at = run_at or _now_iso()
    end_idx = msg_idx_end if msg_idx_end is not None else (meta.get("message_count") or 0)

    fm_lines = ["---"]
    fm_lines.append("type: session-dump")
    fm_lines.append(f"source_cli: {cli}")
    fm_lines.append(f"detection_mode: {detection_mode}")
    if session_id:
        fm_lines.append(f"session_id: {session_id}")
    if session_file:
        fm_lines.append(f"session_file: {str(session_file)}")
    fm_lines.append(f"cwd: {cwd}")
    if meta.get("session_start"):
        fm_lines.append(f"session_start: {meta['session_start']}")
    if meta.get("session_end"):
        fm_lines.append(f"session_end: {meta['session_end']}")
    if meta.get("event_count") is not None:
        fm_lines.append(f"event_count: {meta['event_count']}")
    if meta.get("message_count") is not None:
        fm_lines.append(f"message_count: {meta['message_count']}")
    fm_lines.append(f"ingested_at: {today}")
    fm_lines.append("distilled_pages: []")
    fm_lines.append("incremental_runs:")
    fm_lines.append(f"  - run_at: {run_at}")
    fm_lines.append(f"    msg_idx_start: {msg_idx_start}")
    fm_lines.append(f"    msg_idx_end: {end_idx}")
    fm_lines.append(f"    new_message_count: {max(end_idx - msg_idx_start + 1, 0)}")
    fm_lines.append("---")

    out.write_text(
        "\n".join(fm_lines) + "\n\n" + (body or "_(empty body — LLM-dump pending)_\n"),
        encoding="utf-8",
    )
    return out


def cmd_dump(args) -> int:
    wiki = Path(os.path.expanduser(args.wiki)).resolve()
    if not wiki.is_dir():
        emit({"error": f"wiki path not found: {wiki}"})
        return 1

    # Run detection if cli not overridden
    cwd = args.cwd or os.getcwd()
    cli = args.cli
    session_file = Path(args.session_file) if args.session_file else None
    session_id = args.session_id
    detection_mode = args.detection_mode

    if not cli:
        # Inline detect
        if os.environ.get("CLAUDECODE") == "1":
            cli = "claude-code"
            session_id = session_id or os.environ.get("CLAUDE_CODE_SESSION_ID")
            session_file = session_file or _find_claude_session(cwd, session_id)
            detection_mode = "jsonl-read"
        else:
            codex_sid = os.environ.get("CODEX_SESSION_ID") or session_id
            codex_path = _find_codex_session(cwd, codex_sid)
            if codex_path:
                cli = "codex-cli"
                session_file = session_file or codex_path
                session_id = session_id or codex_sid
                detection_mode = "jsonl-read"

    if not cli:
        emit({"error": "could not auto-detect CLI; pass --cli explicitly"})
        return 1
    if not detection_mode:
        detection_mode = "jsonl-read" if session_file else "llm-dump"

    if detection_mode != "jsonl-read":
        emit({"error": "llm-dump mode requires `dump-llm` subcommand with --body-stdin"})
        return 1
    if not session_file or not session_file.is_file():
        emit({"error": f"session file not found: {session_file}"})
        return 1
    size = session_file.stat().st_size
    if size > MAX_SESSION_BYTES:
        emit({
            "error": f"session file {session_file} is {size} bytes (> 50 MB cap)",
            "hint": "narrow scope with --max-tool-output-lines or split session",
        })
        return 2
    if cli == "claude-code":
        parts, meta = _parse_claude_jsonl(session_file, args.max_tool_output_lines)
    elif cli == "codex-cli":
        parts, meta = _parse_codex_jsonl(session_file, args.max_tool_output_lines)
    else:
        emit({"error": f"no JSONL adapter for cli={cli}"})
        return 1

    # State-based incremental dispatch (v2.14.0). Default = incremental.
    state = _read_state(wiki)
    key = _state_key(session_id, session_file)
    entry = state.get("sessions", {}).get(key)
    run_at = _now_iso()
    total = meta.get("message_count") or 0

    # Determine effective mode:
    #   --full → always full write
    #   no state entry → full write (first run)
    #   state entry but dump file missing → full write (state stale, log)
    #   state entry + dump file present → incremental
    effective_mode = "full"
    existing_dump: Path | None = None
    last_idx = 0
    stale_state = False
    if entry is not None:
        dump_rel = entry.get("dump_path") or ""
        if dump_rel:
            cand = (wiki / dump_rel).resolve()
            if cand.is_file():
                existing_dump = cand
                last_idx = int(entry.get("last_msg_idx") or 0)
                if not args.full:
                    effective_mode = "incremental"
            else:
                stale_state = True

    if effective_mode == "incremental":
        new_parts = [p for p in parts if p.idx > last_idx]
        if not new_parts:
            # Nothing new — successful no-op. State unchanged.
            emit({
                "mode": "incremental",
                "no_new_messages": True,
                "dump_path": str(existing_dump),
                "cli": cli,
                "session_id": session_id,
                "session_file": str(session_file),
                "last_msg_idx": last_idx,
                "message_count": total,
                "advisory": (
                    "No messages with idx > last_msg_idx; dump file unchanged. "
                    "Pass --full to force a full reparse + overwrite."
                ),
            })
            return 0
        new_body = _render_parts(new_parts)
        assert existing_dump is not None  # narrowed by branch above
        _append_incremental_to_dump(
            dump_path=existing_dump,
            new_body=new_body,
            new_total_msgs=total,
            msg_idx_start=new_parts[0].idx,
            msg_idx_end=new_parts[-1].idx,
            run_at=run_at,
        )
        # Update state
        state.setdefault("sessions", {})[key] = {
            "dump_path": str(existing_dump.relative_to(wiki).as_posix()),
            "cli": cli,
            "session_file": str(session_file),
            "last_run_at": run_at,
            "last_msg_idx": total,
        }
        _write_state(wiki, state)
        emit({
            "mode": "incremental",
            "dump_path": str(existing_dump),
            "cli": cli,
            "detection_mode": detection_mode,
            "session_id": session_id,
            "session_file": str(session_file),
            "event_count": meta.get("event_count"),
            "message_count": total,
            "msg_idx_start": new_parts[0].idx,
            "msg_idx_end": new_parts[-1].idx,
            "new_message_count": len(new_parts),
            "session_start": meta.get("session_start"),
            "session_end": meta.get("session_end"),
            "size_bytes": existing_dump.stat().st_size,
        })
        return 0

    # Full mode (either --full, no state, or stale state with missing dump).
    body = _render_parts(parts)
    out = _write_dump(
        wiki=wiki, cli=cli, session_file=session_file, session_id=session_id,
        body=body, meta=meta, detection_mode=detection_mode, cwd=cwd,
        dump_path=existing_dump,  # reuse path when --full overwrites a tracked dump
        msg_idx_start=1,
        msg_idx_end=total,
        run_at=run_at,
    )
    state.setdefault("sessions", {})[key] = {
        "dump_path": str(out.relative_to(wiki).as_posix()),
        "cli": cli,
        "session_file": str(session_file),
        "last_run_at": run_at,
        "last_msg_idx": total,
    }
    _write_state(wiki, state)
    emit({
        "mode": "full",
        "dump_path": str(out),
        "cli": cli,
        "detection_mode": detection_mode,
        "session_id": session_id,
        "session_file": str(session_file),
        "event_count": meta.get("event_count"),
        "message_count": total,
        "session_start": meta.get("session_start"),
        "session_end": meta.get("session_end"),
        "size_bytes": out.stat().st_size,
        "stale_state_recovered": stale_state,
        "forced_full": bool(args.full),
    })
    return 0


def cmd_state(args) -> int:
    """Show or forget a session's incremental-tracking entry."""
    wiki = Path(os.path.expanduser(args.wiki)).resolve() if args.wiki else None
    if wiki is None:
        # Fall back to find_wiki_root
        from wiki_lib import find_wiki_root
        wiki = find_wiki_root(None)
    if not wiki.is_dir():
        emit({"error": f"wiki path not found: {wiki}"})
        return 1

    state = _read_state(wiki)
    if args.state_op == "show":
        sessions = state.get("sessions", {})
        if args.session_id:
            entry = sessions.get(args.session_id)
            if entry is None:
                emit({"error": f"no state entry for session_id={args.session_id}",
                      "known_sessions": list(sessions.keys())})
                return 1
            emit({"wiki": str(wiki), "session_id": args.session_id,
                  "entry": entry})
            return 0
        emit({"wiki": str(wiki), "state_path": str(_state_path(wiki)),
              "session_count": len(sessions), "sessions": sessions})
        return 0
    if args.state_op == "forget":
        sessions = state.get("sessions", {})
        if args.session_id not in sessions:
            emit({"error": f"no state entry for session_id={args.session_id}",
                  "known_sessions": list(sessions.keys())})
            return 1
        removed = sessions.pop(args.session_id)
        _write_state(wiki, state)
        emit({"forgot": args.session_id, "removed_entry": removed,
              "advisory": "Next dump for this session will start fresh (full write). "
                          "The existing dump file at raw/sessions/ was NOT deleted; "
                          "remove it manually if you want a clean re-ingest."})
        return 0
    emit({"error": f"unknown state op: {args.state_op}"})
    return 1


def cmd_dump_llm(args) -> int:
    """LLM-dump fallback: agent provides body via --body or stdin."""
    wiki = Path(os.path.expanduser(args.wiki)).resolve()
    if not wiki.is_dir():
        emit({"error": f"wiki path not found: {wiki}"})
        return 1

    cwd = args.cwd or os.getcwd()
    if args.body_stdin:
        body = sys.stdin.read()
    elif args.body:
        body = args.body
    else:
        emit({"error": "must pass --body or --body-stdin"})
        return 1

    meta = {
        "event_count": None,
        "message_count": body.count("\n### "),
        "session_start": None,
        "session_end": None,
    }
    out = _write_dump(
        wiki=wiki, cli=args.cli, session_file=None, session_id=args.session_id,
        body=body, meta=meta, detection_mode="llm-dump", cwd=cwd,
    )
    emit({
        "dump_path": str(out),
        "cli": args.cli,
        "detection_mode": "llm-dump",
        "size_bytes": out.stat().st_size,
    })
    return 0


# ---------------------------------------------------------------------------
# Config (~/.kata/session-ingest.yaml)
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = {"auto_trigger_on_session_end": False}


def _read_config() -> dict:
    cfg = dict(_DEFAULT_CONFIG)
    if not CONFIG_PATH.is_file():
        return cfg
    try:
        text = CONFIG_PATH.read_text(encoding="utf-8")
    except OSError:
        return cfg
    # Minimal YAML reader — only supports flat scalar lines (key: value)
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        if v.lower() in ("true", "yes", "on"):
            cfg[k] = True
        elif v.lower() in ("false", "no", "off"):
            cfg[k] = False
        elif v.isdigit():
            cfg[k] = int(v)
        else:
            cfg[k] = v
    return cfg


def _write_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# kata session-ingest per-machine config (gitignore by convention)"]
    for k, v in sorted(cfg.items()):
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        else:
            lines.append(f"{k}: {v}")
    CONFIG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_config(args) -> int:
    if args.config_op == "show":
        emit({"config_path": str(CONFIG_PATH), "config": _read_config()})
        return 0
    if args.config_op == "get":
        cfg = _read_config()
        if args.key not in cfg:
            emit({"error": f"unknown key: {args.key}", "available": list(cfg.keys())})
            return 1
        emit({"key": args.key, "value": cfg[args.key]})
        return 0
    if args.config_op == "set":
        cfg = _read_config()
        v_str = args.value
        if v_str.lower() in ("true", "yes", "on"):
            v: object = True
        elif v_str.lower() in ("false", "no", "off"):
            v = False
        elif v_str.isdigit():
            v = int(v_str)
        else:
            v = v_str
        cfg[args.key] = v
        _write_config(cfg)
        emit({"set": args.key, "value": v, "config_path": str(CONFIG_PATH)})
        return 0
    emit({"error": f"unknown config op: {args.config_op}"})
    return 1


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="kata session-ingest helper (v1.11)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # detect
    pd = sub.add_parser("detect", help="probe environment + filesystem for active CLI")
    pd.add_argument("--cwd", default=None, help="override cwd (default: os.getcwd())")
    pd.add_argument("--session-id", default=None,
                    help="override session id (default: env var)")
    pd.set_defaults(func=cmd_detect)

    # dump (jsonl-read path)
    pdmp = sub.add_parser("dump", help="parse session JSONL + write raw dump")
    pdmp.add_argument("--wiki", required=True, help="wiki root path")
    pdmp.add_argument("--cli", default=None,
                      help="override CLI name (default: auto-detect)")
    pdmp.add_argument("--session-file", default=None,
                      help="override session file path (default: auto-detect)")
    pdmp.add_argument("--session-id", default=None,
                      help="override session id (default: env var)")
    pdmp.add_argument("--detection-mode", default=None,
                      choices=[None, "jsonl-read", "llm-dump"],
                      help="override detection mode")
    pdmp.add_argument("--cwd", default=None, help="override cwd")
    pdmp.add_argument("--max-tool-output-lines", type=int,
                      default=DEFAULT_MAX_TOOL_OUTPUT_LINES,
                      help=f"truncate tool outputs to N lines (head 2/3 + tail 1/3); "
                           f"default {DEFAULT_MAX_TOOL_OUTPUT_LINES}")
    pdmp.add_argument("--full", action="store_true",
                      help="force a full reparse + overwrite the dump file. "
                           "Default is incremental: only messages with idx > "
                           "state.last_msg_idx are appended (v2.14.0+).")
    pdmp.set_defaults(func=cmd_dump)

    # dump-llm (LLM-dump path)
    pdl = sub.add_parser("dump-llm", help="write a raw dump from agent-provided body")
    pdl.add_argument("--wiki", required=True)
    pdl.add_argument("--cli", required=True,
                     help="CLI name (gemini-cli / copilot-cli / opencode / kimi-cli / unknown)")
    pdl.add_argument("--session-id", default=None)
    pdl.add_argument("--cwd", default=None)
    pdl.add_argument("--body", default=None, help="dump body content")
    pdl.add_argument("--body-stdin", action="store_true",
                     help="read dump body from stdin")
    pdl.set_defaults(func=cmd_dump_llm)

    # state (v2.14.0 — incremental tracking inspection / reset)
    pst = sub.add_parser("state", help="inspect / forget per-session incremental "
                                       "tracking entries (v2.14.0+)")
    st_sub = pst.add_subparsers(dest="state_op", required=True)
    st_show = st_sub.add_parser("show", help="print state (all sessions or one)")
    st_show.add_argument("--wiki", default=None,
                         help="wiki root path (auto-detected if omitted)")
    st_show.add_argument("--session-id", default=None,
                         help="show only this session's entry")
    st_forget = st_sub.add_parser("forget",
        help="remove a session entry so next dump starts fresh (full write); "
             "does NOT delete the dump file itself")
    st_forget.add_argument("--wiki", default=None,
                           help="wiki root path (auto-detected if omitted)")
    st_forget.add_argument("--session-id", required=True)
    pst.set_defaults(func=cmd_state)

    # config
    pcfg = sub.add_parser("config", help="read/write ~/.kata/session-ingest.yaml")
    cfg_sub = pcfg.add_subparsers(dest="config_op", required=True)
    cfg_sub.add_parser("show")
    pg = cfg_sub.add_parser("get")
    pg.add_argument("key")
    ps = cfg_sub.add_parser("set")
    ps.add_argument("key")
    ps.add_argument("value")
    pcfg.set_defaults(func=cmd_config)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
