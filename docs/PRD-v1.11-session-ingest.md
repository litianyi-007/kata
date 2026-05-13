# PRD v1.11 — Session-ingest skill (multi-CLI session distillation)

Status: Draft v2 — round-1 open questions closed
Date: 2026-05-12 (round-2 2026-05-12)
Author: litianyi

## Context

kata today only ingests **artifacts** — URLs, files, pasted text via
`wiki-ingest`. But across the NECallKit dogfood and other multi-CLI work, the
high-value knowledge is increasingly **born inside the conversation itself**:
debugging the IPC reentrancy bug, decoding a switchCallType regression,
deciding why we rejected one design and picked another. By the time the user
remembers to write it down as a "source", half of it is gone.

Meanwhile the user runs multiple AI CLIs side by side — Claude Code today,
Codex CLI for tougher debugging, Gemini / Copilot / OpenCode / Kimi for
specific tasks. Each holds knowledge in its own transcript format and there
is no skill that says "take what we just figured out and put it in the wiki."

This PRD introduces a single skill, `wiki-session-ingest`, that **reads the
currently active CLI's session, asks the user which knowledge points are
worth keeping, and distills each into the wiki** through the existing
`wiki-ingest` pipeline. It does not replace `wiki-ingest`; it feeds it.

## Goals

- One user-facing entry point (`/kata:wiki-session-ingest`) that works
  from inside any of the six target CLIs without extra arguments.
- Deterministic session-file reading for Claude Code and Codex CLI (the
  two CLIs we use most and whose formats are stable).
- LLM-driven session dump fallback for Gemini / Copilot / OpenCode / Kimi
  CLI — the AI writes its own session summary to disk.
- Interactive multi-select of knowledge points the AI extracted from the
  session; the user picks which to distill (Method 1 in design discussion).
- Output funnels through the existing `wiki-ingest` pipeline. No parallel
  ingest path, no duplicate index.md / log.md writers, no separate raw
  layout.
- Every distilled page carries provenance: `source_cli`, `session_id`,
  `cwd`, plus pointer to the raw session dump under
  `raw/sessions/`.

## Non-goals

- **No auto-ingest.** The skill never writes wiki pages without an
  explicit user multi-select on the candidate list. The
  auto-trigger-at-session-end config (see §Auto-trigger config) only
  decides whether the skill **starts**; it never bypasses the
  multi-select step.
- **No write to live CLI transcripts.** The skill is read-only on
  `~/.claude/projects/`, `~/.codex/sessions/`, etc.
- **No cross-CLI session correlation.** If the user has two CLIs open
  side-by-side, each session is ingested independently. No merge.
- **No real-time streaming / watching.** The skill is user-invoked,
  one-shot per call.
- **No automated "knowledge point" extraction outside the AI in the
  active session.** No background heuristic / NER service.
- **No multi-machine session aggregation.** Sessions are per-machine;
  syncing is the wiki repo's job, not the skill's.
- **No retroactive ingest of dozens of past sessions in one batch** in
  MVP. The skill targets "the current session" or "one specific session
  by id". Bulk historical ingest is deferred.

## Personas / user stories

- **Dogfood maintainer (Claude Code primary)** — after a 2-hour
  debugging session that lands a bug fix and a contract assertion, runs
  `wiki-session-ingest`, picks 3 of 5 candidates, ends with three new /
  updated wiki pages and a `raw/sessions/claude-2026-05-12-...md`.
- **Codex CLI deep-dive user** — uses Codex for a tough algorithm
  refactor in `~/.codex/sessions/...`. The skill reads the rollout JSONL
  directly, presents knowledge points, distills the ones worth keeping.
- **Gemini / Copilot / OpenCode / Kimi user** — invokes the skill in
  that CLI; the AI dumps the session as it understands it (Method A) to
  the same `raw/sessions/` folder and continues the same flow.
- **Cross-CLI maintainer** — does not want the skill to assume a single
  CLI. The same skill body and the same output shape work everywhere.

## CLI detection (decision tree)

Runs at the start of every invocation. Falls through top-to-bottom:

