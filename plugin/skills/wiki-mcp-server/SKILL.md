---
name: wiki-mcp-server
description: "Run a kata wiki as a Model Context Protocol (MCP) server over stdio. Any MCP-aware agent (Claude Code, Cursor, Continue, another kata acting as a federation client) can connect and call exposed read-only tools (wiki-search in Phase 0; wiki-query / wiki-graph / wiki-spec-preflight in Phase 1+). Read-only by design — write skills are never exposed across the MCP boundary."
user-invocable: true
argument-hint: "[--wiki=<path>] [--transport=stdio]"
---

# wiki-mcp-server

The first half of v1.12 cross-wiki federation: a kata wiki advertises
itself to other MCP clients as a queryable knowledge base. The second
half (the federation client side that consumes other wikis' MCP
servers) ships in v2.10.0 / Phase 2.

## When to use

- **Cross-wiki federation** (the original v1.12 use case) — kata A's
  `wiki-query` skill fans out to kata B by spawning B's
  `mcp_server.py` as a subprocess
- **Non-kata MCP client integration** — Claude Code / Cursor /
  Continue can use kata as a search backend even if they don't ship
  with kata
- **Multi-wiki workflows on one machine** — register N kata wikis as
  N separate MCP servers in your client's settings; each shows up as
  a distinct tool surface

Skip if:
- You only have one kata wiki and only use it via Claude Code slash
  commands (`/kata:wiki-search` etc) — the slash commands hit the
  scripts directly without MCP overhead
- You're worried about read-then-write — the MCP surface is
  intentionally read-only; for write workflows use the regular skills

## Phase scope (v2.8.0)

Exposed tools:

| Tool | Status (v2.8.0) | Notes |
|---|---|---|
| `wiki-search` | ✓ shipped | 3-pass deterministic search; tier filter; tag/type filter |
| `wiki-query` | Phase 1 (v2.9.0) | Synthesized answer + citations |
| `wiki-graph` | Phase 1 (v2.9.0) | Read subset only — no `--apply` exposed |
| `wiki-spec-preflight` | Phase 1 (v2.9.0) | Advisory candidates for spec authoring |

**Never exposed**: `wiki-ingest`, `wiki-import`, `wiki-tier --pin`,
`wiki-dream --apply`, any other write skill. Cross-wiki write
requires explicit `wiki-import` against the peer's filesystem path.

## How to start the server

Manual / testing:

```bash
py -3 plugin/scripts/mcp_server.py --wiki ~/.llm-wiki/NECallKit
```

The server speaks JSON-RPC 2.0 over stdio. Each request/response is
one line of JSON, newline-terminated. The server's stdout is the
MCP wire; stderr is for diagnostics. **Do not print to stdout from
anywhere except the JSON-RPC reply path**.

## Integration: Claude Code MCP client

Add to `.claude/settings.json` (or `~/.claude/settings.json` for
global):

```json
{
  "mcpServers": {
    "kata-necallkit": {
      "command": "py",
      "args": [
        "-3",
        "C:/path/to/kata/plugin/scripts/mcp_server.py",
        "--wiki",
        "C:/Users/you/.llm-wiki/NECallKit"
      ]
    }
  }
}
```

Then in Claude Code, the kata MCP server's tools appear in the
client's tool catalog. Calling `wiki-search` from inside an agent
flow now hits the kata wiki via MCP rather than the slash-command
shell-out path.

## Integration: another kata (federation client side)

The kata federation client (shipping in v2.10.0 / Phase 2) reads
`{wiki_path}/.federation.yaml` and spawns peer MCP servers
automatically:

```yaml
# {wiki_path}/.federation.yaml
peers:
  - name: necallkit
    wiki_id: 7b52f6df-d7cf-47ab-b980-6042cf3a675c
    endpoint: stdio
    command:
      - py
      - -3
      - "C:/path/to/kata/plugin/scripts/mcp_server.py"
      - --wiki
      - "~/.llm-wiki/NECallKit"
    enabled: true
    timeout_seconds: 5
```

See `docs/PRD-v1.12-cross-wiki-federation.md` for the full federation
design.

## Protocol surface (Phase 0)

Implemented JSON-RPC methods:

| Method | Direction | Purpose |
|---|---|---|
| `initialize` | client → server | Handshake; client sends protocolVersion + clientInfo, server responds with protocolVersion + capabilities + serverInfo |
| `initialized` / `notifications/initialized` | client → server | Client acknowledges init; no response needed |
| `tools/list` | client → server | Server returns list of available tools with input schemas |
| `tools/call` | client → server | Server invokes tool and returns result blocks |
| `shutdown` | client → server | Graceful shutdown; server replies OK then exits on next EOF |

