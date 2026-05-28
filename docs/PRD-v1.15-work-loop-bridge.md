---
spec_relationships:
  - kind: extends
    target: docs/PRD-v1.11-session-ingest.md
    note: |
      v1.11 captures what was learned in a CLI session AFTER the work is
      done — it is post-hoc. v1.15 acts BEFORE the work starts and during
      the work, making the kata-aware execution loop the default shape of
      the work itself, not an afterthought. Both ship complementary
      bridges between transcript / execution and the wiki.
  - kind: refines
    target: docs/PRD-v1.13-spec-history-management.md
    note: |
      v1.13 closed the loop on the spec corpus — new specs must answer
      for prior specs. v1.15 closes the loop on the actual code work
      that follows a spec. Together they cover "what was decided" and
      "what was done about it" as two sides of the same kata reach into
      AI-paired engineering.
  - kind: references
    target: docs/PRD-v1.6-autodreaming.md
    note: |
      Auto-dreaming surfaces dormant pages on relevance. v1.15
      generated skills explicitly run wiki-search and wiki-graph as
      Step 2 of every work-loop, which is the durable-on-demand
      complement to dreamer's periodic resurfacing.
---

# PRD v1.15 — Work-Loop Bridge (`wiki-skill-create`)

Status: Draft v1
Date: 2026-05-20
Author: surebeli

## The structural gap

Kata's documentation closed loop is real and complete:

```
ingest → cross-link → query → file-back ↻
```

But the **actual work** — searching source, reading code, editing files,
running tests, verifying the fix, deciding it's done — happens **outside**
this loop. Whether to re-enter the loop after work (by ingesting the
result) is voluntary. Whether to re-enter it before work (by querying
prior wiki knowledge first) is voluntary.

The result is predictable: kata's compounding effect depends on
individual discipline. When a user is new, distracted, or under time
pressure, the loop opens. Pages that should have been written stay in
chat memory and evaporate. Decisions that were already filed don't get
consulted because querying the wiki was one extra step nobody required.

**The fix is not to make kata execute the work itself** — that's an
infinite compatibility problem (every project has its own tech stack,
build commands, test runners, deployment pipeline). The fix is to
**structurally encode the work-loop as a skill that lives in the
project**, so the agent doing the work follows the loop by default —
because the loop is the SKILL.md the agent reads at the start of work.

## The proposal

A new kata skill, `wiki-skill-create`, that **generates a project-local
skill** wrapping kata's query/ingest capabilities with the project's
actual work pipeline into one closed loop. The generated skill is
checked into the project's git repo and becomes the default entry
point for that kind of work in that project.

The 7-step canonical loop the generated skill encodes:

```
1. Input problem statement
2. Query kata wiki (search + graph) for prior knowledge
3. Source search + verification of current behavior
4. Modify code (if needed)
5. Test / build / manual verify
6. Human confirmation gate
7. File back to kata wiki (wiki-ingest the result)
```

Steps 2 and 7 close the loop. Step 6 ensures human authority over what
counts as "done" (no silent declarations of victory by the agent).

## Strategic positioning

Kata's reach map after v1.15:

```
Phase 1 — AI-paired engineering
  ├─ Doc loop closed (v1.1–v1.10)
  ├─ Spec drift defended (v1.13 SHM)
  └─ Work execution loop closed (v1.15 — this PRD)        ← NEW
Phase 2 — Team spec authoring (designed, not built)
```

This is the third concrete reach into AI-paired engineering, parallel
to documentation (the original) and spec corpus management (v1.13).
After v1.15 ships, kata has a story for the three places where
knowledge leaks happen in AI-paired engineering: when a source enters
(ingest), when specs accumulate (preflight), and when work is executed
(the work loop). Each leak point now has a skill.

## Naming

The new kata skill: **`wiki-skill-create`**.

- Matches the `wiki-*` prefix convention used by all 17 existing kata
  skills.
- Verb-first (`create`) per CSO naming guidance from
  `superpowers:writing-skills`.
- Mirrors Anthropic's general "skill-creator" pattern; users who know
  that pattern will recognize what this does.

The generated skills are named by the user (kebab-case, validated by
the scaffolding script). Suggested names per pattern:
`feature-ship-loop`, `bugfix-loop`, `debug-loop`, etc. The pattern is
not hardcoded into the generated skill's name — the user can name it
whatever fits their project's culture.

## Foundation: built on Anthropic SKILL.md conventions

