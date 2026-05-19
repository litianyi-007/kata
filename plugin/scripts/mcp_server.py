#!/usr/bin/env python3
"""Kata MCP server — v1.12 Phase 0+1 (v2.9.0).

Exposes a kata wiki as a Model Context Protocol server over stdio.
Any MCP-aware agent (Claude Code, Cursor, Continue, another kata
acting as a federation client, etc.) can connect and call exposed
read-only tools.

Phase 0 (shipped v2.8.0):
    - Tool: `wiki-search` (delegates to search_naive.py)
    - Transport: stdio only
    - JSON-RPC 2.0 wire format
    - Hand-rolled — no MCP SDK dependency; stdlib only

Phase 1 (this version, v2.9.0):
    - Add `wiki-graph` (read subset — neighbors / shortest-path / hubs /
      orphans / cluster / stats; `--apply`-style writes NOT exposed)
    - Add `wiki-spec-preflight` (advisory mode only — no `--enforce`)
    - serverInfo.kata extended with tier_distribution (active/archived/
      frozen counts) for federation peers' capacity inspection
    - wiki-query intentionally NOT exposed: synthesis happens caller-side
      in the federation client over server-side search/graph results.
      Adding "wiki-query" as a tool would either (a) duplicate
      wiki-search since there's no underlying script, or (b) build a
      synthesis-server feature that doesn't fit the federation model.

Phase 2+ (v2.10.0+):
    - Federation client side + kata:// URI scheme + .federation.yaml
    - SSE transport (for cross-machine peers)

Read-only by design. Write-side skills (wiki-ingest, wiki-import,
wiki-tier --pin, wiki-dream --apply) are NEVER exposed. Cross-wiki
write requires explicit `wiki-import` against filesystem.

Usage:

    mcp_server.py --wiki <path> [--transport stdio]

Typical use: started by an MCP client via its server registration.
See plugin/skills/wiki-mcp-server/SKILL.md for the registration
snippet per client.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Force UTF-8 on stdio before importing anything that touches stdout/stdin.
# When Claude Code spawns this server on Windows, the inherited locale is
# typically cp1252, which mangles non-ASCII content (wiki titles, excerpts,
# Chinese tags) on the JSON-RPC wire. Both legs need explicit reconfigure:
# stdout (JSON-RPC out to Claude Code) AND child env (search_naive reads
# .md files; PYTHONUTF8=1 flips Python's UTF-8 mode for child file IO too).
try:
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stdin.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from wiki_lib import (  # noqa: E402
    compute_tier,
    discover_pages,
    find_wiki_root,
    load_schema,
)


# MCP protocol version we implement. Pin to the latest stable spec
# revision; bump when the wire format changes (rare).
MCP_PROTOCOL_VERSION = "2024-11-05"
KATA_SERVER_NAME = "kata-wiki"

# Path to sibling helper scripts (same directory as this file)
SCRIPTS_DIR = Path(__file__).resolve().parent


def _read_plugin_version() -> str:
    """Single source of truth — read kata version from plugin.json.
    Falls back to "unknown" if the file is missing or malformed (e.g.
    when this script is copied out of the plugin tree for testing)."""
    try:
        plugin_json = SCRIPTS_DIR.parent / ".claude-plugin" / "plugin.json"
        return str(json.loads(plugin_json.read_text(encoding="utf-8"))
                    .get("version", "unknown"))
    except (OSError, ValueError):
        return "unknown"


KATA_SERVER_VERSION = _read_plugin_version()


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 helpers
# ---------------------------------------------------------------------------

def _send(message: dict) -> None:
    """Write a JSON-RPC message to stdout. Each message is one line."""
    line = json.dumps(message, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _result(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code: int, message: str, data=None) -> dict:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


# JSON-RPC 2.0 standard error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


# ---------------------------------------------------------------------------
# Server state
# ---------------------------------------------------------------------------

class ServerState:
    def __init__(self, wiki_path: Path) -> None:
        self.wiki_path = wiki_path
        self.schema = load_schema(wiki_path)
        self.wiki_id = self.schema.get("wiki_id") or ""
        self.domain = self.schema.get("domain") or ""
        self.categories = [
            c.get("name") for c in self.schema.get("categories", [])
            if isinstance(c, dict) and c.get("name")
        ]
        self.initialized = False
        # Compute tier_distribution once at boot. SCHEMA.md changes during
        # runtime require server restart — same contract as v1.8 sync. Cheap
        # for wikis under a few thousand pages; if it becomes a startup
        # bottleneck on huge wikis, gate behind a `--skip-tier-stats` flag.
        self._tier_distribution = self._compute_tier_distribution()

    def _compute_tier_distribution(self) -> dict[str, int]:
        """active / archived / frozen counts across the whole wiki.

        Surfaced in `serverInfo.kata.tier_distribution` so a federation
        client can size up the peer before querying ("does this kata even
        have content?", "is the active surface thin or saturated?").
        """
        counts = {"active": 0, "archived": 0, "frozen": 0}
        try:
            pages = discover_pages(self.wiki_path)
        except Exception:
            return counts
        for page in pages:
            try:
                tier = compute_tier(page, self.schema)
            except Exception:
                continue
            if tier in counts:
                counts[tier] += 1
        return counts

    def server_info(self) -> dict:
        """The `serverInfo` block returned by `initialize` + reused by
        federation peers as the identity-check + capacity-inspection source.
        """
        info = {
            "name": KATA_SERVER_NAME,
            "version": KATA_SERVER_VERSION,
        }
        # Custom kata block — federation client reads wiki_id from here
        # for the v1.8-style identity check, plus tier_distribution for
        # peer capacity inspection (Phase 1+).
        if self.wiki_id:
            info["kata"] = {
                "wiki_id": self.wiki_id,
                "wiki_path": str(self.wiki_path),
                "domain": self.domain,
                "categories": self.categories,
                "tier_distribution": self._tier_distribution,
            }
        return info


# ---------------------------------------------------------------------------
# Tool: wiki-search
# ---------------------------------------------------------------------------

WIKI_SEARCH_TOOL = {
    "name": "wiki-search",
    "description": (
        "Search the kata wiki by keyword. Three-pass deterministic search "
        "(index.md scan + frontmatter scan + body scan) returning ranked "
        "results with page summaries and matching excerpts. Defaults to "
        "active-tier content. Read-only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search terms (whitespace-separated; "
                               "negate with leading '-'). Required."
            },
            "tag": {
                "type": "string",
                "description": "Optional tag filter (matches frontmatter "
                               "`tags:` entries)."
            },
            "type": {
                "type": "string",
                "description": "Optional page-type filter (entity, "
                               "concept, decision, etc — must be in "
                               "SCHEMA.md's category set)."
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default 10).",
                "default": 10
            },
            "tier": {
                "type": "string",
                "enum": ["active", "archived", "frozen", "all"],
                "description": "Memory-tier filter. Default: active.",
                "default": "active"
            }
        },
        "required": ["query"]
    }
}


def _invoke_wiki_search(state: ServerState, arguments: dict) -> dict:
    """Subprocess search_naive.py with the given arguments. Returns the
    parsed JSON envelope. Raises on non-zero exit."""
    query = arguments.get("query")
    if not query or not isinstance(query, str):
        raise ValueError("'query' is required and must be a non-empty string")

    argv = [
        sys.executable,
        str(SCRIPTS_DIR / "search_naive.py"),
        "--wiki", str(state.wiki_path),
        "--query", query,
    ]
    if arguments.get("tag"):
        argv += ["--tag", str(arguments["tag"])]
    if arguments.get("type"):
        argv += ["--type", str(arguments["type"])]
    if arguments.get("limit") is not None:
        argv += ["--limit", str(int(arguments["limit"]))]
    if arguments.get("tier"):
        argv += ["--tier", str(arguments["tier"])]

    # Force UTF-8 on the subprocess boundary (same defense as
    # tests/run_smoke.py's run() helper for windows-latest CI)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"search_naive.py exited {result.returncode}: "
            f"{result.stderr[:500]}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"search_naive.py produced non-JSON output: {e}")


# ---------------------------------------------------------------------------
# Generic JSON-subprocess helper (used by Phase 1 tools)
# ---------------------------------------------------------------------------

def _run_json_subprocess(argv: list[str], script_name: str,
                         allowed_exit_codes: tuple[int, ...] = (0,)) -> dict:
    """Run a kata helper script that emits a JSON envelope on stdout.

    UTF-8 forced on both legs (env + decoding) — same fix as v2.8.1 for
    Chinese / non-ASCII content. Raises RuntimeError on unexpected exit
    code or non-JSON output. The 30s timeout is the same per-call cap
    used by wiki-search.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=30,
    )
    if result.returncode not in allowed_exit_codes:
        raise RuntimeError(
            f"{script_name} exited {result.returncode}: "
            f"{result.stderr[:500]}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{script_name} produced non-JSON output: {e}")


