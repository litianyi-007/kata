#!/usr/bin/env python3
"""Kata federation client — v1.12 Phase 2 (v2.10.0).

The other half of cross-wiki federation. Phase 0+1 made each kata
expose itself as an MCP server. Phase 2 makes a kata act as an MCP
client too: when wiki-query / wiki-search runs in kata A, it can
fan out to katas B, C, ... registered in A's `.federation.yaml` and
merge results with provenance.

This script does the mechanical work; skills (wiki-federate,
wiki-query) call it. Subcommands:

    federation_client.py federate-search --wiki <local-wiki> \\
        --query "..." [--limit N] [--tier active|all|archived|frozen] \\
        [--peers name1,name2]      # restrict fan-out to specific peers
        [--no-federate]            # local-only, ignore federation.yaml

    federation_client.py list-peers --wiki <wiki-path>
        # show registered peers + their enabled state + last-known status

    federation_client.py resolve-uri --uri kata://<name-or-uuid>/<path> \\
        --wiki <wiki-path>
        # given a kata:// URI, resolve to {peer name, wiki_id, path}
        # NB: this is just URI parsing + registry lookup. Actually
        # fetching the referenced page goes through federate-search /
        # the peer's wiki-search tool.

PRD: docs/PRD-v1.12-cross-wiki-federation.md
Decisions: D1.1 (Query-only), D1.2 (MCP), D2.1 (per-wiki yaml),
           D2.2 (name-first URI), D2.3 (explicit trust), D2.4 (5s default)
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

# Force UTF-8 on stdio — same defense as mcp_server.py. When this script
# is spawned by an agent (Claude Code), Windows locale may be cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stdin.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from wiki_lib import _parse_yaml_block, emit  # noqa: E402


MCP_PROTOCOL_VERSION = "2024-11-05"
FEDERATION_CLIENT_NAME = "kata-federation-client"
FEDERATION_CLIENT_VERSION = "2.10.0"
DEFAULT_PEER_TIMEOUT = 5.0  # seconds per peer (PRD D2.4)
MAX_PARALLEL_PEERS = 8       # ThreadPoolExecutor cap

# UUIDv4 detection for kata:// URI resolution (PRD D2.2 name-first,
# wiki_id-fallback). Strict: position 13 must be '4', position 17 must
# be 8/9/a/b. Lowercased before match.
UUID_V4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


# ---------------------------------------------------------------------------
# kata:// URI parsing
# ---------------------------------------------------------------------------

@dataclass
class KataURI:
    """Parsed kata:// URI. PRD §"kata:// URI scheme"."""
    raw: str                  # original input string
    identifier: str           # peer name OR wiki_id UUID, as written
    identifier_type: str      # "name" or "wiki_id"
    path: str                 # wiki-relative path within the peer
    valid: bool               # False if parse failed (callers can skip)
    error: str | None = None


def parse_kata_uri(s: str) -> KataURI:
    """Parse a kata:// URI. Lenient: returns KataURI with valid=False on
    malformed input rather than raising — callers (preflight, lint)
    typically want to surface unresolvable references, not crash.
    """
    if not isinstance(s, str):
        return KataURI(raw=str(s), identifier="", identifier_type="name",
                       path="", valid=False, error="not a string")
    if not s.startswith("kata://"):
        return KataURI(raw=s, identifier="", identifier_type="name",
                       path="", valid=False, error="missing kata:// prefix")
    rest = s[len("kata://"):]
    if "/" not in rest:
        return KataURI(raw=s, identifier="", identifier_type="name",
                       path="", valid=False,
                       error="missing path component after host")
    ident, path = rest.split("/", 1)
    if not ident:
        return KataURI(raw=s, identifier="", identifier_type="name",
                       path=path, valid=False, error="empty identifier")
    is_uuid = bool(UUID_V4_RE.match(ident.lower()))
    return KataURI(
        raw=s,
        identifier=ident,
        identifier_type="wiki_id" if is_uuid else "name",
        path=path,
        valid=True,
    )


