#!/usr/bin/env python3
"""Unified read/write for SCHEMA.md config — backs the wiki-config skill.

Why surgical edits, not re-serialization
----------------------------------------
SCHEMA.md is human-edited. It contains comments, blank lines, ordering
choices, prose between YAML blocks. A round-trip through our YAML parser
+ emitter would erase all of that. So writes are line-level: we locate the
exact line of the leaf key inside the right block and replace its value
verbatim. Reads use the parser (load_schema).

Supported paths
---------------
- Depth-2 scalars:  memory_tiers.active_days
- Depth-3 scalars:  dreaming.weights.entity
- Top-level scalar: domain (rare; mostly a depth-2 affair)

Not supported (v1.6) — adding new keys or editing list items. The script
returns a clear error message in those cases. For new sections (e.g.
introducing a `dreaming:` block where none exists), the wiki-config skill
prints the YAML block for the user to paste manually.

Usage:
    config_io.py --wiki <path> show
    config_io.py --wiki <path> get  --path memory_tiers.active_days
    config_io.py --wiki <path> set  --path memory_tiers.active_days --value 540
    config_io.py --wiki <path> explain --path dreaming.confidence_threshold
    config_io.py --wiki <path> validate
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from wiki_lib import emit, find_wiki_root, load_schema

SCHEMA_VALIDATE = Path(__file__).resolve().parent / "schema_validate.py"

# Documentation map for --explain. Keep this in sync with TRD additions.
DOCS = {
    "memory_tiers.enabled": (
        "Whether the three-tier (active/archived/frozen) aging system is on. "
        "When false, all query skills return all pages regardless of age."
    ),
    "memory_tiers.active_days": (
        "Max age (days) of a page's driving date for it to count as 'active'. "
        "Default 365. Active pages are the default surface for all queries."
    ),
    "memory_tiers.archived_days": (
        "Max age (days) before a page is treated as 'frozen'. Pages with "
        "(active_days < age <= archived_days) are 'archived'. Default 730."
    ),
    "memory_tiers.driving_field": (
        "Frontmatter field used to compute age. Default 'published_at' "
        "(falls back to 'ingested_at' if missing)."
    ),
    "dreaming.enabled": "Whether wiki-dream runs at all.",
    "dreaming.strategy": (
        "Re-promotion strategy. v1.6 supports only 'co-occurrence'. "
        "v1.8+ will add 'citational' and 'temporal'."
    ),
    "dreaming.cadence": (
        "How often dreaming should run: weekly | daily | manual. "
        "Drives the cron line wiki-init writes."
    ),
    "dreaming.confidence_threshold": (
        "Pages scoring below this are not surfaced as candidates. "
        "Range [0, 1]. Default 0.6. Raise to reduce noise; lower for recall."
    ),
    "dreaming.max_repromote_per_run": (
        "Hard cap on candidates per run. Default 10. Even if 30 pages score "
        "above threshold, only the top 10 are shown."
    ),
    "dreaming.weights.entity": (
        "Weight for entity overlap between an old page and recent ingests. "
        "Default 0.5 — primary signal for market research."
    ),
    "dreaming.weights.tag": (
        "Weight for tag resurgence. Default 0.2 — supporting signal."
    ),
    "dreaming.weights.citation": (
        "Weight for direct inbound [[wikilink]] from a new page. Default 0.4."
    ),
    "dreaming.resurgence.dormancy_window_days": (
        "How long a tag must have been dormant before its return counts as "
        "resurgence. Default 180."
    ),
    "dreaming.resurgence.min_count": (
        "How many new pages must carry the tag before it counts as resurgent. "
        "Default 3."
    ),
}


def get_path(schema: dict, path: str):
    parts = path.split(".")
    cur = schema
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def cmd_show(wiki_root: Path) -> dict:
    schema = load_schema(wiki_root)
    return {
        "wiki": str(wiki_root),
        "memory_tiers": schema.get("memory_tiers"),
        "dreaming": schema.get("dreaming"),
        "custom_dimensions": schema.get("custom_dimensions"),
        "tag_taxonomy_count": len(schema.get("tag_taxonomy") or []),
        "categories": [c.get("name") if isinstance(c, dict) else c
                       for c in (schema.get("categories") or [])],
    }


def cmd_get(wiki_root: Path, path: str) -> dict:
    schema = load_schema(wiki_root)
    value = get_path(schema, path)
    return {"path": path, "value": value, "exists": value is not None}


def cmd_explain(path: str) -> dict:
    return {"path": path, "doc": DOCS.get(path, f"No documentation for {path!r} yet.")}


def cmd_set(wiki_root: Path, path: str, raw_value: str) -> dict:
    schema_md = wiki_root / "SCHEMA.md"
    if not schema_md.exists():
        return {"error": f"SCHEMA.md not found at {schema_md}"}

    current = get_path(load_schema(wiki_root), path)
    if current is None:
        return {
            "error": (
                f"path {path!r} not found in SCHEMA.md. v1.6 wiki-config "
                f"only edits existing scalars; for new sections, edit "
                f"SCHEMA.md by hand or run wiki-init to bootstrap."
            ),
        }

    parsed_value = _parse_user_value(raw_value)
    rendered = _render_yaml_value(parsed_value)

    text = schema_md.read_text(encoding="utf-8")
    new_text, replaced = _surgical_replace(text, path, rendered)
    if not replaced:
        return {
            "error": (
                f"could not locate the line for {path!r} in SCHEMA.md. "
                f"Either the parser sees the value but the writer can't, or "
                f"the value is on a non-trivial line (multiline string, "
                f"inline comment, etc). Edit SCHEMA.md manually."
            ),
        }

    schema_md.write_text(new_text, encoding="utf-8")

    # Validate after write; if invalid, revert.
    proc = subprocess.run(
        [sys.executable, str(SCHEMA_VALIDATE), "--wiki", str(wiki_root)],
        capture_output=True, text=True,
    )
    try:
        validation = json.loads(proc.stdout)
    except json.JSONDecodeError:
        validation = {"valid": False, "errors": [proc.stdout, proc.stderr]}

    if not validation.get("valid", False):
        schema_md.write_text(text, encoding="utf-8")
        return {
            "error": "validation failed after edit; reverted SCHEMA.md",
            "path": path,
            "old_value": current,
            "attempted_value": parsed_value,
            "validation_errors": validation.get("errors", []),
        }

    _append_log(wiki_root, path, current, parsed_value)
    return {
        "path": path,
        "old_value": current,
        "new_value": parsed_value,
        "validation": "passed",
        "schema_md": str(schema_md.relative_to(wiki_root)),
    }


def cmd_validate(wiki_root: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCHEMA_VALIDATE), "--wiki", str(wiki_root)],
        capture_output=True, text=True,
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"valid": False, "errors": ["validator produced non-JSON output"],
                "raw_stdout": proc.stdout[:500], "raw_stderr": proc.stderr[:500]}


# ---------- helpers ----------

def _parse_user_value(raw: str):
    """Parse user-supplied --value into the right Python type."""
    s = raw.strip()
    if s.lower() in ("true", "yes"):
        return True
    if s.lower() in ("false", "no"):
        return False
    if s.lower() in ("null", "none", "~"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


def _render_yaml_value(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        # Use bare scalar where safe; quote when in doubt.
        if re.fullmatch(r"[A-Za-z0-9_./:-]+", v):
            return v
        return '"' + v.replace('"', '\\"') + '"'
    return json.dumps(v, ensure_ascii=False)


def _surgical_replace(text: str, dotted_path: str, new_yaml_value: str) -> tuple[str, bool]:
    """Find the line for dotted_path inside the right ```yaml block and
    replace its value. Returns (new_text, replaced)."""
    parts = dotted_path.split(".")
    leaf = parts[-1]
    ancestor_keys = parts[:-1]

    out_lines = []
    replaced = False
    in_yaml_block = False
    block_lines: list[str] = []
    block_start = -1

    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        if not in_yaml_block:
            if re.match(r"^```ya?ml\s*$", line.rstrip()):
                in_yaml_block = True
                block_lines = [line]
                block_start = i
                i += 1
                continue
            out_lines.append(line)
            i += 1
            continue
        # in yaml block
        block_lines.append(line)
        if line.rstrip() == "```":
            in_yaml_block = False
            # Process this block
            new_block, did = _try_replace_in_block(block_lines, ancestor_keys, leaf, new_yaml_value)
            if did and not replaced:
                out_lines.extend(new_block)
                replaced = True
            else:
                out_lines.extend(block_lines)
            block_lines = []
            i += 1
            continue
        i += 1

    if in_yaml_block:  # unterminated; bail
        return text, False
    return "".join(out_lines), replaced


