---
spec_relationships:
  - kind: refines
    target: docs/PRD-v1.13-spec-history-management.md
    note: |
      v1.13 shipped Phase 0/2/4 as ship-with-caveats and Phase 3 as
      opt-in preview. The codex audit task-mpci827r-1prafp identified
      Phase 3's structural problem: it writes authoritative-looking
      metadata (banner / spec_superseded_by / tier flip / reverse-index)
      append-only, with no path back when the source spec's relationship
      is later edited or removed. v1.14 relands the entire propagation
      pipeline against a transaction model. v1.13 PRD's Phase 3 section
      is preserved as historical context; this PRD supersedes the
      implementation contract.
  - kind: extends
    target: docs/PRD-v1.12-cross-wiki-federation.md
    note: |
      Phase 4 lineage view in v1.13 only reads .spec-reverse-index.yaml
      for counts — the cross-wiki edges are not actually walked into the
      rendered tree. v1.14 closes that gap so federated supersession is
      a first-class edge in spec-history, not a footnote.
---

# PRD v1.14 — Spec Propagation Reconcile (transactional reland of v1.13 Phase 3)

Status: Draft v1
Date: 2026-05-19
Author: surebeli
Triggered by: codex audit task-mpci827r-1prafp (verdict hold-for-changes
on v1.13 Phase 3 + several v1.14-shaped findings on Phases 2 + 4)

## Context

v1.13 SHM (Spec History Management) shipped 2026-05-19 across 4 phases.
A Codex GPT-5.5 xhigh audit conducted same-day returned `hold-for-changes`
overall, with Phase 3 (auto-propagation) the worst-scoring component. The
audit's "biggest worry" is worth quoting verbatim:

> Phase 3 creates authoritative-looking metadata that it cannot reconcile.
> A single edited or downgraded source spec can leave old pages permanently
> bannered, archived, excluded from dreamer, and shown as superseded in
> lineage.

This is not a bug class fixable by point patches. It's a structural shape:
v1.13 Phase 3 is append-only, has no transaction boundary with Phase 2's
ingest gate, no ownership model for the writes it makes, and no reverse
operation. Patching individual symptoms (path traversal, multi-superseder
collision, schema $ref) leaves the shape intact.

v2.13.1 (shipped 2026-05-19) lands the critical security fix (path
traversal) + cheap ride-alongs (schema $ref, strict bool, doc updates) +
relabels Phase 3 as `PREVIEW` with `auto_propagation.enabled` default-off.
This PRD is what comes next.

## Goals

Reland Phase 3 against a transactional / reconcilable model. Concretely:

1. **Phase 3 is part of the Phase 2 ingest transaction**, not a separate
   post-step. If propagation fails on any target, the new spec is not
   written and no targets are modified.

2. **Every write is owned by a `managed_by: kata-spec-propagate` marker
   carrying the source spec's stable identifier.** Reverse propagation
   becomes possible because we can scan for "writes owned by source X
   whose current relationship list no longer mentions this target" and
   roll them back.

3. **The reverse-index file (`.spec-reverse-index.yaml`) is walked into
   the Phase 4 lineage tree** as first-class federated edges, not just
   counted. v1.13's Phase 4 stub is closed.

4. **Multi-superseder semantics are explicit**, not last-writer-wins:
   the schema declares the policy (`reject` / `merge` / `keep-first`)
   and the banner / tier flip behaves accordingly.

5. **Concurrent ingest is safe** through per-target file locks + atomic
   temp-write-rename.

6. **Phase 2 enforcement validates `kind` and requires `note`**, closing
   the audit's high-severity finding that enforcement is target-only.

Out of scope:
- New propagation kinds beyond `supersedes` (would expand surface
  unnecessarily; defer to v1.15+ if requested)
- A separate `wiki-spec rollback` user-facing command (the reverse
  happens implicitly during ingest of the editing source spec; manual
  rollback is a v1.15+ idea)
- Cross-wiki write-back (federation contract remains read-only)
- Spec text content checks (banner content is structural only; semantic
  drift detection is a different feature)

## Architecture

### Today (v2.13.x, what we're replacing)

```
wiki-ingest
  ├─ Phase 0: preflight scoring             (advisory)
  ├─ Phase 2: enforcement (--enforce)       (gate; rejects if uncovered)
  ├─ write new spec                         (filesystem)
  └─ Phase 3: spec_propagate.py             (separate subprocess)
       ├─ banner write                       ← independent file write
       ├─ frontmatter rewrite                ← independent file write
       ├─ tier_override write                ← independent file write
       └─ .spec-reverse-index.yaml write     ← independent file write
        (no transaction; no ownership; no reverse)
```

### Target (v2.14.0)