def resolve_kata_uri(uri: KataURI, peers: list[dict]) -> dict | None:
    """Match a parsed URI against the local federation registry.

    Returns the matching peer dict (so caller can spawn it), or None
    if unresolvable. PRD D2.2: try the URI's identifier as a name
    first; if it parses as UUIDv4, also try wiki_id match.

    Name and wiki_id are case-insensitive on the lookup side (the
    registry's `name:` pattern is `^[a-z][a-z0-9-]*$` so case
    doesn't actually vary, but UUIDs come in either casing).
    """
    if not uri.valid:
        return None
    ident_lower = uri.identifier.lower()
    for peer in peers:
        if not isinstance(peer, dict):
            continue
        if peer.get("name", "").lower() == ident_lower:
            return peer
    if uri.identifier_type == "wiki_id":
        for peer in peers:
            if not isinstance(peer, dict):
                continue
            if (peer.get("wiki_id") or "").lower() == ident_lower:
                return peer
    return None


# ---------------------------------------------------------------------------
# Federation config (per-wiki .federation.yaml — PRD D2.1)
# ---------------------------------------------------------------------------

def load_federation_config(wiki_root: Path) -> list[dict]:
    """Read `{wiki_path}/.federation.yaml` and return the peers array.

    Empty list if the file doesn't exist (no federation configured).
    Returns peers as-written (including disabled ones); caller filters
    by `enabled: true` if needed.
    """
    cfg_path = wiki_root / ".federation.yaml"
    if not cfg_path.is_file():
        return []
    # M1 (v2.11.1): emit stderr warnings on parse failure so the user
    # can distinguish "no peers configured" (silent OK) from "registry
    # is broken" (silent BUG pre-v2.11.1).
    try:
        text = cfg_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        sys.stderr.write(
            f"[federation_client] failed to read {cfg_path}: "
            f"{type(e).__name__}: {e}\n"
            f"Federation peers will not load.\n"
        )
        return []
    try:
        parsed = _parse_yaml_block(text)
    except Exception as e:
        sys.stderr.write(
            f"[federation_client] {cfg_path} is malformed YAML: "
            f"{type(e).__name__}: {e}\n"
            f"Federation peers will not load. Fix the file or remove "
            f"it. Common cause on Windows: unquoted `C:/...` path in "
            f"`command:` array (stdlib YAML parser treats bare colons "
            f"as mapping separators).\n"
        )
        return []
    peers = parsed.get("peers") or []
    if not isinstance(peers, list):
        sys.stderr.write(
            f"[federation_client] {cfg_path}: `peers:` must be a list "
            f"(got {type(peers).__name__}); ignoring registry.\n"
        )
        return []
    return [p for p in peers if isinstance(p, dict)]


# ---------------------------------------------------------------------------
# MCP client (stdio, sync, with reader thread for timeout-bounded reads)
# ---------------------------------------------------------------------------

class WikiIdMismatchError(Exception):
    """Peer's serverInfo.kata.wiki_id ≠ registry's expected wiki_id.

    PRD D1.5: catches misconfigured pointer, peer re-init drop, or
    deliberate same-org impersonation. The peer is refused this
    session; user prompted to update the registry.
    """


