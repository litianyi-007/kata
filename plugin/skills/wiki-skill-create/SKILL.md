---
name: wiki-skill-create
description: "Generate a project-local skill that bridges kata's documentation loop (search/query/ingest) with the actual work pipeline of THIS project (code edit / test / build / human verify). Picks a pattern (issue-fix / feature-build / bug-debug / custom), captures project context (tech stack, build commands, kata wiki binding), renders a SKILL.md that encodes the 7-step work loop, runs static verification. v1.15 MVP. Closes the gap between 'what was figured out' and 'what kata's wiki knows.'"
user-invocable: true
argument-hint: "[--pattern <issue-fix|feature-build|bug-debug|custom>] [--supplement-action <source-search|web-search|doc-lookup|custom>] [--name <skill-name>] [--target <claude-code|codex|wiki>] [--no-ingest-after]"
---

# wiki-skill-create

Generates a **project-local skill** in the current project that wraps
kata's query/ingest with the project's actual work pipeline into one
closed loop. The generated skill is checked into the project repo and
becomes the default entry point for that kind of work in that project.

> Karpathy's lineage: the wiki compiles project memory once and keeps
> it current. This skill extends the loop into the work execution
> itself — making "consult kata before, file back after" the structural
> default in your project, not a discipline you have to remember.

## When to use

- A project recurringly does the same shape of work (bugfixes,
  feature ships, debugging) and you want kata's compounding effect to
  reach into that work
- The team adopts kata and asks "how do we wire kata into our actual
  daily workflow?" — generating a project-local skill is the answer
- An existing kata-aware loop in this project has drifted from how
  the team actually works — regenerate it against the current shape

## When NOT to use

- The work is a one-off with no recurring shape → don't bother with a
  skill, just use kata directly
- The project has no kata wiki bound and you don't intend to bind one
  → the generated skill's wiki-ingest step won't work; either run
  `wiki-init` first or skip
- You want a generic SKILL.md without kata loop integration → use
  Anthropic's standard skill-creator pattern instead; kata's version
  bakes the loop in

## Pre-flight (orientation guard)

Before phase 1, read the orientation files if not already done this
session:

```
read_file {wiki_path}/SCHEMA.md     # page types, tag taxonomy
read_file {wiki_path}/index.md      # what kata already knows
read_file {wiki_path}/log.md        # recent context (last 20 lines)
```

If no kata wiki is bound yet (`find_wiki_root` returns nothing), the
skill still works — the generated SKILL.md gets a placeholder for
`{{WIKI_PATH}}` and the user binds a wiki later via `wiki-init`. But
explicitly tell the user this is happening; they may want to bind
first.

## Phase 1 — Discover project context

Run the deterministic discovery script:

```bash
python {plugin_root}/scripts/skill_scaffold.py discover
```

Emits a JSON envelope:

```json
{
  "project_root": "F:/work/myapp",
  "git_root": "F:/work/myapp",
  "project_name": "myapp",
  "kata_wiki_path": "C:/Users/.../.llm-wiki/myapp",
  "tech_stack": ["nodejs", "typescript"],
  "test_command": "npm test",
  "build_command": "npm run build",
  "lint_command": "npm run lint",
  "existing_skill_homes": [".claude/skills"],
  "existing_generated_skills": [],
  "kata_version": "2.15.0",
  "available_patterns": ["bug-debug", "custom", "feature-build", "issue-fix"]
}
```

Read it before asking the user anything. The output drives the next
phase — what stack, what wiki, what skills already exist.

If `existing_generated_skills` lists any prior kata-generated skills,
**mention them** before phase 2 — the user might want to evolve an
existing skill instead of creating a new one. Don't auto-overwrite.

## Phase 2 — Pattern selection

Present the 4 MVP patterns to the user via **AskUserQuestion**:

```
Question: "Which work-loop pattern fits the kind of work this skill should drive?"
single-select
options:
  - label: "issue-fix"
    description: "Concrete bug or fix request → query kata → source search → minimal edit → test → human verify → wiki-ingest"
  - label: "feature-build"
    description: "Feature needing design → query kata → spec draft + wiki-spec preflight → implement → verify → ingest spec + impl learnings"
  - label: "bug-debug"
    description: "Systematic bug investigation → reproduce → query kata by symptom AND mechanism → root cause → fix + regression test → ingest lesson"
  - label: "custom"
    description: "None of the above fit — user describes their own loop; kata wraps it with the query / human-gate / file-back bookends"
```