# ---------------------------------------------------------------------------
# Tool: wiki-graph (Phase 1, v2.9.0)
# ---------------------------------------------------------------------------

WIKI_GRAPH_TOOL = {
    "name": "wiki-graph",
    "description": (
        "Query the kata wiki as a graph without maintaining a graph DB. "
        "Modes: neighbors / shortest-path / hubs / orphans / cluster / "
        "stats / spec-history. Each call scans .md files fresh and "
        "computes on the fly. Defaults to active-tier pages when memory "
        "tiers are enabled. Read-only — write operations like "
        "wiki-dream --apply are NOT exposed across the MCP boundary. "
        "v2.13.0+: spec-history mode renders v1.13 SHM lineage tree "
        "(supersedes / refines chains) in text / json / mermaid."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["neighbors", "shortest-path", "hubs", "orphans",
                         "cluster", "stats", "spec-history"],
                "description": "Query mode. Required."
            },
            "seed": {
                "type": "string",
                "description": "Source page (for `neighbors` mode). Wiki-"
                               "relative path or page title."
            },
            "src": {
                "type": "string",
                "description": "Source page (for `shortest-path` mode)."
            },
            "dst": {
                "type": "string",
                "description": "Destination page (for `shortest-path` mode)."
            },
            "tag": {
                "type": "string",
                "description": "Tag to cluster by (for `cluster` mode)."
            },
            "depth": {
                "type": "integer",
                "description": "Traversal depth for `neighbors` mode (default 1).",
                "default": 1
            },
            "limit": {
                "type": "integer",
                "description": "Max results / hubs (default 20).",
                "default": 20
            },
            "tier": {
                "type": "string",
                "enum": ["active", "archived", "frozen", "all"],
                "description": "Memory-tier filter. Default: active."
            },
            "format": {
                "type": "string",
                "enum": ["text", "json", "mermaid"],
                "description": "Output format for `spec-history` mode "
                               "(v2.13.0+). text = ASCII tree (default); "
                               "json = nested dict; mermaid = graph DSL for "
                               "markdown / Obsidian embedding."
            }
        },
        "required": ["mode"]
    }
}