The MCP protocol version implemented: `2024-11-05`.

### serverInfo block

```json
{
  "name": "kata-wiki",
  "version": "2.8.0",
  "kata": {
    "wiki_id": "7b52f6df-d7cf-47ab-b980-6042cf3a675c",
    "wiki_path": "/home/user/.llm-wiki/NECallKit",
    "domain": "NECallKit multi-platform SDK",
    "categories": ["platforms", "modules", "features", "bugs", "decisions", "lessons", "queries"]
  }
}
```

The `kata` sub-object is a custom extension. The federation client
reads `kata.wiki_id` to perform the identity check (PRD §Safety):
if the registry says peer A has `wiki_id=X` but the actual
`serverInfo.kata.wiki_id` is Y, the peer is refused this session.

### Tool result shape (wiki-search)

```json
{
  "content": [
    {
      "type": "text",
      "text": "<JSON envelope from search_naive.py>"
    }
  ],
  "structuredContent": {
    "query": "payment flow",
    "results": [...],
    "total": 3,
    "passes": {"index": 2, "frontmatter": 5, "body": 8}
  },
  "isError": false
}
```

The text block is the human-readable form; `structuredContent`
(kata-specific extension) is the parsed envelope so a federation
client doesn't have to re-parse the text. MCP clients that don't
recognize `structuredContent` simply use the text block.

## Safety contract

- **Read-only.** Server NEVER writes anywhere. Write-side skills are
  not registered as tools and not callable through this surface.
- **No subprocess shell expansion.** Tool arguments are passed
  through to subprocess as argv tokens; no shell interpretation.
- **30-second per-call timeout** on subprocess invocations. A pathological
  search query won't hang the server forever.
- **Refuse to start without SCHEMA.md.** No `wiki_id` means no
  identity check possible; federation clients couldn't trust the
  server. Exit code 1 with explanation on stderr.
- **No mutation of the wiki repo** under any tool path. The server
  doesn't touch index.md, log.md, frontmatter, or anything else.
- **Stderr is for diagnostics only.** Anything printed to stdout
  must be a valid JSON-RPC message (one line, newline-terminated).
  Stray prints would break the wire.

## Lifecycle

```text
1. MCP client (Claude Code / federation peer) spawns mcp_server.py
   via configured command + args (stdio transport).
2. Client sends initialize. Server responds with serverInfo
   including wiki_id.
3. Client sends initialized notification. Server doesn't respond.
4. Client may call tools/list to discover available tools.
5. Client calls tools/call as needed during the session.
6. When done, client sends shutdown. Server replies, then waits
   for EOF on stdin.
7. Client closes stdin. Server's readline returns "", exits 0.
```

A federation client may not send shutdown — it may just close stdin.
The server treats EOF as a clean exit; no state to flush.

## Diagnostics

For now, the server doesn't log to a file. Stderr can be redirected:

```bash
py -3 plugin/scripts/mcp_server.py --wiki ~/.llm-wiki/X 2>~/.kata/mcp.log
```

A future enhancement (v1.12+ polish): structured per-request stderr
logging with timing breakdowns. Out of scope for MVP.

## Known limitations (Phase 0)

- **Only one tool** (`wiki-search`) — Phase 1 adds the other three
- **stdio only** — Phase 1 adds SSE for cross-machine federation
- **No incremental results** — `tools/call` returns the full result
  in one MCP response (search is fast enough this isn't a problem)
- **No subscriptions / progress notifications** — search is
  synchronous; if a future tool needs progress (e.g. dreaming
  diagnostic), the protocol supports `notifications/progress` but
  we don't use it yet
- **Server doesn't auto-reload SCHEMA.md.** If you edit SCHEMA.md
  while the server is running, restart it for the change to take
  effect. Same contract as v1.8 sync.

## See also

- `docs/PRD-v1.12-cross-wiki-federation.md` — full v1.12 design
- `plugin/scripts/search_naive.py` — the subprocess invoked by
  `tools/call wiki-search`
- `plugin/skills/wiki-search/SKILL.md` — the slash-command surface
  for the same functionality (kept in parallel; both reach
  search_naive.py)
- `docs/PRD-v1.8-sync.md` §11.9 — the wiki_id identity-check pattern
  this server's `serverInfo.kata.wiki_id` block reuses