Sanity-check the choice against the discovery output. If the user picks
`feature-build` but the project has no `wiki-spec` skill enabled or no
kata wiki bound, flag the mismatch before proceeding.

## Phase 2.5 — Pick a supplement action (v2.15.1+)

The kata query in Step 2 of the generated skill won't always have a
match. When it doesn't, the work loop pivots to a **primary source**
to fill the gap. That primary source is project-specific — code repos
use source search, materials projects use web search, doc-heavy
projects use documentation lookup, niche scenarios use custom.

`skill_scaffold.py discover` emits a `suggested_supplement_action`
based on detected context:

| Project signal | Suggested supplement |
|---|---|
| Tech stack detected (nodejs/python/rust/go/etc) | `source-search` |
| Project has `docs/` directory | `doc-lookup` |
| Mostly markdown, no manifest | `web-search` |
| None of the above | No suggestion — ask user |

Present the catalog via **AskUserQuestion** with the suggested option
first (recommended):

```
Question: "When kata's wiki returns no match for the loop's input, what's
          the primary source the agent should pivot to?"
single-select
options:
  - label: "source-search (Recommended)"          # if suggestion was source-search
    description: "Grep / Glob / Read against the project's source code. Best for code repos."
  - label: "web-search"
    description: "WebSearch + WebFetch against the public internet. Best for materials/research projects."
  - label: "doc-lookup"
    description: "Local docs/ + authoritative external doc sites (vendor docs, API references). Best for doc-driven projects."
  - label: "custom"
    description: "Describe your own supplement (data warehouse query, API probe, internal channel, etc.)"
```

If the user picks `custom`, collect six extra fields via short prompts:

- `CUSTOM_SUPPLEMENT_TITLE` — section heading for the supplement step
- `CUSTOM_SUPPLEMENT_DEFAULT` — what to do when kata had a hit
- `CUSTOM_SUPPLEMENT_ESCALATION` — what to do when kata missed (more
  aggressive)
- `CUSTOM_SUPPLEMENT_TOOLS` — which tools the agent should reach for
- `CUSTOM_SUPPLEMENT_OUTPUT` — what artifact to produce for Step 7

These pass to `skill_scaffold.py render` via `--var KEY=VALUE`.

**Each supplement-action snippet auto-encodes hit/miss escalation
language.** When kata has a hit, the supplement step is *verification*
(corroborate against primary source). When kata misses, the supplement
step is *load-bearing discovery* (primary diagnosis path; Step 7's
file-back becomes high-value as first-of-kind kata content). This
asymmetry is baked into every snippet — no extra prompting needed.

## Phase 3 — Capture skill metadata

Three short prompts (don't bundle into one giant AskUserQuestion — clarity
beats efficiency here):

1. **Skill name** — kebab-case, e.g. `fix-loop`, `feature-ship`, `debug-runbook`.
   The script validates `^[a-z][a-z0-9-]*$`; if the user gives something else,
   ask again rather than silently sanitizing.

2. **One-line description** — what the skill does. Used in commit
   messages, PR descriptions, and (for `custom` pattern) the SKILL.md's
   description field. Coach toward "Use when…" framing if the answer
   reads as first-person or imperative.

3. **Target placement** — show the default first:
   - `claude-code` (default) → `<project_root>/.claude/skills/<name>/SKILL.md`
   - `codex` → `~/.codex/skills/<name>/SKILL.md` (global to user)
   - `wiki` → `<wiki_path>/skills/<name>/SKILL.md` (wiki-scoped, rare)

   Use AskUserQuestion if the user hasn't already specified `--target`.

For `custom` pattern, ALSO collect:

- `DESCRIPTION` — same as the metadata prompt above
- `WHEN_TO_USE` — multi-line markdown bullet list
- `WHEN_NOT_TO_USE` — multi-line markdown bullet list
- `CUSTOM_STEPS` — the body of the loop, the user-defined middle phases
- `MANUAL_VERIFICATION` — one line: what should the human check
- `ARGUMENT_HINT` — short string for the SKILL.md frontmatter
- `INGEST_PAGE_TYPE` — `decision` / `lesson` / `feature` / `bug` etc.

Capture each by short user prompt. Don't generate placeholder values silently.

## Phase 4 — Render

Invoke the scaffold:

```bash
python {plugin_root}/scripts/skill_scaffold.py render \
    --pattern {pattern} \
    --supplement-action {supplement} \
    --skill-name {name} \
    --target {target}
```

For the `custom` pattern, append `--var KEY=VALUE` for each user-provided
field. Use **single-quoted strings** in shell to preserve any special chars.