Generated skills follow Anthropic's standard SKILL.md format:

- Frontmatter fields: `name` (kebab-case letters/numbers/hyphens),
  `description` (third person, starts with "Use when…"),
  `user-invocable` (bool), `argument-hint` (optional string).
- Max 1024 chars in frontmatter.
- Body in markdown with `##` section headings.

**No kata-specific frontmatter fields are added.** The generated skill
is portable to any environment that consumes SKILL.md — Anthropic
Claude Code, Codex CLI, or the standalone copy-paste path. Kata-
specific information lives in body sections (specifically, the kata
wiki path, the wiki-ingest invocation in step 7, and a sentinel HTML
comment for provenance tracking).

The sentinel comment, placed at the bottom of every generated SKILL.md:

```markdown
<!-- kata:generated-skill pattern={pattern} kata_version={version} generated_at={iso-date} -->
```

This lets `wiki-skill-create` later detect, list, or regenerate
kata-authored skills under a project without touching skills the user
hand-wrote.

## Pattern catalog (MVP — 4 patterns)

Each pattern is a `.md.tmpl` template under
`plugin/skills/wiki-skill-create/templates/`. The MVP ships 4. Each
pattern is **one template file** — no inheritance, no partials. Adding
a new pattern means dropping a new `.md.tmpl` file (one-line change to
`PATTERN_REGISTRY` in the scaffold script registers it).

### Pattern 1 — `issue-fix`

The canonical loop. For: a specific reported issue, a request to "fix
X," a small-to-medium code change tied to a problem statement.

Encodes the 7 steps exactly as listed above. No spec phase, no
extensive design discussion — the assumption is the work is concrete
enough to start coding after the kata query lands.

Middle phases (steps 3–5): code search, minimal modification, run the
project's test + build commands.

### Pattern 2 — `feature-build`

For: a feature that needs design before code. Adds a spec phase
between the kata query and the code change.

Middle phases:
- 2.5. Draft a spec (in the project, not yet ingested)
- 2.6. Run `wiki-spec preflight` against the bound kata wiki to surface
       related prior specs (Phase 0 / Phase 2 of v1.13 SHM)
- 2.7. Refine spec based on preflight findings; declare
       `spec_relationships:` for the prior specs that matter
- 3.   Then implement → test → human verify → wiki-ingest BOTH the
       spec (as a `decision` or `feature` page) AND the impl learnings
       (as a `lesson` or `feature` page)

This is the natural shape of multi-step feature work in a team that
uses kata for spec corpus management. v1.15 is the execution-layer
counterpart to v1.13's spec-layer story.

### Pattern 3 — `bug-debug`

For: a bug that needs systematic investigation before fixing. The
"reproduce → root-cause → fix → regression test" shape.

Middle phases:
- 3.1. Reproduce the bug (specific steps, ideally automated)
- 3.2. Identify the root cause (not just symptom)
- 3.3. Search kata for similar prior bugs by symptom OR root cause
       (the prior bug may have a different surface)
- 3.4. Fix
- 3.5. Add a regression test that fails before the fix and passes
       after
- 5–7. Standard test/verify/file-back flow

Step 7 always files the bug as a `lesson` page with the root cause as
the dominant content (so the next agent searching for "similar
symptom" finds the structural shape, not just the surface
description).

### Pattern 4 — `custom`

For: anything the first three don't fit. The orchestrator prompts the
user for their loop description — they list their steps in natural
language — and the template substitutes them into a standard
scaffolding (frontmatter, output-format block, sentinel comment).

The custom pattern's template has fewer hardcoded sections and more
placeholder regions. The agent invoking `wiki-skill-create` is
responsible for shaping the body to the user's description; the
scaffold provides the wrapping.

This is the escape hatch: rather than force a 5th, 6th, 7th template
into MVP, the custom path covers the long tail.

## Placement of generated skills

Three placement options, picked per invocation via `--target`:

| `--target` value | Path | Use when |
|---|---|---|
| `claude-code` (default) | `<project>/.claude/skills/<name>/SKILL.md` | Project is git-managed, team uses Claude Code, you want the skill to ship with the repo |
| `codex` | `~/.codex/skills/<name>/SKILL.md` | User wants the skill globally available across all Codex CLI projects |
| `wiki` | `<wiki_path>/skills/<name>/SKILL.md` | Niche — the skill is wiki-scoped, not project-scoped (uncommon; documented as an edge case) |