```text
1. $CLAUDECODE == "1"
   → cli = "claude-code"
     session_file = ~/.claude/projects/{slug-of-cwd}/{CLAUDE_CODE_SESSION_ID}.jsonl
     mode = "jsonl-read"

2. $CODEX_SESSION_ID nonempty
   OR (~/.codex/sessions/{today}/rollout-*.jsonl exists AND
       at least one file's session_meta.payload.cwd matches current $PWD)
   → cli = "codex-cli"
     session_file = <best match: cwd-equal + most-recent timestamp>
     mode = "jsonl-read"

3. $GEMINI_CLI == "1" OR similar known sentinel
   → cli = "gemini-cli"
     session_file = none
     mode = "llm-dump"

4. $COPILOT_CLI == "1" OR similar known sentinel
   → cli = "copilot-cli"

5. $OPENCODE / opencode-specific marker
   → cli = "opencode"

6. $KIMI_CLI / similar
   → cli = "kimi-cli"

7. None of the above
   → cli = "unknown"
     session_file = none
     mode = "llm-dump"
     prompt user once: "Which CLI is this? [skip / type a name]"
```

Steps 3–6 are recorded as "to be confirmed at implementation time".
Each can be patched in by trying the sentinel env first; if it does not
exist, fall back to "unknown" — the LLM-dump path works regardless.

CLI name and detection mode are written into the raw dump frontmatter
(`source_cli:`, `detection_mode:`) so the user / future agent can audit.

### Session-id resolution rules

- **Claude Code**: `CLAUDE_CODE_SESSION_ID` is authoritative. The CLI
  guarantees the jsonl file at the derived path.
- **Codex CLI**: prefer `$CODEX_SESSION_ID` if set; otherwise the rollout
  scan picks **the most-recent `session_meta.payload.cwd == $PWD` match
  in today's directory, with yesterday as fallback**. If two candidates
  tie within 60 seconds, prompt the user to pick.
- **Cwd path normalization**: Codex stores `cwd` with `\\` on Windows;
  comparison must lowercase and unify path separators before equality.

## Data model

### Raw session dump

Lives at:

```
{wiki_path}/raw/sessions/{cli}-{date}-{slug}-{short-id}.md
```

Example:

```
raw/sessions/claude-code-2026-05-12-llm-wiki-yaml-12434e19.md
```

Frontmatter (required):

```yaml
---
type: session-dump
source_cli: claude-code            # one of the six known names | "unknown"
detection_mode: jsonl-read         # jsonl-read | llm-dump
session_id: 12434e19-22b8-4e47-...
session_file: ~/.claude/projects/F--workspace-ai-kata/12434e19-...jsonl
cwd: <workspace>/ai/kata
session_start: 2026-05-12T08:30:00Z
session_end: 2026-05-12T10:45:00Z   # last user / assistant message ts
ingested_at: 2026-05-12
distilled_pages:                    # filled after multi-select completes
  - pages/decisions/llm-wiki-yaml-single-path-cache.md
  - pages/features/multi-wiki-coexistence-doc.md
---
```

Body:

- For `jsonl-read`: a curated, **non-truncated** transcript. The Python
  adapter converts the JSONL into readable markdown sections (user turns,
  assistant turns, tool calls collapsed to one-liners, tool outputs
  truncated to head/tail). Decorative events (`file-history-snapshot`,
  `permission-mode`, etc.) are filtered out.
- For `llm-dump`: the AI writes a chronological summary of the session
  to the same body location. Same skeleton headings (`## User questions`,
  `## Decisions`, `## Outcomes`).

### Knowledge point candidate

Generated in-memory only (not written to disk until distilled):

```yaml
- title: "llm-wiki.yaml is a single-path cache (multi-wiki via registry)"
  one_liner: "Confirms .llm-wiki.yaml binds to one wiki; multi-wiki uses registry.yaml or per-submodule innermost-wins."
  page_type: decision                # decision | feature | bug | lesson | concept (per SCHEMA.md)
  proposed_path: pages/decisions/llm-wiki-yaml-single-path-cache.md
  evidence_anchors:
    - "session message #142"         # message index inside the dump
    - "session message #167"
  related_pages:                     # existing wiki pages this overlaps
    - pages/architecture/path-resolution-chain.md
  conflicts:                         # existing pages with contradictory content
    - none
```

Candidates are presented as a numbered list; user multi-selects (e.g.,
`1,3,4` or interactive checkbox); selected ones become wiki-ingest
inputs.

## User workflows

### Default flow (Claude Code, jsonl-read)