If the user wants a preview first, use `--dry-run` — it emits the rendered
preview (first 500 chars) without writing the file. Useful when the user is
on the fence about content.

Read the script's emit output for the resolved `target_path`. Show it to
the user before claiming success.

## Phase 5 — Verify

```bash
python {plugin_root}/scripts/skill_scaffold.py verify {target_path}
```

Emits a check breakdown. If `ok: false`, surface the failures clearly:

- Unresolved `{{VAR}}` → re-render with the missing `--var KEY=VALUE`
- First-person language → ask user to rephrase the description
- Missing sentinel → likely a template bug; check the template file
- Bad name → user typo; restart phase 3

Don't auto-fix. The user makes the call.

## Phase 6 — Print next-steps

Tell the user how to invoke the new skill:

```
Generated: <project>/.claude/skills/<name>/SKILL.md

Invoke in Claude Code:
  /your-skill-name "<input>"

Or in Codex CLI (if --target codex):
  Just describe the work; Codex routes to the skill by description match.

The generated skill assumes:
  - Kata wiki bound at: <wiki-path>
  - Test command: <test-cmd>
  - Build command: <build-cmd>

Edit <skill-md-path> to customize the body as your project's work
shape evolves. The sentinel comment at the bottom is the only
machine-managed part — preserve it for future kata tooling.
```

## Phase 7 — Optional: wiki-ingest the generated skill

Ask the user (one prompt):

> "Ingest this new skill into the kata wiki so future queries can find
> it? (y/n, default y)"

If yes:

```bash
/kata:wiki-ingest <target_path> \
    --page-type=feature \
    --evidence-anchors=<git-commit-or-PR-link>
```

This is the META layer of the loop: the skill that closes work loops
is itself filed back into kata, so the wiki knows which projects have
adopted which patterns. Skip if the user has no wiki bound yet (run
this manually later after `wiki-init`).

If the user passed `--no-ingest-after`, skip the prompt and don't ingest.

## Output format

```
[Operation] wiki-skill-create | <pattern> → <skill-name>

[Discovery]
- Project:        <name> at <root>
- Tech stack:     <list>
- Kata wiki:      <path or "not bound yet">
- Existing skills: <count>

[Pattern]
- Selected:       <pattern>
- Template:       <template-path>

[Generated]
- Created: <target-path> (<size> bytes)
- Verification: <ok|N failures>

[Customization tips]
- Edit <target-path> to refine the loop's middle phases
- The sentinel comment marks this as kata-generated

[Wiki-ingest]
- <skipped | done with commit <sha>>

[Suggested next]
→ Run /<skill-name> on a real task in this project to dogfood the loop
→ /kata:wiki-digest to see the new skill page in the wiki
```

## Customization after generation

The generated SKILL.md is now **owned by the project**, not by kata.
The user edits it as their project's work shape evolves:

- Add a deploy phase between test and verify
- Replace `wiki-ingest` with `wiki-session-ingest` for richer
  transcript capture
- Adjust which kata search command to use (e.g. `wiki-graph` for
  structure-heavy work, `wiki-search` for text-heavy)
- Add project-specific guards (CI gate, code review trigger)

The sentinel comment `<!-- kata:generated-skill ... -->` is the only
part kata's future tooling cares about. Preserve it (or delete it
intentionally if the skill has diverged enough that kata shouldn't
track it as generated).

## Known limitations (v1.15 MVP)

- **No auto-update on kata version bumps.** A v2.15.0-generated skill
  doesn't auto-refresh against v2.16 templates. v1.16 will add a
  `--update <name>` workflow that preserves user-added sections.
- **Single-target render per invocation.** To put the skill in both
  `.claude/skills/` and `~/.codex/skills/`, run twice with different
  `--target`. A `--target both` shortcut is future polish.
- **Codex-format transformation NOT done.** Generated skills follow
  Anthropic's SKILL.md format. Codex CLI's existing
  `install_codex_skills.py` handles transformation if needed; this
  skill doesn't take on that surface.
- **No live execution test of the generated skill.** Verification is
  static (frontmatter parse, sentinel, placeholders). To smoke-test
  the generated skill, the user runs it on a real input.

## See also

- `docs/PRD-v1.15-work-loop-bridge.md` — full design + rationale
- `wiki-session-ingest` — post-hoc capture (complements this skill's
  before-and-during reach)
- `wiki-spec` — spec corpus preflight (referenced by `feature-build`
  pattern)
- `superpowers:writing-skills` — Anthropic's general SKILL.md
  conventions that v1.15's generated skills adhere to
