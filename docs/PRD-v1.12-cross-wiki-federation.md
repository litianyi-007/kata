# PRD v1.12 — Cross-wiki federation via MCP (query-only)

Status: Draft v2 — round-1 open questions closed
Date: 2026-05-18 (round-2 2026-05-18)
Author: surebeli

## Context

Kata is single-wiki by design. The whole product principle is the
self-closing loop: one root, one SCHEMA.md, one tier system, one
dreaming pass. That principle is load-bearing — v2.5.0 removed
`external_sources` precisely because reaching outside `{wiki_path}/`
broke it (see ADR
`~/.llm-wiki/kata/decisions/2026-05-17-external-sources-removed.md`).

But there's a real cooperation need that doesn't violate self-closing:
**two or more full kata wikis cooperating at the query layer**. The
patterns we see in real use:

- **Individual multi-wiki.** A single user with a NECallKit wiki AND a
  kata self-meta wiki. Writing a feature in kata sometimes needs to
  reference a decision from NECallKit.
- **Same-machine multi-project.** A developer with 5 active projects =
  5 kata wikis. Cross-project lessons / patterns / vendor docs need to
  inform each other without forcing one giant wiki.
- **Cross-team.** Team A's wiki references Team B's ratified
  decisions, possibly on another machine or in another organization.

v1.12 introduces **federated query** between independent kata wikis
through the Model Context Protocol (MCP). Each kata wiki exposes
itself as an MCP server. A query in kata A can fan out to registered
kata B / C / ... and merge results — without either side losing
authority over its own content.

The v1.13 PRD already references "v1.12 federation" as the right
answer for cross-source needs. This PRD makes that reference real.

## Goals

- **Query-only cooperation**: a kata can ask another kata's
  `wiki-query` / `wiki-search` / `wiki-spec preflight`, receive curated
  results, and cite them — without ever reading the other side's
  filesystem directly.
- **MCP as the wire** so that the same surface is reachable by **any
  MCP-aware agent** (Claude Code, Cursor, Continue, etc.), not just
  another kata. Federation is one consumer of the MCP server, not the
  only one.
- **First-class `kata://` URI scheme** for cross-wiki citations.
  Distinct from the removed `external://` because both endpoints are
  full self-closing kata wikis with wiki_id, SCHEMA, tier system, and
  dreaming.
- **wiki_id-based identity** for trust + provenance. Identity is the
  immutable UUID already established by v1.8 sync; no new auth surface.
- **Read-only across the boundary by default.** Wiki A never modifies
  wiki B. If A wants B's content as a kata page of its own, A runs
  `wiki-import` against B's exported page — same single-source-of-truth
  rule as v2.5.0.
- **Discoverability** through a small per-machine registry file
  `{wiki_path}/.federation.yaml`. Listing a wiki there = declaring trust;
  removing = revoking.

## Non-goals

- **No cross-wiki write.** Federation does not enable wiki A to ingest
  pages into wiki B, modify B's SCHEMA.md, or call B's tier-management
  skills.
- **No real-time sync.** Cross-wiki sync is the union of single-wiki
  syncs (each side does its own v1.8 sync against its own remote).
  Federation is per-query, not background-replicated.
- **No conflict resolution across wikis.** If A cites B's page F011
  and B later updates F011, A's citation becomes stale. Surfacing that
  is a v1.13 Phase 4 lineage-view concern, not v1.12's.
- **No identity federation.** No SSO, no token exchange between
  organizations, no PKI. v1.12 trust is per-machine, per-config-file —
  appropriate for "I trust these wikis because I configured them
  locally."
- **No agent-to-agent (A2A) protocol bridging.** A2A standards are
  immature; v1.12 ships MCP only. See §"A2A: deferred, not blocked"
  below for the rationale and the future-extension shape.
- **No automatic dependency resolution.** If A cites `kata://B/X.md`
  and X.md depends on `kata://C/Y.md`, A does not automatically fetch
  Y. Transitive federation is a v1.12+ enhancement, not MVP.