```text
$ /kata:wiki-session-ingest

[Phase 1] Detect CLI
  → claude-code (env CLAUDECODE=1)
  → session: ~/.claude/projects/F--workspace-ai-kata/12434e19-...jsonl
  → 287 events, 2h 15m span

[Phase 2] Write raw session dump
  → raw/sessions/claude-code-2026-05-12-llm-wiki-yaml-12434e19.md (38 KB)

[Phase 3] Extract knowledge points (AI reads dump + existing index.md)
  Found 5 candidates:

  1. [decision] llm-wiki.yaml is a single-path cache
     → pages/decisions/llm-wiki-yaml-single-path-cache.md (new)
     Related: architecture/path-resolution-chain.md

  2. [feature] Multi-wiki coexistence: per-project, registry, nested override
     → pages/features/multi-wiki-coexistence-doc.md (new)

  3. [lesson] .llm-wiki.yaml belongs in source-repo .gitignore
     → pages/lessons/per-machine-binding-state.md (new)

  4. [bug] _read_simple_yaml only keeps last key when duplicated
     → pages/bugs/yaml-parser-keeps-last-key.md (new)

  5. [decision] (low confidence) v1.10 wiki-vault vs local-directory should split
     → pages/decisions/v1.10-split-into-v1.11-federation.md (new)

[Phase 4] Multi-select
  Which knowledge points should I distill? (comma-separated, or 'all' / 'none')
  > 1,2,3

[Phase 5] Distill (calls wiki-ingest per selected candidate)
  ✓ Created pages/decisions/llm-wiki-yaml-single-path-cache.md
  ✓ Created pages/features/multi-wiki-coexistence-doc.md
  ✓ Created pages/lessons/per-machine-binding-state.md
  ✓ Updated index.md (3 new entries)
  ✓ Appended log.md
  ✓ Updated raw dump frontmatter (distilled_pages)
  ✓ git add + commit "wiki-session-ingest: claude-code 2026-05-12 (3 pages)"

[Done] 3 pages distilled, 2 candidates skipped (saved in raw dump for later).
```

### Codex CLI flow

Identical to the above, except Phase 1 reports `codex-cli` and reads the
rollout JSONL discovered via the cwd-match heuristic.

### Generic CLI fallback (Gemini / Copilot / OpenCode / Kimi / unknown)

```text
$ /kata:wiki-session-ingest

[Phase 1] Detect CLI
  → cli = gemini-cli  (env GEMINI_CLI=1)        # or "unknown" + prompt
  → no session file known; using LLM-dump mode

[Phase 2] AI writes session dump from context
  → raw/sessions/gemini-cli-2026-05-12-feature-x-{short-id}.md

[Phase 3..5] Same as Claude Code flow.
```

### Multi-select UX

- **Interactive checkbox** when running inside Claude Code (uses native
  AskUserQuestion `multiSelect: true`) and in Codex CLI's prompt mode.
- **Plain numbered prompt** (`Enter comma-separated numbers, "all", or
  "none"`) as the universal fallback.
- **No-op exit** when user picks "none" — raw dump remains for future
  recall but nothing else is written.

## Knowledge-point extraction protocol

The AI running the skill applies this protocol to the dump body:

1. **Read** the dump + `index.md` + `SCHEMA.md` (orientation guard).
2. **Identify** candidates by these triggers:
   - User asked a question the AI answered with a confident conclusion
   - AI proposed a design and user approved (or rejected with reasoning)
   - A bug was diagnosed with a clear root cause + fix
   - A workflow / runbook step was executed and verified
   - A SCHEMA.md / convention change was decided
3. **Score** each candidate on:
   - Confidence (was it actually concluded vs. exploratory?)
   - Recurrence (does the user / agent keep returning to this?)
   - Cross-link potential (does it touch existing wiki pages?)
