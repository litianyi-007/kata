---
name: wiki-session-ingest
description: "Ingest the active AI CLI session into the wiki: detect which CLI you're in (Claude Code / Codex CLI / Gemini / Copilot / OpenCode / Kimi / unknown), read the session transcript, write a raw session dump, extract knowledge-point candidates, multi-select with the user, and distill each into wiki pages via the existing wiki-ingest pipeline. v1.11 MVP. Captures the conversation-born knowledge that's normally lost when the user 'forgets to write it down.'"
user-invocable: true
argument-hint: "[--session-id <id>] [--session-file <path>] [--cli <name>] [--max-tool-output-lines N] [--auto-trigger]"
---

# wiki-session-ingest

The other ingest skills (`wiki-ingest`, `wiki-import`) handle artifacts —
URLs, files, pasted text. This one handles **the conversation itself**.

When you debug an IPC reentrancy bug across two hours with Claude Code,
the knowledge that compounds is the *reasoning trail* — what you tried,
what didn't work, why you chose the fix you did. By the time you
remember to write it down, half of it is gone. `wiki-session-ingest`
reads the live session, asks you which knowledge points are worth
keeping, and distills the selected ones through the existing
`wiki-ingest` pipeline.

## When to use

- After a deep debugging / design / refactor session that landed real
  conclusions (bug fix, decision, lesson, runbook step)
- At the end of a multi-CLI day when knowledge is scattered across
  Claude Code + Codex CLI transcripts
- Periodically as a sweep — "what did I figure out this week that
  isn't in the wiki?"

Skip if:
- The session was pure execution with no novel reasoning (e.g.
  mechanical refactor following an existing PRD)
- You already wrote it down as an artifact and ingested it via
  `wiki-ingest`
- The session was exploratory and never reached conclusions

## Pre-flight (orientation guard)

Before the first phase, read the orientation files if not already done
this session:

```
read_file {wiki_path}/SCHEMA.md     # page types, tag taxonomy, policies
read_file {wiki_path}/index.md      # content catalog
read_file {wiki_path}/log.md        # last 20 lines (recent context)
```

## Phase 1 — Detect CLI

Invoke the helper script:

```bash
python {plugin_root}/scripts/session_ingest.py detect
```

The script probes (in order):
1. `$CLAUDECODE == "1"` → Claude Code (reads
   `~/.claude/projects/{cwd-slug}/{session-id}.jsonl`)
2. `$CODEX_SESSION_ID` set OR rollout in
   `~/.codex/sessions/{YYYY}/{MM}/{DD}/` whose first-line
   `session_meta.payload.cwd` matches current cwd → Codex CLI
3. `$GEMINI_CLI` / `$COPILOT_CLI` / `$OPENCODE` / `$KIMI_CLI` →
   matching CLI in **LLM-dump mode** (no JSONL adapter)
4. None of the above → `unknown` + LLM-dump mode

Output JSON envelope:

```json
{
  "cli": "claude-code",
  "detection_mode": "jsonl-read",
  "session_id": "12434e19-22b8-...",
  "session_file": "C:/Users/.../.claude/projects/.../12434e19-...jsonl",
  "cwd": "/path/to/your/project"
}
```

If the user passed `--cli <name>`, `--session-file <path>`, or
`--session-id <id>`, those override the auto-detection result. Use
those values for the rest of the flow.

**Confirm with user** if detection is ambiguous (e.g. two Codex
rollouts tied within 60s — the script's cwd-match picks one but the
agent should sanity-check before proceeding).

## Phase 2 — Write raw session dump

### jsonl-read path (Claude Code / Codex CLI)

```bash
python {plugin_root}/scripts/session_ingest.py dump \
    --wiki {wiki_path} \
    --max-tool-output-lines 30
```

The script parses the JSONL, transforms it into readable markdown (with
`### User (msg #N)` / `### Assistant (msg #N)` / `### Tool (msg #N)`
sections, tool outputs truncated head/tail), wraps with frontmatter,
and writes to:

```
{wiki_path}/raw/sessions/{cli}-{date}-{cwd-slug}-{short-id}.md
```

Output JSON includes `dump_path`, `event_count`, `message_count`,
`session_start`, `session_end`, `size_bytes`.

### llm-dump path (Gemini / Copilot / OpenCode / Kimi / unknown)

There's no JSONL adapter for these — **the agent in the active CLI**
writes its own session summary to stdout, piped to the script:

```bash
echo "<body>" | python {plugin_root}/scripts/session_ingest.py dump-llm \
    --wiki {wiki_path} \
    --cli gemini-cli \
    --body-stdin
```

Body convention (the agent writes):