- **No bulk pull.** Federation is per-query, on-demand. There is no
  `wiki-federation-sync-all` command that drags B's content into A.
  Bulk import = run `wiki-import` against B's filesystem path (which
  requires explicit access; not the federation channel).

## Personas / user stories

- **Multi-wiki maintainer (this user)** — has `~/.llm-wiki/NECallKit/`
  + `~/.llm-wiki/kata/`. While authoring a kata-self-meta feature
  page, runs `wiki-query` and gets a related decision from the
  NECallKit wiki in the same result envelope. Cites it via
  `kata://necallkit/decisions/F011.md` if it makes the cut.
- **Cross-project developer** — has 5 kata wikis across active
  projects. Configures one "patterns" kata as a federation target for
  all 5 project wikis. Every `wiki-query` in any project automatically
  fans out to "patterns" first to see if there's a prior-art match.
- **Team lead with kata read-access to peer team** — Team A's kata
  wiki is on the same network as Team B's. A's `federation.yaml`
  registers B's MCP server endpoint. A's authors can query B's
  ratified decisions when writing their own specs; A cites B's pages
  via `kata://teamB/decisions/...` URIs.
- **Independent MCP-client agent (non-kata)** — Cursor or Continue or
  a custom agent connects to a kata's MCP server, calls
  `wiki-query` as one of many available MCP tools, and gets the same
  curated results without knowing what "kata" is. Federation is just
  one consumer of the MCP server, not its only consumer.

## Why MCP and not the alternatives

Five candidate transport layers were considered (see this session's
2026-05-18 design discussion). The matrix:

| Transport | Pros | Cons | Verdict |
|---|---|---|---|
| Local filesystem direct | Zero protocol overhead | Same-machine only; breaks self-closing | Rejected (it was `external_sources`) |
| HTTP daemon | Standard, easy to debug | New daemon to manage; port allocation; firewall complexity | Rejected |
| **MCP server** | **Anthropic-native; ANY MCP client can use, not just kata; stdio + SSE both supported; capability declaration built in; per-tool authz** | **Newer protocol (2025), but stable; requires SDK or hand-rolled JSON-RPC** | **CHOSEN** |
| Git-based (clone B locally) | Works behind firewall; no live process | Async / lag; B's authority over its own data weaker | Rejected for query path (still valid for bulk import) |
| SSH stdio | Simple if both sides are CLI | Auth + permissions get complex; not multi-client | Rejected |

The decisive argument for MCP: **every consumer the user already runs
is an MCP client**. Claude Code is. Cursor is. Continue is. Codex CLI's
roadmap is. A kata MCP server gets free interop with all of them.
Federation between two katas is then a specialization of "two MCP
clients pointed at the same server" rather than a kata-specific
protocol.

## A2A: deferred, not blocked

Agent-to-Agent protocols (Google A2A, AGI agent interop) operate at a
higher layer than MCP — they assume each side has agent identity,
goal reasoning, and conversation state. Kata is data + skills, not an
agent in that sense. Wrapping kata as an A2A agent would force it to
adopt a layer it doesn't natively have.

The plan: **kata exposes MCP today; A2A bridge is a future shim.** If
an A2A standard matures and ecosystem demand surfaces, a kata
A2A-wrapper agent can be built that consumes the MCP server. The data
model (wiki_id-based identity, `kata://` URI scheme) is designed
forward-compatibly:

- `kata://` URIs carry just enough identity to be A2A-citeable later
- federation.yaml entries can hold extra fields (`agent_id`, capability
  flags) without disturbing today's MCP-only consumers
- The MCP server's tool surface mirrors what an A2A agent would
  expose anyway (query / fetch / preflight)

This is the same deferral pattern v1.13 used for Phase 3+4 — design
forward, ship only what's needed today.

## Why query-only and not citation+ingest or bidirectional

Three coordination granularities were considered (see 2026-05-18
discussion):

| Granularity | What it means | Verdict |
|---|---|---|
| **Query-only** | A can ask B's wiki-query; B returns curated results; A cites by URI | **CHOSEN** (MVP) |
| Citation + ingest | A can pull B's page wholesale into A's wiki | Use `wiki-import` against B's filesystem path (no federation channel needed) — see Migration |
| Bidirectional dreaming | A and B participate in each other's auto-dreaming | Out of scope; would require shared trust on tier changes |