```
wiki-ingest
  └─ Phase 2+3: single transaction
       ├─ preflight scan                                         (read-only)
       ├─ enforcement gate (kind + note + target validation)     (gate)
       ├─ resolve declared relationships to canonical edges     (read-only)
       ├─ snapshot pre-state of every prospective target        (in-memory)
       ├─ compute desired post-state (additive + reverse)       (in-memory)
       ├─ acquire per-target file locks                          (filesystem)
       ├─ write to .kata-spec-staging/<txn-id>/                  (filesystem)
       ├─ verify staged writes pass post-state asserts          (read-only)
       ├─ atomic move staged → in-place (rename(2) per target)   (filesystem)
       ├─ release locks                                          (filesystem)
       └─ commit txn log entry                                   (filesystem)

  on any failure → abort: release locks, delete staging dir, log,
  exit non-zero. The ingest's new-spec write does NOT happen unless
  the entire transaction is committable.
```

### Ownership model

Every write Phase 3 makes carries a managed-by marker:

```yaml
# F015-old.md frontmatter (target of supersession)
spec_superseded_by:
  - path: decisions/F017-new-auth.md
    date: 2026-05-19
    note: F015 replaced
    managed_by: kata-spec-propagate
    source_txn: txn-2026-05-19-093521
    source_spec_id: <stable-spec-id-of-F017>
tier_override: archived
tier_reason: "Superseded by F017 on 2026-05-19"
tier_managed_by: kata-spec-propagate
tier_source_spec_id: <stable-spec-id-of-F017>
```

```html
<!-- kata:spec-banner BEGIN -->
<!-- kata:spec-banner-meta source_spec_id=<id> txn=<txn-id> -->
> **⚠ Superseded by [[F017-new-auth]] on 2026-05-19.**
> ...
<!-- kata:spec-banner END -->
```

On ingest of an edited F017 whose `spec_relationships` no longer
contains a `kind: supersedes target: F015` entry:

1. Read F017's NEW relationships
2. Scan all wiki pages + reverse-index for `source_spec_id == F017`
3. For each found write whose target is NOT in F017's new
   relationship list → REVERT it (strip banner, remove
   spec_superseded_by entry, restore tier if `tier_managed_by ==
   kata-spec-propagate`)
4. Apply NEW relationships (add new entries, update changed notes)

This makes Phase 3 idempotent AND reversible. The same edit that
once-created the propagation can also remove it.

### Source spec identity

`source_spec_id` must be stable across edits. Options:

- **D1.1: Path-based** (`decisions/F017-new-auth.md`) — simple, breaks on rename
- **D1.2: UUID frontmatter field** — stable across renames, requires injection on first ingest
- **D1.3: Hash of normalized title + first ingest date** — semi-stable, breaks on title edit

Lean: **D1.2** with auto-injection on first ingest. wiki-ingest already
mutates frontmatter for other reasons (`type`, `tags` normalization);
adding a `spec_id` field with auto-UUID is a small extension. Pre-existing
specs missing a `spec_id` get one assigned on first re-ingest.

### Multi-superseder policy

Schema gains a single new field:

```yaml
spec_authoring:
  auto_propagation:
    on_multiple_superseders: reject | merge | keep-first | last-wins
```

- `reject` (recommended default): the second supersession is refused at
  Phase 2 enforcement; author must explicitly resolve.
- `merge`: banner is rendered from the FULL set; `spec_superseded_by` list
  carries all entries (already the v1.13 behavior); tier_reason uses
  "Superseded by F017, F020 on ..."
- `keep-first`: only the first supersession wins; subsequent attempts log
  a warning but don't modify the target.
- `last-wins`: current de-facto v1.13 behavior; documented but not
  recommended.

### Reverse-index in Phase 4

`graph_query.py --mode spec-history` currently loads
`.spec-reverse-index.yaml` but only counts entries. v1.14 makes federated
edges first-class in `_build_spec_history_tree()`:

- Outbound walk reads `kata://` targets from `spec_relationships` AS
  BEFORE (already works in v2.13.0).
- Inbound walk additionally scans `external_supersessions:` for
  `external_target == kata://<this-wiki-id>/<seed-path>` matches, listing
  every wiki that supersedes us via reverse-index.
- Mermaid output adds a `EXT_<hash>` node per federated source with
  proper edge styling. Existing `EXT_` nodes (outbound federated targets)
  are preserved with `[fed]` annotation.

## Phases

### Phase 0: spec_id auto-injection (low-risk groundwork)

Pre-work that doesn't change behavior. Lands first so Phase 3 has stable
IDs to work with.

- wiki-ingest assigns `spec_id: <uuid>` to any spec frontmatter without one
- `wiki-spec --backfill-ids` for existing wikis (batch one-shot)
- Schema validation accepts spec_id as optional
- Test: ingest twice → ID stable; edit non-frontmatter → ID stable; rename
  file → ID stable

### Phase 1: enforcement validation (closes audit high #1)