```markdown
## User questions

- Q1: <question summary>
- Q2: <question summary>

## Decisions

- D1: <decision + brief rationale>
- D2: <decision + brief rationale>

## Outcomes

- O1: <what changed / shipped>
- O2: <bug found + fixed>

## Detailed turn-by-turn

### Turn 1
<summary of exchange>
...
```

Keep turn-by-turn concise (no verbatim quotes longer than a few lines);
the goal is enough context to extract knowledge points in Phase 3, not
to preserve the literal transcript.

### Safety guards (PRD §Safety)

- **Read-only on CLI transcript directories.** Script never modifies
  `~/.claude/projects/` or `~/.codex/sessions/`.
- **Size cap.** Sessions > 50 MB are refused with exit code 2 — narrow
  with `--max-tool-output-lines` or pass a `--session-id` for a
  specific older session.
- **Dirty-wiki guard.** Before writing, check `git status` in
  {wiki_path}. If uncommitted changes exist, refuse and ask the user
  to commit or stash first (same contract as `wiki-import`).
- **Import-lock.** If `wiki-import` is mid-flight (lock file present),
  refuse — same lock as `wiki-import` to serialize ingest.

## Phase 3 — Extract knowledge-point candidates

The agent reads:
- The dump body just written
- `index.md` (existing wiki coverage)
- `SCHEMA.md` (allowed page types + tag taxonomy)

Then identifies candidates per the protocol (PRD §Knowledge-point
extraction protocol):

**Triggers** (a candidate is worth surfacing):
- User asked a question; agent answered with a confident conclusion
- Agent proposed a design; user approved (or rejected with reasoning)
- A bug was diagnosed with a clear root cause + fix
- A runbook step was executed and verified
- A SCHEMA.md / convention change was decided