4. **Filter out** before presenting:
   - Pure session housekeeping ("let me read the file")
   - Steps that didn't reach a conclusion ("we'll come back to this")
   - Knowledge already on an existing wiki page (cite, don't re-create)
5. **Present** ≤8 candidates ranked by score. If >8 strong candidates,
   show top 8 and note the count.

Candidates are **labeled by SCHEMA.md page types** the wiki already
declares (decision / feature / bug / lesson / concept / etc.). If the
domain wiki doesn't have a matching type, propose adding one via the
existing "pause and propose a SCHEMA.md update" guard.

## Auto-trigger config

Default invocation is **manual**: the user runs `/kata:wiki-session-ingest`
when they want a knowledge sweep. This is the only path tested in MVP
acceptance.

Per round-1 decision, a global config flag is recognized in MVP so users
who want a per-session prompt can opt in **without code changes**:

```yaml
# ~/.kata/session-ingest.yaml  (per-machine, gitignored by convention)
auto_trigger_on_session_end: false   # default
```

Semantics when `auto_trigger_on_session_end: true`:

- On session end (CLI-specific signal — Claude Code `Stop` hook, Codex
  CLI equivalent, etc.), the skill **starts** automatically.
- It still runs the full pipeline (read session → write raw dump →
  extract candidates → **prompt the user to multi-select**).
- It never silently writes wiki pages. If the user is not present at
  prompt time, the raw dump is still saved (durable capture) but no
  wiki page is created; the user can finish the multi-select later by
  re-invoking the skill on that dump.

CLI-specific hook wiring (Claude Code `settings.json` Stop hook, Codex
CLI equivalent, etc.) is documented in SKILL.md and **not auto-installed
by kata**. The flag's existence and the wiring doc are MVP
deliverables; making the wiring one-command is a v1.12 polish.

Rationale: the user's pain point ("by the time you remember, half of it
is gone") is real — but full auto-trigger violates the curation
contract. Opt-in config + multi-select preserves both signals. Default
false keeps existing users unaffected.

## Companion change — `wiki-ingest` extension flags

`wiki-session-ingest` is a thin wrapper that funnels candidates into the
existing `wiki-ingest` pipeline. For that handoff to work, `wiki-ingest`
needs three new **optional** flags. This is a sub-deliverable of v1.11
(call it **Phase 0** — must land before the skill can be exercised
end-to-end).

### New flags

```bash
wiki-ingest <source> \
  [--page-type=<type>] \
  [--proposed-path=<repo-relative-path>] \
  [--evidence-anchors=<comma-separated-anchors>]
```

- `--page-type` — short hint of the target page type as declared in
  SCHEMA.md (decision / feature / bug / lesson / concept / etc.).
  `wiki-ingest` may override based on its own SCHEMA.md analysis but
  uses this as the strong default. Backward compat: unset → existing
  inference behavior.
- `--proposed-path` — wiki-relative path the upstream skill **wants**
  the page to land at. `wiki-ingest` treats this as a hint, not a
  command. If the path collides with an existing page, `wiki-ingest`'s
  current "create vs update" policy applies (default: update with
  diff preview). Backward compat: unset → existing path derivation.
- `--evidence-anchors` — comma-separated opaque tokens (e.g.,
  `session-msg-142,session-msg-167`) that the upstream skill wants
  preserved in the new page's frontmatter under
  `evidence_anchors:`. `wiki-ingest` writes them verbatim. Backward
  compat: unset → frontmatter unchanged.

### Non-changes

- Existing `wiki-ingest <url|file|text>` shape is unchanged.
- All three flags are **strictly additive**; no existing flag changes
  semantics.
- No new mandatory frontmatter field. `evidence_anchors:` is optional
  and only appears when the flag is passed.

### Files touched in Phase 0

- `plugin/scripts/wiki_ingest.py` — accept new argv flags, plumb
  through to page-write logic.
- `plugin/skills/wiki-ingest/SKILL.md` — document the three flags
  under the existing "Arguments" / "Steps" sections.
- `tests/run_smoke.py` — small fixture covering: flag pass-through to
  frontmatter, collision behavior with `--proposed-path`, missing-flag
  back-compat.

Phase 0 ships **before** Phases 1–5 of `wiki-session-ingest`.

## Integration with `wiki-ingest`

`wiki-session-ingest` does **not** reimplement page creation, frontmatter
prompts, image handling, or index/log writes. It:

1. Writes the raw dump to `raw/sessions/{...}.md`.
2. For each user-selected candidate, **invokes `wiki-ingest` once**
   passing:
   - source path = the raw dump
   - hint flags: `--page-type={candidate.page_type}`,
     `--proposed-path={candidate.proposed_path}`,
     `--evidence-anchors={...}`
3. Lets `wiki-ingest` handle: SCHEMA.md orientation, custom dimension
   prompts (already implemented), cross-link generation, conflict
   detection, image references, index/log updates, git commit.

The three hint flags (`--page-type` / `--proposed-path` /
`--evidence-anchors`) ship as Phase 0 of this PRD — see §Companion
change. The human-driven `wiki-ingest <url|file|text>` path is
unchanged.

## Safety rules

- **No write to CLI transcript directories.** Only read. Verified by
  test: skill on a chmod-locked transcript dir still proceeds to LLM-dump
  fallback without error.
- **Raw dump is immutable after creation.** Once Phase 2 finishes, the
  body is never rewritten. Only `distilled_pages:` frontmatter gets
  appended in Phase 5.
- **No silent ingest.** A user multi-select of "none" produces zero
  wiki page changes (raw dump still saved; user can re-run the skill
  later pointing at it).
- **Dirty wiki guard.** Same as `wiki-import`: refuse to start if
  `git status` shows uncommitted wiki changes. Reuse the existing
  `wiki-import` import-lock to serialize against concurrent ingest.
- **Session-file size guard.** If the JSONL exceeds 50 MB, refuse and
  ask the user to narrow the scope (`--from-message-id=...`,
  `--last-hours=2`). Avoids OOM on month-long sessions.
- **Privacy.** The raw dump is markdown in the user's wiki repo — it
  goes through normal git sync. Anything in the conversation (API keys
  accidentally pasted, internal URLs) ships with the wiki. Document this
  loudly in the skill prompt and in SKILL.md.

## CLI sentinel env vars (implementation-time confirmation matrix)

Filled in as we verify each CLI. **Bold = verified from a live env on
2026-05-12. Italic = to be verified inside that CLI.**

| CLI | Sentinel | Session-id var | Session path | Detection mode |
|---|---|---|---|---|
| **Claude Code** | **`CLAUDECODE=1`** | **`CLAUDE_CODE_SESSION_ID`** | **`~/.claude/projects/{slug}/{id}.jsonl`** | **jsonl-read** |
| Codex CLI | _`CODEX_*`_ (verify in Codex) | _`CODEX_SESSION_ID`_ | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (cwd-match fallback) | jsonl-read (with cwd-match fallback) |
| Gemini CLI | _to verify_ | _to verify_ | — | llm-dump |
| Copilot CLI | _to verify_ | _to verify_ | — | llm-dump |
| OpenCode | _to verify_ | _to verify_ | — | llm-dump |
| Kimi CLI | _to verify_ | _to verify_ | — | llm-dump |

Codex CLI's cwd-match fallback works **regardless** of whether its
sentinel env is set. So Codex jsonl-read does not depend on row-1
verification. For the other 4 CLIs, llm-dump is the safe default —
verifying their sentinels is a quality-of-life polish, not a
correctness requirement.

## MVP scope vs deferred

### Phase 0 (companion change — ships first)

- `wiki-ingest` accepts three new optional flags: `--page-type`,
  `--proposed-path`, `--evidence-anchors`. See §Companion change.
- `wiki-ingest` SKILL.md documents the flags.
- Smoke test for flag pass-through and collision behavior.

### Phase 1–5 (the skill itself)

- Claude Code jsonl adapter (deterministic via env).
- Codex CLI jsonl adapter (cwd-match fallback; sentinel env optional).
- LLM-dump path for the other 4 CLIs and the unknown case.
- Single-skill entry point `wiki-session-ingest`.
- Multi-select via AskUserQuestion (Claude Code) and plain prompt
  (others).
- Raw dump frontmatter spec.
- `~/.kata/session-ingest.yaml` parsed; `auto_trigger_on_session_end`
  flag respected (default false). Hook wiring documented per CLI, **not**
  auto-installed.
- Smoke test with synthetic Claude Code + Codex jsonl fixtures.
- Documentation: SKILL.md, README entry, CHANGELOG.

### Deferred (v1.12+)

- Sentinel-env detection for Gemini / Copilot / OpenCode / Kimi
  (LLM-dump remains the safe default until each is verified).
- Auto-wired CLI hooks (one-command install of Stop hook for Claude
  Code, equivalent for Codex). MVP only documents the wiring.
- Bulk historical session ingest (`--since=2026-05-01`).
- Cross-CLI session merge (two CLIs working on the same task).
- Token-budget-aware AI summarization for >200k-token sessions.
- `wiki-impact`-style "this session changed knowledge — what else
  might be affected?" report.
- Interactive editing of a candidate before distilling (`title`,
  `page_type`, `proposed_path` tweak).
- `--scrub-secrets` flag to redact API-key-shaped tokens before the
  raw dump is committed.

## Risks

- **Codex cwd-match ambiguity** when the user has two Codex terminals
  open on the same project. Mitigation: if multiple rollouts tie within
  60s, prompt for picker. Realistic frequency: low.
- **Knowledge-point hallucination.** AI may surface "candidates" that
  aren't well-grounded. Mitigation: every candidate carries
  `evidence_anchors` (message ids); reject candidates with <2 anchors.
- **Raw dump bloat.** A 4-hour Claude Code session can produce a
  ~500-KB dump. Wiki repo grows quickly. Mitigation: dump body uses
  tool-output truncation (head 20 lines + tail 10 lines); custom
  threshold via `--max-dump-kb=200` flag.
- **`wiki-ingest` extension creep.** Adding too many hint flags
  weakens its single-source contract. Mitigation: the new flags are
  strictly optional; existing `wiki-ingest <url|file|text>` shape stays
  primary.
- **Session-id collisions across machines.** Two machines could
  generate the same short-id slug in the filename. Mitigation: use
  full-uuid prefix in filename, not short-id.
- **Privacy leakage via raw dump committed to a synced wiki.** API
  keys / tokens pasted into the chat would end up in git history.
  Mitigation: SKILL.md flags this loudly; future `--scrub-secrets`
  flag is a v1.12 candidate.

## Acceptance criteria (MVP)

- Running `/kata:wiki-session-ingest` inside Claude Code in this
  repo produces:
  1. A new raw dump under `raw/sessions/` whose
     `session_id` matches `$CLAUDE_CODE_SESSION_ID`.
  2. ≥3 knowledge-point candidates labeled with SCHEMA.md page types.
  3. Multi-select prompt; selecting 1–N produces 1–N new wiki pages
     each linked back to the dump.
  4. `index.md` and `log.md` updated; one clean git commit per
     invocation.
- Same flow runs in Codex CLI inside any project under
  `<workspace>/`, detecting the rollout JSONL by cwd-match without
  the user supplying a session id.
- Same flow runs in a CLI for which detection returns `unknown` and
  produces a dump via LLM-dump mode, with `detection_mode: llm-dump`
  in the frontmatter.
- Dirty-wiki guard refuses to start when wiki repo has uncommitted
  changes; import-lock serializes against concurrent `wiki-import`.
- Smoke test fixture covers: jsonl-read happy path, cwd-match Codex
  resolution, llm-dump fallback, multi-select all/none/partial.

## Decisions log

### Round 1 — 2026-05-12

**D1.1 — Raw dump path: `raw/sessions/`.**

Choice: dedicated top-level `raw/sessions/`, **not** `raw/external/...`.

Rationale (user-confirmed):
- `external` / `extension` is reserved for the v1.10-class concept of an
  **outboard data source array** searched only on low-confidence
  `wiki-search` with an explicit toggle. Session dumps are the user's
  own work product, not an outboard data source — putting them under
  `external/` would conflate two distinct concepts.
- Session volume / retention pressure justifies a top-level namespace
  (separate gc / archival policy is easier when it has its own root).
- Cross-references in v1.10 PRD should be updated when v1.10 rewrites
  `external_sources` → `extension`. That update is **out of scope for
  this PRD**; tracked separately.

**D1.2 — Auto-trigger: manual default + opt-in config flag.**

Choice: skill is manually invoked by default. A global per-machine
config file `~/.kata/session-ingest.yaml` holds
`auto_trigger_on_session_end: false` (default). When `true`, the skill
**starts** on session end via CLI-specific hook wiring (documented but
not auto-installed in MVP). The multi-select step still always runs;
the flag never bypasses curation.

Rationale (user-confirmed):
- The pain point ("by the time you remember, half is gone") is real.
- But automatic page creation violates the curation contract.
- Opt-in config + always-prompt-on-multi-select preserves both. Default
  false ⇒ no behavior change for existing users.
- Putting the flag in MVP (rather than v1.12) lets power users wire it
  up immediately; the cost is one config-file read on skill start.

**D1.3 — `proposed_path` collision: defer to `wiki-ingest`.**

Choice: `wiki-session-ingest` does not implement collision policy; it
passes `--proposed-path` as a hint to `wiki-ingest`, which applies its
existing "create or update" policy (default: update with diff preview).

Rationale: keeps one source of truth for page-write decisions. Avoids
divergent collision semantics between the two skills.

**D1.4 — Companion change (Phase 0): three optional flags on `wiki-ingest`.**

Choice: ships as Phase 0 of v1.11, before Phases 1–5 of the new skill.
Flags are `--page-type`, `--proposed-path`, `--evidence-anchors`, all
strictly additive. See §Companion change for full spec.

Rationale: without these, `wiki-session-ingest` can't hand off
structured hints, and would have to re-implement page-write logic.
Phase 0 is small and well-bounded.

## Open questions

None blocking. Round-1 closed all three OQs above. Implementation-time
verification of sentinel envs (tasks #10, #11) is tracked separately
and does not gate the PRD lock.