class MCPClient:
    """Stdio MCP client wrapping a single peer kata's mcp_server.py.

    Lifecycle: spawn → initialize handshake (verifies wiki_id) →
    one or more `tools/call` → shutdown + EOF. Use as context
    manager to guarantee cleanup.

    Reader uses a daemon thread + queue.Queue so reads are
    timeout-bounded on Windows (where stdlib select doesn't work
    against pipes the same way as Unix).
    """

    def __init__(self, peer_config: dict, timeout: float | None = None) -> None:
        self.name = peer_config.get("name", "<unnamed>")
        self.expected_wiki_id = peer_config.get("wiki_id") or ""
        self.endpoint = peer_config.get("endpoint", "stdio")
        self.command = list(peer_config.get("command") or [])
        if timeout is not None:
            self.timeout = float(timeout)
        else:
            self.timeout = float(peer_config.get("timeout_seconds",
                                                 DEFAULT_PEER_TIMEOUT))
        self.proc: subprocess.Popen | None = None
        self.actual_wiki_id: str | None = None
        self.peer_server_info: dict = {}
        self._msg_id = 0
        self._reader_q: queue.Queue = queue.Queue()
        self._reader_thread: threading.Thread | None = None

    def __enter__(self) -> "MCPClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # -- lifecycle ---------------------------------------------------

    def connect(self) -> None:
        if self.endpoint != "stdio":
            raise NotImplementedError(
                f"endpoint {self.endpoint!r} not supported in Phase 2 MVP "
                f"(stdio only; SSE deferred)"
            )
        if not self.command:
            raise ValueError(
                f"peer {self.name!r}: no `command` configured for stdio endpoint"
            )

        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        # Expand ~ in command tokens (e.g. when stdio command points at
        # a script under ~/.kata or args contain ~/.llm-wiki/...).
        expanded = [os.path.expanduser(str(t)) for t in self.command]
        # M4 validation: peer registry might have `command:` as a string
        # (user mistake — yaml without the `- ` list marker). list("str")
        # iterates chars, producing a Popen call that fails with
        # FileNotFoundError on `'p'`. Catch the misconfiguration here
        # with a clear error message before Popen.
        if not all(isinstance(t, str) and t for t in expanded):
            raise ValueError(
                f"peer {self.name!r}: 'command' must be a list of non-empty "
                f"strings (got {self.command!r}). Check .federation.yaml — "
                f"each command token needs its own `- \"...\"` line."
            )
        self.proc = subprocess.Popen(
            expanded,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
        )
        self._start_reader()

        # H1 (v2.11.1): wrap post-spawn init in try/except that cleans up
        # the subprocess on ANY failure. Pre-v2.11.1, if initialize timed
        # out / failed / hit wiki_id mismatch, the subprocess leaked
        # (with-block's __exit__ never runs since __enter__ never
        # returned). Identity-check failure is the most-likely trip, so
        # the leak compounded with every misconfigured peer.
        try:
            # initialize handshake
            try:
                init_reply = self._call("initialize", {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "clientInfo": {
                        "name": FEDERATION_CLIENT_NAME,
                        "version": FEDERATION_CLIENT_VERSION,
                    },
                    "capabilities": {},
                })
            except TimeoutError as e:
                raise TimeoutError(
                    f"peer {self.name!r} initialize timed out after "
                    f"{self.timeout}s: {e}"
                )

            if "error" in init_reply:
                raise RuntimeError(
                    f"peer {self.name!r} initialize failed: "
                    f"{init_reply['error']}"
                )

            self.peer_server_info = init_reply.get("result", {}).get("serverInfo", {})
            kata_info = self.peer_server_info.get("kata") or {}
            self.actual_wiki_id = kata_info.get("wiki_id")

            # Identity check — PRD D1.5
            if self.expected_wiki_id and self.actual_wiki_id != self.expected_wiki_id:
                raise WikiIdMismatchError(
                    f"peer {self.name!r}: expected wiki_id "
                    f"{self.expected_wiki_id!r}, got {self.actual_wiki_id!r}"
                )

            # Send initialized notification (no response per spec)
            self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except BaseException:
            # BaseException catches KeyboardInterrupt + SystemExit too so
            # we clean up the subprocess on Ctrl-C as well. Re-raise to
            # propagate the original exception unchanged.
            self.close()
            raise

    def close(self) -> None:
        if not self.proc:
            return
        try:
            # Polite shutdown; ignore errors if peer is already dying
            self._send({"jsonrpc": "2.0", "id": 99999, "method": "shutdown"})
        except Exception:
            pass
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    # -- public RPC --------------------------------------------------

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Call `tools/call` on the peer. Returns the `result` dict
        (the MCP tool response payload — content array + structuredContent
        for kata tools). Raises RuntimeError on tool error or
        TimeoutError on no-reply.
        """
        reply = self._call("tools/call", {"name": name,
                                          "arguments": arguments})
        if "error" in reply:
            raise RuntimeError(
                f"peer {self.name!r} tools/call {name!r} failed: "
                f"{reply['error']}"
            )
        return reply.get("result", {})

    # -- internals ---------------------------------------------------

    def _start_reader(self) -> None:
        def _reader() -> None:
            assert self.proc is not None
            while True:
                try:
                    line = self.proc.stdout.readline()
                except Exception:
                    break
                if not line:
                    break
                self._reader_q.put(line)

        self._reader_thread = threading.Thread(target=_reader, daemon=True)
        self._reader_thread.start()

    def _send(self, msg: dict) -> None:
        assert self.proc is not None and self.proc.stdin is not None
        line = json.dumps(msg, ensure_ascii=False) + "\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()

    def _call(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC request, read replies until one matches our id
        (timeout-bounded). Notifications / out-of-order responses are
        ignored — we only care about the matching id."""
        self._msg_id += 1
        req_id = self._msg_id
        self._send({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        })
        deadline = time.time() + self.timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(
                    f"peer {self.name!r}: no reply to {method!r} within "
                    f"{self.timeout}s"
                )
            try:
                line = self._reader_q.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(
                    f"peer {self.name!r}: no reply to {method!r} within "
                    f"{self.timeout}s"
                )
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                # Garbage line — skip, the peer might be misbehaving
                continue
            if msg.get("id") == req_id:
                return msg
            # Otherwise it's an unrelated notification or stale reply; drop