**Filter out** before presenting:
- Pure session housekeeping ("let me read the file")
- Steps that didn't reach a conclusion ("we'll come back to this")
- Knowledge already on an existing wiki page (cite, don't re-create)

**Score** each on:
- Confidence — was it actually concluded vs exploratory?
- Recurrence — does the topic keep coming back?
- Cross-link potential — does it touch existing wiki pages?

**Hallucination guard** (PRD §Risks): reject candidates with < 2
evidence_anchors (i.e. < 2 distinct message ids backing the
candidate). Every surfaced candidate must cite at least 2
`session-msg-N` anchors.

**Present** ≤ 8 candidates ranked by score. Each candidate has:

```yaml
- title: "<one-line title — what the page would be called>"
  one_liner: "<≤120 char description for the multi-select prompt>"
  page_type: decision           # decision / feature / bug / lesson /
                                # concept / prd / rfc / adr / task-spec
                                # (must be one SCHEMA.md declares)
  proposed_path: decisions/<slug>.md
  evidence_anchors: [session-msg-142, session-msg-167]
  related_pages:                 # existing wiki pages that overlap
    - pages/architecture/<slug>.md
  conflicts: []                  # existing pages with contradictory content
```

Label each candidate with a SCHEMA.md-declared page type. If a
candidate doesn't fit any existing type, **pause and propose adding
the type to SCHEMA.md** rather than mis-filing (schema guard).

## Phase 4 — Multi-select

Present the ranked candidates to the user via **AskUserQuestion**
(multi-select, one question per skill invocation):

```
Question: "Which knowledge points should I distill from this session?"
multiSelect: true
options:
  - label: "[decision] llm-wiki.yaml is a single-path cache"
    description: "Confirms .llm-wiki.yaml binds to one wiki; multi-wiki uses registry.yaml..."
  - label: "[feature] Multi-wiki coexistence: per-project / registry / nested"
    description: "..."
  - label: "[lesson] .llm-wiki.yaml belongs in source-repo .gitignore"
    description: "..."
  - label: "[bug] _read_simple_yaml only keeps last key when duplicated"
    description: "..."
```

If the user picks zero options ("none"), exit cleanly — the raw dump
is still saved for future recall. Report the exit + zero-pages
outcome.

## Phase 5 — Distill (per selected candidate)

For each selected candidate, invoke the existing `wiki-ingest` skill
with the hint flags shipped in v2.6.0 (Phase 0):

```
wiki-ingest {dump_path} \
    --page-type={candidate.page_type} \
    --proposed-path={candidate.proposed_path} \
    --evidence-anchors={comma-joined-anchors}
```

`wiki-ingest` handles: SCHEMA.md orientation, custom-dimension
prompts, cross-link generation, conflict detection, image references,
`index.md` / `log.md` updates, git commit. This skill does **not**
re-implement any of that.

After each successful ingest:
1. Append the new page's wiki-relative path to the raw dump's
   `distilled_pages:` frontmatter array (open the dump, edit the YAML
   block in place, save).
2. Track for the final report.

After all selected candidates are distilled:
- Surface any hint overrides (`wiki-ingest` may have overridden
  `--page-type` or `--proposed-path` based on SCHEMA.md analysis;
  report those to the user so they know what landed vs what was
  requested).
- Make a single git commit covering all distilled pages + the raw
  dump (commit message:
  `wiki-session-ingest: {cli} {date} ({N} pages)`).

## Auto-trigger config

Default is **manual invocation only**. The user runs
`/kata:wiki-session-ingest` when they want a knowledge sweep.

For users who want a session-end auto-prompt, an opt-in config flag
lives at `~/.kata/session-ingest.yaml`:

```yaml
auto_trigger_on_session_end: false   # default
```

Manage via the helper script:

```bash
python {plugin_root}/scripts/session_ingest.py config show
python {plugin_root}/scripts/session_ingest.py config set auto_trigger_on_session_end true
python {plugin_root}/scripts/session_ingest.py config get auto_trigger_on_session_end
```

When `true`, the skill should be wired into the CLI's session-end hook
(Claude Code `Stop` hook in `.claude/settings.json`, Codex CLI
equivalent). MVP **documents** this wiring but does not auto-install.
Even with the flag on, the multi-select step still runs — never silent
writes.

### Claude Code Stop hook example

In `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python {plugin_root}/scripts/session_ingest.py config get auto_trigger_on_session_end | grep -q true && echo 'run /kata:wiki-session-ingest to capture this session'"
          }
        ]
      }
    ]
  }
}
```

(The hook just emits a reminder; user runs the skill manually.
Auto-spawning a slash command from a hook is a v1.12 polish.)

## Safety rules

- **No write to CLI transcript directories** — script enforces this
- **Raw dump is immutable after Phase 2** — only the `distilled_pages:`
  frontmatter array is appended in Phase 5; the body is never rewritten
- **No silent ingest** — multi-select is hard-required; "none" produces
  zero wiki page changes
- **Dirty-wiki guard** — refuse to start if `git status` shows
  uncommitted wiki changes
- **Privacy warning** — the raw dump is markdown in your wiki repo, so
  it ships with `wiki-sync`. Anything in the conversation (API keys,
  internal URLs, sensitive PII) goes with it. Review before sync if the
  session touched secrets. Future `--scrub-secrets` flag is deferred to
  v1.12.

## Output format

```
[Operation] wiki-session-ingest | {cli} session {short-id}

[Detection]
- CLI:        {cli} ({detection_mode})
- Session id: {session_id}
- Source:     {session_file or 'agent-rendered'}
- Cwd:        {cwd}

[Raw dump]
- raw/sessions/{cli}-{date}-{slug}-{short-id}.md ({size_bytes} bytes)
- Messages: {message_count} (events: {event_count})
- Span:     {session_start} → {session_end}

[Candidates surfaced]
- 5 candidates (top score: 8.5)

[Multi-select]
- Selected: 3 / 5
- Skipped:  2 (remain in raw dump for future recall)

[Distilled]
- Created: {N} new wiki pages
- Updated: {M} existing pages
- Hint overrides: {if any — list each (requested → landed)}
- Commit:  {sha} "wiki-session-ingest: {cli} {date} ({N} pages)"

[Summary]
{1-2 sentences on what was captured. Surface novel decisions or
contradictions worth user attention.}

[Suggested next]
→ kata:wiki-digest   (see the wiki's updated coverage)
→ kata:wiki-lint     (check for new orphans or stale cross-references)
```

## Known limitations (v1.11 MVP)

- **JSONL adapters are Claude Code + Codex CLI only.** Other 4 CLIs go
  through the LLM-dump path; sentinel-env detection for them is
  implementation-time polish, not blocking.
- **No cross-CLI session merge.** If you're working on the same task in
  Claude Code and Codex side-by-side, each session ingests
  independently — no automatic correlation.
- **No bulk historical re-ingest.** MVP targets the active session or
  one explicit `--session-id`. Sweeping last-30-days of sessions is
  deferred.
- **No secret scrubber.** A `--scrub-secrets` flag is on the v1.12
  candidate list; for now, eyeball the raw dump before sync.
- **No real-time streaming.** Skill is one-shot per invocation.

## See also

- `wiki-ingest` — runs the actual page-write per candidate (Phase 5
  delegates to it via `--page-type / --proposed-path /
  --evidence-anchors` hints shipped in v2.6.0)
- `wiki-import` — for bulk import of an existing markdown corpus
  (different problem: artifact ingest, not session ingest)
- `wiki-sync` — multi-machine sync; raw session dumps ship through this
  pipeline. Review for secrets before sync.
- `docs/PRD-v1.11-session-ingest.md` — full design + decision log.