Query-only is the smallest unit of cooperation. Citation+ingest is
better served by the existing `wiki-import` skill (kata already solves
that problem — see v2.5.0 removal ADR for why we don't want a parallel
ingest path). Bidirectional dreaming requires deep trust ("you can
re-promote my frozen pages") that's hard to bound; deferred.

## Architecture overview

```
┌──────────────────────────────────────────────────────────────────┐
│  Kata A (wiki_id: a1...)                                         │
│                                                                  │
│  ┌─────────────────────┐         ┌──────────────────────────┐    │
│  │ wiki-query skill    │ ───────►│ MCP client (built-in)    │    │
│  │ (with federation)   │         │                          │    │
│  └─────────────────────┘         └──────────────┬───────────┘    │
│                                                 │                │
│  ┌─────────────────────┐                        │                │
│  │ .llm-wiki/          │   reads                │                │
│  │   federation.yaml   │ ◄──────────────────────┘                │
│  └─────────────────────┘                        │                │
└─────────────────────────────────────────────────┼────────────────┘
                                                  │ MCP over stdio
                                                  │ or SSE
                                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│  Kata B (wiki_id: b2...)                                         │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │ kata MCP server (plugin/scripts/mcp_server.py)              ││
│  │                                                             ││
│  │ Tools exposed:                                              ││
│  │   - wiki-query     (the existing wiki-query skill body)     ││
│  │   - wiki-search    (subset: keyword + tag filter)           ││
│  │   - wiki-spec-preflight (Phase 0 advisory)                  ││
│  │                                                             ││
│  │ Server reads:                                               ││
│  │   - {wiki_path}/SCHEMA.md (capability declaration)          ││
│  │   - {wiki_path}/index.md, pages/*  (query targets)          ││
│  │                                                             ││
│  │ Server NEVER writes anywhere.                               ││
│  └──────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

Same kata binary on both sides. Same `wiki-query` skill body. The
federation is just "the wiki-query skill is now also reachable through
MCP" + "wiki-query can fan out to MCP clients pointed at other katas."

## Phase breakdown

### Phase 0 — MCP server scaffold (kata as MCP server)

Ship a minimal MCP server that exposes `wiki-search` as one tool. No
client side, no federation, no `kata://` URIs. Just: any MCP-aware
agent (including itself) can connect via stdio and call
`wiki-search`. Validates the protocol surface end-to-end before adding
complexity.

Deliverables:
- `plugin/scripts/mcp_server.py` — stdio MCP server, single tool
- `plugin/skills/wiki-mcp-server/SKILL.md` — how to start it, how to
  test it, how to register it with Claude Code / Cursor
- Smoke test: spawn server, send JSON-RPC `tools/list` and
  `tools/call wiki-search`, assert results format
- `wiki_id` exposed in `serverInfo` per MCP spec

Versioning: v2.8.0.

### Phase 1 — Tool surface expansion + capability declaration

Add `wiki-query`, `wiki-graph` (read subset), `wiki-spec-preflight` as
MCP tools alongside `wiki-search`. Tool descriptions read from each
skill's SKILL.md `description:` field — single source of truth. The
server's `serverInfo` declares wiki domain, categories from SCHEMA.md,
and `wiki_id` so MCP clients can negotiate.

Deliverables:
- 3 more tools on the server
- Capability declaration via `serverInfo.capabilities` + custom
  `serverInfo.kata` block (domain, categories, tier-system enabled,
  spec_authoring enabled)
- Smoke tests for each tool
- `wiki-mcp-server` SKILL.md grows tool-by-tool reference

Versioning: v2.9.0.

### Phase 2 — Federation client side + `kata://` URI scheme

Kata becomes an MCP client too: when `wiki-query` is invoked locally
in kata A, it also fans out to katas listed in A's
`{wiki_path}/.federation.yaml`, merges responses, sorts by score,
preserves provenance. New `kata://<name|wiki_id>/<path>` URI scheme
for citations in `spec_relationships:`, query results, and free-form
references.

Deliverables:
- `plugin/scripts/federation_client.py` — MCP client wrapper
- `{wiki_path}/.federation.yaml` schema + reader
- `kata://` URI parser + resolver
- `wiki-query` skill grows `--federate` flag (default on if
  federation.yaml exists; off if not)
- Fan-out timeout / error handling (default: 3s per peer, fall back
  to local-only on timeout)
- Provenance: every result carries `source_wiki: <wiki_id>` +
  `source_wiki_name: <name>` for citation
- Smoke test: 2 fixture wikis, federate query, assert merged ranked
  result with provenance fields

Versioning: v2.10.0.

### Phase 3 — Cross-wiki spec preflight + enforcement integration

Integration with v1.13. When authoring a new spec in kata A, preflight
optionally fans out to federated katas. A's
`spec_relationships:` block can target `kata://B/decisions/X.md` URIs.
The v1.13 Phase 2 enforcement gate normalizes `kata://` URIs the same
way it normalizes wikilinks/stems.

Deliverables:
- `spec_preflight.py` learns `--federate` to include cross-wiki
  candidates
- `kata://` URI added to the normalization paths in
  `_normalize_target` and `_candidate_match_keys`
- Provenance carried into the `enforcement` block (which wiki did
  each candidate come from)
- Smoke test for cross-wiki preflight + enforcement

Versioning: v2.11.0.

## Data model

### `kata://` URI scheme

Form: `kata://<name-or-wiki-id>/<path-relative-to-wiki-root>`

Where `<name-or-wiki-id>` is either:
- A **name** matching a registry entry's `name:` field
  (`kata://necallkit/decisions/F011.md`)
- A **wiki_id UUID** for unambiguous identity
  (`kata://b2f6d18e-2eb6-4b75-9d40-c92a4f1d5e83/decisions/F011.md`)

Resolution:
1. Try name match first against `{wiki_path}/.federation.yaml` `name:`
   fields
2. If no match and the part is UUIDv4-shaped, try `wiki_id:` match
3. If still no match → unresolvable (citation kept verbatim; queries
   skip; preflight enforcement-gate notes it as unresolvable
   reference)

**Why distinct from removed `external://`**: both names point at
external data, but:
- `external://name/path` (removed) pointed at a **raw markdown
  directory** with no kata semantics — no `wiki_id`, no SCHEMA, no
  tier system, no dreaming. Required inventing a lifecycle to behave.
- `kata://name/path` points at **another full kata wiki** with all of
  the above. The other side is itself self-closing; we're just
  consuming its query API. No new lifecycle invented.

### `{wiki_path}/.federation.yaml`

**Per-wiki**, in the wiki root. Each kata wiki has its own peer
registry — wiki A can federate with X+Y while wiki B federates with
only Y. Locked per Q1 review (2026-05-18): asymmetric peering is a
feature, not a complication.

The file is normally git-tracked alongside the wiki (no secrets — just
peer slugs + endpoints + wiki_id UUIDs). Multi-machine sync via
v1.8 carries it forward like any other wiki file. Per-machine
endpoint overrides (e.g. stdio paths that differ per OS) are handled
inside each entry via the existing `wiki_id`-keyed
machine-fingerprint mechanism v1.10 introduced (out of scope for
this PRD; addressed when stdio endpoints across machines need it).

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
    description: "NECallKit project wiki (local)"
    enabled: true
    timeout_seconds: 5
    capabilities:
      - wiki-search
      - wiki-query
      - wiki-spec-preflight

  - name: patterns
    wiki_id: c1d2e3f4-5678-90ab-cdef-1234567890ab
    endpoint: sse
    url: "http://patterns-kata.local:8765/mcp"
    description: "Shared patterns kata (team-wide)"
    enabled: true
    timeout_seconds: 8
```

Schema fields:

| Field | Required | Description |
|---|---|---|
| `name` | yes | Short slug used in `kata://<name>/...`. Pattern: `^[a-z][a-z0-9-]*$`. Must be unique within the registry. |
| `wiki_id` | yes | UUIDv4 from peer's SCHEMA.md. Identity check at first connect; mismatch refuses (same contract as v1.8 sync). |
| `endpoint` | yes | `stdio` or `sse`. Selects MCP transport. |
| `command` | if stdio | Argv array for spawning the peer's MCP server. The kata launching it must have file-system access to the peer's wiki root. |
| `url` | if sse | HTTP URL of the peer's MCP server's SSE endpoint. |
| `description` | optional | Human-readable label for audit / debugging. |
| `enabled` | optional, default true | Disable a peer without removing the entry. |
| `timeout_seconds` | optional, default 3 | Per-call timeout; on timeout, federation falls back to local-only and records the timeout in the result envelope. |
| `capabilities` | optional | Allowlist of which tools to call on this peer. If unset, the kata's MCP client queries `tools/list` once at connect and uses the union with local needs. |

### Cross-wiki result envelope

`wiki-query` and `wiki-search` results gain two fields per candidate
when federation is active:

```json
{
  "candidates": [
    {
      "path": "decisions/F011-merge-back.md",
      "title": "F011 merge-back lane discipline",
      "type": "decisions",
      "tier": "active",
      "score": 8.5,
      "source_wiki": "7b52f6df-d7cf-47ab-b980-6042cf3a675c",
      "source_wiki_name": "necallkit",
      "uri": "kata://necallkit/decisions/F011-merge-back.md",
      "signals": { ... }
    },
    {
      "path": "decisions/v1.13-phase2-enforcement-gate.md",
      "title": "v1.13 Phase 2: relationship declaration enforcement gate",
      "tier": "active",
      "score": 7.2,
      "source_wiki": "self",
      "uri": "decisions/v1.13-phase2-enforcement-gate.md",
      "signals": { ... }
    }
  ],
  "federation": {
    "peers_queried": ["necallkit", "patterns"],
    "peers_timed_out": [],
    "peers_unreachable": [],
    "local_only_fallback": false
  }
}
```

Local candidates have `source_wiki: "self"` (or omit `source_wiki`
entirely; both forms accepted by the v1.13 enforcement
normalization). The `federation:` diagnostic block surfaces
per-peer outcomes so the user / agent can see if a peer didn't
respond.

## Safety / trust model

### Trust is local-config

`{wiki_path}/.federation.yaml` is the **only** trust surface in v1.12.
A peer is trusted iff:
- It appears in the local registry with `enabled: true`
- Its first-connect `wiki_id` matches the registry's expected `wiki_id`
  (identity check borrowed from v1.8 sync §11.9)

There is **no remote auth**, no token exchange, no PKI. The model is
"local trust on a manually-curated list" — appropriate for
single-user multi-wiki and same-org cross-team. Inappropriate (out of
scope) for arbitrary-internet federation.

### Read-only contract

The MCP server tools exposed in Phase 0-1 are **all read-only**:
- `wiki-search` — reads pages, returns ranked matches
- `wiki-query` — reads pages, returns synthesized answer + citations
- `wiki-graph` (read subset) — reads frontmatter + links, returns
  graph queries (no `--apply` flag exposed)
- `wiki-spec-preflight` — reads pages, returns candidate list

Skills that mutate (`wiki-ingest`, `wiki-import`, `wiki-tier --pin`,
`wiki-dream --apply`) are **not exposed** as MCP tools. This is a hard
boundary: federation is for reading. Cross-wiki write requires
explicit human action through `wiki-import` against the peer's
filesystem path (which itself requires the peer's local user's
consent — it's just `wiki-import`, not federation).

### wiki_id identity check at connect

On first MCP connect to a peer, the kata MCP client:
1. Calls `serverInfo` to retrieve the peer's declared `wiki_id`
2. Compares against the registry entry's `wiki_id`
3. **Mismatch → refuse to use the peer this session**; surface the
   mismatch in `federation.peers_unreachable` with reason

This catches: misconfigured pointer (registry says peer A but the
endpoint actually serves peer B), peer re-init that dropped its
`wiki_id`, deliberate impersonation in a same-org network.

### Failure modes

| Failure | Behavior |
|---|---|
| Peer unreachable (stdio command fails / SSE URL down) | `peers_unreachable: [...]` in result; local-only result still returned |
| Peer times out (> `timeout_seconds`) | `peers_timed_out: [...]`; local-only fallback returned |
| Peer returns garbage / wrong shape | Treated as timeout: result discarded, peer marked timed-out for this session |
| `wiki_id` mismatch | Peer marked unreachable + identity-mismatch reason; user prompted to update registry |
| Local registry missing | Federation silently off; behaves like pre-v1.12 (local-only) |
| Local registry malformed | Skill refuses to start; surface YAML parse error to user |

Critically: **no failure mode produces a hard error to the user
query**. Local results always come back if local is healthy. The
`federation:` diagnostic block is the only signal of peer issues.

## CLI surface

### Server side

```bash
# Manual start (for testing / SSE deployment)
py -3 plugin/scripts/mcp_server.py --wiki ~/.llm-wiki/NECallKit \
    [--transport stdio|sse] [--port 8765]

# Typical use: started by an MCP client (Claude Code etc.) automatically
# via the client's MCP server registration. See SKILL.md for the
# registration snippet per client.
```

### Client side (federation in `wiki-query`)

```bash
# Default: if {wiki_path}/.federation.yaml exists and has any
# enabled peer, federation is on
/kata:wiki-query "How does payment flow work?"

# Force-disable federation for one call
/kata:wiki-query "..." --no-federate

# Restrict to specific peers
/kata:wiki-query "..." --federate-peers=necallkit,patterns

# Diagnostics: show federation block in output
/kata:wiki-query "..." --explain
```

### Registry management

```bash
# Show registered peers
/kata:wiki-federation list

# Add a peer (interactive prompts for name, wiki_id, endpoint)
/kata:wiki-federation add

# Disable a peer without removing
/kata:wiki-federation disable necallkit

# Remove a peer
/kata:wiki-federation remove necallkit
```

(`wiki-federation` is a new skill, but minimal — most of the work is
the federation.yaml read/write, identical pattern to
`session_ingest.py config` from v1.11.)

## Test plan

### Phase 0 tests
- T-mcp-1: server starts, `tools/list` returns `wiki-search`
- T-mcp-2: `tools/call wiki-search` against fixture wiki returns
  expected results
- T-mcp-3: `serverInfo` exposes `wiki_id` from fixture SCHEMA.md
- T-mcp-4: server refuses to start if `--wiki` path has no SCHEMA.md

### Phase 1 tests
- T-mcp-5: all 4 read-tools exposed; each returns its expected shape
- T-mcp-6: write-skills NOT exposed (negative test — agent attempts
  `tools/call wiki-ingest` → tool not found)
- T-mcp-7: capability declaration carries domain + categories from
  SCHEMA.md
- T-mcp-8: stdio + SSE transports both pass T-mcp-1 through T-mcp-6

### Phase 2 tests
- T-fed-1: 2-fixture-wiki federation; `wiki-query` against A fans out
  to B, merged result has provenance fields, ordering correct
- T-fed-2: peer unreachable → `peers_unreachable: [B]`, local-only
  result returned with non-zero exit
- T-fed-3: peer timeout → `peers_timed_out: [B]`, local-only fallback
- T-fed-4: wiki_id mismatch → peer marked unreachable + reason
- T-fed-5: malformed federation.yaml → skill refuses to start with
  parse-error message
- T-fed-6: `kata://necallkit/path.md` URI parser + resolver
- T-fed-7: `--no-federate` flag suppresses fan-out

### Phase 3 tests
- T-fed-8: cross-wiki spec preflight surfaces peer-wiki candidates
- T-fed-9: v1.13 enforcement gate accepts `kata://necallkit/X.md` as
  a covered target

## Migration

### From "nothing" (v2.7.0 and earlier)

No migration. Federation is opt-in:
- No `federation.yaml` → behavior identical to pre-v1.12
- All skills' default behavior unchanged

### Bulk content migration (when federation isn't enough)

If a user decides "actually I want B's `decisions/F011.md` as a
first-class kata page in A", the path is:
1. Run `wiki-import` in A against B's filesystem path (requires
   file-system access to B's wiki root — federation doesn't grant
   this)
2. `wiki-import` copies the page with proper frontmatter + cross-link
3. Future queries hit local; the federation channel for that
   particular page is no longer needed

This intentionally mirrors v2.5.0's removal logic: when you genuinely
want a page in your wiki, use the existing import skill rather than
inventing a separate "federation pull" command.

## Decisions log

### Round 1 — 2026-05-18

**D1.1 — Query-only granularity (not citation+ingest, not bidirectional).**
Citation+ingest is already served by `wiki-import`; building it into
federation would duplicate that surface. Bidirectional dreaming
requires deep trust on tier changes that's hard to bound. Query-only
is the smallest unit of useful cooperation.

**D1.2 — MCP as transport (over HTTP / git / SSH stdio).**
Decisive argument: every MCP client the user already runs (Claude
Code, Cursor, Continue, Codex CLI roadmap) can consume a kata MCP
server. Federation between two katas is a specialization of "two MCP
clients pointed at the same server," not a kata-specific protocol.

**D1.3 — A2A: deferred, not blocked.**
Kata is data + skills, not an agent with goal reasoning. Wrapping
kata as A2A would force a layer it doesn't natively have. The MCP
surface (tools + serverInfo) is forward-compatible with an A2A
wrapper if one becomes useful — the wrapper would just consume the
MCP tools.

**D1.4 — `kata://` URI scheme legitimate (unlike removed `external://`).**
Both names point at external data. But `external://` pointed at a raw
markdown directory with no kata semantics (no wiki_id, no SCHEMA, no
tier system) — required inventing a lifecycle to behave. `kata://`
points at another full kata wiki with all of the above; consuming its
query API doesn't require inventing anything new.

**D1.5 — wiki_id identity check at first connect.**
Reuse the v1.8 sync identity-check pattern (PRD-v1.8 §11.9):
SCHEMA.md `wiki_id` is canonical, immutable; mismatch refuses the
peer this session. Catches misconfigured pointers + drop-and-reinit +
same-org impersonation.

**D1.6 — Read-only contract; write requires `wiki-import` against filesystem.**
The MCP server exposes only read skills. Cross-wiki write requires
explicit `wiki-import` invocation against the peer's filesystem path.
This mirrors v2.5.0's principle: when you want a page in your wiki,
ingest it through the existing import skill — don't invent a parallel
"federation pull" surface.

**D1.7 — Local-config trust, no remote auth.**
`{wiki_path}/.federation.yaml` is the only trust surface for MVP.
Appropriate for single-user multi-wiki + same-org cross-team.
Out-of-scope for arbitrary-internet federation; that's a v1.12+
extension if there's demand.

### Round 2 — 2026-05-18 (Q1-Q4 locked)

**D2.1 — `.federation.yaml` is per-wiki.**
Located at `{wiki_path}/.federation.yaml`, not in `~/.llm-wiki/`.
Different wikis can federate with different peers — wiki A peers with
X+Y while wiki B peers with only Y. Asymmetric peering is a feature,
not an oversight. The file is normally git-tracked alongside the wiki
(no secrets, just slugs + endpoints + wiki_id UUIDs) and rides
forward via v1.8 sync like any other wiki file. Per-machine endpoint
overrides (e.g. when a stdio command path differs across OSes) are
handled inside individual entries via the existing `wiki_id`-keyed
machine-fingerprint mechanism from v1.10 — out of scope for v1.12
MVP unless a real cross-platform setup demands it.

**D2.2 — `kata://` URI: name-first daily, wiki_id-form for long-lived.**
Daily use writes names (`kata://necallkit/decisions/F011.md`) for
readability. For long-lived citations in `spec_relationships:`,
synced wiki pages, or anything that travels across machines, the
skills prompt the author to use the wiki_id form
(`kata://7b52f6df-.../decisions/F011.md`) instead. Resolution order
in the URI parser: name first, fall back to wiki_id-shaped UUIDv4.
The storage layer does NOT auto-normalize to wiki_id — the author's
chosen form is preserved verbatim.

**D2.3 — Trust is explicit only; no TOFU prompts.**
A peer is trusted iff it appears in the local `.federation.yaml`
with `enabled: true`. No trust-on-first-use prompt path. If a
federated query returns a result containing a `kata://X/...` URI and
X isn't in the local registry, the URI is treated as unresolvable
and surfaced in the result's `federation:` diagnostic block as such.
Adding a peer is a deliberate `/kata:wiki-federation add` action (or
a manual edit). Rationale: explicit beats clever for trust; TOFU has
a long history of accidentally building bad-habit pathways.
Reconsider only if a real workflow surfaces where TOFU's friction is
prohibitive and the security cost is bounded.

**D2.4 — Timeout 5s default, no retry, per-peer adjustable.**
`timeout_seconds: 5` is the default in the registry schema —
balancing stdio cold-spawn cost (Python interpreter + module load)
against tight fan-out latency budgets. No retry on timeout — flaky
peers fall out of the current query and are marked in
`federation.peers_timed_out`; they'll be retried on the next user
query naturally. Per-peer override via the existing
`timeout_seconds` field. Docs recommend `10` for heavy stdio peers
(large wikis loading hub graph at boot), `3` for low-latency SSE
peers.

## Risks

- **MCP protocol churn.** MCP is young (2025 onwards); breaking
  changes possible. Mitigation: pin to a specific MCP SDK version;
  the wiki-query skill side is decoupled — only the
  `mcp_server.py` + `federation_client.py` shims touch the protocol.
- **Latency in deep query fan-out.** If kata A federates with 5
  peers, every wiki-query waits for the slowest one (up to
  `timeout_seconds`). Mitigation: per-peer timeout + parallel
  fan-out (asyncio) + `peers_timed_out` diagnostic so the user can
  see which peer slowed them down.
- **Stale citations.** A's kata page cites `kata://B/X.md`. B later
  archives or moves X.md. A's citation becomes unresolvable.
  Mitigation: surface unresolvable URIs in `wiki-lint` (v1.12+
  polish); v1.13 Phase 4 lineage view is the longer-term answer.
- **wiki_id collisions across re-inits.** If a user runs
  `wiki-init --refresh-id` on a peer, that peer's wiki_id changes
  and federation breaks until the registry is updated. Surface this
  loudly via the identity-mismatch error path.
- **Skill discovery confusion.** An MCP client connects to a kata
  MCP server and sees `wiki-search` as a tool — but the user's
  Claude Code session has its own `kata:wiki-search` slash command.
  Two paths to the same skill. Mitigation: docs make clear that the
  MCP tool exists for cross-wiki / non-Claude-Code clients; native
  Claude Code users prefer the slash command.
- **Privacy leakage.** A query in kata A may be sent verbatim to
  peer B. If A is internal and B is a team-wide kata, the query
  text crosses a trust boundary. Mitigation: doc that
  `federation.yaml` defines the trust boundary explicitly; if a
  query is sensitive, use `--no-federate`.

## Out of scope (deferred or rejected)

- **Cross-wiki write through federation** (v1.12-and-never; use
  `wiki-import`)
- **Bidirectional dreaming** (deferred indefinitely; trust model too
  hard to bound)
- **Transitive federation resolution** (A → B → C citation
  resolution; v1.12+ enhancement if demand)
- **Identity federation / SSO / token exchange** (rejected for kata's
  scope)
- **A2A protocol bridging** (deferred; MCP is forward-compatible)
- **TOFU trust prompts** (deferred; explicit registry beats clever
  for trust)
- **Cross-wiki conflict resolution** (deferred; surfaced by v1.13
  Phase 4 lineage view)
- **Per-wiki federation.yaml** (deferred; per-machine sufficient for
  MVP)
- **Bulk pull command** (rejected; `wiki-import` already covers this
  cleanly and properly)