# ---------------------------------------------------------------------------
# Fan-out search across local + federated peers
# ---------------------------------------------------------------------------

def _local_search(wiki_root: Path, query: str, limit: int,
                  tier: str | None) -> dict:
    """Run search_naive.py against the local wiki. Returns the JSON
    envelope. Raises RuntimeError on failure."""
    scripts_dir = Path(__file__).resolve().parent
    argv = [
        sys.executable,
        str(scripts_dir / "search_naive.py"),
        "--wiki", str(wiki_root),
        "--query", query,
        "--limit", str(int(limit)),
    ]
    if tier:
        argv += ["--tier", tier]
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"local search_naive.py exited {result.returncode}: "
            f"{result.stderr[:500]}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"local search_naive.py produced non-JSON: {e}")


def _query_peer_search(peer: dict, query: str, limit: int,
                       tier: str | None) -> dict:
    """Connect to a peer, call its wiki-search tool, return the
    structuredContent envelope (kata-extension; falls back to parsing
    the text block if not present)."""
    with MCPClient(peer) as client:
        args: dict = {"query": query, "limit": int(limit)}
        if tier:
            args["tier"] = tier
        result = client.call_tool("wiki-search", args)
    # Prefer structuredContent (kata extension — no re-parse needed).
    # Fall back to text block parse if peer is a non-kata MCP server.
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content") or []
    if content and isinstance(content, list) and content[0].get("type") == "text":
        try:
            return json.loads(content[0]["text"])
        except json.JSONDecodeError:
            return {"results": []}
    return {"results": []}


def _query_peer_spec_preflight(peer: dict, new_spec_path: str, limit: int,
                                include_archived: bool,
                                include_frozen: bool) -> dict:
    """Connect to a peer, call its wiki-spec-preflight tool, return the
    structuredContent envelope (or parse text-block fallback)."""
    with MCPClient(peer) as client:
        args: dict = {
            "new_spec_path": new_spec_path,
            "limit": int(limit),
            "include_archived": bool(include_archived),
            "include_frozen": bool(include_frozen),
        }
        result = client.call_tool("wiki-spec-preflight", args)
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content") or []
    if content and isinstance(content, list) and content[0].get("type") == "text":
        try:
            return json.loads(content[0]["text"])
        except json.JSONDecodeError:
            return {"candidates": []}
    return {"candidates": []}


def federate_spec_preflight(wiki_root: Path, new_spec_path: str,
                             peers: list[dict], limit: int = 10,
                             include_archived: bool = False,
                             include_frozen: bool = False,
                             peer_filter: set[str] | None = None) -> dict:
    """Parallel fan-out wiki-spec-preflight to enabled peers. Returns
    a federation envelope with:
    - `peer_candidates`: list of candidate dicts, each annotated with
      `source_wiki`, `source_wiki_name`, `uri` (`kata://<name>/<path>`)
    - `federation`: diagnostic block (peers_queried / peers_timed_out
      / peers_unreachable / local_only_fallback)

    Unlike federate_search, this does NOT run a local preflight —
    caller (spec_preflight.py) does that itself, then merges with our
    peer_candidates. Separation of concerns lets spec_preflight retain
    its enforcement gate logic locally.
    """
    diagnostic = {
        "peers_queried": [],
        "peers_timed_out": [],
        "peers_unreachable": [],
        "local_only_fallback": False,
    }

    enabled_peers = []
    for p in peers:
        if not p.get("enabled", True):
            continue
        if peer_filter and p.get("name") not in peer_filter:
            continue
        if not p.get("wiki_id"):
            diagnostic["peers_unreachable"].append({
                "name": p.get("name", "<unnamed>"),
                "reason": "registry entry missing wiki_id — refused",
            })
            continue
        enabled_peers.append(p)

    if not enabled_peers:
        diagnostic["local_only_fallback"] = True
        return {"peer_candidates": [], "federation": diagnostic}

    peer_candidates: list[dict] = []
    with ThreadPoolExecutor(
        max_workers=min(MAX_PARALLEL_PEERS, len(enabled_peers)),
        thread_name_prefix="federate-pf",
    ) as pool:
        futures = {
            pool.submit(_query_peer_spec_preflight, peer, new_spec_path,
                        limit, include_archived, include_frozen): peer
            for peer in enabled_peers
        }
        for future in as_completed(futures):
            peer = futures[future]
            name = peer.get("name", "<unnamed>")
            try:
                envelope = future.result()
            except TimeoutError as e:
                diagnostic["peers_timed_out"].append({
                    "name": name,
                    "timeout_seconds": peer.get("timeout_seconds",
                                                DEFAULT_PEER_TIMEOUT),
                    "reason": str(e),
                })
                continue
            except WikiIdMismatchError as e:
                diagnostic["peers_unreachable"].append({
                    "name": name,
                    "reason": f"wiki_id mismatch: {e}",
                })
                continue
            except (RuntimeError, OSError, FileNotFoundError, Exception) as e:
                diagnostic["peers_unreachable"].append({
                    "name": name,
                    "reason": f"{type(e).__name__}: {e}",
                })
                continue

            for c in envelope.get("candidates", []):
                c["source_wiki"] = peer.get("wiki_id")
                c["source_wiki_name"] = name
                c["uri"] = f"kata://{name}/{c.get('path', '')}"
                peer_candidates.append(c)
            diagnostic["peers_queried"].append(name)

    return {"peer_candidates": peer_candidates, "federation": diagnostic}


