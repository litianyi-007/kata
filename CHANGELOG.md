# Changelog

All notable changes to Kata (previously `ak-wiki` — see v2.0.0 below) are
recorded here. The plugin follows [semver](https://semver.org/) — major
bumps signal a manifest or skill-API change.

## [2.14.0] — 2026-05-20 — wiki-session-ingest: incremental mode (default)

`wiki-session-ingest` previously re-parsed the entire session JSONL on
every invocation and overwrote the dump file. v2.14.0 makes re-invocation
**incremental by default**: only messages with `idx > state.last_msg_idx`
are rendered and appended to the existing dump.

### Added

- **Per-session state file** at `{wiki}/raw/sessions/.session-ingest-state.yaml`,
  keyed by `session_id`. Each entry tracks `dump_path`, `last_msg_idx`,
  `last_run_at`, `cli`, `session_file`. State ships through wiki-sync,
  so multi-machine setups stay coherent.
- **`--full` flag on `dump`** — forces a full reparse + overwrite. Reuses
  the state-recorded dump path (filename stable across days). Output
  carries `"forced_full": true`.
- **`session_ingest.py state show` / `state forget` subcommands** —
  inspect or reset incremental tracking. `forget` removes a session's
  state entry so the next dump starts fresh (full write); does NOT
  delete the existing dump file.
- **Incremental section delimiter** in the dump body:
  `<!-- kata:session-ingest INCREMENTAL run_at=… msg_start=… msg_end=… -->`
  marks each appended block, so the dump remains human-readable across
  many incremental runs.
- **Frontmatter `incremental_runs:` array** — each entry records
  `run_at`, `msg_idx_start`, `msg_idx_end`, `new_message_count`. The
  initial full write also creates one entry. `--full` reset rewrites it
  back to a single entry.

### Changed

- **Default mode is incremental.** First call: full write (creates state).
  Same-session re-invoke: incremental. Same-session re-invoke with no
  growth: no-op success with `"no_new_messages": true` — dump file is
  byte-identical.
- **Dump filename is stable across days for tracked sessions.** Previously
  `{cli}-{today}-{slug}-{short-id}.md` recomputed `today` every call, so a
  multi-day session would produce orphaned per-day files. With state, the
  filename is recorded on the first dump and reused.
- **JSONL parsers** now return `list[MessagePart]` (with stable `idx`)
  instead of pre-joined `str`. Enables msg-idx slicing for incremental
  dispatch. The rendered output is byte-identical to v2.13.1 for the
  full-write case (same line spacing).
- **MCP server version** auto-reads from `plugin.json` (introduced in
  v2.13.1) — picks up the 2.14.0 bump without code change.

### Tests

- **T-session-inc-1** — first dump → mode=full, state file initialized,
  `last_msg_idx` matches `message_count`.
- **T-session-inc-2** — re-dump with no JSONL growth → mode=incremental,
  `no_new_messages: true`, dump byte-identical (strict equality check).
- **T-session-inc-3** — JSONL grows by 2 messages → incremental append.
  Verifies: original body preserved, delimiter present, frontmatter
  `message_count` bumped, `incremental_runs:` has 2 entries, state
  `last_msg_idx` updated.
- **T-session-inc-4** — `--full` flag reuses state-recorded path,
  reparses from msg #1, resets `incremental_runs:` to a single entry,
  removes all incremental delimiters.
- **T-session-inc-5** (bonus) — `state forget` removes session entry;
  next dump → mode=full again.

### Notes

- **LLM-dump path (`dump-llm`) is always full** — agent-supplied bodies
  have no stable `msg_idx`. Each `dump-llm` call still overwrites.
- **Cross-session sweep is still NOT supported.** v2.14.0 is incremental
  *within* one session, not *across* sessions. A `--sweep` subcommand
  that scans all session files for new ones since last sweep is on the
  v1.15+ idea list, not in this release.
- **State file ships through wiki-sync.** Multi-machine setups dumping
  the same session_id will converge. If you don't want this, add
  `raw/sessions/.session-ingest-state.yaml` to your wiki's `.gitignore`.

## [2.13.1] — 2026-05-19 — codex audit hardening (path traversal + Phase 3 PREVIEW)

Response patch to Codex GPT-5.5 xhigh audit task-mpci827r-1prafp (verdict
**hold-for-changes** on v1.13 SHM). This patch lands the critical security
fix + the cheapest hardening that's safe to ship same-day. The structural
findings (Phase 3 cannot reverse, no transaction, multi-superseder semantics,
reverse-index not in lineage, federated/local key collision) are tracked
separately in `docs/PRD-v1.14-spec-propagation-reconcile.md` and will reland
the entire propagation pipeline against a transaction model. Until v1.14
ships, Phase 3 is officially **opt-in preview** — see warnings below.

### Fixed (security)

- **Critical: path-traversal in `spec_propagate.py`** — a `spec_relationships`
  declaration of `target: ../../foo.md` or absolute path could cause kata to
  write a banner / `spec_superseded_by` frontmatter / `tier_override`
  archive flip to a file outside the wiki root. `_resolve_local_target()`
  now: (a) rejects absolute target paths outright, (b) resolves the
  candidate and requires `relative_to(wiki_root.resolve())`, (c) rejects
  empty targets after wikilink-strip. Sibling `rglob` branch was already
  scope-safe but is now explicitly commented. New smoke test **T-prop-6**
  asserts an outside-wiki sentinel file is byte-identical after a
  malicious spec attempts both traversal flavors.

### Changed (Phase 3 PREVIEW posture)

- `spec_propagate.py`: `auto_propagation.enabled` truthiness changed from
  `bool(value)` to `value is True`. String `"false"` no longer coerces;
  required value is now the literal YAML `true`.
- `spec_preflight.py`: same hardening on
  `spec_authoring.enforce_relationship_declaration`. Avoids the symmetrical
  enforcement-bypass.
- Disabled-state advisory now explicitly labels Phase 3 as PREVIEW and
  points at the v1.14 PRD for the reconcile reland.

### Changed (docs)

- `plugin/skills/wiki-spec/SKILL.md`: new "Phase 3 PREVIEW caveat" section
  documents the append-only failure mode. Phase 4 section updated from
  "(future)" to "(shipped v2.13.0)". "Known limitations" rewritten to
  reflect the actual phase coverage.
- `plugin/skills/wiki-ingest/SKILL.md`: stale `external://` URI example
  in `spec_relationships` template replaced with `kata://<peer>/<path>`
  (federation contract, post v1.12). Added path-traversal note.
- `docs/PRD-v1.13-spec-history-management.md`: header now carries a
  PREVIEW status update referencing the codex audit; "External-target
  carve-out" section reworked to use the `kata://` URI scheme (v1.12)
  instead of the dead `external://` scheme (v1.13 Phase 1 was reverted).

### Fixed (correctness)

- `schema/wiki-schema.json`: `spec_authoring` was only defined under
  `$defs` and never referenced from top-level `properties`. Validation
  silently passed any junk under `spec_authoring`. Added
  `properties.spec_authoring: {"$ref": "#/$defs/spec_authoring"}`.
- `plugin/scripts/mcp_server.py`: `KATA_SERVER_VERSION` no longer
  hardcoded ("2.9.0" stale). Now read from `plugin.json` at import time
  with safe `"unknown"` fallback. Single source of truth.

### Note on the structural verdict

The codex audit's "biggest worry" — that Phase 3 creates authoritative-
looking metadata it cannot reconcile — is acknowledged and NOT fixed in
this patch. Banner write-then-orphan, multi-superseder merge collision,
supersedes→refines reversal, and concurrent ingest races remain open.
These are structural and need the v1.14 transaction model, not point
patches. Phase 3 default-off + PREVIEW labeling is the interim mitigation;
production wikis should not opt in until v1.14 ships.

### Audit trail

- Codex task: `task-mpci827r-1prafp` — GPT-5.5 xhigh, 10m43s, completed
- Verdict: `hold-for-changes`. Per-phase: Phase 0/4 ship-with-caveats,
  Phase 2/3 hold-for-changes
- Critical: 1 (path traversal — fixed here)
- High: 6 (1 fixed: schema $ref; 5 deferred to v1.14)
- Medium: 5 (deferred to v1.14)
- Low: 3 (2 fixed here: external:// docs, mcp_server version; 1 deferred:
  wiki-spec Phase 4 "future" wording — also fixed here)

## [2.13.0] — 2026-05-19 — v1.13 SHM Phase 4 (spec-history lineage view)

**v1.13 SHM complete.** Closes the 4-phase plan from PRD-v1.13. Adds
visualization layer: `wiki-graph --mode spec-history` walks the
supersedes / refines chain from a seed page and renders as ASCII tree,
JSON, or Mermaid graph DSL. Includes cross-wiki via the v1.12
federation channel (kata:// supersedes shown as federated leaves;
reads `.spec-reverse-index.yaml` written by Phase 3).

### Added

- **`graph_query.py --mode spec-history`** — new mode alongside
  neighbors / shortest-path / hubs / orphans / cluster / stats:
  - **Outbound walk**: from seed, follows `spec_relationships:` array
    recursively (depth-limited, cycle-safe via visited set). Each
    edge has `kind` (supersedes / refines / extends / parallel /
    contradicts) + target page metadata (title, tier, published_at).
  - **Inbound walk**: from seed, scans every other page in the wiki
    for `spec_relationships.target` references pointing AT the seed.
    Reports which pages declare relationships pointing at us.
    Stem-fuzzy match (supports `[[wikilink]]`, full path,
    bare stem).
  - **Federation hooks**: `kata://<peer>/<path>` outbound edges
    surface as `{kind, target_uri, federated: true, note}` leaves —
    no recursion into peer (would require federation client
    integration; deferred to v1.13+ polish).
  - **Reverse-index integration**: reads `.spec-reverse-index.yaml`
    (written by Phase 3 `spec_propagate.py` for kata:// supersedes)
    and exposes count in the tree result. Future cross-wiki inbound
    walk would use this — currently a Phase 5+ feature stub.

- **`graph_query.py --format text|json|mermaid`** — new CLI flag for
  spec-history mode output:
  - **text** (default): ASCII tree with `supersedes→` arrow notation
    and indented recursion
  - **json**: nested dict tree (full structure, programmatic
    consumption)
  - **mermaid**: graph LR DSL with `-->|<kind>|` edge labels and
    `EXT_*[(uri)]` federated nodes; embed directly in markdown /
    Obsidian

- **`wiki-graph` MCP tool inputSchema enum extended** to include
  `spec-history` mode + new `format` enum property. Federation
  clients can now request lineage trees from peer katas through MCP
  (caller still synthesizes; server returns structured tree).
  Dispatch in `mcp_server._invoke_wiki_graph()` plumbs through
  `--seed`, `--depth`, `--format`.

### Smoke tests T-graph-1..4 (Tests 47-50)

Builds on the v2.12.0 Phase 3 fixture (F017 supersedes F015, refines
F011, supersedes kata://peer-z/F100). After Phase 3 ran, F015 has
`tier_override: archived` and `spec_superseded_by:` populated, so
the lineage view sees a real propagated state.

- **T-graph-1**: text format. F017 tree root, supersedes/refines/
  federated outbound, ASCII rendered; `supersedes→` arrow + tier
  labels visible.
- **T-graph-2**: json format. Nested tree dict; F015 child's tier
  is `archived` (post-Phase-3 state reflected through to lineage
  view).
- **T-graph-3**: mermaid format. `graph LR` DSL header, `-->|supersedes|`
  / `-->|refines|` edge labels, `EXT_*` nodes for federated
  `kata://peer-z/...` URI.
- **T-graph-4 (bonus)**: inbound walk. Query lineage starting from
  F015 — F017 must appear as `kind: supersedes` inbound source
  (proves the reverse scan works).

### Refactor

- Moved spec-history helpers (`_load_reverse_index`,
  `_build_spec_history_tree`, `_render_spec_history_text`,
  `_render_spec_history_mermaid`) **above** the `if __name__ ==
  "__main__"` block. Python's top-level statement order matters: the
  `if __name__` block ran before bottom-of-file helpers were bound,
  causing `NameError: '_load_reverse_index' is not defined`. Idiom
  fix: helpers go above the entry-point guard.
- Added `import re` (used by mermaid node-id sanitizer).

### Migration

Drop-in. No schema changes. No config changes. To use:

```bash
/kata:wiki-graph --mode spec-history --seed decisions/F017-new.md
# default: ASCII tree to terminal

/kata:wiki-graph --mode spec-history --seed F017-new --format mermaid
# Mermaid DSL for embedding in markdown / Obsidian

# Through federation: a peer kata can be asked for its lineage tree
# via mcp__<peer>__wiki-graph(mode=spec-history, seed=..., format=json)
```

### v1.13 SHM status: COMPLETE

| Phase | Version | Status |
|---|---|---|
| 0 — advisory preflight | v2.2.0 | ✓ |
| 1 — external_sources (removed) | v2.3.0 / v2.5.0 | removed (see ADR) |
| 2 — enforcement gate | v2.4.0 | ✓ |
| 3 — auto-propagation | v2.12.0 | ✓ |
| 4 — lineage view | v2.13.0 | ✓ (this commit) |

Originally planned: 4 phases. Shipped: 3 phases (Phase 1 removed +
ADR documents why). PRD-v1.13 has been the design backbone for ~25%
of the cooldown's net code output.

### Validation

All 50 smoke tests pass (46 prior + 4 new T-graph-1..4 with
sub-assertions). Pre-commit hook clean.

---

## [2.12.0] — 2026-05-19 — v1.13 SHM Phase 3 (auto-propagation)

Closes the supersede-loop. When a newly-ingested spec declares
`kind: supersedes target: ...`, kata auto-applies banner + reverse-link
+ tier flip to the target page (no more manual housekeeping). Closes
v1.6 dogfood Week 1's channel-mismatch finding by giving the dreamer
an explicit "this spec is dead" signal.

### Added

- **`plugin/scripts/spec_propagate.py`** (~400 lines, stdlib only) —
  three propagation actions per `kind: supersedes` target:
  - **Banner**: marker-delimited block (`<!-- kata:spec-banner BEGIN/END -->`)
    prepended after the target's frontmatter. Idempotent via marker
    detection + in-place replace.
  - **Reverse link**: appends `spec_superseded_by: [{path, date, note}]`
    to target's frontmatter. Dedups by `path:` field across re-runs.
  - **Tier flip**: sets `tier_override: archived` + `tier_reason:
    "Superseded by <stem> on <date>"`. **Skipped** if author already
    pinned the page (detected by tier_reason NOT starting with
    "Superseded by") — author's manual tier wins.

- **Federation carve-out**: `kata://<peer>/<path>` targets do NOT
  modify the peer wiki (read-only contract from v1.12). Instead,
  records the supersession in a kata-local
  `{wiki_path}/.spec-reverse-index.yaml`:

  ```yaml
  external_supersessions:
    - external_target: kata://peer-b/decisions/F011.md
      superseded_by: decisions/F017-new.md
      date: 2026-05-19
      note: "F011 absorbed into F017"
  ```

  Dedups by (external_target, superseded_by) pair on re-run.

- **`wiki_dream.py` reject-signal hook**: candidate pool excludes
  pages where:
  - `spec_superseded_by:` frontmatter is a non-empty list, OR
  - `tier_override: archived` AND `tier_reason:` starts with
    `"Superseded by"`

  These pages are dead by explicit declaration, not by inference —
  never resurface them via co-occurrence dreaming regardless of
  score. Closes the **v1.6 Week 1 channel-mismatch finding**
  (project memory `project_dogfood_v1.6` flagged that `--apply` was
  underused; the new reject channel is more targeted than tier
  alone).

- **Schema `spec_authoring.auto_propagation`** block in
  `schema/wiki-schema.json`:
  - `enabled: false` (default, opt-in)
  - `kinds_to_propagate: ["supersedes"]` (default; future could add
    `refines`)
  - `auto_tier_flip: true` (default)
  - `banner_template:` (optional override; default 3-line blockquote)

- **`wiki-spec` SKILL.md** Phase 3 docs section added (replaces the
  "Phase 3 future" stub).

### Smoke tests T-prop-1..5 (Tests 42-46)

- **T-prop-1**: 2-spec fixture (F015 + F017). F017's supersedes F015
  → F015 gets banner + spec_superseded_by entry + tier_override=archived
  with correct tier_reason. Each field asserted individually.
- **T-prop-2**: F017 also has `kind: refines target: F011`. F011
  must NOT be modified (refines not in `kinds_to_propagate`); appears
  in `skipped` list with the explanatory reason.
- **T-prop-3**: F017's `kind: supersedes target: kata://peer-z/...`
  writes to `.spec-reverse-index.yaml`. No file-modification on any
  peer (peer doesn't even exist in fixture). channel=`reverse-index`.
- **T-prop-4**: Re-running propagation on the same F017 produces
  exactly 1 banner marker, 1 `spec_superseded_by` entry, 1
  `tier_override` line, 1 reverse-index entry. Idempotency proven.
- **T-prop-5**: Dreamer fixture with F015 (superseded) + F020 (recent
  active, heavy tag overlap with F015). Without the v2.12.0 hook,
  F015 would resurface as a candidate. After hook: F015 is excluded
  from dream candidates. v1.6 channel-mismatch fix verified
  end-to-end.

### Migration

Drop-in. Wikis without `spec_authoring.auto_propagation.enabled: true`
behave exactly as v2.11.1. To enable:

```yaml
# SCHEMA.md
spec_authoring:
  enabled: true
  enforce_relationship_declaration: true   # Phase 2 (optional)
  auto_propagation:
    enabled: true                          # Phase 3 master toggle
    kinds_to_propagate: [supersedes]
    auto_tier_flip: true
```

Existing supersede declarations from before v2.12.0 won't
retroactively propagate — only newly-ingested specs trigger. To
backfill, the user can manually run
`spec_propagate.py --new-spec <path>` on each prior spec containing
a supersede declaration (idempotent, safe to run multiple times).

### Validation

All 46 smoke tests pass (41 prior + 5 new T-prop-1..5). Pre-commit
hook clean.

---

## [2.11.1] — 2026-05-19 — Codex-review patch — federation client cleanup + doc fixes

Patch from a structural review by Codex GPT-5.5 xhigh (partial run;
shared runtime crashed at synthesis but caught 6 reading-phase
findings — see review log for details). Addresses HIGH + MEDIUM
items; LOW/NIT items deferred.

### Fixed

- **H1 — MCPClient subprocess leak on `connect()` failure**
  (`plugin/scripts/federation_client.py`)

  Pre-v2.11.1: when `connect()` raised post-`Popen()` —
  `TimeoutError`, `RuntimeError` on init failure, `WikiIdMismatchError`
  on identity check — the subprocess outlived the `with MCPClient(...)`
  context manager because `__enter__` never returned, so `__exit__`
  never ran. Every misconfigured peer leaked one orphan `python.exe`.
  Compounded across a flaky-peer dogfood session.

  Fixed by wrapping the post-spawn init block in a try/except that
  calls `self.close()` (which terminates the subprocess gracefully then
  force-kills if needed) and re-raises the original exception.

  Uses `except BaseException` so cleanup also runs on `KeyboardInterrupt`
  / `SystemExit`. Smoke Test 40 (T-fed-6) regression-guards by
  instantiating `MCPClient` with a deliberately wrong `wiki_id`,
  catching the `WikiIdMismatchError`, then asserting `self.proc is None`.

- **M1 — Silent failure on malformed `.federation.yaml`**
  (`plugin/scripts/federation_client.py`)

  Pre-v2.11.1: parse errors caught with bare `except Exception:` and
  returned empty list. Indistinguishable from "no peers configured" —
  the user's trust list silently disappeared with no diagnostic.

  Fixed: parse failures (and read failures, and "peers is not a list"
  schema errors) now emit a `[federation_client] ...` warning to stderr
  explaining the cause. Also includes the most common Windows pitfall
  in the malformed-YAML warning text: `command:` array with unquoted
  drive-colon paths.

  Smoke Test 41 (T-fed-7) regression-guards by using a YAML anchor
  (`&anchor`) — which the kata-stdlib YAML subset explicitly rejects —
  and capturing stderr to verify the warning fires.

- **M3 — Skill SKILL.md overpromised "in parallel"**
  (`plugin/skills/wiki-federate/SKILL.md`)

  Pre-v2.11.1: doc claimed `federate-search` "Runs local search **in
  parallel** with fan-out to each enabled peer." Actual sequence in
  `federate_search()`: local first (blocking sync), THEN
  ThreadPoolExecutor for fan-out. Local search blocks the whole call
  before any peer query begins.

  Fixed wording: "Runs local search, **then** fans out **in parallel**
  to each enabled peer. (Local search blocks before fan-out begins —
  peer queries don't start until local completes. Slow local search =
  delayed peer queries.)"

- **M4 — `command:` field type not validated**
  (`plugin/scripts/federation_client.py`)

  If a user mistakenly writes `command: "py mcp_server.py"` (string,
  no `- ` list marker) instead of `command: ["py", ...]`,
  `list("py mcp_server.py")` produces `['p', 'y', ' ', ...]` and Popen
  fails with `FileNotFoundError: 'p'`. The diagnostic block then
  reports "peer unreachable: 'p'" — cryptic.

  Fixed: `MCPClient.__init__` now validates that every expanded
  command token is a non-empty string; otherwise raises `ValueError`
  with a clear message naming the field, the bad value, and the
  required shape (`- "..."`). `federate_search` / `federate_spec_preflight`
  catch `ValueError` → `peers_unreachable` with the readable reason.

- **L1 — PRD documentation drift: "asyncio" vs threading**
  (`docs/PRD-v1.12-cross-wiki-federation.md` §Risks)

  Pre-v2.11.1: PRD risk section said "parallel fan-out (asyncio)" but
  impl uses `ThreadPoolExecutor`. Fixed to "threading via ThreadPoolExecutor".

### Not in scope (deferred)

Codex findings handled here: H1, M1, M3, M4, L1.
Deferred to follow-up commits when convenient:

- **M2** — Phase 3 federated preflight passes local filesystem path to
  peer. Works for same-machine stdio; breaks future SSE. Fix when SSE
  lands (v2.12+) by reading draft content client-side and passing via
  a new `new_spec_content:` argument.
- **L2-L5, N1-N3** — polish-grade: `except Exception` over-catch,
  reader queue unboundedness, Windows pipe-buffering edge cases, etc.

### Validation

All 41 smoke tests pass (39 prior + 2 new for H1/M1 regressions).
Pre-commit hook clean.

### Migration

Drop-in. Behavior change: malformed `.federation.yaml` now writes to
stderr. If a user had a broken yaml that was silently producing
empty results, they'll now see the warning and can act on it. Not a
breaking change — empty result is the same, the user just gets
notified.

---

## [2.11.0] — 2026-05-19 — v1.12 cross-wiki federation Phase 3 (federated spec preflight + enforcement)

**v1.12 is complete.** The four-phase plan from PRD-v1.12 ships: each
kata is both MCP server (v2.8.0/v2.9.0) and MCP client (v2.10.0), and
spec preflight + Phase 2 enforcement now span federated peers
(v2.11.0). A new spec in kata A can declare `kind: supersedes
target: kata://peer-b/decisions/F100.md`, and A's ingest gate enforces
the declaration against B's actual page over MCP.

### Added

- **`spec_preflight.py --federate` flag** — opt-in per invocation.
  When set:
  1. Local preflight runs as before (kata-internal candidates)
  2. `federation_client.federate_spec_preflight()` fans out in
     parallel to each enabled peer in `.federation.yaml`, calling
     each peer's `wiki-spec-preflight` MCP tool
  3. Peer candidates merge into the same ranked list, annotated with
     `source_wiki` (peer's wiki_id), `source_wiki_name` (peer's
     registry slug), `uri` (`kata://<peer-name>/<path>`)
  4. Same scoring rule, same threshold, same enforcement coverage
     check — federated candidates participate identically
  5. Phase 3 enforcement-rejection report includes the peer
     provenance fields so caller knows whether to chase a missing
     declaration locally or via the federation channel

- **`--federate-peers name1,name2` flag** — restrict fan-out to
  specific peers when needed (default: all enabled peers in
  `.federation.yaml`)

- **`federation_client.federate_spec_preflight()`** helper —
  parallel `ThreadPoolExecutor` fan-out + per-peer timeout + peer
  failures captured in `peers_unreachable` / `peers_timed_out`
  diagnostic. Doesn't run local preflight itself (separation of
  concerns: `spec_preflight.py` does that and retains its
  enforcement-gate logic locally; this helper just gets peer
  candidates).

- **`_candidate_match_keys()` cross-wiki normalization** — federated
  candidates now contribute multiple match keys for the enforcement
  coverage check:
  - Peer-relative path (`decisions/F100-payment-flow.md`)
  - Bare stem (`F100-payment-flow`)
  - `kata://<peer-name>/<path>` URI (name form, PRD D2.2 daily)
  - `kata://<peer-wiki_id>/<path>` URI (long-lived form, PRD D2.2)

  So an author who declares **any** of these forms in
  `spec_relationships: target:` correctly covers the federated
  candidate. Symmetric matching across name/uuid + URI/path
  representations.

- **Phase marker `phase: 3`** in output envelope when `--federate`
  is active. Phase numbers now compose as overlays: federation
  (Phase 3) wins over enforcement (Phase 2) wins over advisory
  (Phase 0). Callers can switch on the largest active phase.

- **`tier_breakdown.federated`** key when federation is active —
  counts of peer candidates separate from local active/archived/
  frozen. Pattern intentionally distinct from the v2.5.0-removed
  `external_sources` (which violated self-closing); federated
  candidates remain attributed to their owning kata wiki, never
  flatten into the local hierarchy.

- **Smoke Test 39 (T-fed-5)** with 3 subassertions:
  - 5a: 2-wiki fixture, federated F100 surfaces with kata:// URI +
    provenance; enforcement rejects without declaration
  - 5b: declaration `target: kata://peer-b/decisions/F100-...`
    matches via URI normalization → accept
  - 5c: wiki_id-form declaration
    (`kata://<uuid>/decisions/F100-...`) also accepts (PRD D2.2
    long-lived citation form)

### Fixed

- **T-sync-21 timing threshold loosened from 10s → 15s** with
  comment. Observed flake during Phase 2/3 dogfood (subprocess churn
  on Windows pushed pre-receive-reject path to ~11.5s; the 7s sleep
  added by retry path keeps the with-retry minimum at ~13s, so the
  15s threshold still cleanly distinguishes "didn't retry" from
  "retried").

### Phase scope (v1.12 complete)

| Phase | Version | Status |
|---|---|---|
| Phase 0 — MCP server scaffold (wiki-search) | v2.8.0 | ✓ |
| Phase 0 dogfood fixes (UTF-8, robustness) | v2.8.1 | ✓ |
| Phase 1 — wiki-graph + wiki-spec-preflight + tier_distribution | v2.9.0 | ✓ |
| Phase 2 — federation client + kata:// URI + .federation.yaml | v2.10.0 | ✓ |
| Phase 3 — federated spec preflight + enforcement | v2.11.0 | ✓ |

What's NOT in v1.12 (intentionally — see PRD §Out of scope):
- SSE transport for cross-machine peers (stdio only; Phase 2+ if demand)
- Connection pooling (fresh subprocess per query is fine for MVP)
- Transitive resolution (A→B→C URIs); permanent out of scope
- Bidirectional dreaming (PRD: trust model too hard to bound)
- TOFU trust prompts (PRD D2.3 explicit-only)
- `wiki-query` SKILL.md federation integration (agent-orchestration;
  separate small commit when next opportunity comes up)

### Validation

All 39 smoke tests pass (38 prior + 1 new T-fed-5 with 3 sub-assertions).
Pre-commit hook clean. No regression in T-sync-21 after threshold
adjustment.

### Migration

Drop-in. Wikis without `.federation.yaml` are unaffected. To enable
cross-wiki preflight:
1. Already have a peer registered (Phase 2)? Add `--federate` to
   ingest's preflight call (or trigger from
   `wiki-spec preflight --federate`)
2. In new specs, declare cross-wiki relationships with
   `target: kata://<peer-name>/<path>` or
   `target: kata://<peer-wiki-id>/<path>`
3. Enforcement gates the new spec against both local + peer
   candidates uniformly

---

## [2.10.0] — 2026-05-19 — v1.12 cross-wiki federation Phase 2 (federation client + kata:// URI)

**The federation loop closes.** Phase 0+1 made each kata an MCP server.
Phase 2 makes a kata an MCP client too: it can spawn peer kata servers
registered in its `.federation.yaml`, fan out queries in parallel, and
merge responses with provenance preserved as `kata://<peer>/<path>`
URIs. v1.12 is now functionally complete (Phase 3 is integration with
v1.13 spec preflight, not new federation primitives).

### Added

- **`plugin/scripts/federation_client.py`** (~600 lines) — stdlib-only:
  - **`MCPClient`** class wrapping a single peer's stdio MCP server.
    Reader thread + `queue.Queue` for timeout-bounded reads on Windows
    (stdlib `select` can't time-bound pipe reads cross-platform). Strict
    JSON-RPC 2.0 wire. Context-manager safe (`with MCPClient(peer) as c`).
  - **`parse_kata_uri()`** / **`KataURI`** dataclass — parses
    `kata://<name-or-uuid>/<path>`. Lenient (returns `valid=False`
    rather than raising) so callers like `wiki-lint` can surface
    unresolvable references rather than crash on them.
  - **`resolve_kata_uri()`** — name-first lookup against registry; UUID
    fallback when the identifier parses as UUIDv4 (PRD D2.2).
  - **`load_federation_config()`** — reads `{wiki_path}/.federation.yaml`
    (PRD D2.1 per-wiki). Lenient: missing file = no federation, malformed
    YAML = empty registry.
  - **`federate_search()`** — runs local `search_naive.py` + parallel
    fan-out (`ThreadPoolExecutor`, max 8 concurrent peers) to enabled
    peers. Per-peer timeout (5s default, PRD D2.4). On peer failure,
    surfaces in `federation.peers_timed_out` / `peers_unreachable` with
    reasons; local results always returned.
  - **Provenance preservation**: federated results gain `source_wiki`
    (peer's wiki_id), `source_wiki_name` (peer's registry name), `uri`
    (`kata://<name>/<path>`). Local results gain `source_wiki: "self"`.
    Merged + sorted by score; capped at `limit`.
  - **`WikiIdMismatchError`** — raised when peer's `serverInfo.kata.wiki_id`
    ≠ registry's `wiki_id` (PRD D1.5 identity check). Refused for the
    session; surfaced in `peers_unreachable` with `reason: "wiki_id mismatch"`.
  - **Three CLI subcommands**: `federate-search`, `list-peers`, `resolve-uri`.

- **`plugin/skills/wiki-federate/SKILL.md`** — author-facing
  documentation:
  - Configuration: `.federation.yaml` schema with all fields explained
  - Subcommand reference + JSON output shape
  - 6-row failure-mode table (none fatal to local query)
  - Safety contract (identity check, read-only, no transitive resolution,
    no remote auth, privacy warning)
  - kata:// URI scheme (name form for daily use, wiki_id form for
    long-lived citations per PRD D2.2)
  - **Windows path quoting note**: stdlib YAML subset treats bare
    colons as mapping separators, so `C:/...` paths MUST be quoted
    in `command:` arrays. Documented as a hard rule in the schema
    example.

- **Smoke tests T-fed-1..4** (Tests 35-38 in `run_smoke.py`):
  - **T-fed-1**: 2-fixture federation end-to-end. Local + peer results
    merge correctly; peer hits gain `source_wiki_name`, `kata://`
    URI, and peer's wiki_id as `source_wiki`. `federation.peers_queried`
    contains the peer name.
  - **T-fed-2**: wiki_id mismatch — registry says X but peer reports Y.
    Peer refused this session, listed in `peers_unreachable` with reason.
    Local results still returned (no fatal error to user query).
  - **T-fed-3**: `kata://` URI parser — name form, wiki_id-UUID form,
    unresolvable URI all behave correctly. `resolved=false` is
    non-fatal.
  - **T-fed-4a**: `--no-federate` flag suppresses fan-out, returns
    local-only with `local_only_fallback: true`.
  - **T-fed-4b**: `list-peers` reports registry contents + yaml location.

### Changed

- Root `SKILL.md` description + plugin manifest: 16 → 17 skills
  (`wiki-federate` joins); v1.12 phase status updated to "Phase 0+1+2
  shipped".
- Test fixture YAML quoting: `command:` array tokens are now quoted in
  the smoke test setup (Windows drive colon would otherwise mis-parse).

### Phase scope (what's in v2.10.0 vs deferred)

| Slice | Status | When |
|---|---|---|
| MCP client (stdio) | ✓ v2.10.0 | now |
| `kata://` URI parser + resolver | ✓ v2.10.0 | now |
| `.federation.yaml` per-wiki registry | ✓ v2.10.0 | now |
| Parallel fan-out + per-peer timeout | ✓ v2.10.0 | now |
| `wiki_id` identity check at connect | ✓ v2.10.0 | now |
| `wiki-federate` skill | ✓ v2.10.0 | now |
| **Phase 3 — federated spec preflight** | Designed in PRD §Phase 3 | v2.11.0 |
| SSE transport (cross-machine) | Deferred | v2.12+ |
| Connection pooling | Deferred | when latency complaints surface |
| Transitive resolution (A→B→C URIs) | Out of scope | PRD §Out of scope |

### Validation

All 38 smoke tests pass (34 prior + 4 new T-fed-1..4). Pre-commit hook
clean. Manual: `federation_client.py list-peers` against a sample
registry works, identity-mismatch path was exercised end-to-end during
test setup.

### Why no `wiki-query` skill integration in v2.10.0

`wiki-query` is the natural caller, but its current implementation is
SKILL-driven (agent reads SKILL.md and orchestrates search +
synthesis). Wiring federation into wiki-query is **agent-orchestration
work** — adding a "if `.federation.yaml` exists, call
`federation_client.py federate-search` instead of `search_naive.py`
directly" step to the wiki-query SKILL.md. That's a v2.10.x or v2.11.0
follow-up (PRD §"Author workflow (where federation actually shows up)")
to keep this commit focused on the script + skill primitives.

### Migration

Drop-in. Existing wikis without `.federation.yaml` behave exactly
like pre-v1.12 (federation_client.py is opt-in). To enable
federation:
1. Identify trusted peer kata wikis (must have a stable `wiki_id` —
   v1.8 sync writes one)
2. Create `{wiki_path}/.federation.yaml` with the peer's name +
   wiki_id + command (stdio command to spawn its mcp_server.py)
3. Validate via `wiki-federate peers` then `wiki-federate search`
4. Quote every command token (Windows colon → YAML mapping mishap)

---

## [2.9.0] — 2026-05-19 — v1.12 cross-wiki federation Phase 1 (MCP tool surface expansion)

**Second batch of MCP tools land.** Kata's MCP server now exposes 3
read-only tools instead of 1, with `tier_distribution` capability
declaration for federation-peer inspection. Phase 2 (federation client
side + `kata://` URI) is the next deliverable.

### Added

- **MCP tool: `wiki-graph`** (`plugin/scripts/mcp_server.py`) —
  subprocess-wraps `graph_query.py`. Exposes 6 read modes:
  - `stats` — total pages / edges / tier distribution
  - `hubs` — top pages by in-degree
  - `orphans` — pages with no links in/out
  - `neighbors` — graph traversal from a seed page, configurable depth
  - `shortest-path` — find path between two pages
  - `cluster` — group pages by tag
  Write-side `--apply`-style operations NOT exposed (no such flags on
  graph_query, but the principle holds for future modes).
- **MCP tool: `wiki-spec-preflight`** — subprocess-wraps
  `spec_preflight.py` in advisory mode only. Returns ranked prior-spec
  candidates for a new draft. Inputs: `new_spec_path` (required),
  `limit`, `include_archived`, `include_frozen`. **`--enforce` /
  `--enforce-threshold` / `--enforce-mode` deliberately NOT exposed**:
  write-blocking semantics don't translate cross-wiki (B can't gate
  A's ingest decisions; A enforces locally combining own + federated
  candidates).
- **`serverInfo.kata.tier_distribution`** — boot-time snapshot of
  active / archived / frozen page counts. Federation client uses this
  for peer capacity inspection ("does this kata have content?", "is
  the active surface saturated?") before sending real queries.
- **Smoke tests T-mcp-5..8** (Tests 31-34 in `run_smoke.py`):
  - T-mcp-5: `wiki-graph` stats + hubs work; invalid mode returns
    `INVALID_PARAMS` (-32602)
  - T-mcp-6: `wiki-spec-preflight` surfaces F100 candidate;
    `enforcement` block correctly absent from output
  - T-mcp-7: `serverInfo.kata.tier_distribution` populated from a
    7-page fixture
  - T-mcp-8: `tools/list` returns all 3 Phase 1 tools

### Changed

- `mcp_server.py` introduces `_run_json_subprocess()` helper +
  `TOOL_INVOKERS` dispatch table — adding a 4th tool is now schema
  definition + invoker function + 1-line registration. No more
  copy-paste of the run-subprocess pattern.
- T-mcp-2 (Phase 0 smoke) loosened from "tools count == 1" to
  "wiki-search is in the tool list"; the strict count assertion moved
  to T-mcp-8 (Phase 1).
- `wiki-mcp-server` SKILL.md phase scope table refreshed; serverInfo
  example includes `tier_distribution`; known-limitations adjusted.

### Why `wiki-query` is NOT in this release (and not planned)

In the federation model, synthesis is **caller-side**. Kata A asks
peer kata B for raw query material (`wiki-search` results,
`wiki-graph` structure, `wiki-spec-preflight` candidates), then A's
agent synthesizes across A's local results + B's responses, with
citations to both via the `kata://` URI scheme (Phase 2). Server-side
synthesis would either:

- (a) Duplicate `wiki-search` (since there's no underlying
  `wiki_query.py` script — wiki-query is currently agent-driven via
  SKILL.md instructions in Claude Code, with no equivalent for a
  cross-process MCP boundary)
- (b) Build a synthesis-server feature that conflicts with the
  "query-only" federation contract — the server is supposed to return
  material, not opinions

Decision recorded in PRD §"Phase 1 — Tool surface expansion" and
re-affirmed by this CHANGELOG entry.

### Validation

All 34 smoke tests pass (30 prior + 4 new MCP tests). Pre-commit hook
clean.

### Migration

Drop-in. Existing MCP clients pointed at a kata server keep working —
the new tools just show up in `tools/list`. Federation clients (Phase
2+) gain the `tier_distribution` field at no cost.

---

## [2.8.1] — 2026-05-18 — Phase 0 dogfood fixes (discover_pages robustness + MCP UTF-8)

Three bugs surfaced by the first live Phase 0 dogfood (Claude Code MCP
client → kata MCP server → real NECallKit + kata-self wikis):

### Fixed

- **A — `discover_pages` aborted on first bad-frontmatter page**
  (`plugin/scripts/wiki_lib.py`). A single page with an unsupported
  YAML scalar style (`key: |` block scalar) crashed the entire scan,
  taking down wiki-search / wiki-query / spec_preflight / MCP server
  end-to-end. Now per-page parse errors are caught, logged to stderr
  as `[discover_pages] skipped <path>: <error>`, and the walk
  continues. One rotten page no longer poisons the whole wiki.
  Regression test: smoke Test 30 builds a fixture with one good +
  one bad page and asserts the good page still surfaces.

- **B — MCP server stdio inherited cp1252 on Windows**
  (`plugin/scripts/mcp_server.py`). When Claude Code spawned the
  server, the inherited locale was cp1252, mangling Chinese / non-ASCII
  content in JSON-RPC responses (wiki titles, excerpts, tag values
  showed as `��`). Server now forces UTF-8 on stdout/stdin via
  `sys.stdout.reconfigure(encoding="utf-8")` AND sets `PYTHONUTF8=1`
  + `PYTHONIOENCODING=utf-8` in its own environment so child
  `search_naive.py` reads `.md` files as UTF-8 too. Belt-and-braces:
  fixes both the JSON-RPC wire (server → client) and the file-read
  layer (child subprocess → markdown content).

- **C — kata self-meta ADR used `|` block scalar in frontmatter**
  (`~/.llm-wiki/kata/decisions/2026-05-17-external-sources-removed.md`).
  The `essay_angle:` field used the YAML `|` literal block-scalar
  style, which `wiki_lib._parse_yaml_block` doesn't support. Quoted
  the value as a single-line string as the immediate fix. Proper
  parser support for `|` block scalars is a separate v1.12+ wiki_lib
  enhancement (out of scope for v2.8.1). The robustness fix in (A)
  means even if a future ADR hits the same issue, the scan won't die
  — the page just gets skipped + logged.

### Why this happened on day-1 dogfood

The MCP smoke tests (T-mcp-1..4 in v2.8.0) used a synthetic fixture
wiki with ASCII-only content + well-formed YAML frontmatter. Both
real wikis (NECallKit with 110 Chinese pages, kata self-meta with
yesterday's ADR) tripped real-world content patterns that the
fixture didn't cover. Classic "smoke green, real users red" gap.
The fix pattern is now baked into Test 30 — future regressions on
malformed frontmatter caught at CI.

### Validation

All 30 smoke tests pass (29 prior + new Test 30). Live re-test
against kata-self now returns 5 ranked results with correct UTF-8
content; live re-test against NECallKit no longer garbles Chinese
titles.

---

## [2.8.0] — 2026-05-18 — v1.12 cross-wiki federation Phase 0 (MCP server scaffold)

**First half of cross-wiki federation lands.** Kata wiki can now
advertise itself as an MCP server over stdio. Any MCP-aware agent
(Claude Code, Cursor, Continue, or another kata acting as a
federation client in Phase 2+) can connect and call exposed
read-only tools.

PRD: `docs/PRD-v1.12-cross-wiki-federation.md` (Draft v2, Q1-Q4 locked).

### Added

- **`plugin/scripts/mcp_server.py`** — JSON-RPC 2.0 over stdio,
  stdlib-only implementation:
  - `initialize` handshake returns `protocolVersion: 2024-11-05` +
    `serverInfo.kata.{wiki_id, wiki_path, domain, categories}` for
    the v1.8-style identity check (federation peers verify
    `wiki_id` matches their registry entry before trusting the peer
    this session)
  - `notifications/initialized` no-op
  - `tools/list` returns the one Phase 0 tool: `wiki-search`
  - `tools/call wiki-search` subprocesses `search_naive.py`,
    returns both `content[0].text` (human-readable JSON dump) AND
    `structuredContent` (the parsed envelope — custom kata
    extension so federation clients don't re-parse)
  - `shutdown` graceful exit
  - Refuses to start without SCHEMA.md (exit 1 + stderr explains
    why — no `wiki_id` = no identity check = unsafe to trust)
  - 30-second per-call timeout on subprocess invocations
- **`plugin/skills/wiki-mcp-server/SKILL.md`** — how to start the
  server, how to register it with Claude Code's `.claude/settings.json`
  `mcpServers:` block, how a federation client (v2.10.0+) will
  spawn it, protocol surface reference, safety contract.
- **Smoke tests T-mcp-1 through T-mcp-4** in `run_smoke.py`:
  - T-mcp-1: server starts, handshake returns protocolVersion +
    serverInfo
  - T-mcp-2: `tools/call wiki-search` returns ranked results with
    both text and structuredContent blocks; write skills NOT
    exposed (negative test on `wiki-ingest`)
  - T-mcp-3: `serverInfo.kata.wiki_id` is surfaced from SCHEMA.md
    for federation identity check
  - T-mcp-4: server refuses to start without SCHEMA.md (exit
    non-zero + stderr explains)

### Phase scope (what ships in v2.8.0 vs later)

| Tool | Status (v2.8.0) | When |
|---|---|---|
| `wiki-search` | ✓ shipped | now |
| `wiki-query` | not exposed | Phase 1 (v2.9.0) |
| `wiki-graph` (read subset) | not exposed | Phase 1 (v2.9.0) |
| `wiki-spec-preflight` | not exposed | Phase 1 (v2.9.0) |
| Federation client side | not built | Phase 2 (v2.10.0) |
| `kata://` URI scheme | not implemented | Phase 2 (v2.10.0) |
| Cross-wiki spec preflight | not integrated | Phase 3 (v2.11.0) |

**Never exposed** (hard boundary, by design): `wiki-ingest`,
`wiki-import`, `wiki-tier --pin`, `wiki-dream --apply`, any other
write skill. The MCP surface is read-only; cross-wiki write goes
through explicit `wiki-import` against the peer's filesystem path.

### Why this design

Five transport candidates evaluated (PRD §"Why MCP and not the
alternatives"); MCP won because **every consumer the user already
runs is an MCP client** — Claude Code, Cursor, Continue, Codex CLI
roadmap. Free interop with all of them; federation between two
katas is then a specialization of "two MCP clients pointed at the
same server."

A2A protocol bridging is deferred (PRD §D1.3 / §"A2A: deferred, not
blocked"). MCP surface is forward-compatible if an A2A wrapper
becomes useful later.

### Migration

None required. The server is a new file, not exposed by default.
To use it from Claude Code, add an entry to your
`.claude/settings.json` `mcpServers:` block (see SKILL.md for the
snippet). Existing kata workflows are unaffected.

### Validation

29 smoke tests pass (25 prior + 4 new MCP tests). Pre-commit hook
clean. Manual: server spawned with `--wiki ~/.llm-wiki/X` responds
to interactive JSON-RPC input.

---

## [2.7.0] — 2026-05-18 — v1.11 session-ingest MVP (Phase 1-5)

**The conversation-born knowledge channel.** Until v2.7.0 kata could
only ingest artifacts (URLs, files, pasted text). The reasoning trail
in a 2-hour debugging session — what was tried, what was rejected, why
the chosen fix won — was never captured unless the user remembered to
write it down. v1.11 closes that gap.

### Added

- **`wiki-session-ingest` skill** (`plugin/skills/wiki-session-ingest/SKILL.md`)
  - One user-facing entry point that works from inside any of six
    target CLIs without extra arguments
  - Five phases: detect CLI → write raw dump → extract knowledge-point
    candidates → multi-select → distill via `wiki-ingest`
  - Multi-select UX via AskUserQuestion (Claude Code native) +
    numbered-prompt fallback for terminal-only CLIs
  - Provenance: every distilled page carries `source_cli`,
    `session_id`, `cwd`, plus `evidence_anchors` pointing back into the
    raw dump via `session-msg-N` ids
  - Integration with `wiki-ingest` via the v2.6.0 hint flags
    (`--page-type`, `--proposed-path`, `--evidence-anchors`) — single
    source of truth for page-write; no duplicate ingest path

- **`plugin/scripts/session_ingest.py`** helper (~600 lines, stdlib-only)
  - **`detect`** subcommand — probes `$CLAUDECODE`, `$CODEX_SESSION_ID`,
    `~/.codex/sessions/{YYYY}/{MM}/{DD}/` rollouts (cwd-match against
    `session_meta.payload.cwd`), `$GEMINI_CLI` / `$COPILOT_CLI` /
    `$OPENCODE` / `$KIMI_CLI` sentinels, falls back to `unknown` +
    LLM-dump mode. Returns JSON with `cli`, `detection_mode`,
    `session_id`, `session_file`.
  - **`dump`** subcommand — parses Claude Code or Codex CLI JSONL into
    readable markdown body (filters decorative events, renders tool
    calls + outputs with head/tail truncation), wraps with frontmatter,
    writes to `{wiki}/raw/sessions/{cli}-{date}-{slug}-{short-id}.md`.
  - **`dump-llm`** subcommand — agent provides body via `--body` or
    stdin; script wraps with frontmatter for Gemini / Copilot /
    OpenCode / Kimi / unknown paths.
  - **`config show|get|set`** subcommands — reads/writes
    `~/.kata/session-ingest.yaml` (the per-machine
    `auto_trigger_on_session_end` flag, default false).
  - **Safety**: 50 MB session-size cap (exit code 2 + hint to narrow
    scope), read-only on `~/.claude/projects/` and
    `~/.codex/sessions/`, dirty-wiki guard documented in SKILL.

- **Decision tree CLI detection** (PRD §CLI detection):
  - Tier 1: `$CLAUDECODE == "1"` → Claude Code, JSONL adapter
  - Tier 2: `$CODEX_SESSION_ID` set OR rollout under
    `~/.codex/sessions/.../*` whose first-line
    `session_meta.payload.cwd` matches cwd → Codex CLI, JSONL adapter
    (cwd normalization handles Windows backslash + case)
  - Tier 3-6: `$GEMINI_CLI` / `$COPILOT_CLI` / `$OPENCODE` /
    `$KIMI_CLI` → LLM-dump mode
  - Tier 7: unknown → LLM-dump fallback; agent renders the body

- **Auto-trigger opt-in** at `~/.kata/session-ingest.yaml`
  (`auto_trigger_on_session_end: false` by default). Documented hook
  wiring for Claude Code's `Stop` hook + Codex equivalent; MVP does
  NOT auto-install (one-command install is a v1.12 polish). Even with
  the flag on, the multi-select step still runs — no silent writes.

- **Tests 23, 24, 25** in `tests/run_smoke.py`:
  - **Test 23**: Claude Code end-to-end — synthetic JSONL fixture with
    user/assistant/tool/decorative events; HOME-overridden detect
    finds the slug-of-cwd project dir; dump parses 4 messages, filters
    `file-history-snapshot`, preserves conclusion text and message
    anchors
  - **Test 24**: Codex CLI cwd-match — synthetic rollout with
    `session_meta.payload.cwd` matching fixture cwd; detect finds it
    via the cwd-match heuristic (CLAUDECODE explicitly unset in env
    overrides to prevent leak from parent Claude Code process); dump
    parses user/assistant/tool events
  - **Test 25**: LLM-dump path — agent-supplied body via `--body`
    wrapped with frontmatter; `~/.kata/session-ingest.yaml`
    show/set/get roundtrip on a tempdir HOME

### Changed

- Root `SKILL.md` frontmatter: "14 skills" → "15 skills (… spec /
  session-ingest)"; description mentions v1.11 MVP shipped + Claude
  Code + Codex adapters + LLM-dump fallback
- Plugin manifest + marketplace.json bumped 2.6.0 → 2.7.0

### Deferred to v1.12

- Sentinel-env detection for Gemini / Copilot / OpenCode / Kimi
  (LLM-dump remains the safe default until each is verified inside the
  respective CLI)
- Auto-wired CLI hooks (one-command install of Stop hook etc.) — MVP
  only documents the wiring per CLI
- Bulk historical session ingest (`--since=2026-05-01`)
- Cross-CLI session merge (two CLIs working on the same task)
- Token-budget-aware AI summarization for >200k-token sessions
- `--scrub-secrets` flag to redact API-key-shaped tokens before the
  raw dump is committed
- Interactive editing of a candidate before distilling (title /
  page_type / proposed_path tweak)

### Migration

None required. The new skill is purely additive; existing
`wiki-ingest` flows are unaffected. To opt in to auto-trigger:

```bash
py -3 plugin/scripts/session_ingest.py config set \
    auto_trigger_on_session_end true
```

Then wire a Claude Code `Stop` hook per the SKILL.md example, or the
Codex CLI equivalent.

---

## [2.6.0] — 2026-05-17 — v1.11 session-ingest Phase 0 (wiki-ingest hint flags)

**Companion change** to unblock v1.11 `wiki-session-ingest` (Phase 1-5
shipping in v2.7.0). Three strictly-additive optional flags on the
`wiki-ingest` skill let an upstream caller hand off structured hints
rather than re-deriving them.

### Added

- **`--page-type=<type>`** — strong default for new-page type
  (`decision` / `feature` / `bug` / `lesson` / `concept` / `prd` /
  `rfc` / `adr` / `task-spec` / etc; must be SCHEMA.md-declared). Agent
  follows the hint unless SCHEMA.md analysis reveals a clear mismatch,
  in which case it overrides and notes the override in the report.
- **`--proposed-path=<wiki-relative>`** — preferred destination path
  for the new page. Treated as a hint, not a command:
  - Free path → used as-is
  - Existing page → standard "create vs update" policy applies
    (default: update with diff preview)
  - SCHEMA.md category conflict → fall back to inference, note override
- **`--evidence-anchors=<comma-separated>`** — opaque tokens preserved
  verbatim in the new page's frontmatter under `evidence_anchors:`.
  Typical: `session-msg-142,session-msg-167` from v1.11
  session-ingest. Field omitted entirely when flag unset.

All three flags are documented in `plugin/skills/wiki-ingest/SKILL.md`
under new sub-step **④b** (between page-write and cross-reference).
Existing `wiki-ingest <url|file|text>` invocation shape is unchanged;
all hints are optional.

### Why

v1.11 `wiki-session-ingest` (Draft v2 locked PRD) needs to invoke
`wiki-ingest` per knowledge-point candidate during its Phase 5 distill
loop, with structured hints so each candidate lands at the right path
under the right type with provenance anchors preserved. Without Phase 0,
`wiki-session-ingest` would have to either re-implement page-write logic
(violating single-source-of-truth) or hand off without structured hints
(losing precision).

### Migration

None required. All three flags are additive; existing wiki-ingest flows
are unaffected.

---

## [2.5.0] — 2026-05-17 — v1.13 SHM Phase 1 removed (external_sources)

**Removes a feature shipped in v2.3.0 the previous day** because the
abstraction broke kata's self-closing principle. v2.4.0 Phase 2
enforcement stays — it's purely kata-internal and unaffected.

### Removed

- `external_sources` array from `schema/wiki-schema.json` + the
  `$defs/external_source` definition
- `_load_external_sources()` / `_enumerate_external_pages()` helpers
  from `plugin/scripts/spec_preflight.py`
- CLI flags `--no-external` and `--include-frozen-external`
- External-candidate scoring loop in `spec_preflight.main()`
- `external://<source>/<path>` URI normalization branch in
  `_candidate_match_keys()` (Phase 2 was kata-internal; URI branch
  was a leftover from Phase 1)
- Output fields `external_sources_scanned`, `external_skipped`,
  `tier_breakdown.external`, and the per-candidate `source` /
  `source_treatment` / `writeable` / `fs_path` fields
- `tests/run_smoke.py` Test 21 (Phase 1 end-to-end fixture)
- `plugin/skills/wiki-spec/SKILL.md` Phase 1 documentation,
  external-source configuration table, and Phase 1 output sample

### Why

Three reasons compounding:

1. **`wiki-import` already covers human-curated bulk ingest**. A team
   with a legacy SDD spec corpus can run
   `wiki-import <corpus> --priority=recency --per-file-prompt` and get
   exactly the curated import external_sources was trying to avoid. The
   "avoid bulk-import" framing was solving a non-problem.
2. **Authority + self-closing violation**. `external_sources` reached
   outside `{wiki_path}/` to enumerate, score, and surface third-party
   markdown files. That breaks the kata invariant that the wiki is a
   compiled artifact under one root. To make it work we'd have had to
   invent an entire lifecycle (transit → graduation → blocklist → TTL)
   — and the fact that we needed to invent a lifecycle to make the
   abstraction behave is itself a sign the abstraction was wrong.
3. **Federation is the right architecture for cross-source**. Two
   self-closing kata wikis cooperating at the `wiki-query` ↔
   `wiki-query` layer (planned for v1.12) preserves both sides'
   authority. Reaching into raw markdown dirs does not.

Empirical motivation: a NECallKit test (363 historical specs/docs)
returned `page_count: 0` for both external sources, because 95%+ of the
legacy corpus had no YAML frontmatter — and a path-pattern type
inference patch to fix it would have been a sunk-cost workaround for an
abstraction that needed removal, not extension. Full architectural
reasoning in
`~/.llm-wiki/kata/decisions/2026-05-17-external-sources-removed.md`
(kata self-meta wiki ADR, also intended as essay seed material).

### Migration

- Wikis that adopted `external_sources` in v2.3.0 (window: 2026-05-16 →
  2026-05-17, very few users): remove the `external_sources:` block
  from `.wiki-plugins.yaml`. If the historical corpus is still needed,
  run `wiki-import <corpus_path>` instead — it produces real kata pages
  with proper frontmatter, full graph participation, and tier lifecycle.
- v2.4.0 Phase 2 enforcement (`--enforce`, `enforce_relationship_declaration`,
  threshold + mode CLI) is unchanged.
- v2.2.0 Phase 0 advisory preflight is unchanged.

### Validation

All 21 smoke tests pass after Test 21 removal (the deleted test was the
only one that exercised external_sources). Pre-commit hook clean.

---

## [2.4.0] — 2026-05-16 — v1.13 SHM Phase 2: relationship declaration enforcement

**Closes the loop** the v1.13 problem statement called out: until Phase 2,
preflight surfaced related prior specs but the author was free to ignore
them. With Phase 2, a wiki opting in via SCHEMA.md gets an ingest-time
gate that rejects new specs whose `spec_relationships:` block does not
address every above-threshold preflight candidate. This is the
spec-drift fix that motivated v1.13.

### New

- **`spec_preflight.py --enforce` flag** — parses the new spec's
  `spec_relationships:` block from frontmatter, compares declared
  targets against the full (unbounded by `--limit`) ranked candidate
  list, and rejects on uncovered above-threshold candidates.
- **`--enforce-threshold <float>`** — per-invocation override of the
  schema's `enforcement_score_threshold`. Useful for tighter or looser
  one-shot runs without editing SCHEMA.md.
- **`--enforce-mode strict|confirm`** — per-invocation override of the
  schema's `enforcement_mode`. strict → exit code 2 on uncovered;
  confirm → exit code 1 so the caller can prompt the user before
  rejecting.
- **Target normalization** — declared targets accept any of:
  - Wiki-relative path: `decisions/F100-foo.md`
  - Path without `.md`: `decisions/F100-foo`
  - Bare stem: `F100-foo`
  - Wikilink form: `[[F100-foo]]` or `[[F100-foo|display alias]]`
  - External URI: `external://sdd-specs/F011-bar.md`
  Match is case-insensitive on both full key and bare stem.
- **`enforcement` block in JSON output** — when enforcement is active:
  - `enabled`, `mode`, `threshold`
  - `declared_relationships` (kind, target, note for each)
  - `declared_count`, `above_threshold_count`, `covered_count`,
    `uncovered_count`
  - `uncovered`: array of {path, title, type, tier, score} for each
    above-threshold candidate not covered by declarations
  - `decision`: `accept` or `reject`
- **Schema additions** in `spec_authoring`:
  - `enforcement_score_threshold: 5.0` (default; tune per-wiki)
  - `enforcement_mode: strict` (default; `confirm` opt-in)
  - existing `enforce_relationship_declaration: false` remains the
    master toggle
- **`wiki-ingest` SKILL** — step ②b documents the Phase 2 gate: when
  `enforce_relationship_declaration: true`, re-run preflight with
  `--enforce` after the author has had a chance to add declarations;
  abort ingest on exit code 2 / 1 with the structured `enforcement`
  report.

### Changed

- **`wiki-spec` SKILL** — Phase scope updated (Phase 0+1+2 → scan +
  advisory + enforcement); CLI examples include the new flags; the
  Known-limitations section now flags Phase 3+ (auto-propagation,
  lineage view) as the remaining work
- **Root `SKILL.md` frontmatter** — description: "Phase 0+1" → "Phase
  0+1+2 — wiki + external-source backfill + relationship-declaration
  enforcement on ingest"
- **`run_smoke.py` `run()` helper** — `allowed_exit_codes` parameter
  added (defaults to `{0, 1}`, backwards compatible). Test 22 passes
  `{0, 2}` to allow the strict-mode rejection path.

### Validation

`tests/run_smoke.py` Test 22 covers all five enforcement paths:
- Run 1: schema enables enforcement, no declarations → exit 2, decision
  `reject`, F100 surfaces in `uncovered`
- Run 2: add `spec_relationships: [{kind: supersedes, target:
  decisions/F100-payment-flow.md}]` → exit 0, decision `accept`,
  `covered_count: 1`, `uncovered_count: 0`
- Run 3: schema is strict, `--enforce-mode confirm` overrides → exit 1
  on reject (caller-prompts path)
- Run 4: `--enforce-threshold 999.0` raises bar above any candidate
  score → `above_threshold_count: 0`, decision `accept`
- Run 5: declaration uses `[[wikilink]]` form (stem only) → normalization
  matches it to the full-path candidate, decision `accept`

All 22 smoke tests pass on Windows + Linux + macOS.

### Migration

- Existing wikis with `spec_authoring.enabled: false` (default for new
  wikis): nothing changes.
- Existing wikis with Phase 0+1 enabled but no enforcement set: nothing
  changes. `spec_preflight` continues to run in advisory mode.
- To opt in: add to SCHEMA.md `spec_authoring:` block:
  ```yaml
  enforce_relationship_declaration: true
  enforcement_score_threshold: 5.0     # adjust after observing
  enforcement_mode: strict             # or confirm for caller-prompts
  ```
  Then run a manual preflight on a few existing specs to calibrate
  the threshold before turning the gate on for live ingest.

---

## [2.3.0] — 2026-05-16 — v1.13 SHM Phase 1: external source backfill

**Extends Phase 0** (v2.2.0) so a kata adoption in the middle of an
existing SDD-style project can scan a pre-existing spec corpus without
bulk-importing every old spec. The historical corpus stays on disk
where it is; kata enumerates it for preflight only.

### New

- **`.wiki-plugins.yaml` `external_sources:` array** — separate from
  v1.10's `external_plugins:` (which executes CLI tools for query
  fallback). Each `external_sources` entry has:
  - `name`: identifier for the URI scheme (`external://<name>/<path>`)
  - `type`: `directory` (Phase 1 only; future phases may add git-remote)
  - `root`: absolute or `~`-prefixed path to the directory
  - `treatment`: `active | raw | frozen` (default `raw`)
  - `description`: optional human-readable label
  - `discover.type_field`: frontmatter key holding the type (default
    `type`; override for corpora using `category` or `doc_type`)
  - `discover.exclude`: substring patterns to skip (e.g. `drafts/`)
- **Treatment semantics**:
  - `active` — participates in default wiki-search + spec preflight
  - `raw` — excluded from default search, included in spec preflight
    (the right choice for most historical-corpus adoptions)
  - `frozen` — excluded everywhere unless `--include-frozen-external`
- **URI scheme `external://<source>/<path>`** for cross-source
  references in `spec_relationships:` targets. Phase 3 auto-propagation
  will skip these (kata cannot edit external pages); Phase 3 will
  instead write a kata-internal reverse-index file.
- **`plugin/scripts/spec_preflight.py`** extended with:
  - `_load_external_sources(wiki_root)` — reads
    `.wiki-plugins.yaml`'s `external_sources` block
  - `_enumerate_external_pages(source, spec_types_set)` — walks the
    source's `root` directory, filters by frontmatter type, returns
    page records (path, uri, title, type, tags, body, source, treatment)
  - External-candidate scoring loop in `main()` (uses the same
    heuristics as kata-side: title overlap, tag overlap, wikilink
    reference, type match; sets `hub_score=0` and adds `-0.5`
    authority penalty for external)
- **CLI flags**: `--no-external` (skip external entirely),
  `--include-frozen-external` (also scan frozen-treatment sources).
- **JSON output additions**:
  - `external_sources_scanned`: per-source diagnostic
    (name, treatment, page_count, scored_count, elapsed_ms)
  - `external_skipped`: sources excluded by treatment filter
  - `tier_breakdown.external`: count of external candidates
  - `candidates[].source` / `source_treatment` / `writeable: false` /
    `fs_path` on external candidates only

### Changed

- `wiki-spec` skill argument-hint extended with `--no-external` +
  `--include-frozen-external`
- `wiki-spec` SKILL.md Phase scope updated (Phase 0+1 → advisory;
  Phase 2 → enforcement; Phase 3 → auto-propagation)
- Root `SKILL.md` frontmatter description: "Phase 0" → "Phase 0+1 —
  wiki + external-source backfill via .wiki-plugins.yaml"
- `schema/wiki-schema.json`: new top-level array `external_sources`
  + new `$defs/external_source` definition

### Validation

`tests/run_smoke.py` Test 21 validates Phase 1 end-to-end:
- Builds fixture with 1 kata-managed spec + 2 external specs (and 1
  non-spec README that should be filtered out)
- Configures `.wiki-plugins.yaml` with `external_sources` entry,
  `treatment: raw`
- Runs preflight against a new draft that link-references the F011
  external spec and shares tags with both
- Asserts: phase=1, `external_sources_scanned` populated correctly,
  F011 surfaces as external candidate with `writeable: false`, URI
  scheme `external://sdd-specs/...`, signals correct
- Asserts: `--no-external` suppresses external enumeration entirely

### Migration

`external_sources` is additive. Existing `external_plugins` (v1.10
query-fallback CLI tools) continue to work unchanged — they're a
different array. Wikis without `external_sources` block behave
exactly as v2.2.0.

To enable Phase 1 backfill of a historical corpus:

```yaml
# In wiki's .wiki-plugins.yaml
external_sources:
  - name: legacy-specs
    type: directory
    root: ~/work/myproject/docs/specs
    treatment: raw
```

Then `wiki-spec preflight --new-spec <draft>` will surface candidates
from both the kata wiki AND the legacy directory.

## [2.2.0] — 2026-05-16 — v1.13 SHM (Spec History Management) Phase 0

**New optional skill: `wiki-spec`**. First phase of a multi-phase feature
that closes the spec-drift gap in SDD / superpowers-style workflows.
Phase 0 ships an advisory-only preflight scan; Phase 1+ extends to
external sources, enforces relationship declaration, and auto-propagates
supersession across the wiki. Off by default; opt-in per wiki via
`spec_authoring.enabled: true` in SCHEMA.md.

### Motivation

LLM-driven SDD / superpowers flows generate many specs over time. Each new
spec is authored fresh, often by a different session/agent, with no
mechanism that makes the new spec "answer for" the older specs whose scope
it overlaps. Result: spec corpora drift from "coherent decision record"
into "pile of disconnected pages". Kata's wedge has always been project
memory; spec history is a structured subset of that problem that needs
its own primitives.

### New

- **`plugin/scripts/spec_preflight.py`** — given a draft spec file (need
  not be in the wiki yet), scan wiki pages whose frontmatter `type` is in
  `spec_authoring.spec_types`, rank by relevance signals (title overlap,
  tag overlap, wikilink reference, hub score, type match), emit JSON.
  Default `spec_types` covers SDD-style (`prd`, `design`, `rfc`, `adr`,
  `task-spec`) and kata-native (`decisions`).
- **`plugin/skills/wiki-spec/SKILL.md`** — new skill exposing the
  `preflight` subcommand. Phase 0 surfaces candidates; the author / agent
  reads them and decides whether to declare relationships in the new
  spec's frontmatter. No enforcement yet.
- **`schema/wiki-schema.json`** — adds `spec_authoring` config block:
  `enabled`, `spec_types`, `preflight` (auto/manual/off),
  `relationship_kinds`, `enforce_relationship_declaration` (Phase 2
  toggle, off in Phase 0).
- **Convention** for per-spec frontmatter (Phase 0 manual, Phase 2
  enforced): `spec_relationships: [{kind, target, note}]` with kinds
  `supersedes | refines | extends | parallel | contradicts | references | custom`.

### Roadmap (subsequent phases, not in this release)

| Phase | Adds |
|---|---|
| 1 | Preflight reaches external sources via `.wiki-plugins.yaml` `treatment: raw\|frozen\|active` (supersedes v1.10 PRD) |
| 2 | Required `spec_relationships:` declaration; ingest rejects on missing |
| 3 | Auto-propagation: superseded specs get banner + tier flip + reverse-link; integrates with v1.6 dreamer reject-signal channel |
| 4 | `wiki-graph --spec-history <topic>` coherence view |

Forthcoming: `docs/PRD-v1.13-spec-history-management.md` (Day 3 of the
2026-05-16 cooldown roadmap will draft it formally; this CHANGELOG entry
is the minimum-viable design contract for now).

### Changed

- **Skill count**: 13 → 14 (Test 18 assert updated implicitly via `>= 13`).
- **Plugin manifest version**: 2.1.0 → 2.2.0 in both
  `.claude-plugin/marketplace.json` and `plugin/.claude-plugin/plugin.json`.

### Migration

No migration required. `spec_authoring` is opt-in:

```yaml
# In SCHEMA.md of any wiki that wants the feature:
spec_authoring:
  enabled: true
  spec_types: [decisions]   # narrow to your wiki's conventions
```

Wikis without this block continue to behave exactly as in v2.1.0.

### Validation

`tests/run_smoke.py` Test 20 validates Phase 0 end-to-end: builds a
fixture wiki with 2 prior decisions + 1 new draft spec, runs preflight,
verifies the link-referenced same-tagged candidate ranks first with the
correct signals (link_reference + type_match + tag_overlap ≥3) and that
advisory text is present.

## [2.1.0] — 2026-05-14 — wiki-search tier-aware ranking + coverage signal

**Backward-compatible additions** to `wiki-search`. No skill API changes,
no manifest changes. Pin behavior (`tier_override: active` in page
frontmatter) now actually surfaces pinned pages in top-N results.

### New

- **`tier_breakdown` field** in `search_naive.py` JSON envelope — aggregate
  tier distribution `{active, archived, frozen}` over the full unfiltered
  match set. Lets callers see coverage shape at a glance without scanning
  every result. Useful when a query has high archived hits but low active
  hits, signaling stale or mis-categorized content.
- **`low_active_coverage` hint** in `search_naive.py` JSON envelope — boolean,
  true when active hits < 20% of total matches and total matches ≥ 3. The
  threshold filters out tiny match sets to avoid false alarms.
- **`wiki-search` SKILL.md** documents how to use both new fields in
  summary lines and follow-up suggestions.

### Changed

- **Rank order** in `search_naive.py:rank_key` — `tier` is now a tiebreaker
  after `tag_match`, before `hub`. Active > archived > frozen. User-pinned
  pages bubble up above implicit hub centrality. Strong title/tag match
  still wins. Net effect on prior queries against a real wiki: pinned
  architecture pages went from absent in top-10 to top-1 / top-9 / top-10
  positions for the same query.
- **`_excerpt()`** in `search_naive.py` — strips H1/H2 heading lines
  before term-finding so excerpts contain body content instead of
  `"# Title  ## Section Header …"` noise. Falls back to original
  behavior if the query term appears only in headings.

### Motivation

Real dogfood session on 2026-05-14: an agent ran three wiki-search
queries and got 28/30 archived results. The agent correctly self-reported
the surface signal but had to scan all results to detect the pattern.
Investigating the cause revealed two design errors:

1. Tier semantics designed for research wikis (where archived = stale)
   mis-fired for architecture wikis (where archived = stable but
   unmaintained). Fix: per-page `tier_override:` was already supported
   in v1.6, but `tier_breakdown` + `low_active_coverage` make the
   mis-fire visible to callers.
2. `rank_key` did not consider tier as a ranking signal, so pinning a
   page kept it in the active pool but did not surface it in top-N.
   Fix: tier tiebreaker.

Full evidence chain in `docs/dogfood-necallkit-hn-essay.md` →
"2026-05-14 — wiki-search natural experiment". Pre-PRD design idea
spawned by the same session: `docs/idea-coverage-matrix-dreamer.md`.

### Migration

None required. All changes are additive or behavior fixes to
under-specified ordering. Existing wiki-search callers ignoring the new
fields work unchanged.

If you have pages whose architectural facts are stable but date-aged
into `archived` tier, pin them with frontmatter:

```yaml
tier_override: active
tier_reason: stable architecture fact, not subject to time decay
```

Next session's wiki-search will surface them in top results.

## [2.0.0] — 2026-05-13 — Rebrand to **Kata**

**⚠ BREAKING CHANGE for slash commands.** All commands previously invoked
as `/ak-wiki:wiki-*` are now `/kata:wiki-*`. Update your muscle memory and
any scripts. The 13 skill names themselves (wiki-init, wiki-ingest, etc.)
are unchanged — only the plugin prefix moved.

### Why rebrand

The previous name framed the project as "an implementation of Karpathy's
LLM-Wiki idea." Reality is the opposite: llm-wiki is one substrate, and
the product is a **workflow + project memory layer for AI-paired
engineering** that compiles business semantics, manages spec authoring +
disagreement, and lets each builder adapt the workflow to their own
project. The new name captures the **accept-adapt-transcend mastery
curve** at the heart of the product.

### Breaking changes

| Identifier | Old | New |
|---|---|---|
| Brand | AK LLM Wiki / ak-wiki | **Kata** |
| Plugin name | `ak-wiki` | `kata` |
| Slash command prefix | `/ak-wiki:*` | `/kata:*` |
| Marketplace name | `ak-llm-wiki` | `kata` |
| Env var | `AK_WIKI_HOME` | `KATA_HOME` |
| Project binding file (secondary, low-use) | `.ak-wiki.yaml` | `.kata.yaml` (`.llm-wiki.yaml` still primary) |
| Per-machine state dir | `~/.ak-wiki/` (sync-reports etc.) | `~/.kata/` |
| Stash tag pattern | `.ak-wiki-stash-tag` | `.kata-stash-tag` |
| Public repo URL | `surebeli/AK-llm-wiki` | `surebeli/kata` |

### Migration

For existing users (if any):

1. **Slash commands:** retrain. `/ak-wiki:wiki-init` → `/kata:wiki-init`.
2. **Env var:** rename `AK_WIKI_HOME` → `KATA_HOME` in shell profile.
3. **Per-machine state directory:** optional rename — if you depend on
   sync reports or stash tags, `mv ~/.ak-wiki ~/.kata`. Otherwise let the
   new state dir build fresh.
4. **Project binding files:** if you placed `.ak-wiki.yaml` in any
   project repo root, rename to `.kata.yaml` (or rely on `.llm-wiki.yaml`
   which is still the primary form).
5. **Repo URL:** GitHub redirects old URL `surebeli/AK-llm-wiki` to
   `surebeli/kata` for ~30 days. Update remotes:
   ```bash
   git remote set-url origin https://github.com/surebeli/kata.git
   ```
6. **Self-meta wiki on disk:** `~/.llm-wiki/ak-wiki/` is **not**
   auto-renamed. User decides whether to rename to `~/.llm-wiki/kata/`
   (no auto-migration of `wiki_id` in `SCHEMA.md` either way).

### What did NOT change

- 13 skill names (`wiki-init`, `wiki-ingest`, etc.) — they operate on the
  wiki artifact; the wiki is what Kata produces, so the noun stays.
- All algorithms / scripts / behavior.
- Wiki filesystem layout (`raw/`, `SCHEMA.md`, `index.md`, `log.md`).
- The `.llm-wiki.yaml` primary binding file (only the secondary
  `.ak-wiki.yaml` alias was renamed).

### Positioning shift in README + manifests

- README opening flipped from "A plugin... based on Karpathy" to "A
  workflow + project memory layer for AI-paired engineering." The
  Karpathy lineage table is preserved further down as `## Design
  lineage` — credit is intact; framing is product-first.
- `plugin.json` + `marketplace.json` descriptions rewritten with
  workflow framing. Keywords dropped `karpathy`, `rag-alternative`;
  added `workflow`, `ai-paired-engineering`, `builder`, `kata`,
  `project-memory`, `multi-llm`, `spec-management`.
- Essay style guide bumped to v1.2; new §2 Builder ethos sub-section
  formalizes the accept-adapt-transcend stance for all future essays.

## [Unreleased]

### Documentation

- Clarify that `.llm-wiki.yaml` is a **single-path cache** — one wiki per
  file, not a list. Document the recommended multi-wiki coexistence
  patterns (per-project bindings, global `registry.yaml`, hybrid with
  nested innermost-wins override) in README → "Multiple wikis on one
  machine"; cross-referenced from `plugin/CLAUDE.md`, `plugin/AGENTS.md`,
  `SKILL.md`, `plugin/skills/wiki-init/SKILL.md`, and the NECallKit
  multi-machine onboarding handbook.
- Recommend adding `.llm-wiki.yaml` to project `.gitignore` when the
  project repo is git-managed — the binding is per-machine local state
  (paths differ across OS and developers); shared mappings should live
  in `~/.llm-wiki/registry.yaml` outside the repo.

## [1.7.2] — 2026-05-07

Multi-project global-install patch. ak-wiki can now be installed once and
used from arbitrary engineering repositories while resolving each project
to its own independent wiki under `~/.llm-wiki/{project}`. If no project
is specified or detected, skills fall back to `~/.llm-wiki/common`.

### Added — multi-project resolver

- `wiki_lib.find_wiki_root()` now resolves in this order: explicit
  `--wiki` / `--path`, `WIKI_PATH`, current wiki root, `LLM_WIKI_PROJECT`
  under `LLM_WIKI_HOME`, project-local `.llm-wiki.yaml` / `.ak-wiki.yaml`,
  `~/.llm-wiki/registry.yaml`, git root name as `~/.llm-wiki/{repo}`,
  legacy `~/.ak-wiki/config.yaml`, then `~/.llm-wiki/common`.
- Project binding files can use either:
  `project: necall` or `wiki_path: ~/.llm-wiki/necall`.
- `LLM_WIKI_HOME` customizes the base directory; default remains
  `~/.llm-wiki`.

### Changed — init layout

- `wiki_init.py` now creates `raw/external/` and `raw/imported/` by
  default, matching the external fallback and bulk-import workflows.
- `wiki_init.py --path` is optional; when omitted it initializes the wiki
  selected by the resolver, so running it inside a git repo creates
  `~/.llm-wiki/{repo}` by default.
- Template initialization copies `templates/<name>/index.md` when present,
  instead of always rendering the generic index.

### Documentation

- README documents the `~/.llm-wiki/{project}` layout, `.llm-wiki.yaml`,
  environment variables, and full path resolution order.
- Claude/Codex operational docs and the standalone `SKILL.md` now describe
  the same resolver and raw directory layout.

### Tests

- Smoke tests cover project binding resolution, `LLM_WIKI_PROJECT`, and
  fallback to `~/.llm-wiki/common`.

## [1.7.1] — 2026-04-26

Polish patch shipped during the v1.6 dogfood window. No new product
features — closes the gap where four skills (lint, digest, search,
init) were still pure-prompt despite earlier roadmap intent. Each now
has a deterministic script backing the mechanical part; the LLM-only
parts (judgment, narrative synthesis, schema evolution) remain in the
skill prompt.

### Added — scripts that were promised but missing

- `plugin/scripts/lint_naive.py` — structural lint: broken wikilinks,
  index gaps, true orphans, missing required frontmatter, tag drift
  (vs SCHEMA.md taxonomy), stale pages by `updated`, page-size cap,
  tier override sanity, custom-dimension completeness. Returns JSON
  grouped by check + severity. **Content gaps and SCHEMA.md evolution
  remain LLM tasks** in the wiki-lint skill prompt.
- `plugin/scripts/digest.py` — activity counts from log.md, inventory
  by type/tag, tier distribution, recently updated list, top hubs by
  inbound link count, stale custom-dimension values. **Theme
  clustering and coverage gaps remain LLM tasks** in the wiki-digest
  skill prompt.
- `plugin/scripts/wiki_init.py` — actually implements `--non-interactive`
  (prior versions only documented it). Writes SCHEMA.md / index.md /
  log.md / category dirs / raw layout from CLI flags or a domain
  template (`--template market_research`). Auto-validates the resulting
  SCHEMA.md against schema/wiki-schema.json before exit.

### Changed — skills wired to existing scripts

- `wiki-search` SKILL.md gained an `## Implementation` block pointing
  at `plugin/scripts/search_naive.py` (the script existed in v1.5 but
  the skill never referenced it).
- `wiki-lint` SKILL.md gained an `## Implementation` block routing
  structural checks through `lint_naive.py` while keeping content gaps
  and schema-evolution proposals as LLM tasks.
- `wiki-digest` SKILL.md gained an `## Implementation` block routing
  inventory/activity through `digest.py` while keeping theme
  clustering as an LLM task.
- `wiki-init` SKILL.md non-interactive section now shells out to
  `wiki_init.py` instead of describing the flow in prose only.

### Added — git pre-commit hook

- `.githooks/pre-commit` runs `tests/run_smoke.py` and
  `scripts/build_skill_md.py --check` on every commit that touches
  scripts/skills/schema/tests. Opt-in via
  `git config --local core.hooksPath .githooks`. README has the
  enable command in a new "Contributing" section.

### Tests

- Smoke test grew from 26 to 29 assertions: lint findings (Test 14),
  digest output shape (Test 15), wiki_init bootstrap + schema_validate
  pipe (Test 16).

### Internal

- 12 skills total still; `templates/market_research/` reachable via
  `wiki_init.py --template market_research`.

## [1.7.0] — 2026-04-25

The watcher release. Closes the gap where files dropped in `raw/` would
sit unprocessed because the user forgot to invoke `/wiki-ingest`. Built
in parallel with the v1.6 dogfood window — the watcher is code-isolated
from the dreamer (no shared state), so the two features ship without
blocking each other.

### Added — raw watcher daemon

- `plugin/scripts/wiki_watch.py` — polling daemon for `raw/articles/`,
  `raw/papers/`, `raw/transcripts/`, `raw/external/`. Stdlib only (no
  inotify/watchdog). 5-second poll, 5-second debounce against in-progress
  writes. Queue persisted to `.wiki-ingest-queue.json` with statuses
  `pending` / `processed` / `failed` / `removed`.
- `plugin/skills/wiki-watch/SKILL.md` — user-invokable skill. Modes:
  `--start`, `--stop`, `--status`, `--drain`, `--remove`. **Drain is
  always explicit** — the script never invokes `wiki-ingest` itself; the
  skill loops pending entries through `wiki-ingest` and marks each.
- Cross-platform daemonization: `subprocess.DETACHED_PROCESS` on
  Windows, `start_new_session=True` on POSIX.
- `docs/watcher.md` — full design + systemd/launchd/Task Scheduler
  recipes for headless deployment.

### Added — tests

- Smoke test grew from 22 to 26 assertions (Test 13: detection,
  debounce, min-size skip, queue remove, status without daemon).

### Documentation

- README adds an "Auto-ingest from raw/" section between "Quick start"
  and "Auto-dreaming".
- `docs/PRD-v1.7-watcher.md` and `docs/TRD-v1.7-watcher.md` document
  product + technical design.
- `docs/TASKS.md` extended with v1.7 phase and the parallelism note.

### Internal

- 12 skills total now (was 11 in v1.6).

## [1.6.0] — 2026-04-25

The auto-dreaming release. v1.6 ships the first feature that runs without
the user — a weekly job that re-evaluates frozen and archived pages
against recent activity and surfaces those whose relevance has resurfaced.
Strategy is benchmarked end-to-end with a CI precision/recall gate.

### Added — auto-dreaming

- `plugin/scripts/wiki_dream.py` — co-occurrence dreamer. Reads
  `log.md` + page mtime since the last watermark; scores frozen/archived
  pages on entity overlap, tag resurgence, and direct citation; emits
  candidates to `dreaming/{YYYY-MM-DD}.md` for review. **Filesystem-only
  by design** — never reads chat sessions.
- `plugin/skills/wiki-dream/SKILL.md` — user-invokable skill.
- `templates/market_research/SCHEMA.md` — domain template carrying the
  starter `dreaming:` block, custom dimensions (`launch_date`,
  `company_status`, `maturity`, `venue`), and the AI-market tag taxonomy.
- `tests/dreaming_fixtures/market_research/` — synthetic 92-page
  fixture with 8 planted recent ingests (Databricks-Mosaic acquisition,
  DeepSeek-V3 paper reviving MoE, multimodal tag resurgence) and
  hand-curated `expected.json` ground truth.
- `tests/run_dreaming_eval.py` — benchmark runner. `--gate` flag
  enforces `precision >= 0.7` and `recall >= 0.5` per PRD §4.

### Added — unified config interface

- `plugin/scripts/config_io.py` — surgical line-level edits to
  `SCHEMA.md` blocks. Validates after every write and reverts on
  failure. Logs each change to `log.md`.
- `plugin/skills/wiki-config/SKILL.md` — `--show / --get / --set /
  --explain / --validate`. Domain skills (`wiki-tier`, `wiki-init`)
  retain their UX shortcuts; `wiki-config` is the generic path-based
  alternative.

### Added — schema additions

- `schema/wiki-schema.json` gained the `dreaming:` block:
  `enabled`, `strategy`, `cadence`, `confidence_threshold`,
  `max_repromote_per_run`, `weights.{entity,tag,citation}`,
  `resurgence.{dormancy_window_days,min_count}`. Cross-field rules
  (already in v1.5) enforce ranges.
- `schema_validate.py` now handles `const` (needed for `if/then` blocks
  validating per-item conditional requirements like
  `custom_dimensions[*].type == "enum" → enum_values required`).

### Added — CI

- `.github/workflows/test.yml` runs `tests/run_dreaming_eval.py
  --fixture market_research --gate` after the smoke tests, blocking
  any PR that drops the dreamer's precision below 0.7 or recall below
  0.5 on the fixture.

### Tests

- Smoke test grew from 15 to 22 assertions covering wiki-config
  (show/get/set/revert/explain/log) and the dreaming gate.

### Documentation

- `docs/dreaming.md` — design depth, configuration, security model,
  reject-signal policy, why-not-embeddings.
- README adds an "Auto-dreaming" section between "Memory tiers" and
  "External fallback plugins".

### Internal

- `wiki_lib.py` gained: log parser, watermark IO, increment extraction,
  resurgence detection — pure stdlib, used by both the dreamer and
  any future strategy.

## [1.5.0] — 2026-04-25

Foundation release. No new features; closes the v1.4 gap between "scripts
exist" and "skills actually call them," adds CI, and prepares the schema
validator and search/image scripts for v1.6 (auto-dreaming).

### Changed — skills now invoke scripts

- `wiki-graph`, `wiki-tier`, `wiki-import` SKILL.md files gained an
  `## Implementation` block with the exact `Bash:` invocations of their
  matching script in `plugin/scripts/`. Skill prose still describes the
  algorithm for context, but the script is now declared as the source of
  truth — agents shell out instead of model-computing graph BFS or tier
  thresholds.

### Added — new scripts

- `plugin/scripts/ingest_images.py` — extracts `![](url)` references,
  downloads remote images to `raw/assets/`, rewrites paths in place. Per-
  download cap 10 MiB, per-source cap 50 MiB. Uses stdlib `urllib`; no
  third-party deps.
- `plugin/scripts/search_naive.py` — deterministic 3-pass search
  (index.md → frontmatter → body). Tier-filters by default, returns
  ranked JSON. Backs `wiki-search` when qmd is not installed.
- `scripts/build_skill_md.py` — keeps the autogenerated skill-table block
  in root `SKILL.md` in sync with `plugin/skills/*/SKILL.md` frontmatter.
  `--check` mode exits nonzero on drift; CI uses it as a gate.

### Added — schema validation

- `schema_validate.py` now runs five cross-field rules after structural
  validation: `active_days < archived_days`, `custom_dimensions.name`
  uniqueness, `custom_dimensions.applies_to` references declared
  categories, `dreaming.weights.*` ≥ 0, `dreaming.confidence_threshold`
  ∈ [0, 1]. The dreaming rules are forward-compatible with v1.6.

### Added — CI

- `.github/workflows/test.yml` runs `tests/run_smoke.py` on push and PR
  against main, matrix on Python 3.10/3.11/3.12/3.13 × ubuntu/windows.
  Plus a schema-check job that compiles all `plugin/scripts/` and
  validates `schema/wiki-schema.json` is valid JSON.

### Added — tests

- Smoke test grew from 11 to 15 assertions (image rewrite, naive search
  determinism, three cross-field violations, well-formed dreaming block).

### Added — product planning

- `docs/PRD-v1.6-autodreaming.md` — product requirements for v1.6
  auto-dreaming, scoped to the market-research domain.
- `docs/TRD-v1.6-autodreaming.md` — technical design: data flow,
  scoring algorithm, fixture spec, eval CI gate.
- `docs/TASKS.md` — sequenced task list with acceptance criteria for
  v1.5 and v1.6.

## [1.4.0] — 2026-04-25

### Added — packaging fidelity

- `plugin/.claude-plugin/plugin.json` — required Claude Code plugin manifest
  (was missing in 1.3; install worked accidentally because the marketplace
  manifest carried the metadata).
- `tests/build_fixture.py` and `tests/run_smoke.py` — 50-page synthetic wiki
  plus 11 smoke tests covering graph, tier, schema validation, and external
  plugin security. Stdlib only.
- `CHANGELOG.md` (this file).

### Added — deterministic algorithms

- `plugin/scripts/wiki_lib.py` — shared library: page discovery, frontmatter
  parsing, indent-aware YAML subset parser, graph build, tier compute,
  shortest-path BFS, neighbor BFS, hub scoring.
- `plugin/scripts/graph_query.py` — backs `wiki-graph` for neighbors,
  shortest-path, hubs, orphans, cluster, and stats modes. Skill becomes a
  thin wrapper that calls the script and formats the JSON.
- `plugin/scripts/tier_compute.py` — backs `wiki-tier --show / --preview /
  --list` with deterministic distribution and delta computation.
- `plugin/scripts/schema_validate.py` — validates `SCHEMA.md` and
  `.wiki-plugins.yaml` against `schema/wiki-schema.json` (a real JSON Schema
  document, not a prompt rule).
- `plugin/scripts/import_checkpoint.py` — JSON checkpoint IO for
  `wiki-import --resume`. No more "agent self-discipline" persistence.
- `plugin/scripts/external_plugin_run.py` — secure runner for
  `.wiki-plugins.yaml` entries.

### Changed — security model for external plugins

**Breaking.** `command_template:` is removed; plugins now declare `argv:` as
a list of literal tokens. The runner uses `subprocess.run(argv, shell=False)`
— a shell never sees the substituted query. After substitution any token
containing `;`, `|`, `&`, `&&`, `||`, `` ` ``, `$(`, `<`, `>`, or newline is
refused. Output is sanitized for prompt-injection markers (`<system>`,
`<|im_start|>`, `IGNORE PREVIOUS`, `[[INST]]`) before landing in `raw/`.
Outputs are sized (`max_output_bytes`, default 1 MiB) and timeboxed
(`timeout_seconds`, default 60). Env passed to children is filtered to a
small allowlist.

Migration is documented in `plugin/PLUGINS.md`.

### Fixed — packaging consistency

- README install commands corrected: `claude /plugin marketplace add` +
  `claude /plugin install` (the previous `claude plugin install` was not the
  real CLI). All slash-command examples now show the `/` prefix that Claude
  Code actually accepts.
- Codex CLI section: removed the non-spec `.codex-plugin/plugin.json`. Codex
  CLI integration is now documented honestly as a copy-based flow (drop
  `AGENTS.md` + `skills/` + `scripts/` into the project root).
- Skill count unified to **9** (was inconsistently `10` in
  `marketplace.json`, the removed Codex manifest, and root `SKILL.md`).

### Added — README clarity

- "Two ways to use this" section: a 3-step path for the standalone prompt
  vs. the full plugin path.
- Comparison table vs. Obsidian Copilot, MCP memory servers, and
  RAG/vector DBs — clarifies what the wiki is *for* relative to neighbors.

## [1.3.0] — 2026-04-12

- External fallback plugins: `.wiki-plugins.yaml` registry and the
  `wiki-query` fallback flow (`on_empty` / `on_low_confidence` /
  `on_request`). _Note: 1.3 used `command_template:` which 1.4 removed._
- `wiki-graph` skill: structured frontmatter / neighbor / shortest-path /
  hubs / orphans / cluster modes, plus mermaid output.

## [1.2.0] — 2026-04-12

- Three-tier memory aging (`active` / `archived` / `frozen`), tier
  computation on-the-fly from `published_at`, `wiki-tier` skill for
  inspection and threshold management.

## [1.1.0] — 2026-04-12

- Custom frontmatter dimensions in SCHEMA.md, with `refresh_on` schedule
  driving when `wiki-ingest` / `wiki-import` / `wiki-digest` prompt for
  values.
- `wiki-import`: 5-phase bulk migration (Discovery → Mapping →
  Deduplication → Wave processing with checkpoint → Navigation update).
- Image handling in `wiki-ingest`: download referenced images to
  `raw/assets/` and rewrite source paths.

## [1.0.0] — 2026-04-12

- Initial release. 6 skills (init, ingest, search, digest, query, lint)
  implementing Karpathy's LLM Wiki concept as a Claude Code plugin.
- SCHEMA.md as the single authoritative config.
- `raw/` immutability, `index.md` + `log.md`, Karpathy-style log format.
