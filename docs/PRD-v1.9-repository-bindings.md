# PRD v1.9 — Branch-aware Repository Bindings

Status: Draft
Date: 2026-05-08

## Context

Code documentation wikis age differently from research or personal wikis. Many
pages are true only for a specific repository, branch, and commit range. During
the NECallKit dogfood, Electron camera/switch knowledge depended on files in
`packages/`, `desktop/core/`, Electron wrapper code, and native staging scripts.
Those facts were branch-scoped: a feature branch could be stale or experimental
while `master` remained canonical.

kata needs first-class repository metadata so agents can answer:

- Which repository and local checkout does this wiki describe?
- Which branch was a page verified against?
- Did a code diff make this page stale?
- When a feature branch lands, how do we promote its wiki knowledge to the
  default branch without losing branch history?

## Goals

- Register repositories with remote URL, local path, default branch, and active
  branch.
- Allow switching the wiki's repository context without implicitly changing the
  user's git checkout.
- Let pages declare branch-scoped code bindings: files, globs, symbols,
  contracts, tests, and verified commits.
- Produce impact reports from branch diffs that identify pages likely to need
  review.
- Support promoting page bindings from a feature/base branch to the default
  branch after merge.
- Preserve raw history and query history even when a branch is retired.

## Non-goals

- No automatic documentation rewrite from code diffs.
- No mandatory AST index in the MVP.
- No automatic `git checkout` by default.
- No replacement for git workflow, PR review, or CI.
- No assumption that the default branch is named `main` or `master`.

## Data Model

### `.wiki-repos.yaml`

Each wiki may include a repository registry at its root:

```yaml
version: 1
active_repo: necallkit
repositories:
  - id: necallkit
    remote_url: https://github.com/netease-kit/NECallKit.git
    local_path: <workspace>/project/NECallKit
    default_branch: master
    active_branch: specs/002-electron-callkit
    branches:
      - name: specs/002-electron-callkit
        base_branch: master
        base_commit: abc1234
        head_commit: def5678
        status: working
      - name: master
        head_commit: 123abcd
        status: canonical
```

Repository fields:

- `id`: stable short identifier used by page bindings.
- `remote_url`: canonical remote used for identity checks and reporting.
- `local_path`: user's local checkout path.
- `default_branch`: stable baseline branch for canonical wiki knowledge.
- `active_branch`: default branch context for import/query/impact operations.
- `branches`: known branch snapshots and lifecycle status.

Branch statuses:

- `canonical`: stable branch that represents durable wiki truth.
- `working`: active feature or bugfix branch.
- `merged`: branch knowledge has been promoted to another branch.
- `retired`: branch is no longer active, but history remains queryable.
- `stale`: local metadata no longer matches repo state or verified commits.

### Page Frontmatter

Code-bound pages can declare `code_bindings`:

```yaml
code_bindings:
  - repo: necallkit
    branch_scope: specs/002-electron-callkit
    base_branch: master
    verified_commit: def5678
    code_refs:
      - packages/callkit-runtime-electron/src/runtime.ts
      - desktop/core/src/call_controller.cpp
      - desktop/core/src/signaling/signaling_handler.*
    symbols:
      - switchCallType
      - onVideoAvailable
      - ApplyResolvedSwitchCallType
    contracts:
      - "onCallTypeChange handles call type; onVideoAvailable/onVideoMuted only update video availability"
      - "audio/video switching must not accidentally mutate local camera preference"
    tests:
      - node --test packages/callkit-runtime-electron/test/runtime-contract.test.ts
      - node --test Electron/scripts/test/switch-call-type-control-source.test.js
```

Rules:

- `branch_scope` is required for branch-aware bindings.
- `verified_commit` records the commit where the page was last confirmed.
- Multiple bindings are allowed when a page spans repositories or branches.
- Pages without `code_bindings` behave like normal wiki pages.

## User Workflows

### Register A Repository

```text
wiki-repo add --id necallkit \
  --remote https://github.com/netease-kit/NECallKit.git \
  --local <workspace>/project/NECallKit \
  --default-branch master
```

Expected behavior:

- Validate that `local_path` exists and is a git repository.
- Read current branch and head commit.
- Write or update `.wiki-repos.yaml`.
- Do not mutate project files.

### Switch Wiki Context

```text
wiki-repo switch necallkit specs/002-electron-callkit
```

Default behavior:

