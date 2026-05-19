---
name: wiki-federate
description: "Cross-wiki federation — query peer kata wikis via MCP and merge results with provenance. v1.12 Phase 2: federation client side. wiki A's search/query can fan out to katas B, C, ... listed in {wiki_path}/.federation.yaml, returning ranked merged results with kata://<peer>/<path> URIs for citation. Read-only across the boundary; peer wiki_id is verified before trusting (PRD D1.5). Phase 0+1 made each kata an MCP server; this skill is the other half — making it an MCP client too."
user-invocable: true
argument-hint: "search <query> [--wiki=<path>] [--limit=10] [--peers=name1,name2] [--no-federate] | peers [--wiki=<path>] | resolve <kata://uri> [--wiki=<path>]"
---

# wiki-federate

The federation client side of v1.12. v2.8.0/v2.9.0 made a kata serve
itself over MCP; v2.10.0 (this skill) makes a kata **consume** other
kata MCP servers — query them, merge results, preserve provenance.

## When to use

- A query in kata A would benefit from kata B / C's content too
  ("how do other projects handle X?", "is there a prior decision on Y
  in the patterns kata?")
- Authoring a new spec in kata A that may overlap with prior specs in
  federated peers
- Cross-team / cross-project knowledge surfacing without forcing
  bulk-import

Skip if:
- Only one kata exists on this machine
- The federation peer isn't trusted (don't add to `.federation.yaml`
  in the first place — PRD D2.3 trust-is-explicit)
- You want to ingest the peer's content as first-class A pages — use
  `wiki-import` against the peer's filesystem path instead (PRD D1.6)

## Configuration

Each wiki has its own `.federation.yaml` at the wiki root (PRD D2.1
per-wiki, not per-machine):

```yaml
# {wiki_path}/.federation.yaml
peers:
  - name: necallkit
    wiki_id: 7b52f6df-d7cf-47ab-b980-6042cf3a675c
    endpoint: stdio
    command:
      - "py"
      - "-3"
      - "C:/path/to/kata/plugin/scripts/mcp_server.py"
      - "--wiki"
      - "~/.llm-wiki/NECallKit"
    description: "NECallKit project wiki"
    enabled: true
    timeout_seconds: 5
```

**Quote every command token.** The kata-stdlib YAML subset parser
treats bare colons as mapping separators, so on Windows the
`C:/...` drive colon in a bare path will be mis-parsed as
`{C: /...}`. Quoting (`"C:/..."`) tells the parser it's a literal
string. This applies to the executable, script path, `--wiki` flag
name (technically OK unquoted, but consistency wins), and the wiki
root. Posix paths (`/home/user/...`) are colon-free and survive
unquoted, but the schema example quotes everything for one
consistent rule.

Fields:
- `name` (required) — used in `kata://<name>/...` URIs. Pattern `^[a-z][a-z0-9-]*$`.
- `wiki_id` (required) — peer's UUIDv4 from its SCHEMA.md. Identity-check on first connect; mismatch refuses (PRD D1.5).
- `endpoint` — `stdio` (Phase 2 MVP only). `sse` deferred.
- `command` — argv array to spawn the peer's MCP server (for `stdio`). Tokens go through `os.path.expanduser`; no shell expansion.
- `enabled` (default `true`) — disable without removing.
- `timeout_seconds` (default `5`) — per-call timeout. PRD D2.4 recommends `10` for heavy stdio peers (large wikis with slow boot), `3` for low-latency SSE.

Asymmetric peering is a feature: wiki A's `.federation.yaml` can list
B but B's `.federation.yaml` need not list A.

## Subcommands

### `search` — federated query

```bash
python {plugin_root}/scripts/federation_client.py federate-search \\
    --wiki {wiki_path} \\
    --query "F011 merge-back" \\
    [--limit 10] \\
    [--tier active|all|archived|frozen] \\
    [--peers necallkit,patterns] \\
    [--no-federate]
```

Runs local search, **then** fans out **in parallel** to each enabled
peer. Merges all results into a single ranked envelope. (Local search
blocks before fan-out begins — peer queries don't start until local
completes. Slow local search = delayed peer queries.)

**Output shape**:

```json
{
  "query": "F011 merge-back",
  "results": [
    {
      "path": "decisions/F011-internal.md",
      "title": "...",
      "score": 8.5,
      "source_wiki": "self"
    },
    {
      "path": "decisions/F011-shared-pattern.md",
      "title": "...",
      "score": 7.8,
      "source_wiki": "7b52f6df-...",
      "source_wiki_name": "necallkit",
      "uri": "kata://necallkit/decisions/F011-shared-pattern.md"
    }
  ],
  "federation": {
    "peers_queried": ["necallkit"],
    "peers_timed_out": [],
    "peers_unreachable": [],
    "local_only_fallback": false
  }
}
```

