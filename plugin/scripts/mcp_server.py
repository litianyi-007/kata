#!/usr/bin/env python3
"""Kata MCP server — v1.12 Phase 0 (v2.8.0).

Exposes a kata wiki as a Model Context Protocol server over stdio.
Any MCP-aware agent (Claude Code, Cursor, Continue, another kata
acting as a federation client, etc.) can connect and call exposed
read-only tools.

Phase 0 (this version, v2.8.0):
    - Tool: `wiki-search` (delegates to search_naive.py)
    - Transport: stdio only
    - JSON-RPC 2.0 wire format
    - Hand-rolled — no MCP SDK dependency; stdlib only

Phase 1+ (v2.9.0+):
    - Add `wiki-query`, `wiki-graph` (read subset), `wiki-spec-preflight`
    - Add SSE transport
    - Capability declaration carries SCHEMA.md domain + categories

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

from wiki_lib import find_wiki_root, load_schema  # noqa: E402


# MCP protocol version we implement. Pin to the latest stable spec
# revision; bump when the wire format changes (rare).
MCP_PROTOCOL_VERSION = "2024-11-05"
KATA_SERVER_NAME = "kata-wiki"
KATA_SERVER_VERSION = "2.8.0"

# Path to sibling helper scripts (same directory as this file)
SCRIPTS_DIR = Path(__file__).resolve().parent


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

    def server_info(self) -> dict:
        """The `serverInfo` block returned by `initialize` + reused by
        federation peers as the identity-check source.
        """
        info = {
            "name": KATA_SERVER_NAME,
            "version": KATA_SERVER_VERSION,
        }
        # Custom kata block — federation client reads wiki_id from here
        # for the v1.8-style identity check.
        if self.wiki_id:
            info["kata"] = {
                "wiki_id": self.wiki_id,
                "wiki_path": str(self.wiki_path),
                "domain": self.domain,
                "categories": self.categories,
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
    return _result(req_id, {"tools": [WIKI_SEARCH_TOOL]})


def handle_tools_call(state: ServerState, req_id, params) -> dict:
    if not isinstance(params, dict):
        return _error(req_id, INVALID_PARAMS, "params must be an object")
    name = params.get("name")
    arguments = params.get("arguments") or {}

    if name == "wiki-search":
        try:
            envelope = _invoke_wiki_search(state, arguments)
        except ValueError as e:
            return _error(req_id, INVALID_PARAMS, str(e))
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            return _error(req_id, INTERNAL_ERROR, str(e))
        # MCP tool result: content array of typed blocks
        return _result(req_id, {
            "content": [{
                "type": "text",
                "text": json.dumps(envelope, ensure_ascii=False, indent=2),
            }],
            # Custom: also expose structured payload so federation clients
            # don't have to re-parse the text block. The MCP spec permits
            # additional keys.
            "structuredContent": envelope,
            "isError": False,
        })

    return _error(
        req_id, METHOD_NOT_FOUND,
        f"unknown tool: {name!r}",
        data={"available_tools": ["wiki-search"]},
    )


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