def _invoke_wiki_graph(state: ServerState, arguments: dict) -> dict:
    """Subprocess graph_query.py for the requested mode."""
    mode = arguments.get("mode")
    if not mode or not isinstance(mode, str):
        raise ValueError("'mode' is required and must be a string")
    valid_modes = {"neighbors", "shortest-path", "hubs", "orphans",
                   "cluster", "stats", "spec-history"}
    if mode not in valid_modes:
        raise ValueError(f"unknown mode {mode!r}; expected one of {sorted(valid_modes)}")

    argv = [
        sys.executable,
        str(SCRIPTS_DIR / "graph_query.py"),
        "--wiki", str(state.wiki_path),
        "--mode", mode,
    ]
    if mode == "neighbors":
        seed = arguments.get("seed")
        if not seed:
            raise ValueError("'seed' is required for mode=neighbors")
        argv += ["--seed", str(seed)]
        if arguments.get("depth") is not None:
            argv += ["--depth", str(int(arguments["depth"]))]
    elif mode == "shortest-path":
        src = arguments.get("src")
        dst = arguments.get("dst")
        if not src or not dst:
            raise ValueError("'src' and 'dst' are both required for mode=shortest-path")
        argv += ["--src", str(src), "--dst", str(dst)]
    elif mode == "cluster":
        tag = arguments.get("tag")
        if not tag:
            raise ValueError("'tag' is required for mode=cluster")
        argv += ["--tag", str(tag)]
    elif mode == "spec-history":
        # Phase 4 (v2.13.0+) — supersession / refinement lineage tree
        seed = arguments.get("seed")
        if not seed:
            raise ValueError("'seed' is required for mode=spec-history")
        argv += ["--seed", str(seed)]
        if arguments.get("depth") is not None:
            argv += ["--depth", str(int(arguments["depth"]))]
        fmt = arguments.get("format") or "text"
        if fmt not in ("text", "json", "mermaid"):
            raise ValueError(
                f"'format' must be text|json|mermaid for spec-history; "
                f"got {fmt!r}"
            )
        argv += ["--format", fmt]
    # hubs / orphans / stats take no mode-specific required args

    if arguments.get("limit") is not None:
        argv += ["--limit", str(int(arguments["limit"]))]
    if arguments.get("tier"):
        argv += ["--tier", str(arguments["tier"])]

    return _run_json_subprocess(argv, "graph_query.py")