The default is **project-local Claude Code skill** because that's
where the generated skill knows the most (build commands, test
commands, project conventions, the bound kata wiki). Globalizing too
early loses that specificity.

Project-local skills are git-tracked by default. The generated SKILL.md
goes into version control alongside the project source. This is
deliberate: the skill represents *how this project does AI-paired work
with kata*, which is a piece of team knowledge that benefits from
versioning, PR review, and history.

## Wiki linkage — two layers

### Layer 1: generated skills file back

Every generated skill encodes `wiki-ingest` as step 7. The agent that
follows the skill sees this in the SKILL.md and runs it. This is the
*structural* layer: the loop is closed because the skill mandates it,
not because the user remembers to.

The exact ingest invocation is parameterized by `{{WIKI_PATH}}` and
`{{INGEST_HINTS}}` (page type, evidence anchors) at render time. If
the project's bound wiki is unknown, the template falls back to a
`<your-kata-wiki-path>` placeholder that the user fills in once before
first use.

### Layer 2: the meta-skill files itself back

After `wiki-skill-create` generates a SKILL.md, it can optionally run
`wiki-ingest` against the new file. This files the *creation event*
itself into the kata wiki as a `feature` page: "this project added a
work-loop skill on date X, pattern Y, name Z."

Why this matters: kata's wiki now knows which projects have closed
their work loops and how. Future queries against the wiki can return
"3 of your projects have an issue-fix loop; here are their skills" —
the meta-knowledge of execution-loop adoption becomes searchable
within kata itself.

This second layer is opt-in (a question the orchestrator asks at end
of run), not mandatory. The user might be generating skills in a
project that doesn't have a kata wiki bound yet, or they might want
to commit the skill first and ingest separately.

## Discovery: what context does the scaffold detect?

The `skill_scaffold.py discover` subcommand inspects the project root
and emits a JSON envelope:

```json
{
  "project_root": "F:/work/myapp",
  "git_root": "F:/work/myapp",
  "project_name": "myapp",
  "kata_wiki_path": "C:/Users/.../.llm-wiki/myapp",
  "kata_wiki_id": "abc12345-...",
  "tech_stack": ["nodejs", "typescript"],
  "test_command": "npm test",
  "build_command": "npm run build",
  "lint_command": "npm run lint",
  "existing_skill_homes": [".claude/skills"],
  "existing_skills": [],
  "kata_version": "2.15.0"
}
```

Detection is heuristic and deterministic:

| Tech stack signal | Detection rule | Default commands |
|---|---|---|
| Node.js / npm | `package.json` exists | `npm test`, `npm run build`, `npm run lint` (filtered by `scripts` block in package.json) |
| Python | `pyproject.toml` or `setup.py` | `pytest`, `python -m build`, `ruff` |
| Rust | `Cargo.toml` | `cargo test`, `cargo build`, `cargo clippy` |
| Go | `go.mod` | `go test ./...`, `go build ./...`, `go vet ./...` |
| Multiple | All detected stacks listed | First non-conflicting default per command |
| None | Empty list | Placeholders like `<your-test-command>` |

When a project has multiple stacks (e.g., a Go backend + TS frontend),
the user is asked once which is "primary" for this skill's purpose;
the answer drives the test/build command substitution.

If kata wiki binding is detected (via `find_wiki_root()` from
`wiki_lib.py` — same resolution order as every other kata skill), the
`kata_wiki_path` field populates and templates substitute it directly.
If not, templates render the literal placeholder
`<bind-a-kata-wiki-via-wiki-init-first>`.

## Verification (after render)

`skill_scaffold.py verify <path>` runs static checks:

1. **Frontmatter parses** as YAML (uses the kata-stdlib subset parser)
2. **Required fields present**: `name`, `description`
3. **Name format valid**: `^[a-z][a-z0-9-]*$`
4. **Frontmatter ≤ 1024 chars** (Anthropic limit)
5. **Description starts with "Use when"** (CSO guidance)
6. **Description in third person** (no first-person pronouns — `\b(I|me|my|we|our)\b` regex check)
7. **Sentinel comment present** (the `<!-- kata:generated-skill ... -->` line)
8. **No unresolved `{{VAR}}` placeholders** (catches incomplete substitution)
9. **`argument-hint` present if `user-invocable: true`** (best practice)

Verification returns structured output. Failures don't auto-fix; the
user sees what's wrong and chooses whether to regenerate. This matches
the spec_preflight + spec_propagate pattern from v1.13: deterministic
scripts emit, agent + user decide.