def federate_search(wiki_root: Path, query: str, peers: list[dict],
                    limit: int = 10, tier: str | None = "active",
                    peer_filter: set[str] | None = None) -> dict:
    """Run local search + parallel fan-out to enabled peers. Merge
    results into a single ranked envelope with provenance.

    `peer_filter`, if provided, restricts fan-out to peers whose `name`
    is in the set. Empty / None = use all enabled peers.

    Returns envelope with:
    - `query`, `tier_filter`, `results` (merged + sorted by score
      descending; capped at `limit`)
    - per-result provenance: `source_wiki` ("self" or peer wiki_id),
      `source_wiki_name` (None for local; peer name for federated),
      `uri` ("kata://<peer-name>/<path>" for federated; bare path for
      local — local doesn't need a URI)
    - `federation` diagnostic block: peers_queried, peers_timed_out,
      peers_unreachable (with reasons), local_only_fallback (bool)
    """
    # Step 1: local search (always)
    try:
        local = _local_search(wiki_root, query, limit, tier)
    except RuntimeError as e:
        return {
            "query": query,
            "results": [],
            "federation": {
                "peers_queried": [],
                "peers_timed_out": [],
                "peers_unreachable": [],
                "local_only_fallback": False,
                "local_error": str(e),
            },
        }

    # Annotate local results with provenance
    for r in local.get("results", []):
        r["source_wiki"] = "self"
        # No URI for local — caller already knows the wiki

    diagnostic = {
        "peers_queried": [],
        "peers_timed_out": [],
        "peers_unreachable": [],
        "local_only_fallback": False,
    }

    enabled_peers = []
    for p in peers:
        if not p.get("enabled", True):
            continue
        if peer_filter and p.get("name") not in peer_filter:
            continue
        if not p.get("wiki_id"):
            diagnostic["peers_unreachable"].append({
                "name": p.get("name", "<unnamed>"),
                "reason": "registry entry missing wiki_id — refused",
            })
            continue
        enabled_peers.append(p)

    if not enabled_peers:
        diagnostic["local_only_fallback"] = True
        return {**local, "federation": diagnostic}

    # Step 2: parallel fan-out
    federated_results: list[dict] = []
    with ThreadPoolExecutor(
        max_workers=min(MAX_PARALLEL_PEERS, len(enabled_peers)),
        thread_name_prefix="federate",
    ) as pool:
        futures = {
            pool.submit(_query_peer_search, peer, query, limit, tier): peer
            for peer in enabled_peers
        }
        for future in as_completed(futures):
            peer = futures[future]
            name = peer.get("name", "<unnamed>")
            try:
                peer_envelope = future.result()
            except TimeoutError as e:
                diagnostic["peers_timed_out"].append({
                    "name": name,
                    "timeout_seconds": peer.get("timeout_seconds",
                                                DEFAULT_PEER_TIMEOUT),
                    "reason": str(e),
                })
                continue
            except WikiIdMismatchError as e:
                diagnostic["peers_unreachable"].append({
                    "name": name,
                    "reason": f"wiki_id mismatch: {e}",
                })
                continue
            except (RuntimeError, OSError, FileNotFoundError, Exception) as e:
                diagnostic["peers_unreachable"].append({
                    "name": name,
                    "reason": f"{type(e).__name__}: {e}",
                })
                continue

            # Annotate peer results with provenance + kata:// URI
            for r in peer_envelope.get("results", []):
                r["source_wiki"] = peer.get("wiki_id")
                r["source_wiki_name"] = name
                r["uri"] = f"kata://{name}/{r.get('path', '')}"
                federated_results.append(r)
            diagnostic["peers_queried"].append(name)

    # Step 3: merge + sort by score (descending), apply limit
    all_results = list(local.get("results", [])) + federated_results
    all_results.sort(key=lambda r: -float(r.get("score", 0)))
    all_results = all_results[:limit]

    return {
        **local,
        "results": all_results,
        "federation": diagnostic,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_federate_search(args) -> int:
    wiki_root = Path(os.path.expanduser(args.wiki)).resolve()
    if not wiki_root.is_dir():
        emit({"error": f"--wiki not found: {wiki_root}"})
        return 1
    if args.no_federate:
        peers = []
    else:
        peers = load_federation_config(wiki_root)
    peer_filter = None
    if args.peers:
        peer_filter = {n.strip() for n in args.peers.split(",") if n.strip()}
    envelope = federate_search(
        wiki_root=wiki_root,
        query=args.query,
        peers=peers,
        limit=args.limit,
        tier=args.tier,
        peer_filter=peer_filter,
    )
    emit(envelope)
    return 0


def cmd_list_peers(args) -> int:
    wiki_root = Path(os.path.expanduser(args.wiki)).resolve()
    if not wiki_root.is_dir():
        emit({"error": f"--wiki not found: {wiki_root}"})
        return 1
    peers = load_federation_config(wiki_root)
    summary = [{
        "name": p.get("name"),
        "wiki_id": p.get("wiki_id"),
        "endpoint": p.get("endpoint", "stdio"),
        "enabled": p.get("enabled", True),
        "timeout_seconds": p.get("timeout_seconds", DEFAULT_PEER_TIMEOUT),
        "description": p.get("description"),
    } for p in peers]
    emit({
        "wiki": str(wiki_root),
        "federation_yaml": str(wiki_root / ".federation.yaml"),
        "exists": (wiki_root / ".federation.yaml").is_file(),
        "peers": summary,
        "peer_count": len(summary),
    })
    return 0


def cmd_resolve_uri(args) -> int:
    wiki_root = Path(os.path.expanduser(args.wiki)).resolve()
    if not wiki_root.is_dir():
        emit({"error": f"--wiki not found: {wiki_root}"})
        return 1
    uri = parse_kata_uri(args.uri)
    if not uri.valid:
        emit({"uri": args.uri, "valid": False, "error": uri.error})
        return 1
    peers = load_federation_config(wiki_root)
    matched = resolve_kata_uri(uri, peers)
    emit({
        "uri": args.uri,
        "valid": True,
        "identifier": uri.identifier,
        "identifier_type": uri.identifier_type,
        "path": uri.path,
        "resolved": matched is not None,
        "peer_name": matched.get("name") if matched else None,
        "peer_wiki_id": matched.get("wiki_id") if matched else None,
        "peer_endpoint": matched.get("endpoint") if matched else None,
    })
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="kata federation client (v1.12 Phase 2)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("federate-search",
                        help="local search + parallel fan-out to peers")
    pf.add_argument("--wiki", required=True, help="local wiki root path")
    pf.add_argument("--query", required=True)
    pf.add_argument("--limit", type=int, default=10)
    pf.add_argument("--tier", default="active",
                    choices=["active", "archived", "frozen", "all"])
    pf.add_argument("--peers", default=None,
                    help="comma-separated peer names to restrict fan-out "
                         "(default: all enabled peers)")
    pf.add_argument("--no-federate", action="store_true",
                    help="local-only, skip federation entirely")
    pf.set_defaults(func=cmd_federate_search)

    pl = sub.add_parser("list-peers", help="show registered peers")
    pl.add_argument("--wiki", required=True)
    pl.set_defaults(func=cmd_list_peers)

    pr = sub.add_parser("resolve-uri", help="parse + resolve a kata:// URI")
    pr.add_argument("--uri", required=True)
    pr.add_argument("--wiki", required=True)
    pr.set_defaults(func=cmd_resolve_uri)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