# ---------------------------------------------------------------------------
# Tool: wiki-spec-preflight (Phase 1, v2.9.0 — advisory mode only)
# ---------------------------------------------------------------------------

WIKI_SPEC_PREFLIGHT_TOOL = {
    "name": "wiki-spec-preflight",
    "description": (
        "Surface prior specs in the kata wiki that overlap with a new "
        "spec draft, ranked by relevance signals (title overlap / tag "
        "overlap / wikilink reference / hub score / type match). "
        "Advisory mode only across the MCP boundary — the --enforce gate "
        "is intentionally NOT exposed because write-blocking semantics "
        "don't translate cross-wiki (B can't block A's ingest; A enforces "
        "locally combining its own + federated candidates). Read-only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "new_spec_path": {
                "type": "string",
                "description": "Filesystem path to the new spec draft file. "
                               "Required. The file need not exist in the wiki "
                               "yet; typically a draft in raw/ or a separate "
                               "working dir."
            },
            "limit": {
                "type": "integer",
                "description": "Max candidates to return (default 10).",
                "default": 10
            },
            "include_archived": {
                "type": "boolean",
                "description": "Include archived-tier pages in candidates "
                               "(default false). Useful for `decisions` "
                               "where ratified specs age into archived.",
                "default": False
            },
            "include_frozen": {
                "type": "boolean",
                "description": "Include frozen-tier pages (default false). "
                               "Implies include_archived. Rare — for "
                               "deep-history audits.",
                "default": False
            }
        },
        "required": ["new_spec_path"]
    }
}


def _invoke_wiki_spec_preflight(state: ServerState, arguments: dict) -> dict:
    """Subprocess spec_preflight.py in advisory mode (no --enforce)."""
    new_spec_path = arguments.get("new_spec_path")
    if not new_spec_path or not isinstance(new_spec_path, str):
        raise ValueError("'new_spec_path' is required and must be a string")

    argv = [
        sys.executable,
        str(SCRIPTS_DIR / "spec_preflight.py"),
        "--wiki", str(state.wiki_path),
        "--new-spec", str(new_spec_path),
    ]
    if arguments.get("limit") is not None:
        argv += ["--limit", str(int(arguments["limit"]))]
    if arguments.get("include_archived"):
        argv += ["--include-archived"]
    if arguments.get("include_frozen"):
        argv += ["--include-frozen"]
    # Deliberately NOT passing --enforce / --enforce-threshold / --enforce-mode
    # — those are caller-local concerns, not federation-server concerns.

    return _run_json_subprocess(argv, "spec_preflight.py")


# ---------------------------------------------------------------------------
# Method dispatchers
# ---------------------------------------------------------------------------

def handle_initialize(state: ServerState, req_id, params) -> dict:
    """Handshake. Client sends protocolVersion + clientInfo; we respond with
    protocolVersion + capabilities + serverInfo.
    """
    state.initialized = True
    return _result(req_id, {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {
            "tools": {
                # Indicate we don't support listChanged notifications in
                # Phase 0 (tool list is static at boot).
                "listChanged": False,
            },
            # No prompts / resources in Phase 0.
        },
        "serverInfo": state.server_info(),
    })


def handle_initialized(state: ServerState, req_id, params) -> dict | None:
    """`initialized` is a notification (no id, no response). Some clients
    send it as a request with an id; we handle both by responding empty
    when there's an id."""
    if req_id is None:
        return None
    return _result(req_id, {})


def handle_tools_list(state: ServerState, req_id, params) -> dict:
    return _result(req_id, {
        "tools": [
            WIKI_SEARCH_TOOL,
            WIKI_GRAPH_TOOL,
            WIKI_SPEC_PREFLIGHT_TOOL,
        ]
    })


# Tool dispatch table — name → invoker. Adding a new MCP tool means:
# 1. Define <TOOL>_TOOL dict with name + description + inputSchema
# 2. Implement _invoke_<tool>(state, arguments) → JSON envelope
# 3. Append to TOOL_INVOKERS below and to the handle_tools_list array above
TOOL_INVOKERS = {
    "wiki-search": _invoke_wiki_search,
    "wiki-graph": _invoke_wiki_graph,
    "wiki-spec-preflight": _invoke_wiki_spec_preflight,
}