## Open questions

### OQ1: Should generated skills auto-update with kata version bumps?

When kata v2.16 ships, a project's `.claude/skills/feature-ship-loop/SKILL.md`
was generated against v2.15 templates. Does kata offer a `wiki-skill-create
--update <name>` to regenerate the skill against the new templates while
preserving customizations?

Lean: yes, but **v1.16 work**. MVP doesn't ship this; users who
customized their generated skills shouldn't worry about auto-overwrite.
v1.16 adds a sentinel-aware re-render that preserves user-added
sections (anything outside the sentinel-delimited templated zones).

### OQ2: Should generated skills be allowed under `~/.codex/skills/` *and* `.claude/skills/` simultaneously?

Per `--target`, the MVP writes to one place. A user wanting both runs
the command twice with different `--target` values. Reasonable for
MVP; future polish could ship a `--target both` shortcut.

### OQ3: Cross-CLI portability

The generated SKILL.md is Anthropic-format. Codex CLI consumes its
own slightly-different SKILL convention (multiple files, different
frontmatter set). Does the scaffold render *one* SKILL.md that works
for both, or branch on `--target`?

Decision for MVP: render *one* SKILL.md that adheres to Anthropic's
standard format. Codex CLI's `install_codex_skills.py` (already in
kata) can transform if needed; v1.15 doesn't take on that
transformation surface.

### OQ4: Sentinel comment as the only kata-identifier

The sentinel HTML comment is the only signal that a skill was
generated by kata. Should we also write a separate
`.kata-skill-metadata.yaml` next to each generated SKILL.md for
machine-readable provenance?

Lean: no for MVP. The sentinel comment is parseable (key=value pairs,
stable format) and avoids a second file per skill. v1.16+ may revisit.

## Tests (MVP)

In `tests/run_smoke.py`:

- **T-skill-create-1** — `discover` on a JS fixture returns
  `tech_stack=["nodejs"]`, `test_command="npm test"`,
  `build_command` populated from `scripts.build`.
- **T-skill-create-2** — `render` of `issue-fix` template against a
  fixture context produces a valid SKILL.md (all 9 verification
  checks pass).
- **T-skill-create-3** — `render` of all 4 patterns against the same
  fixture (parametric run): each produces a passing SKILL.md with
  distinct middle-phase content.
- **T-skill-create-4** — `verify` rejects a malformed SKILL.md with
  unresolved `{{VAR}}`; rejects one with first-person language;
  rejects one with missing frontmatter.
- **T-skill-create-5** — Cross-platform path: render under both
  `.claude/skills/` and `~/.codex/skills/`-style absolute paths;
  sentinel comment present in both.

## Risks

| Risk | Mitigation |
|---|---|
| Generated skills bitrot as kata changes | Sentinel version tag + future `--update` workflow (v1.16); MVP users accept the bitrot risk for now |
| Project-local default surprises users who expected wiki-local | `--target` is explicit; orchestrator prints the chosen path before writing |
| Custom pattern's freeform body invites low-quality skills | Verification's `description` and frontmatter checks catch the worst; the body shape is the user's call |
| Tech-stack detection misses multi-language repos | Multi-stack is detected as a list; user picks primary; placeholders left for unmatched cases |
| Confusion between Anthropic's general "skill-creator" and kata's `wiki-skill-create` | Doc clearly: kata's is the kata-flavored specialization; both can coexist; user picks based on whether kata loop integration is wanted |

## Out of scope

- **Auto-updating generated skills on kata bumps** — see OQ1; v1.16
- **Cross-CLI skill format transformation** — see OQ3; Codex
  conversion stays in `install_codex_skills.py`
- **Sharing patterns across users (a pattern marketplace)** — interesting
  long-tail idea; not MVP
- **Auto-running the generated skill on a sample input as a smoke
  test** — useful but adds a "execute arbitrary code" risk surface;
  manual smoke for MVP

## Related

- [[PRD-v1.11-session-ingest]] — files transcript-born knowledge AFTER
  work; v1.15 reaches BEFORE and DURING work; the two close opposite
  ends of the same execution gap
- [[PRD-v1.13-spec-history-management]] — spec corpus integrity;
  v1.15 reaches into the *implementation* layer that follows specs
- `superpowers:writing-skills` (Anthropic) — the general SKILL.md
  writing conventions that v1.15 builds on