def _try_replace_in_block(block_lines: list[str], ancestor_keys: list[str],
                          leaf: str, new_value: str) -> tuple[list[str], bool]:
    """Within one ```yaml block, find ancestor_keys -> leaf and replace."""
    # Strip the ```yaml fence and trailing ```
    body = block_lines[1:-1]
    indent_stack = []  # list of (indent, key)

    for idx, raw_line in enumerate(body):
        line = raw_line.rstrip("\n")
        stripped = line.lstrip(" \t")
        indent = len(line) - len(stripped)
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", stripped)
        if not m:
            continue
        key, value_part = m.group(1), m.group(2)
        # Pop stack until we're back to a parent indent
        while indent_stack and indent_stack[-1][0] >= indent:
            indent_stack.pop()
        ancestor_chain = [k for _, k in indent_stack]
        if ancestor_chain == ancestor_keys and key == leaf:
            # Replace this line's value, preserving any inline comment
            comment_match = re.match(r"^(.*?)(\s+#.*)?$", value_part)
            new_line = (" " * indent + key + ": " + new_value
                        + (comment_match.group(2) or ""))
            new_body = list(body)
            new_body[idx] = new_line + ("\n" if raw_line.endswith("\n") else "")
            return [block_lines[0]] + new_body + [block_lines[-1]], True
        if not value_part:
            indent_stack.append((indent, key))

    return list(block_lines), False


def _append_log(wiki_root: Path, path: str, old, new) -> None:
    log_md = wiki_root / "log.md"
    if not log_md.exists():
        return
    entry = (
        f"\n## [{date.today().isoformat()}] config | set {path}\n"
        f"- Old: {old!r}\n"
        f"- New: {new!r}\n"
    )
    with log_md.open("a", encoding="utf-8") as f:
        f.write(entry)


# ---------- CLI ----------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wiki", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("show")
    sub.add_parser("validate")
    g = sub.add_parser("get")
    g.add_argument("--path", required=True)
    e = sub.add_parser("explain")
    e.add_argument("--path", required=True)
    s = sub.add_parser("set")
    s.add_argument("--path", required=True)
    s.add_argument("--value", required=True)

    args = p.parse_args()
    root = find_wiki_root(args.wiki)

    if args.cmd == "show":
        emit(cmd_show(root))
    elif args.cmd == "validate":
        emit(cmd_validate(root))
    elif args.cmd == "get":
        emit(cmd_get(root, args.path))
    elif args.cmd == "explain":
        emit(cmd_explain(args.path))
    elif args.cmd == "set":
        result = cmd_set(root, args.path, args.value)
        emit(result)
        if "error" in result:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