- Update `.wiki-repos.yaml` `active_repo` and `active_branch`.
- Record branch snapshot if missing.
- Do not run `git checkout`.

Explicit checkout behavior:

```text
wiki-repo switch necallkit specs/002-electron-callkit --checkout
```

With `--checkout`, the command must refuse if the repo has a dirty working tree
unless the user explicitly allows a safe stash or chooses to abort.

### Impact Detection

```text
wiki-impact --repo necallkit --base origin/master --head HEAD
```

MVP matching:

- Read changed files from `git diff --name-only`.
- Match changed paths against page `code_refs` and globs.
- Search changed hunks for declared `symbols`.
- Score impact by path match, symbol match, test match, and branch mismatch.

Output example:

```text
Page: bugs/electron-camera-switch-microphone-state-regression-bugfix-set.md
Repo: necallkit
Branch: specs/002-electron-callkit
Base: origin/master@abc1234
Head: HEAD@def5678
Impact: high
Reasons:
- desktop/core/src/call_controller.cpp changed
- symbol ApplyResolvedSwitchCallType changed
- page verified_commit is older than current head
Action:
- review required before marking verified on this branch
```

Impact actions:

- `none`: no meaningful overlap.
- `review`: page may need human/agent review.
- `update`: page likely needs a wiki edit.
- `promote`: page can move from branch-scoped to default branch after merge.

### Promote Branch Knowledge

After a feature branch lands:

```text
wiki-repo promote --repo necallkit \
  --from specs/002-electron-callkit \
  --to master \
  --merge-commit 789abcd
```

Expected behavior:

- Update matching page `branch_scope` from source branch to target branch when
  the page is intended to become canonical.
- Set `verified_commit` to the merge commit or a later verification commit.
- Mark the source branch as `merged`.
- Append a `log.md` entry listing promoted pages.
- Preserve raw imports and branch query pages for auditability.

Promotion should be explicit. A branch merge in git does not automatically mean
all branch-scoped wiki conclusions are canonical.

## Safety Rules

- Context switch is metadata-only unless `--checkout` is explicitly passed.
- Checkout refuses dirty repositories by default.
- Impact reports are advisory; they never rewrite wiki pages automatically.
- `default_branch` is user-configured; never infer `main` or `master`.
- If remote URL in `.wiki-repos.yaml` does not match local `origin`, warn and
  require confirmation before impact or promote.
- If the active branch metadata does not match the local checkout, report the
  mismatch instead of silently proceeding.

## Interaction With Existing Skills

- `wiki-init`: may ask whether to create `.wiki-repos.yaml` when run inside a
  git repository.
- `wiki-config`: can show and edit repository registry fields.
- `wiki-import` / `wiki-ingest`: attach current active repo/branch metadata when
  imported sources are code-bound.
- `wiki-query`: cites branch scope when using code-bound pages.
- `wiki-lint`: reports stale `verified_commit`, missing local paths, unknown repo
  ids, and branch metadata mismatches.
- `wiki-sync`: treats `.wiki-repos.yaml` as normal versioned wiki metadata.

## MVP Implementation Shape

1. Add schema validation for `.wiki-repos.yaml`.
2. Add `repo_registry.py` for read/write/status operations.
3. Add `wiki-repo` skill with `add`, `status`, `switch`, and `promote`.
4. Add `wiki-impact` script/skill using path/glob/symbol matching.
5. Extend `wiki-lint` to validate `code_bindings` and repository references.
6. Update README with the code-bound wiki workflow.

## Dogfood Acceptance Criteria

The NECallKit dogfood should demonstrate:

- Repository registered with local path, remote URL, and non-assumed default
  branch.
- Electron camera/switch pages declare code bindings for runtime, desktop core,
  signaling, and Electron staging scripts.
- A diff touching `ApplyResolvedSwitchCallType` or `onVideoAvailable` produces a
  high-impact report for the relevant wiki pages.
- Switching wiki context to a feature branch does not checkout the local repo.
- After a branch lands, `promote` updates branch-scoped pages to the default
  branch and records the transition in `log.md`.

## Open Questions

- Should `code_bindings` be part of required frontmatter, or remain optional
  custom frontmatter validated only when present?
- Should branch query pages be stored under `queries/branches/{branch}/` or stay
  flat with branch in frontmatter?
- Should impact reports be stored under `raw/external/wiki-impact/` or
  `reports/impact/` outside the compiled page graph?