`source_wiki: "self"` for local results; peer wiki_id + name + URI
for federated results. The `federation` diagnostic always populates
even on success (so the caller can audit which peers responded).

### `peers` — list registered peers

```bash
python {plugin_root}/scripts/federation_client.py list-peers \\
    --wiki {wiki_path}
```

Returns the peer registry contents + whether `.federation.yaml`
exists at all (handy for diagnosing "why isn't fan-out happening?").

### `resolve` — parse + lookup a kata:// URI

```bash
python {plugin_root}/scripts/federation_client.py resolve-uri \\
    --uri "kata://necallkit/decisions/F011.md" \\
    --wiki {wiki_path}
```

Useful when an agent encounters a `kata://...` citation and needs to
know which peer to consult. PRD D2.2: name-first lookup, fall back to
wiki_id UUID if the identifier parses as UUIDv4.

## Failure modes (all non-fatal to local query)

| Failure | Behavior |
|---|---|
| Peer unreachable (stdio command fails, file not found) | `peers_unreachable: [{name, reason}]`; local result still returned |
| Peer times out (> `timeout_seconds`) | `peers_timed_out: [{name, timeout_seconds, reason}]`; local fallback |
| Peer returns garbage / wrong shape | Treated as timeout; results from that peer discarded |
| `wiki_id` mismatch (registry says X, peer reports Y) | `peers_unreachable` with reason "wiki_id mismatch"; the actual ID is included |
| `.federation.yaml` missing | `local_only_fallback: true`; behaves like pre-v1.12 |
| `.federation.yaml` malformed YAML | Treated as empty registry; surfaces in diagnostic |

**Critically**: no failure mode produces a hard error to the user
query. Local results always come back if local is healthy. The
`federation:` block is the only signal of peer issues.

## Safety contract

- **Identity check at every connect** (PRD D1.5). If a peer's
  `serverInfo.kata.wiki_id` ≠ registry's `wiki_id` → refuse the peer
  this session, surface the mismatch.
- **Read-only across the boundary**. The peer's MCP server only
  exposes read tools (`wiki-search`, `wiki-graph`,
  `wiki-spec-preflight`). No write skills traverse federation. If
  you want B's page as a first-class A page, use `wiki-import`
  against B's filesystem (PRD D1.6).
- **No transitive resolution**. If `kata://B/X.md` references
  `kata://C/Y.md`, A doesn't automatically follow. Deferred to
  v1.12+ (PRD §Out of scope).
- **No remote auth**. Trust is the local `.federation.yaml` entry
  + matching `wiki_id`. Appropriate for single-user multi-wiki +
  same-org. Out of scope for arbitrary-internet federation.
- **Privacy**: a federated query sends the query text verbatim to
  each peer. If a query is sensitive, use `--no-federate`.

## Author workflow (where federation actually shows up)

This skill is the script-level surface. The natural caller is
`wiki-query` — when it runs and `.federation.yaml` exists, it should
invoke `federation_client.py federate-search` and merge with the
local result before synthesizing the answer. That higher-level
integration is the wiki-query SKILL's job (and a v2.10.x +/v2.11.0
follow-up); for v2.10.0 MVP, `wiki-federate` is a direct invocation
path.

Author-facing flow:

1. Author adds a peer to `.federation.yaml`
2. Sanity check: `/kata:wiki-federate peers` — confirms registry
3. Test query: `/kata:wiki-federate search "..."` — confirms peer
   responds + identity check passes
4. Daily usage: peer-side participation in queries / spec preflight
   happens automatically once the registry is populated

## kata:// URI scheme

Form: `kata://<name-or-wiki_id>/<path-relative-to-wiki-root>`

Examples:
- `kata://necallkit/decisions/F011-merge-back.md`
  (name form — daily use, readable)
- `kata://7b52f6df-d7cf-47ab-b980-6042cf3a675c/decisions/F011-merge-back.md`
  (wiki_id form — long-lived citations in spec_relationships,
  synced wiki pages; survives peer renames)

PRD D2.2: skills prompt author to use the wiki_id form when the
citation lives in `spec_relationships:` or anywhere it might travel
across machines. Daily search results auto-render as the name form.

## See also

- `wiki-mcp-server` — the other half (server side; v2.8.0 / v2.9.0)
- `docs/PRD-v1.12-cross-wiki-federation.md` — full design + locked
  decisions (D1.1-D1.7, D2.1-D2.4)
- v1.8 sync §11.9 — the `wiki_id` immutability + identity-check
  pattern this skill reuses