- `kind` MUST be one of the schema's `relationship_kinds`
- `note` REQUIRED when Phase 2 enforcement is active
- Malformed entries → enforcement reject, not silent drop
- Federated `target` (anything with `kata://` prefix) MUST use kata:// or
  wiki_id-form; bare-stem federated declarations rejected (closes high #2)

### Phase 2: per-target locks + atomic staging

The transaction substrate. No reconcile logic yet, but every write now
goes through:

- `acquire_lock(target_path)` (file-based, advisory, retry with backoff)
- `staging_dir = .kata-spec-staging/<txn-id>/`
- write all staged files
- atomic move on commit; rm -rf on abort
- release locks

Closes audit high #3 (concurrent ingest race).

### Phase 3: reverse propagation

The core reland. On ingest of any spec with `type` in `spec_types`:

1. Compute current desired write set from new spec's `spec_relationships`
2. Compute extant write set by scanning all targets for `source_spec_id`
   matches
3. Symmetric diff:
   - extant - current = entries to REMOVE (banner strip, frontmatter dedup,
     tier restore IF `tier_managed_by == kata-spec-propagate`)
   - current - extant = entries to ADD (current v1.13 behavior, but staged)
   - intersection = entries to UPDATE (re-render banner with new note)
4. Stage all writes
5. Commit atomically

Closes audit high #4 (supersedes->refines reversal).

### Phase 4: federated reverse-index in lineage tree

Pure read-side change. `_build_spec_history_tree()` adds federated inbound
edges from the reverse-index walk. Mermaid + JSON outputs gain new edge
class.

Closes audit high #5 (reverse-index stub).

### Phase 5: multi-superseder policy enforcement

Schema field + enforcement logic per the four policies above. Default
flips to `reject`; current `last-wins` available as opt-out.

Closes audit medium #1 (multi-superseder merge collision).

## Schema additions

```yaml
spec_authoring:
  enabled: true
  spec_types: [...]
  auto_propagation:
    enabled: true                          # may flip default → true after v1.14 dogfood
    kinds_to_propagate: [supersedes]
    auto_tier_flip: true
    banner_template: "..."
    on_multiple_superseders: reject        # NEW in v1.14
    transaction_log_dir: .kata-spec-txn    # NEW in v1.14
    backfill_spec_ids: true                # NEW in v1.14 Phase 0
```

## Migration

v2.13.x users opted into preview:

1. `wiki-spec --backfill-ids` populates `spec_id` on existing specs
2. `wiki-spec --rebuild-managed-by` rewrites existing propagated writes
   with `managed_by` markers so they're owned by Phase 3 going forward
3. After both: `auto_propagation.enabled` keeps working, but now with
   reverse semantics

v2.13.x users who never opted in: no-op upgrade.

## Test coverage (must-have before merge)

- Phase 0: spec_id stable across edit / rename / re-ingest
- Phase 1: enforcement rejects bad kind, missing note, bare-stem
  federated
- Phase 2: two concurrent `python spec_propagate.py` processes against
  the same target — locks serialize, second one waits, both commits
  succeed in order, no data loss
- Phase 3 reconcile:
  - supersedes A → ingest → propagate
  - edit spec to supersedes B (drop A) → ingest → A reverted, B propagated
  - edit spec to refines A (downgrade) → ingest → A reverted
  - delete relationship entirely → ingest → A reverted
  - rename source spec file → spec_id stable, no orphan writes
- Phase 3 ownership:
  - user manually sets `tier_override: archived` with no managed_by → leave
    alone on reconcile
  - user manually edits banner text → on next propagation, log warning AND
    overwrite (managed_by carries authority; user manual edits to managed
    fields are lost — document this)
- Phase 4: federated lineage walks reverse-index, mermaid renders inbound
  EXT nodes
- Phase 5: each on_multiple_superseders policy tested with two specs
  targeting same victim

Roughly 12-15 new smoke tests.

## Risk

| Risk | Mitigation |
|------|------------|
| Reconcile loop edits everyone's tier_override on first run after upgrade | Backfill migration is opt-in; default keeps current state intact |
| Lock files left behind on crash | Stale lock detection by PID + age; clean on next ingest |
| spec_id collision across wikis (federation) | UUID v4 — collision probability negligible |
| Transaction log grows unbounded | Configurable retention (default 30 days) |
| User loses manual edits to a banner | Document this clearly; managed fields are managed |

## Open questions

- **OQ1**: Should Phase 3 transaction log live in `.kata-spec-txn/` (wiki-
  internal, gitignored) or in `decisions/.kata-spec-txn.md` (git-tracked,
  visible)? Lean gitignored — txn log is operational data, not domain
  knowledge.

- **OQ2**: When reverse propagation strips a banner from an old spec,
  does the page get a "this page was previously marked superseded by X
  on Y, that relationship was revoked Z" history line? Lean yes,
  written to `log.md` not the page itself. Keeps the spec page clean
  and gives auditors a trail.

- **OQ3**: Backwards compatibility for v2.13.x writes (no managed_by
  marker). Treat them as user-pinned (preserve) or as legacy-managed
  (sweep)? Lean **preserve** — safer default; user can opt into a
  sweep via explicit `wiki-spec --adopt-legacy-writes`.

## Related

- [[PRD-v1.13-spec-history-management]] — the PRD this supersedes (Phase 3
  implementation contract). v1.13 Phases 0/2/4 remain in force, just with
  Phase 1 / 5 hardenings landing as additive.
- [[PRD-v1.12-cross-wiki-federation]] — federation contract this respects
- Codex audit task-mpci827r-1prafp — the trigger
- v2.13.1 CHANGELOG — the interim patch that bought us time to write this