def handle_tools_call(state: ServerState, req_id, params) -> dict:
    if not isinstance(params, dict):
        return _error(req_id, INVALID_PARAMS, "params must be an object")
    name = params.get("name")
    arguments = params.get("arguments") or {}

    invoker = TOOL_INVOKERS.get(name)
    if invoker is None:
        return _error(
            req_id, METHOD_NOT_FOUND,
            f"unknown tool: {name!r}",
            data={"available_tools": sorted(TOOL_INVOKERS.keys())},
        )

    try:
        envelope = invoker(state, arguments)
    except ValueError as e:
        return _error(req_id, INVALID_PARAMS, str(e))
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        return _error(req_id, INTERNAL_ERROR, str(e))

    # MCP tool result: content array of typed blocks + custom
    # structuredContent so federation clients skip re-parsing.
    return _result(req_id, {
        "content": [{
            "type": "text",
            "text": json.dumps(envelope, ensure_ascii=False, indent=2),
        }],
        "structuredContent": envelope,
        "isError": False,
    })


def handle_shutdown(state: ServerState, req_id, params) -> dict:
    # Reply OK; main loop will see EOF or exit after this and terminate.
    return _result(req_id, {})


METHOD_HANDLERS = {
    "initialize": handle_initialize,
    "initialized": handle_initialized,
    "notifications/initialized": handle_initialized,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
    "shutdown": handle_shutdown,
}


# ---------------------------------------------------------------------------
# Main stdio loop
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description="Kata MCP server (v1.12 Phase 0). Exposes a kata wiki "
                    "over stdio as JSON-RPC 2.0."
    )
    p.add_argument("--wiki", required=True,
                   help="Wiki root path. Must contain a SCHEMA.md.")
    p.add_argument("--transport", choices=["stdio"], default="stdio",
                   help="Transport. Phase 0: stdio only. SSE in Phase 1+.")
    args = p.parse_args()

    wiki_path = Path(os.path.expanduser(args.wiki)).resolve()
    if not wiki_path.is_dir():
        sys.stderr.write(f"FAIL: --wiki path not found: {wiki_path}\n")
        return 1
    schema_md = wiki_path / "SCHEMA.md"
    if not schema_md.is_file():
        sys.stderr.write(
            f"FAIL: --wiki path missing SCHEMA.md: {schema_md}\n"
            "Kata MCP server refuses to start without a SCHEMA.md "
            "(no wiki_id, no domain, no categories — federation peers "
            "couldn't trust-check this server).\n"
        )
        return 1

    # Lock state once at boot. SCHEMA.md changes during runtime would
    # require server restart — same contract as v1.8 sync.
    state = ServerState(wiki_path)

    # Defer the actual stream read until we're handling input — this lets
    # the test harness probe argument parsing without sending input.
    while True:
        line = sys.stdin.readline()
        if not line:
            # EOF — client closed connection. Exit cleanly.
            return 0
        line = line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError as e:
            _send(_error(None, PARSE_ERROR, f"invalid JSON: {e}"))
            continue

        if not isinstance(message, dict):
            _send(_error(None, INVALID_REQUEST, "request must be an object"))
            continue
        if message.get("jsonrpc") != "2.0":
            _send(_error(message.get("id"), INVALID_REQUEST,
                         "jsonrpc must be '2.0'"))
            continue

        method = message.get("method")
        req_id = message.get("id")
        params = message.get("params")

        handler = METHOD_HANDLERS.get(method)
        if handler is None:
            # Don't respond to unknown notifications (no id), but do
            # respond to unknown requests with method-not-found.
            if req_id is not None:
                _send(_error(req_id, METHOD_NOT_FOUND,
                             f"unknown method: {method!r}"))
            continue

        try:
            response = handler(state, req_id, params)
        except Exception as e:
            _send(_error(req_id, INTERNAL_ERROR,
                         f"unhandled error: {type(e).__name__}: {e}"))
            continue

        if response is not None:
            _send(response)

        # `shutdown` is a request that gets a reply; some clients then
        # close stdin, others send `exit` notification. Either way, the
        # next readline() will return "" and we'll exit.
        if method == "shutdown":
            # No-op here; we wait for EOF rather than forcibly exit so
            # the response actually flushes to the client.
            pass


if __name__ == "__main__":
    sys.exit(main())
