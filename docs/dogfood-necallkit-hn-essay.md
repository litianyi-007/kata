# NECallKit Dogfood Log — HN Essay Evidence

> Running log for the first real kata dogfood on
> `<workspace>\project\NECallKit`.
>
> Primary goal: collect durable evidence, failure modes, user language, and
> story material for a future Hacker News essay about kata.

## Status

**Started:** 2026-05-08 03:08 +08:00  
**Dogfood host:** `<dogfood-host>`  
**kata repo:** `<workspace>\ai\kata`, branch `main`  
**Target project:** `<workspace>\project\NECallKit`, branch
`002-electron-callkit-reuse-enhance`

This is the first end-to-end dogfood run against a large, real, multi-platform
SDK monorepo rather than a synthetic or narrowly scoped fixture.

## Roles

**Maintainer / domain owner:** user

- Provides product judgment, source priorities, and acceptance signals.
- Calls out what would be meaningful to a real NECallKit maintainer.
- Decides which findings are worth preserving as public essay material.

**Agent:** mentor, assistant, and adviser

- Guides the dogfood flow step by step.
- Performs repository reading, wiki operations, synthesis, and bookkeeping.
- Records friction, surprising outcomes, gaps, and reusable quotes.
- Separates product observations about kata from facts about NECallKit.

## Why NECallKit Is A Good Dogfood Case

NECallKit is a realistic stress case for kata because it is not a toy repo:

- It is a multi-platform SDK monorepo covering Android, iOS, Flutter,
  HarmonyOS, Web, MiniProgram, uni-app, Desktop, and Electron.
- It has both long-lived architecture facts and recent feature work.
- It already contains high-signal human-written docs:
  `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `TASKS.md`, `TRACKER.md`, and
  `docs/`.
- It has layered AI-working conventions, including SDD workflows, lessons,
  PRDs, bugfix writeups, and task tracking.
- It should reveal whether kata can turn an existing project corpus into a
  useful compiled knowledge base instead of another chat transcript.

## Initial Read-Only Findings

Observed before any dogfood mutation:

- No `.llm-wiki.yaml` or `.kata.yaml` binding exists in the NECallKit repo.
- NECallKit has a dirty or warning-prone git status command because Git cannot
  access `~/.config/git/ignore`; no changed files were printed
  in the captured output.
- The repo has substantial `node_modules/` content under `Electron/`, so any
  import or source scan must explicitly avoid dependency directories.
- The top-level documentation already describes platform matrix, publishing
  flows, repository structure, and AI-agent operating rules.

## Dogfood Questions

These questions guide the run and should be answered with concrete evidence:

1. Can kata bootstrap a useful project wiki from a large existing monorepo
   without overwhelming the user?
2. Does `wiki-import` correctly separate durable project knowledge from raw
   source material?
3. Does `wiki-query` answer real maintainer questions better after ingestion
   than a fresh chat over the repo?
4. Which parts of the workflow feel magical, which feel slow, and which need
   sharper defaults?
5. What exact story can be told publicly: what was hard before, what changed,
   and why a filesystem wiki is the right artifact?

## Operating Rules For This Dogfood

- Keep a written log in this file after each meaningful step.
- Prefer read-only reconnaissance before touching NECallKit.
- Do not import generated dependencies, build outputs, caches, or vendored
  package folders.
- Treat SCHEMA.md as the contract once the target wiki is initialized.
- Capture user reactions and maintainer judgments verbatim when possible.
- Separate three layers in the notes:
  kata product behavior, NECallKit domain facts, and essay narrative.

## Planned Flow

1. Decide wiki location and binding strategy for NECallKit.
2. Initialize the wiki with a schema fitted to a multi-platform SDK monorepo.
3. Import a small, high-signal starter corpus before attempting any broad scan:
   top-level docs, architecture, task tracker, and selected `docs/` material.
4. Run maintainer-grade queries and record answer quality.
5. File valuable query syntheses back into the wiki.
6. Expand ingestion only after the starter loop proves useful.
7. Extract essay material: before/after, screenshots or command output where
   useful, friction list, and the strongest thesis.

## Essay Material Ledger

### Candidate Thesis

An LLM wiki turns an AI assistant from a clever reader into a maintainer of a
living project memory: the useful output is not the answer in chat, but the
edited knowledge base that future agents and humans can reuse.

### Evidence To Collect

- Time from first project scan to first useful wiki answer.
- Number and type of pages created from the starter corpus.
- Examples where the wiki finds cross-platform structure better than a raw repo
  search.
- Examples where the wiki records contradictions, stale assumptions, or gaps.
- Friction in setup, schema design, import scoping, and query filing.
- User decisions that improved the wiki and would have been missed by full
  automation.

### Potential HN Angles

- "I stopped using chat history as project memory and started compiling a wiki."
- "RAG retrieves; a wiki compounds."
- "The filesystem is the database, git is the audit log, Obsidian is the IDE,
  and the LLM is the maintainer."
- "What happened when I pointed this at a real multi-platform SDK monorepo."

## Running Log

### 2026-05-08 03:08 +08:00 — Start

**Action:** Established the dogfood target and captured initial repository
state.

**Observed:**

- Target project path: `<workspace>\project\NECallKit`
- Target branch: `002-electron-callkit-reuse-enhance`
- kata branch: `main`
- No explicit wiki binding files found in NECallKit.
- NECallKit is a strong first dogfood target because it combines multi-platform
  architecture, release workflows, SDD process docs, and recent Electron/Web
  shared-layer work.

**Advisor note:**

Start with a narrow starter corpus. Importing the entire monorepo immediately
would test scanning volume more than product value. The first useful essay
material should come from whether kata helps a maintainer understand and
operate the project faster.

**Next recommended step:**

Choose wiki path and initialize:

```powershell
py -3 <workspace>\ai\kata\plugin\scripts\wiki_init.py `
  --path <workspace>\project\NECallKit\.wiki `
  --domain "multi-platform audio/video call SDK monorepo"
```

Alternative: use a global wiki path such as
`~/.llm-wiki/necallkit-dogfood` and add a lightweight binding file in the
project. The global path is cleaner if the wiki should outlive or compare
multiple worktrees; the project-local `.wiki/` path is easier to inspect in
place.

### 2026-05-08 03:10 +08:00 — Windows Python Entry Point Friction

**Action:** Checked `wiki_init.py --help` before running initialization.

**Observed:**

- `python plugin\scripts\wiki_init.py --help` failed with a non-ASCII encoding
  error.
- `py -3 plugin\scripts\wiki_init.py --help` succeeded on Python 3.14.0.

**Product note:**

Windows examples should prefer `py -3` or explicitly document that the `python`
launcher must resolve to Python 3 with UTF-8 source handling. This is a small
setup paper cut, but it appears before the user sees any product value.

**Essay note:**

This is useful evidence for the essay because dogfooding immediately found a
real platform assumption: the system is filesystem-native and script-backed, so
cross-platform command examples matter as much as the LLM prompt.

### 2026-05-08 03:20 +08:00 — Wiki Initialized And First Directory Imported

**Action:** User completed wiki initialization, git baseline, first import, and
remote push.

**Observed:**

- Wiki path: `~\.llm-wiki\NECallKit`
- Baseline commit: `a7cec09 wiki: init`
- Import commit: `bb89cfc wiki-import: 002-electron-callkit (56 pages)`
- Imported source: `<workspace>/project/NECallKit/specs/002-electron-callkit`
- Raw originals preserved under:
  `raw/imported/002-electron-callkit/`
- Created pages: 56
- Skipped files: 9 non-document assets
- Categories after import:
  - `features/`: 24 pages
  - `modules/`: 15 pages
  - `decisions/`: 11 pages
  - `bugs/`: 5 pages
  - `queries/`: 1 page
  - `platforms/`: 0 pages
- Remote push completed to `origin/master`.
- Import checkpoint and lock were cleared.
- A temporary import helper remains in the target project:
  `<workspace>\project\NECallKit\.tmp\wiki_import_002_electron_callkit.py`

**Schema state:**

- Domain: `NECallKit 多平台音视频 SDK 研发与维护知识库`
- Categories: `platforms`, `modules`, `features`, `bugs`, `decisions`,
  `queries`
- Memory tier driving field: `ingested_at`
- Tag taxonomy includes platform and architecture tags such as `electron`,
  `desktop`, `web`, `bridge`, `rtc`, `signaling`, `testing`

**Product notes:**

- The first import produced a useful corpus size: large enough to ask real
  questions, small enough to inspect manually.
- The import distribution is skewed toward feature/module/decision pages, which
  matches the source being a feature spec directory rather than the whole
  monorepo.
- `platforms/` is currently empty, which is expected because top-level platform
  docs have not been imported yet. It is also a good test for whether
  `wiki-query` names coverage gaps clearly.
- The leftover temporary import script is a setup residue. Do not delete it yet;
  keep it as evidence until we decide whether this is acceptable workflow
  debris or a cleanup bug.

**Advisor note:**

The next test should not be another import. The wiki has enough knowledge to
answer maintainer-grade questions about the Electron/Web reuse work. We should
run `wiki-digest` first to establish a baseline, then ask targeted questions
whose answers can be judged against the maintainer's memory.

**Next recommended step:**

1. Run `wiki-digest` on `~\.llm-wiki\NECallKit`.
2. Run `wiki-lint` and record structural issues before fixing anything.
3. Ask 2-3 real questions, for example:
   - "Electron/Web reuse 当前还剩哪些 release blocker?"
   - "客户从旧 Web SDK 升级到 reuse 版本需要注意哪些破坏性变化?"
   - "Electron example 和 Web example 的验证边界有什么差异?"

### 2026-05-08 03:24 +08:00 — First Digest And Lint Baseline

**Action:** Ran the mechanical digest and structural lint scripts against the
new NECallKit wiki.

**Commands:**

```powershell
py -3 plugin\scripts\digest.py `
  --wiki ~\.llm-wiki\NECallKit `
  --since all

py -3 plugin\scripts\lint_naive.py `
  --wiki ~\.llm-wiki\NECallKit `
  --check all
```

**Digest baseline:**

- Script page count: 59
- Activity entries: 2 (`init`, `import`)
- Inventory by type:
  - `features`: 24
  - `modules`: 15
  - `decisions`: 11
  - `bugs`: 5
  - `queries`: 1
- Top tags:
  - `electron`: 56
  - `callkit`: 56
  - `nim`: 46
  - `web`: 46
  - `bridge`: 30
  - `rtc`: 29
  - `regression`: 27
  - `desktop`: 26
  - `architecture`: 22
- Tier distribution: `active: 59`
- Top hubs: none

**Lint baseline:**

- Findings: 63 total
- Severity: 63 MEDIUM, 0 HIGH, 0 LOW
- Checks with findings:
  - `orphans`: 59
  - `frontmatter`: 3
  - `index`: 1

**Important product observations:**

- The import produced pages but no effective wikilink graph: every scanned page
  is currently an orphan, and digest has no top hubs.
- `lint_naive.py` treats `SCHEMA.md`, `index.md`, and `log.md` as ordinary wiki
  pages for orphan/frontmatter/index checks. That makes the first lint report
  noisier than it should be for a freshly initialized wiki.
- `digest.py` reports `page_count: 59`, while `index.md` says 56 content pages.
  The difference appears to be those same structural files.
- Earlier, attempting guessed script names `wiki_digest.py` and `wiki_lint.py`
  failed because the real files are `digest.py` and `lint_naive.py`. Skill docs
  were accurate, but script naming is not discoverable from the slash command
  names.

**Advisor note:**

Do not fix all orphans mechanically yet. The first query pass should reveal
which pages deserve to become hubs. A blind linking pass would hide the symptom
without proving the wiki became more useful.

**Essay note:**

This is strong material: the first real import validates persistence and
classification, but also shows that a pile of converted pages is not yet a
compiled wiki. The compounding step is the links and filed syntheses that turn
documents into project memory.

### 2026-05-08 03:30 +08:00 — First Maintainer-Question Search Pass

**Action:** Ran three search probes against the imported wiki to test whether it
can orient a maintainer before any manual graph cleanup.

**Questions tested:**

- `release blocker Electron Web reuse`
- `升级 破坏性 旧 Web SDK reuse`
- `Electron example Web example 验证 边界 差异`

**Observed:**

- Search returned relevant top hits for all three questions.
- For release/readiness, the top hits included:
  `Electron / Web Reuse 升级就绪审查报告`,
  `Electron / Web Reuse 后续工作分解计划`, and
  `Electron / Web Reuse 升级兼容矩阵`.
- For old Web customer upgrade risk, the top hits included:
  `原版 Web SDK / UIKit 客户升级指导`,
  `原版 Web SDK / UIKit 客户升级一页纸`, and the upgrade compatibility
  matrix.
- For example validation boundaries, the top hits included:
  `Electron / Web example 验证链说明` and
  `Electron / Web example 平台差异审核基线`.
- `graph_query.py --mode stats` reported `edges: 0`, confirming that the
  current wiki has search value but no navigable wikilink graph yet.

**First synthesis from reading top hits:**

- Current evidence does not support a blanket "zero-code-change upgrade" claim
  for any customer type.
- Web SDK 1v1 formal API customers look closest to a configuration/dependency
  upgrade path.
- React/Vue3 UIKit customers must be split between minimal provider contract
  users and customers who copied old example-host/provider internals.
- Electron/Web example validation must distinguish formal package contract,
  example purity contract, example host contract, and the actual verification
  chain.
- Allowed platform differences are explicit: Web validates external + group
  call path; Electron defaults to external, keeps managed for internal
  automation/follow-up, and must gray out group call as unsupported.

**Product note:**

The first query pass demonstrates a useful "reader acceleration" loop: search
finds the right sources quickly. It does not yet demonstrate kata's stronger
claim: compiled cross-references and durable query synthesis. The next step
should file one query answer back into `queries/` and link it to the source pages
so the graph starts to compound.

**Suggested first filed query:**

`Electron/Web reuse 当前对外升级口径应该怎么表述，哪些客户必须迁移代码？`

### 2026-05-08 03:40 +08:00 — First Filed Query Created A Graph Hub

**Action:** Filed the first substantive query back into the NECallKit wiki.

**Created:**

- `queries/002-electron-callkit-electron-web-reuse-upgrade-positioning-query.md`

**Question:**

`Electron/Web reuse 当前对外升级口径应该怎么表述，哪些客户必须迁移代码？`

**Sources linked:**

- [[002-electron-callkit-electron-web-reuse-upgrade-compatibility-matrix-2026-04-20]]
- [[002-electron-callkit-electron-web-reuse-upgrade-readiness-review-2026-04-20]]
- [[002-electron-callkit-electron-web-legacy-customer-upgrade-guide-2026-04-20]]
- [[002-electron-callkit-electron-web-legacy-customer-upgrade-one-page-2026-04-20]]

**Synthesis captured:**

- Do not claim "zero-code-change upgrade" or universal seamless upgrade.
- Low-cost upgrade wording is defensible only for `Web SDK 1v1 formal API`
  customers and React/Vue3 customers using the minimum provider contract.
- Customers depending on removed Web SDK side effects, old provider internals,
  old example-host structure, old drag/position semantics, or group-call
  UIKit/provider behavior need migration work or dedicated regression before
  any low-cost claim is made.
- Release notes must explicitly separate "minimum contract can upgrade" from
  "old project can be swapped in-place".

**Verification after filing:**

- `graph_query.py --mode stats` changed from `edges: 0` to `edges: 13`.
- `graph_query.py --mode hubs --limit 10` now reports the new query as the
  top hub with `in: 5`, `out: 4`, `score: 7.0`.
- `search_naive.py --query "upgrade migration compatibility code"` returns
  the new query as the top result.
- `lint_naive.py --check links,orphans,index,frontmatter` reports no broken
  links, but still reports 54 orphan content pages plus the known structural
  noise around `SCHEMA.md`, `index.md`, and `log.md`.
- Git commit in the NECallKit wiki:
  `3826ff6 wiki-query: file electron web upgrade positioning`.

**Product observations:**

- This is the first moment the dogfood wiki demonstrates compounding rather
  than just import/search. A filed query created bidirectional edges and became
  a hub future searches can land on.
- The manual backlink step is effective but too mechanical. A production-quality
  `wiki-query --file` flow should automate source-page backlinks and log/index
  updates.
- Chinese-only search probe `对外升级口径 必须迁移代码` failed with
  `query has no usable terms`, while the English probe worked. This is a real
  CJK tokenization gap for a Chinese-language wiki.

**Essay note:**

This gives the essay a concrete before/after:

- Before filed query: 56 imported pages, 0 graph edges, no hubs.
- After one maintained synthesis: 57 content pages, 13 graph edges, one useful
  hub that captures a maintainer decision.

The stronger story is not "the LLM answered a question"; it is "the answer
became project memory, changed the graph, and is now the easiest future entry
point for that topic."

### 2026-05-08 03:50 +08:00 — Second Filed Query Clarified Example Boundaries

**Action:** Filed a second substantive query back into the NECallKit wiki.

**Created:**

- `queries/002-electron-callkit-example-contract-boundary-query.md`

**Question:**

`Electron/Web example 验证边界与平台差异应该怎么判？`

**Sources linked:**

- [[002-electron-callkit-electron-web-example-validation-chain]]
- [[002-electron-callkit-contracts-electron-web-example-platform-baseline]]
- [[002-electron-callkit-electron-web-release-delivery-guide]]
- [[002-electron-callkit-contracts-electron-node-nim-boundary]]

**Synthesis captured:**

- Electron/Web example 审核不能再按“表层行为完全一致”判定。
- Formal package contract、example purity contract、example host contract、
  and example verification chain are separate evidence layers.
- Umi is a Web React example host concern, not a formal package blocker.
- Web external-only, Electron external/default with managed internal/follow-up,
  Web group call retained, and Electron group call grayed out are allowed
  platform differences when explicitly documented and verified.
- Shared `domain/runtime/core`, formal package consumer identity, and the 1v1
  main path remain non-negotiable shared-layer requirements.

**Verification after filing:**

- `graph_query.py --mode stats` changed from `edges: 13` to `edges: 26`.
- `graph_query.py --mode hubs --limit 12` now reports two query hubs, each with
  `in: 5`, `out: 4`, `score: 7.0`.
- `search_naive.py --query "formal package example host umi managed external"`
  returns the new query as the top result.
- `lint_naive.py --check links,orphans,index,frontmatter` reports no broken
  links. Orphan findings dropped from 54 to 50 content pages, plus the known
  structural-file lint noise.
- Git commit in the NECallKit wiki:
  `63ec617 wiki-query: file example contract boundaries`.
- Pushed to `origin/master`.

**Product observations:**

- The second filed query confirms the pattern: query filing is the moment where
  imported docs become navigable project memory.
- Two query pages now form the first high-signal layer above the imported
  source corpus. This is the likely kata value proposition for real teams:
  not every source needs to be perfectly interlinked up front; filed syntheses
  can become curated hubs as work proceeds.
- `log.md` currently contributes graph edges and appears as a hub candidate.
  That may be mechanically correct but editorially noisy; graph/digest output
  probably should treat `log.md`, `index.md`, and `SCHEMA.md` as system files
  by default.

**Essay note:**

The story now has two concrete maintained decisions:

1. Customer upgrade wording and migration-code classification.
2. Example validation boundaries and allowed platform differences.

Both are exactly the kind of knowledge that usually disappears into review
threads, release docs, or chat. In the wiki, they are now first-class query
pages linked to their evidence.

### 2026-05-08 03:58 +08:00 — Post-Query Digest Snapshot

**Action:** Ran `digest.py --since all` after filing and pushing both query
pages.

**Current wiki state:**

- Page count: 61 script-scanned pages
- Activity entries: 4 total
  - `init`: 1
  - `import`: 1
  - `query`: 2
- Inventory by type:
  - `features`: 24
  - `modules`: 15
  - `decisions`: 11
  - `bugs`: 5
  - `queries`: 3
- Tier distribution: `active: 61`
- Top query hubs:
  - `queries/002-electron-callkit-electron-web-reuse-upgrade-positioning-query.md`
  - `queries/002-electron-callkit-example-contract-boundary-query.md`

**Observed change from baseline:**

- Before filed queries: imported pages were searchable but had no graph edges
  and no hubs.
- After two filed queries: the wiki has 26 graph edges and two high-signal
  query hubs.
- Orphan findings dropped from 59 at baseline to 50 after two query filings,
  without doing a blind bulk-linking pass.

**Advisor note:**

This is enough to justify continuing the dogfood with the next source directory.
The next import should be chosen to test a different shape of knowledge, not
more of the same Electron spec material. Good candidates are top-level project
orientation docs (`README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `TASKS.md`,
`TRACKER.md`) or a second feature/bugfix directory that stresses cross-platform
coverage.

### 2026-05-08 04:02 +08:00 — Local Evidence Log Commit Blocked

**Action:** Attempted to stage this dogfood evidence log inside the kata
repository.

**Observed:**

- `git add docs/dogfood-necallkit-hn-essay.md` failed with:
  `fatal: Unable to create '<workspace>/ai/kata/.git/index.lock': Permission denied`
- `.git/index.lock` was not present.
- `.git` ACL inspection showed explicit deny entries affecting write access.
- NECallKit wiki commits and pushes were already successful; this block only
  affects committing the evidence log in the kata repo.

**Product / process note:**

This is not an kata behavior bug, but it is relevant dogfood process
friction. Evidence capture can still continue in the working tree even when the
plugin repo cannot currently update its git index.

### 2026-05-08 04:20 +08:00 — Second Import Candidate Recon

**Action:** Re-oriented on the initialized wiki and inspected the remaining
NECallKit source corpus before choosing the next import batch.

**Current wiki baseline:**

- Wiki working tree is clean and pushed through
  `63ec617 wiki-query: file example contract boundaries`.
- `SCHEMA.md` categories remain: `platforms`, `modules`, `features`, `bugs`,
  `decisions`, `queries`.
- `index.md` reports 58 catalog pages; `digest.py` scans 61 pages because
  structural files are still counted.
- `graph_query.py --mode stats` reports:
  - pages: 61
  - edges: 26
  - dangling_links: 0
  - active tier pages: 61

**Remaining NECallKit corpus shape:**

- Top-level orientation docs exist and are high-signal:
  `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `TASKS.md`, `TRACKER.md`.
- `docs/guides/` has 4 focused long-lived guides, all relevant to the current
  Electron/Web reuse and Flutter/Electron merge boundary work.
- `docs/lessons/` has 13 compact lessons across logic errors, config issues,
  integration issues, platform issues, performance issues, and patterns.
- `docs/prd/` has multiple feature PRD clusters. `F011-master-low-coupling-sync`
  is a large, recent, high-risk Electron/Web corpus; `F013` and `F015` are
  newer Electron-specific feature clusters.
- `specs/` still contains other feature directories:
  `001-incoming-call-banner`, `001-nim-v10-upgrade`,
  `002-miniprogram-audio-background-permissions`,
  `003-flutter-pc-mac-callkit`, and
  `003-uniapp-miniprogram-flow-alignment`.

**Product observations:**

- The next import should test a different knowledge shape. Importing another
  `specs/*` directory would mostly validate volume and feature-spec mapping
  again; importing top-level docs plus selected guides tests whether the wiki
  can connect feature-local Electron knowledge to the repository-wide platform
  architecture and maintenance rules.
- `platforms/` is still empty after the first import. Top-level docs are the
  right source for platform pages because they describe stable platform
  identities, release shapes, and code locations.
- `docs/lessons/` is a strong later candidate because lessons are naturally
  cross-cutting and could produce the most useful long-term maintainer memory,
  but it should come after the wiki has stable project/platform anchors.

**Process friction:**

- `rg` was unavailable in the current PowerShell environment, so reconnaissance
  fell back to PowerShell file enumeration. This is not an kata product bug,
  but it is evidence that docs and scripts should not assume ripgrep is present
  on Windows dogfood machines.

**Advisor recommendation:**

Use a second, intentionally small import batch:

1. Import top-level orientation docs:
   `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `TASKS.md`, `TRACKER.md`.
2. Include `docs/INDEX.md` and `docs/guides/`.
3. Do not import all `docs/prd/` or all `docs/bugfix/` yet.
4. After import, run digest, graph stats, and lint again.
5. Ask one crossing query that forces the wiki to connect both corpora:
   "Electron/Web reuse 的维护边界如何落到 NECallKit 多平台仓库架构、发布入口和 agent 工作流？"

**Expected proof point:**

If the second import works, the next filed query should connect the existing
Electron/Web feature hubs to new platform/module anchors. That would show the
wiki can move from "feature dossier" to "project operating memory."

### 2026-05-08 11:00 +08:00 — Second Import Executed: Orientation + Guides

**Action:** Imported the curated second batch into the NECallKit wiki.

**Imported source batch:**

- `README.md`
- `ARCHITECTURE.md`
- `AGENTS.md`
- `TASKS.md`
- `TRACKER.md`
- `docs/INDEX.md`
- `docs/guides/electron-merge-impact-baseline.md`
- `docs/guides/electron-flutter-merge-review-checklist.md`
- `docs/guides/electron-web-reuse-development-handbook.md`
- `docs/guides/electron-web-reuse-development-quick-reference.md`

**Dry-run result:**

- 10 total files
- 8 planned creates
- 2 planned updates
- The updates were the two earlier Electron/Web reuse guide stubs created by
  the first import. The new import replaced those migration placeholders with
  the real permanent guide content from `docs/guides/`.

**Import result:**

- Created: 8 wiki pages
- Updated: 2 existing wiki pages
- Raw originals preserved under `raw/imported/necallkit-orientation-guides/`
- Commit pushed:
  `7e4726f wiki-import: necallkit orientation guides (10 files)`

**Immediate verification:**

- `digest.py --since all` page count moved from 61 to 69.
- Inventory gained:
  - `platforms`: 1
  - `modules`: 18 total
  - `decisions`: 15 total
  - `features`: still 24 total, because two existing guide stubs were updated.
- `graph_query.py --mode stats` first reported:
  - pages: 69
  - edges: 63
  - dangling_links: 5

**Problem found by dogfood verification:**

The second importer generated 5 broken wikilinks because it linked to short
guide slugs such as `[[necallkit-docs-guides-electron-web-reuse-development-handbook]]`
while the deduplicated target pages kept their original
`002-electron-callkit-...-2026-04-20` slugs.

**Why this matters:**

- This is a useful product failure, not just an implementation typo.
- Deduplication that updates an existing page must preserve the existing page
  identity and make all new backlinks target that identity.
- A dry-run that only shows create/update counts is insufficient; it should also
  validate that every planned wikilink resolves against the post-import page
  map.

**Fix:**

- Updated the dogfood importer to use the actual deduplicated guide slugs.
- Re-ran the importer as a full update.
- Raw files were unchanged.
- Commit pushed:
  `e3769c7 wiki-import: necallkit orientation guides (10 files)`

**Post-fix verification:**

- `graph_query.py --mode stats`:
  - pages: 69
  - edges: 68
  - dangling_links: 0
  - active tier: 69
- `lint_naive.py --check links,orphans,index,frontmatter`:
  - HIGH: 0
  - MEDIUM: 52
  - links findings: 0
  - remaining findings are the known orphan and structural-file noise.
- Top hubs now include project-level anchors:
  - `queries/002-electron-callkit-example-contract-boundary-query.md`
    with inbound 13
  - `queries/002-electron-callkit-electron-web-reuse-upgrade-positioning-query.md`
    with inbound 12
  - `modules/necallkit-architecture-overview.md` with inbound 4 / outbound 5
  - `features/002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20.md`
    with inbound 3 / outbound 5
  - `modules/necallkit-docs-index.md`,
    `decisions/necallkit-current-task-list.md`, and
    `decisions/necallkit-feature-bug-tracker.md`

**Product observations:**

- The second import succeeded at the intended shape change: the wiki now has
  a `platforms/` page and project-level architecture/task/tracker/docs anchors,
  not just Electron feature pages.
- Filed query pages remained the strongest hubs, which is a good sign: curated
  synthesis remains the top navigation layer even after importing broader
  context.
- The real guide content changed the graph more than the stub pages did. This
  supports the "compiled memory" thesis: placeholders are not enough; durable
  operating documents need to become first-class pages.
- `log.md` still appears as a hub because graph tools count system files. This
  remains a product cleanup item.

**Essay note:**

The run now has a stronger arc:

1. Import a feature dossier: 56 pages, 0 edges.
2. File two maintainer decisions: 61 pages, 26 edges, 2 query hubs.
3. Import project operating context: 69 pages, 68 edges, architecture and guide
   pages become secondary hubs.
4. Verification catches a broken-link dedup bug, and the fix is committed as
   part of the wiki history.

This is exactly the public story to emphasize: the value is not one answer. The
value is a maintained artifact whose graph, history, and health checks evolve as
work proceeds.

### 2026-05-08 11:15 +08:00 — Third Filed Query Connected Feature And Project Memory

**Action:** Filed a crossing query that intentionally used both the first
Electron feature corpus and the second project-orientation corpus.

**Created:**

- `queries/necallkit-electron-web-reuse-operating-boundary-query.md`

**Question:**

`Electron/Web reuse 的维护边界如何落到 NECallKit 多平台仓库架构、发布入口和 agent 工作流？`

**Sources linked:**

- [[necallkit-architecture-overview]]
- [[necallkit-platform-matrix-release-entry]]
- [[necallkit-agent-sdd-operating-contract]]
- [[002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20]]
- [[002-electron-callkit-electron-web-reuse-upgrade-positioning-query]]
- [[002-electron-callkit-example-contract-boundary-query]]

**Synthesis captured:**

- Web/Electron reuse should not be treated as an isolated Electron feature or
  as a requirement that Web and Electron example surfaces be identical.
- `packages/` is the shared truth source for cross-platform semantics, while Web
  and Electron keep formal platform packages and separate example hosts.
- Agent workflow is part of the operating boundary: agents must classify a
  change into shared semantics, runtime adapter, formal wrapper, example host,
  or Electron-only native/managed capability before editing.
- Release evidence must show that platform packages still ship in their formal
  shapes, shared semantics are consumed through wrappers, and platform
  differences are documented rather than mistaken for regressions.
- The maintainer shorthand filed in the query:
  Web/Electron reuse does not erase platform boundaries; it keeps shared
  semantics in one truth source while platform packages, example hosts, release
  entry points, and SDD workflow prove that truth source is consumed correctly.

**Commit:**

- `8acdbe1 wiki-query: file electron web operating boundary`

**Verification after filing:**

- `graph_query.py --mode stats`:
  - pages: 70
  - edges: 85
  - dangling_links: 0
- `graph_query.py --mode hubs --limit 20`:
  - existing upgrade query: inbound 13 / outbound 5 / score 15.5
  - existing example-boundary query: inbound 14 / outbound 5 / score 16.5
  - new operating-boundary query: inbound 7 / outbound 6 / score 10.0
  - architecture overview: inbound 6 / outbound 6 / score 9.0
  - reuse handbook: inbound 5 / outbound 6 / score 8.0
- `lint_naive.py --check links,orphans,index,frontmatter`:
  - HIGH: 0
  - links findings: 0
  - MEDIUM: 52, still the known orphan and structural-file noise.
- `search_naive.py --query "Electron Web reuse operating boundary architecture agent workflow release entry shared source"`:
  - the new filed query is the top result.

**Product observations:**

- This is the first query that truly depends on the second import. The answer
  cannot be produced from only the original Electron spec directory because it
  relies on repository architecture, release entry, and agent workflow.
- Query filing compounded both directions: the new query cites 6 sources, and
  those sources backlink to the query. This raised the query itself into the
  third major hub and strengthened the project-level architecture hub.
- The graph now has a three-layer shape:
  - raw feature documents from the first import,
  - project-level operating documents from the second import,
  - query hubs that encode maintained decisions across both.

**Essay note:**

This is the clearest HN story so far:

Before kata, the answer to a question like "what is the maintenance boundary
of Electron/Web reuse?" would be a chat response or buried in several docs.
After kata, the answer is a new durable page with citations, backlinks,
graph position, git history, and future search priority.

The important claim is not that the LLM found facts. It edited the knowledge
base so the next maintainer or agent starts from a better state.

## HN Essay Spine Snapshot — 2026-05-08 11:25 +08:00

### Working Title Options

- I stopped using chat history as project memory and started compiling a wiki.
- RAG retrieves; a maintained wiki compounds.
- What happened when I pointed an LLM-maintained wiki at a real SDK monorepo.

### Core Thesis

The durable output of an AI coding session should not be a chat transcript. It
should be a maintained project memory: files with citations, links, health
checks, git history, and an evolving graph that future humans and agents can
reuse.

### Story Arc

1. Start with a real monorepo, not a toy benchmark: NECallKit spans Android,
   iOS, Flutter, Desktop, Electron, HarmonyOS, Web, MiniProgram, and uni-app.
2. Import one high-signal feature dossier and discover that "many pages" is not
   yet "compiled memory": 56 imported pages, 0 graph edges.
3. File two real maintainer decisions back into the wiki. The graph changes
   from searchable documents into navigable memory: 61 pages, 26 edges, 2 query
   hubs.
4. Import project operating context: architecture, platform matrix, agent rules,
   task tracker, docs index, and guides. The wiki gains project-level anchors:
   69 pages, 68 edges.
5. Verification catches a real dedup/backlink bug: 5 broken links after the
   second import. Fixing it becomes part of the wiki history.
6. File a crossing query that connects both corpora. The answer becomes the
   third major hub: 70 pages, 85 edges, 0 dangling links.

### Hard Evidence Collected

- Init baseline commit: `a7cec09 wiki: init`
- First import commit: `bb89cfc wiki-import: 002-electron-callkit (56 pages)`
- First query commit:
  `3826ff6 wiki-query: file electron web upgrade positioning`
- Second query commit:
  `63ec617 wiki-query: file example contract boundaries`
- Second import commit:
  `7e4726f wiki-import: necallkit orientation guides (10 files)`
- Second import fix commit:
  `e3769c7 wiki-import: necallkit orientation guides (10 files)`
- Third query commit:
  `8acdbe1 wiki-query: file electron web operating boundary`

### Before / After Metrics

| Moment | Pages | Edges | Dangling links | Notable state |
| --- | ---: | ---: | ---: | --- |
| After first import | 56 content / 59 scanned | 0 | 0 | Searchable dossier, no graph hubs |
| After two filed queries | 61 scanned | 26 | 0 | Two query hubs emerge |
| After second import, before fix | 69 scanned | 63 | 5 | Project anchors added, dedup-link bug exposed |
| After second import fix | 69 scanned | 68 | 0 | Architecture and guide pages become secondary hubs |
| After third filed query | 70 scanned | 85 | 0 | Cross-corpus operating-boundary query becomes third query hub |

### Strongest Example To Use In The Essay

Question:

> What is the maintenance boundary for Electron/Web reuse in this multi-platform
> SDK repo?

Cold chat answer would have been ephemeral. In the dogfood run, the answer became
`queries/necallkit-electron-web-reuse-operating-boundary-query.md`, linked to:

- repository architecture,
- platform/release entry,
- agent SDD rules,
- Web/Electron reuse development guide,
- upgrade-positioning query,
- example-boundary query.

After filing, the page became the third major hub with inbound 7 / outbound 6,
and search for the same topic returns it first.

### Product Friction To Mention Honestly

- Windows command examples matter: `python plugin\scripts\wiki_init.py --help`
  failed with an encoding issue, while `py -3 ...` worked.
- Script names are not discoverable enough: skills are named `wiki-digest` and
  `wiki-lint`, but scripts are `digest.py` and `lint_naive.py`.
- CJK search is weak: Chinese-only query text failed with
  `query has no usable terms`; English token probes worked.
- Structural files pollute reports: `SCHEMA.md`, `index.md`, and `log.md` are
  counted as pages by digest/lint/graph.
- `log.md` appears as a hub candidate because graph tooling counts system file
  wikilinks.
- Dry-run initially failed to validate future wikilink resolution after dedup:
  the second importer created 5 broken links that only lint caught after write.
- The AK repo itself currently cannot stage evidence because `.git` ACL denies
  creating `.git/index.lock`.
- `rg` is not available on the Windows machine, so docs and examples should not
  assume ripgrep.

### Product Claims Supported By This Dogfood

- Import is necessary but not sufficient. The first import created pages, but no
  graph.
- Filed query syntheses are the compounding mechanism. Each valuable answer
  should become a page with source links and backlinks.
- Git makes memory auditable. The wiki history shows exactly when imports,
  syntheses, fixes, and graph changes happened.
- Health checks matter. Lint caught broken links introduced by the importer
  before the problem became invisible background rot.
- A filesystem wiki is inspectable and patchable. The user can read, diff,
  commit, push, and recover the knowledge base using ordinary tools.

### Claims Not Yet Proven

- We have not yet tested `docs/lessons/`, which should be the strongest evidence
  for preventing repeated mistakes.
- We have not compared kata answer quality directly against a fresh cold
  repo read on the same question.
- We have not captured human maintainer acceptance ratings for the filed query
  answers.
- We have not tested multi-machine `wiki-sync` in this NECallKit wiki.
- We have not cleaned up structural-file noise in lint/graph/digest.

### Next Evidence To Collect

1. Import `docs/lessons/` as a third corpus and ask a preventive query:
   "Before implementing the next Electron/Web bugfix, which historical lessons
   should the agent check?"
2. Ask the user to rate the three filed query pages for correctness and
   usefulness, preferably with short quotes.
3. Run a cold baseline: ask the same operating-boundary question without the
   wiki and compare time-to-answer, citations, and persistence.
4. Fix system-file exclusion in graph/digest/lint and record before/after noise
   reduction.
5. Add CJK tokenization support to `search_naive.py` or document the current
   limitation.

### 2026-05-08 11:35 +08:00 — Lessons Corpus Preflight

**Action:** Read-only reconnaissance for a possible third import:
`docs/lessons/`.

**Observed source shape:**

- Total lesson files: 13
- Categories:
  - `config-issues`: 1
  - `integration-issues`: 1
  - `logic-errors`: 7
  - `patterns`: 1
  - `performance-issues`: 1
  - `platform-issues`: 2
- Most lessons share a strong structure:
  problem symptom, root cause, solution, impact scope, prevention strategy, and
  sometimes code-review checkpoints.

**Representative lessons:**

- `L003-signal-controller-state-boundary-handling`
- `L005-signal-event-handler-missing-state-guard`
- `L008-generation-counter-async-race-guard`
- `L011-bridge-action-mismatch-activated-by-new-path`
- `L012-system-back-background-lifecycle-split`
- `L013-electron-switch-calltype-camera-source-bridge-regression`

**Current wiki gap:**

`search_naive.py --query "lessons historical mistakes repeat bug prevention agent workflow"`
currently finds pages that mention `docs/lessons/`, especially
[[necallkit-agent-sdd-operating-contract]], but not the actual lesson bodies,
because they have not been imported yet.

**Why this is the right next corpus:**

- The first import tested feature dossier ingestion.
- The second import tested project operating context.
- `docs/lessons/` would test the strongest maintainer-memory claim:
  preventing repeated mistakes before new code is written.

**Mass-update constraint:**

Importing all lessons would create or update more than 10 wiki files, so this
should not be performed without explicit user confirmation. This is also good
dogfood friction: the skill's mass-update guard is appropriate here because
lesson import will likely create many backlinks and possibly a synthesis query.

**Recommended next experiment:**

1. Dry-run import `docs/lessons/` into a lessons-oriented mapping.
2. If approved, import and commit as one atomic wiki commit.
3. Ask and file a preventive query:
   `下一个 Electron/Web bugfix 开始前，agent 应该先检查哪些历史 lessons？`
4. Verify whether the answer cites actual lessons rather than only AGENTS /
   docs index pages.

**Expected essay payoff:**

If this works, the essay can move from "the wiki remembers decisions" to "the
wiki changes what the agent checks before writing code."

### 2026-05-08 11:45 +08:00 — Lessons Import Dry-Run Plan

**Action:** Built and ran a read-only dry-run planner for `docs/lessons/`.

**Planner script:**

- `scripts/dogfood_plan_necallkit_lessons_import.py`

**Dry-run result:**

- Bundle: `necallkit-lessons`
- Source root: `docs/lessons`
- Total files: 13
- Planned actions:
  - create: 13
- Source categories:
  - `logic-errors`: 7
  - `platform-issues`: 2
  - `config-issues`: 1
  - `integration-issues`: 1
  - `patterns`: 1
  - `performance-issues`: 1
- Minimum files affected by real import: 16
  - 13 lesson pages
  - `SCHEMA.md`
  - `index.md`
  - `log.md`
  - likely additional backlinks from existing pages
- Mass-update confirmation required: yes.

**Schema proposal from dry-run:**

The existing schema has no `lessons` category. The planner proposes adding:

```yaml
categories:
  - name: lessons
    purpose: "Lessons learned, prevention strategies, and reusable debugging/review patterns."
```

Proposed tags:

- `async`
- `camera`
- `lifecycle`
- `logger`
- `performance`
- `state-machine`

**Why not map lessons into `bugs/`:**

Lessons are not just bug reports. They are prevention patterns and review
checkpoints. Mapping them into `bugs/` would preserve text but lose the key
semantic distinction that makes them useful before future work starts.

**Representative planned pages:**

- `lessons/l003-signalcontroller-call-accept-状态边界处理不足-重复调用异常与错误码语义不清.md`
- `lessons/l005-信令事件处理回调同样需要入口状态守卫-被动通知的-callstatus-前置检查.md`
- `lessons/l008-generation-counter-async-handler-的-await-边界竞态守卫模式.md`
- `lessons/l011-旧桥接方法动作语义错接-新调用链接通后激活潜伏-bug.md`
- `lessons/l012-系统返回键退后台与直接退后台不是同一生命周期路径-只修单一路径会留下悬浮窗回归.md`
- `lessons/l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离.md`

**Product observations:**

- The dry-run itself surfaced a schema evolution question. This is the correct
  place for user judgment: the wiki schema should evolve because the project
  corpus contains a durable knowledge type not present in the initial schema.
- The first dry-run version generated low-quality summaries because it treated
  YAML frontmatter as content. The planner was fixed before being treated as
  evidence. This is another small but useful dogfood finding: import previews
  need content-quality checks, not just file counts.
- `docs/lessons/` is the first corpus where kata should prove a stronger
  claim than "answers are remembered": it should change what the agent checks
  before writing code.

**Recommended user decision:**

Approve or reject this schema change before any write:

1. Add `lessons` category and the six proposed tags, then import all 13 lessons.
2. Add `lessons` category only, but defer tag taxonomy expansion.
3. Do not add a new category; map lessons into `bugs/` or `decisions/`.
4. Skip lessons import for now.

### 2026-05-08 11:55 +08:00 — Current Blocking Decisions

**Action:** Audited current state and identified what can proceed without
guessing versus what needs user judgment.

**Verified current state:**

- NECallKit wiki is clean and pushed through
  `8acdbe1 wiki-query: file electron web operating boundary`.
- Current graph state:
  - pages: 70
  - edges: 85
  - dangling links: 0
  - active tier pages: 70
- AK repo working tree still contains uncommitted dogfood artifacts:
  - `README.md` modified from earlier documentation workflow updates.
  - `docs/dogfood-necallkit-hn-essay.md` untracked.
  - `scripts/dogfood_file_necallkit_crossing_query.py` untracked.
  - `scripts/dogfood_import_necallkit_orientation.py` untracked.
  - `scripts/dogfood_plan_necallkit_lessons_import.py` untracked.
- AK repo git staging remains blocked by the `.git/index.lock` ACL issue
  observed earlier; evidence capture can continue in files, but repo commits
  still require permission repair outside this dogfood flow.

**Decision 1 — Lessons import:**

The next import would exceed the 10-file mass-update guard and requires an
explicit choice:

1. Add `lessons` category and six tags, then import all 13 lessons.
2. Add `lessons` category only, defer tags.
3. Map lessons into existing `bugs/` / `decisions/`.
4. Skip lessons import.

**Recommendation:** choose option 1. Reason: lessons are a distinct durable
knowledge type, and the proposed tags (`async`, `camera`, `lifecycle`, `logger`,
`performance`, `state-machine`) are exactly the vocabulary needed for
preventive queries.

**Decision 2 — HN essay draft style:**

Writing a draft requires choosing an angle:

1. Engineering retrospective: most credible; centered on the real dogfood arc,
   bugs, commits, and metrics.
2. Product manifesto: most memorable; centered on "RAG retrieves; wiki
   compounds."
3. Evidence report: most restrained; centered on tables, graph numbers, and
   failure modes.

**Recommendation:** choose engineering retrospective. Reason: the strongest
evidence is the concrete process:
`56 pages / 0 edges -> 70 pages / 85 edges / 0 dangling links`, including a
real broken-link bug caught and fixed by verification.

**Decision 3 — Human acceptance signal:**

Ask the maintainer to rate the three filed query pages:

- [[002-electron-callkit-electron-web-reuse-upgrade-positioning-query]]
- [[002-electron-callkit-example-contract-boundary-query]]
- [[necallkit-electron-web-reuse-operating-boundary-query]]

Suggested rating dimensions:

- Correctness: does it match project reality?
- Usefulness: would it save a maintainer or future agent time?
- Retention: should this page remain as durable wiki memory?

**Why this matters:**

The essay already has operational evidence. The missing evidence is human
judgment that the maintained pages are actually worth keeping.

### 2026-05-08 12:05 +08:00 — Adviser Recommendation Rationale

**Action:** Explained the recommendation for the next dogfood step.

**Recommendation:**

- Import `docs/lessons/` as a distinct `lessons` category.
- Add the six proposed tags:
  `async`, `camera`, `lifecycle`, `logger`, `performance`, `state-machine`.
- Use an engineering retrospective angle for the HN essay draft.

**Why `lessons` should be a category:**

`docs/lessons/` is not only a set of bug reports. Its value is preventive:
each lesson encodes what a future agent or maintainer should check before
writing code. Mapping these files into `bugs/` would preserve their text but
lose the operating meaning: "look here before making the same class of mistake."

Examples:

- `L008 Generation Counter` is an async race-guard pattern.
- `L012 system back lifecycle split` is a lifecycle-path review pattern.
- `L013 Electron switch callType / camera / source bridge` is a cross-layer
  boundary pattern.

**Why the proposed tags matter:**

The proposed tags are retrieval dimensions, not decoration. Future questions
should be able to ask for lifecycle, async race, logger, camera, performance, or
state-machine lessons without knowing the original lesson IDs.

Without these tags, lessons are mostly title-searchable. With them, lessons can
support preventive queries such as:

`下一个 Electron/Web bugfix 开始前，agent 应该先检查哪些历史 lessons？`

**Why not choose the conservative alternatives:**

- Category-only import is safer but weakens future retrieval.
- Mapping lessons into `bugs/` or `decisions/` avoids schema change but makes the
  wiki type system less honest.
- Skipping lessons misses the strongest next product test: whether the wiki can
  change what an agent checks before writing code.

**Why the HN essay should be an engineering retrospective:**

The strongest material from this run is not a slogan. It is the concrete arc:

`56 pages / 0 edges -> 70 pages / 85 edges / 0 dangling links`

The run also contains a real failure mode: the second importer created 5 broken
wikilinks after deduplication, lint caught them, and the fix became part of the
wiki commit history. That is more credible than a product manifesto by itself.

**Essay framing:**

Lead with the real dogfood story, then derive the thesis:

> The useful LLM output was not the chat answer. It was the edited knowledge
> base: cited pages, backlinks, graph position, health checks, and git history.

The product manifesto line, "RAG retrieves; a wiki compounds," should appear as
a conclusion, not the opening claim.

### 2026-05-08 — User Feedback: Raise The `lessons` Admission Bar

**User feedback:**

New `lessons` pages should have a higher admission bar. If every small event
can become a lesson, `lessons/` will grow without bound and lose its value.

**Product interpretation:**

This is the right constraint. `lessons/` cannot become a more flattering name
for `bugs/` or `runbooks/`. It should be scarce operating knowledge: pages that
change what a future maintainer or agent checks before writing code.

**Updated admission policy:**

A source should enter `lessons/` only if it passes both gates:

1. Structural hard gate:
   - explicit root cause,
   - future prevention checklist,
   - transferable future trigger.
2. Lesson-worthiness gate:
   - high severity, or
   - linked / recurring lesson evidence, or
   - cross-boundary or cross-platform impact, or
   - durable review pattern that changes future code review behavior.

Sources that are mainly one-off commands, local workflow reminders, transient
platform facts, or issue-specific fixes should stay in `raw/`, become
`bugs/`/`runbooks/`, or be merged into an existing page until recurrence proves
they deserve durable lesson status.

**Planner update:**

`scripts/dogfood_plan_necallkit_lessons_import.py` now reports an admission
decision for each source:

- `admit`: suitable for `lessons/`.
- `defer`: keep raw or merge into an existing page until it recurs.
- `reject`: do not create a lesson page.

After the stricter gate, the current `docs/lessons/` dry-run reports:

- total source files: 13
- admitted: 11
- rejected: 2
- minimum files affected by admitted import: 14

The rejected examples are useful calibration:

- `L002-miniprogram-local-src-requires-sync-script`: more like runbook /
  workflow guidance than scarce lesson memory.
- `L006-harmony-live-player-mode-live-deprecated`: lacks explicit root-cause
  analysis and looks closer to a one-off platform fact.

**Revised recommendation:**

Do not import all source files merely because they live under
`docs/lessons/`. First import should be a seed set selected from admitted pages,
preferably the highest-leverage prevention patterns:

- async / await race guards,
- state-machine boundary handling,
- lifecycle split regressions,
- Electron source-bridge boundary failures,
- logger serialization crashes.

This preserves `lessons/` as a high-signal memory tier while still testing the
strong kata claim: the wiki should change what the next agent checks before
writing code.

**Seed-set planner update:**

The planner now emits a `recommended_seed_set` so the next import does not
default to all admitted lessons. Current seed set:

- `L008` — Generation Counter async race guard
- `L013` — Electron switch callType / camera / source-bridge boundary
- `L005` — signal event handler state guard
- `L012` — system back vs background lifecycle split
- `L003` — SignalController call/accept state boundary
- `L010` — nim logger circular-reference crash

This seed set would affect approximately 9 files (`6 lesson pages + SCHEMA.md +
index.md + log.md`), below the 10-file mass-update guard. It is a better first
experiment than importing all 11 admitted pages because it tests whether a small
curated lesson corpus can produce a useful preventive checklist.

**Repro command:**

```powershell
py -3 scripts\dogfood_plan_necallkit_lessons_import.py `
  --wiki '~\.llm-wiki\NECallKit' `
  --project '<workspace>\project\NECallKit' `
  --seed-only
```

Use `--seed-limit 3` if the first import should be even smaller:

```powershell
py -3 scripts\dogfood_plan_necallkit_lessons_import.py `
  --wiki '~\.llm-wiki\NECallKit' `
  --project '<workspace>\project\NECallKit' `
  --seed-only --seed-limit 3
```

### 2026-05-08 — Seed Set Rationale Explained

**Action:** Explained why the first `lessons/` seed set contains these six
sources rather than all admitted lessons.

**Rationale:**

The seed set is not "the six most severe bugs." It is the smallest set that can
exercise the preventive-memory claim across distinct reusable dimensions.

- `L008` — Generation Counter async race guard. Future trigger: any
  `await` inside an event handler that can race with `resetState()`, `clear()`,
  or `dispose()`.
- `L013` — Electron switchCallType / camera / source-bridge boundary. Future
  trigger: Electron/Web fixes that touch runtime behavior but may actually
  depend on desktop core and native bridge staging.
- `L005` — passive signal event handler state guard. Future trigger: multi-end
  login or passive signaling events where the receiving client may not be in
  the expected call state.
- `L012` — system back vs direct background lifecycle split. Future trigger:
  Android / Flutter backgrounding, floating-window, or lifecycle regressions
  where multiple OS entry paths must be enumerated.
- `L003` — SignalController call/accept state boundary. Future trigger: API
  state-machine work that must distinguish illegal state from idempotent
  "already in target state" behavior.
- `L010` — nim logger circular-reference crash. Future trigger: third-party
  SDK integration boundaries where wrapper code must sanitize complex objects
  before handing them to vendor code.

**Coverage:**

Together these six cover async races, state-machine semantics, passive event
guards, lifecycle splits, Electron native bridge boundaries, and third-party
integration safety. That makes them better for a first import than simply
maximizing count.

**Expected verification:**

After import, ask:

`下一个 Electron/Web bugfix 开始前，agent 应该先检查哪些历史 lessons？`

The answer should cite these six pages and produce a practical pre-work
checklist. If it only summarizes the source texts, the import did not yet prove
the stronger product claim.

### 2026-05-08 12:34 +08:00 — Lessons Seed Import And Preventive Query

**Action:** Imported the approved `lessons/` seed set and filed the preventive
query.

**Seed import commit:**

- `06c6edc wiki-import: necallkit lessons seed set (6 files)`

**Imported lesson IDs:**

- `L008`
- `L013`
- `L005`
- `L012`
- `L003`
- `L010`

**Schema changes:**

- Added category: `lessons`
- Added tags: `async`, `camera`, `lifecycle`, `logger`, `performance`,
  `state-machine`

**Import result:**

- Created: 6 wiki pages
- Updated: 0 existing pages
- Raw originals: 6 created under `raw/imported/necallkit-lessons-seed/`
- Push completed

**Preventive query commit:**

- `cac98d5 wiki-query: file electron web bugfix lessons preflight`

**Filed query:**

- `queries/necallkit-electron-web-bugfix-preflight-lessons-query.md`

**Question:**

`下一个 Electron/Web bugfix 开始前，agent 应该先检查哪些历史 lessons？`

**Answer shape:**

The filed query turned the six seed lessons into a concrete pre-work checklist:

- async race: check every `await` boundary against reset / clear / dispose.
- state-machine boundary: distinguish illegal state, repeated call, and already
  in target state.
- passive signal guard: validate current `callStatus` for NIM / RTC / signaling
  events, not only active APIs.
- lifecycle split: enumerate OS / host lifecycle entry paths before fixing
  background or floating-window regressions.
- Electron bridge boundary: verify source bridge, staged native artifact, and
  manifest before trusting Electron demo/package behavior.
- logger / SDK boundary: sanitize complex objects before passing them to vendor
  logger or SDK code.

**Verification after query:**

- Graph stats: 77 pages, 134 edges, 0 dangling links.
- New query hub:
  `queries/necallkit-electron-web-bugfix-preflight-lessons-query.md`
  entered the top hubs with inbound 7 / outbound 9 / score 11.5.
- `wiki-lint --check links,frontmatter,index` found 4 medium issues, all
  pre-existing structural-file noise:
  `SCHEMA.md` not referenced by index, and missing frontmatter on
  `SCHEMA.md`, `index.md`, `log.md`.
- No new broken links or frontmatter errors on the lesson/query pages.

**Essay payoff:**

This is the clearest proof point so far for the compounding-memory thesis. The
wiki did not merely store six more documents. It converted curated historical
lessons into a reusable pre-flight checklist that changes what the next agent
should inspect before writing code.

Updated arc:

1. Initial feature dossier: 56 pages, 0 edges.
2. Filed maintainer decisions: 61 pages, 26 edges.
3. Project operating context: 69 pages, 68 edges.
4. Operating-boundary query: 70 pages, 85 edges.
5. Lessons seed + preventive query: 77 pages, 134 edges, 0 dangling links.

This strengthens the essay thesis:

> RAG retrieves prior context. A maintained wiki changes the next workflow.

### 2026-05-08 — HN Brief Materialized

**Action:** Created a condensed writing brief:

- `docs/dogfood-necallkit-hn-brief.md`

**Purpose:**

The running log remains the raw evidence trail. The brief is the writing-facing
artifact: thesis, story arc, commit timeline, graph metrics, strongest proof
point, friction, honest limits, and candidate opening / closing.

**Current remaining gaps before a public essay draft:**

- Ask the maintainer to rate the filed query pages for correctness, usefulness,
  and retention.
- Optionally run a cold-baseline comparison against the same preflight question
  without using the wiki.
- Decide whether to mention the AK repo evidence-commit blocker or omit it as
  implementation noise.

### 2026-05-08 — Query Acceptance Worksheet Added

**Action:** Created a maintainer review worksheet:

- `docs/dogfood-necallkit-query-acceptance.md`

**Purpose:**

The user asked where to validate the four filed query pages. The worksheet
points to `~\.llm-wiki\NECallKit\queries\`, lists the four
files, and provides a correctness / usefulness / retention rubric.

**Why this matters for the essay:**

The run now has operational evidence. The remaining high-value evidence is the
maintainer's judgment about whether the generated wiki pages are actually worth
keeping.

### 2026-05-08 — Maintainer Query Acceptance Captured

**Action:** Recorded maintainer ratings in:

- `docs/dogfood-necallkit-query-acceptance.md`
- `docs/dogfood-necallkit-hn-brief.md`

**Ratings:**

| Query | Correctness | Usefulness | Retention |
| --- | ---: | ---: | ---: |
| Upgrade positioning | 5 | 4 | 5 |
| Example boundary | 5 | 4 | 5 |
| Operating boundary | 5 | 5 | 5 |
| Lessons preflight | 5 | 5 | 5 |

**Interpretation:**

- All four filed query pages were rated 5/5 for correctness.
- All four filed query pages were rated 5/5 for long-term retention.
- The two later cross-corpus pages, especially the lessons preflight query,
  reached 5/5/5 across all dimensions.

**Essay impact:**

This closes the largest evidence gap: the dogfood now has human maintainer
acceptance, not only graph metrics and commits.

### 2026-05-08 18:13 +08:00 — Knock-It-Out B055 Closed-Loop Review

**Action:** Reviewed a completed `knock-it-out` run from:

- `~\.codex\sessions\2026\05\08\rollout-2026-05-08T17-39-15-019e06f4-9d30-7d42-b59e-573ac56f1b71.jsonl`

**Input issue:**

`【electron-win/mac】有多个摄像头时拔掉当前使用的摄像头，未自动路由到使用其他摄像头`

**Observed outcome:**

- The agent completed B055 code-side remediation in NECallKit.
- It saved ingestible source records under:
  `<workspace>\project\NECallKit\docs\bugfix\B055-electron-camera-unplug-reroute\`
- It updated `TRACKER.md` and `TASKS.md`.
- It preserved the manual validation gap for Windows / macOS Electron React/Vue3
  real-device unplug regression.

**Wiki signal:**

The NECallKit wiki did not yet contain an exact B055 answer. A search for
`B055 Electron 摄像头拔掉 当前 fallback` returned related guardrail pages rather
than a direct fix record, including:

- `queries/necallkit-electron-web-reuse-operating-boundary-query.md`
- `queries/necallkit-electron-web-bugfix-preflight-lessons-query.md`
- `lessons/l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离.md`
- `bugs/electron-camera-switch-microphone-state-regression-bugfix-set.md`
- `decisions/electron-switchcalltype-remediation-history.md`

This is a **medium-confidence wiki hit**: the wiki supplied the right operating
boundaries and regression warnings, but not the root cause or final patch for
this specific device-unplug bug.

**What worked:**

- `knock-it-out` successfully guided the solving agent to create durable
  documents instead of leaving the result only in chat history.
- Existing wiki knowledge showed up in the implementation path: keep
  `switchCallType`, camera preference, and RTC video availability separate;
  do not turn a camera/device problem into an audio-only transition; verify the
  Electron source bridge and `bridgeStrategy=source`; keep B045-style regression
  coverage.
- The final response correctly proposed the minimal next wiki input:
  `docs/bugfix/B055-electron-camera-unplug-reroute/`.

**Improvement direction:**

- `knock-it-out` should make the pre-source wiki checkpoint harder to skip. A
  visible `Wiki Answer` block with `Confidence`, pages used, warnings, gaps, and
  source search plan should appear before deep source work.
- Skill discovery needs to be more robust across installed roots. This rollout
  exposed friction around resolving wiki skills from `.codex/skills` versus
  `.agents/skills`; fallback to manual wiki-page reading loses the auditable
  `wiki-query` confidence contract.
- The confidence model is useful in practice: this run should not be labeled
  "wiki answered the bug." It should be labeled "wiki provided medium-confidence
  guardrails; source investigation produced the new answer."
- The closed loop now has a concrete next action: ingest the B055 bugfix folder
  as the smallest curated batch, then file a reusable query page for Electron
  camera device-removal fallback. Only promote to a lesson if later fixes show
  this pattern recurs beyond B055.

**Essay payoff:**

This is a strong narrative example for the HN essay. The wiki was not a RAG dump
with an exact answer waiting inside. It supplied reusable engineering
constraints, forced the agent to preserve the new fix as a durable document, and
created a clear next ingest candidate. That is the "compiled project memory"
claim in a real maintenance loop: query -> partial hit -> source fix -> durable
record -> curated ingest.

### 2026-05-08 19:16 +08:00 — Knock-It-Out B056 Wiki-Guided Fix Review

**Action:** Reviewed the second completed `knock-it-out` run from:

- `~\.codex\sessions\2026\05\08\rollout-2026-05-08T18-38-28-019e072a-d7a8-7cc2-abde-b04ab2d0e7c3.jsonl`

**Input issue:**

`【electron-win/mac】mac呼叫win视频通话，mac切换到音频，再切换到视频，win看mac提示对方关闭了摄像头。怀疑是协议实现缺失，信令通知切换，send->ack->res，可能是缺失ack或者res，或者使用错了字段定义。需要从定义出做一定的推理`

**Observed outcome:**

- The agent fixed B056 and committed it in NECallKit:
  `e169d0b2aae3c644a0ce9990e8cfb3f3e4c45a9a`
  (`feat: 修复 Electron 音视频切换远端摄像头状态`).
- The fix touched Electron runtime state handling rather than native protocol
  definitions.
- It saved ingestible source records under:
  `<workspace>\project\NECallKit\docs\bugfix\B056-electron-video-switch-remote-camera-closed\`
- It updated `TRACKER.md` and `TASKS.md`.
- It left the right manual validation gap: mac -> win and win -> mac real-device
  video -> audio -> video regression, plus true camera-close behavior.

**Wiki signal:**

The run explicitly found the wiki skills and treated the wiki result as a
Medium-confidence answer before deep code work. The wiki did not contain a
direct B056 fix, but it supplied the right prior constraints:

- B045/B047-style regression surface.
- `switchCallType`, local camera preference, and remote RTC video availability
  must remain separate.
- `cid=3,type,state` and source-bridge behavior must be checked before assuming
  a protocol-field gap.
- `onVideoAvailable(false)` / `onVideoMuted(true)` should not be interpreted as
  a call-type switch or local camera preference change.

The important correction was that the user's initial hypothesis was plausible
but wrong: the source already had `send(state=1) -> agree/res(state=2) /
reject(state=3)` and the bridge capability propagated `state`. The actual
answer was a runtime interpretation bug: video stop/mute events during audio
mode polluted `remoteVideoAvailable` / `remoteVideoMuted`, and `muted=false`
did not restore `remoteVideoAvailable=true`.

**What worked better than B055:**

- The agent stated that wiki skills were available, then gave a Medium
  confidence judgment before source investigation.
- Wiki output was converted into a concrete source checklist:
  `cid=3/type/state`, native event mapping, runtime pending/ack/res handling,
  and UI overlay clearing.
- The run followed a credible TDD loop: first target the suspected state-machine
  gap, observe red failures, apply the smallest runtime fix, then run regression
  and guard tests.
- Durable evidence was produced and committed, so the fix can now be ingested
  without relying on chat history.

**Verification captured in the run:**

- `node --test packages/callkit-runtime-electron/test/video-switch-regression.test.ts`
  passed 2/2.
- `node --test packages/callkit-runtime-electron/test/runtime-contract.test.ts`
  passed 20/20 after the red-test cleanup issue was fixed.
- `node --test Electron/scripts/test/switch-call-type-control-source.test.js`
  passed 6/6.
- React/Vue3 shared core and Electron wrapper call-view tests passed.
- `cd Electron && npm run build:native:source` passed, with staged
  `manifest.json` confirmed as `bridgeStrategy=source`.

**Improvement direction:**

- `knock-it-out` improved, but should still require the literal structured
  `## Wiki Answer` block. In this run the information existed in commentary,
  but not in the standard reusable format.
- The closed-loop step should be stronger after a successful fix: suggest both
  ingesting `docs/bugfix/B056-electron-video-switch-remote-camera-closed/` and
  filing a query such as "Electron 音视频切换后远端摄像头关闭 overlay 排查清单".
- The B056 record is a better lesson candidate than B055 if this pattern appears
  again: it captures a reusable reasoning move, "do not assume protocol absence
  before separating protocol capability from runtime state interpretation."
  For now, keep it as a bugfix page plus query candidate, not a lesson.

**Essay payoff:**

This is the strongest `knock-it-out` dogfood example so far. The user supplied a
specific but uncertain hypothesis. The wiki did not simply retrieve an answer;
it constrained the reasoning path, prevented an unnecessary native protocol
change, pushed the agent toward source verification, and produced a committed
fix plus durable records. This is the story to tell: compiled knowledge changes
the next debugging trajectory.

### 2026-05-08 19:19 +08:00 — Ongoing Knock-It-Out Review Protocol

**Action:** Established the review role for the next several `knock-it-out`
runs.

**User intent:** The user will keep running `knock-it-out` on NECallKit issues.
This dogfood log should become the unified evidence ledger, while the reviewer
decides when the output is worth pushing back into the NECallKit wiki.

**Review procedure for each rollout log:**

1. Extract the input issue / requirement, target branch, whether a fix or
   diagnosis happened, and whether the run created a durable project record.
2. Classify wiki coverage:
   - **High:** direct prior page or query answers the issue and only current
     branch verification was needed.
   - **Medium:** wiki gave correct guardrails, prior constraints, or source
     checklist, but root cause / implementation came from source investigation.
   - **Low:** wiki had only broad background or weak keyword overlap.
   - **No answer:** no meaningful wiki hit, or wiki skills were unavailable.
3. Record gaps: missing exact bugfix, missing query page, stale rule, missing
   source bridge / test guidance, or missing confidence checkpoint.
4. Decide wiki action:
   - **Ingest now:** new durable fix/design record is reusable, has verification,
     and changes future debugging behavior.
   - **Batch later:** multiple small adjacent fixes should be imported together
     as a curated 5-10 file cluster.
   - **Query only:** no new source fact, but the investigation produced a useful
     reusable checklist or synthesis.
   - **Do not ingest:** one-off fix, incomplete record, failed hypothesis, or
     no maintainer value beyond chat.
5. Preserve essay material: where wiki reduced context cost, where it failed,
   what the agent still had to verify in source, and whether the result became
   durable project memory.

**Current ingest candidates:**

- `docs/bugfix/B055-electron-camera-unplug-reroute/` — batch with adjacent
  camera/switch runtime fixes; useful but not urgent alone.
- `docs/bugfix/B056-electron-video-switch-remote-camera-closed/` — strong
  candidate for near-term ingest and a reusable query, because it corrected a
  plausible protocol hypothesis into a runtime state interpretation bug.

**Guardrail:** Do not ingest every successful `knock-it-out` result by default.
The wiki should stay curated. A result earns ingest when it gives future agents
a better starting point than raw repo search: a boundary, a regression matrix, a
source checklist, or a durable root-cause pattern.

### 2026-05-08 19:48 +08:00 — Knock-It-Out B057 Product-Rule Change Review

**Action:** Reviewed the next completed `knock-it-out` run from:

- `~\.codex\sessions\2026\05\08\rollout-2026-05-08T19-19-12-019e0750-1fc7-7b31-814e-2923486f4225.jsonl`

**Input issue / requirement:**

`【electron-win/mac】视频通话过程中，关闭摄像头，切换为音频通话，再切换为视频通话，摄像头是关闭状态。需求有变更，需要在切换回视频通话时，默认打开摄像头（如果之前关闭了摄像头）`

**Observed outcome:**

- The agent implemented B057 in NECallKit.
- It changed both Electron runtime state handling and `desktop/core`, because
  changing only UI/runtime state would not guarantee RTC local capture resumes.
- It created durable records under:
  `<workspace>\project\NECallKit\docs\bugfix\B057-electron-switch-video-default-camera-on\`
- It updated `TRACKER.md`, `TASKS.md`, B045 bugfix docs, and
  `docs/guides/electron-flutter-merge-review-checklist.md`.
- The user later reported manual verification passed, and the agent marked the
  B057 manual test rows as passed.
- NECallKit working tree still had B057 changes uncommitted at review time.

**Wiki signal:**

This was a high-value Medium wiki hit. The wiki did not contain B057, but it
contained the exact historical rule being changed:

- B045/B047: keep `switchCallType` and camera preference separate.
- B020-style guidance: if product definition changes, encode it as an explicit
  product rule rather than silently weakening the invariant.
- Source-bridge guard: desktop/core changes must be verified through source
  bridge and `bridgeStrategy=source`.

The wiki helped classify the task correctly: this was not a bug where old
knowledge should be blindly reapplied. It was a product-rule override of the old
"preserve local camera preference" behavior. The new rule is narrower:

- Non-video -> video resolved switch defaults local camera on.
- Repeated `callType=2` resolved / echo events must not reopen a camera that the
  user just closed during an existing video call.
- Microphone mute state must not be reset.

**What worked:**

- The agent found wiki context first and used it to keep the old B045/B047
  boundary explicit while making the new exception intentional.
- It recognized the change crosses runtime and desktop core, avoiding a
  UI-only fix that would make the button state lie while RTC capture stayed off.
- It updated the old B045 merge-protection wording, not just the new B057 page.
  That is the right behavior for a maintained wiki system: changed judgment must
  revise previous guidance.
- It performed code and product verification: runtime contract, B056 regression,
  source guard, React/Vue shared tests, Electron wrapper tests, source bridge
  build, staged manifest check, and manual Windows/macOS validation.

**Verification captured in the run:**

- `node --test packages/callkit-runtime-electron/test/runtime-contract.test.ts packages/callkit-runtime-electron/test/video-switch-regression.test.ts Electron/scripts/test/switch-call-type-control-source.test.js`
  passed 28/28.
- `node --test packages/callkit-react-core/test/call-view.test.js packages/callkit-vue3-core/test/call-view.test.js Electron/react-uikit/test/call-view.test.js Electron/vue3-uikit/test/call-view.test.js`
  passed 50/50.
- `cd Electron && npm run build:native:source` passed.
- `Electron/out/native/win32-debug/manifest.json` confirmed
  `bridgeStrategy=source`.
- B057 manual regression rows were updated to passed after user validation.

**Wiki ingest decision:**

**Ingest now, after the B057 NECallKit working tree is committed.** This should
not wait for a larger batch because the current wiki already contains older
B045/B047 guidance that is now incomplete. If the wiki is not updated soon, a
future `knock-it-out` query may over-apply the old "preserve camera preference"
rule and miss the new product exception.

Recommended curated source batch:

- `docs/bugfix/B057-electron-switch-video-default-camera-on/analysis.md`
- `docs/bugfix/B057-electron-switch-video-default-camera-on/B057-electron-switch-video-default-camera-on-test.md`
- `docs/bugfix/B045-electron-switch-confirm-local-feedback/analysis.md`
- `docs/bugfix/B045-electron-switch-confirm-local-feedback/B045-electron-switch-confirm-local-feedback-test.md`
- `docs/guides/electron-flutter-merge-review-checklist.md`

Recommended wiki output:

- Update the existing camera/switch bug page or create a small B057 bug page.
- Update / regenerate the reusable switchCallType guard query so it includes
  the new exception.
- Do not promote to `lessons` yet. The lesson candidate is stronger after one
  more recurrence: "when product rules override a previous invariant, update
  the invariant page and query, not only the new bugfix page."

**Improvement direction:**

- `knock-it-out` still did not emit the literal standard `## Wiki Answer` block.
  This run had the right reasoning, but the checkpoint remains hard to audit
  from the final answer alone.
- The skill should explicitly flag "wiki old rule contradicted by new product
  decision" as a special case. That case should trigger wiki update earlier
  than an ordinary new bugfix, because stale wiki guidance is actively harmful.

**Essay payoff:**

B057 is a better essay example than a simple bug fix. The value of the wiki here
was not just retrieval; it exposed the old invariant and forced the agent to
make the new exception explicit, update old docs, and verify both runtime state
and native capture. This demonstrates a key thesis: a useful LLM wiki is a
maintained judgment system, not a static pile of prior answers.

### 2026-05-08 20:18 +08:00 — B057 Ingest Completed And Knock-It-Out Rule Updated

**Action:** Completed the B057 NECallKit wiki ingest after the NECallKit fix was
committed.

**Wiki commit:**

- `3353463 wiki-import: B057 switch video camera rule change`
- Pushed to `origin/master`

**Curated source batch:**

- `docs/bugfix/B057-electron-switch-video-default-camera-on/analysis.md`
- `docs/bugfix/B057-electron-switch-video-default-camera-on/B057-electron-switch-video-default-camera-on-test.md`
- `docs/bugfix/B045-electron-switch-confirm-local-feedback/analysis.md`
- `docs/bugfix/B045-electron-switch-confirm-local-feedback/B045-electron-switch-confirm-local-feedback-test.md`
- `docs/guides/electron-flutter-merge-review-checklist.md`

**Wiki changes:**

- Created:
  `bugs/electron-switch-video-default-camera-on-product-rule-change.md`
- Updated:
  `bugs/electron-camera-switch-microphone-state-regression-bugfix-set.md`
- Updated:
  `queries/electron-switchcalltype-regression-merge-guard-query.md`
- Updated:
  `lessons/l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离.md`
- Updated:
  `decisions/necallkit-docs-guides-electron-flutter-merge-review-checklist.md`
- Preserved raw source evidence under:
  `raw/imported/necallkit-b057-switch-video-default-camera-on/`

**Verification:**

- `wiki-search` for `B057 切回视频 默认打开摄像头 产品规则` now returns the
  new B057 page, the B045 bugfix set, L013, the switchCallType guard query, and
  the merge checklist.
- Graph stats: 84 pages / 174 edges / 0 dangling links.
- `wiki-lint --check links,frontmatter,index` still reports only the known
  structural noise: `SCHEMA.md`, `index.md`, and `log.md` frontmatter/index
  issues. No new broken links.

**Skill update:**

Updated installed skill:

- `~\.agents\skills\knock-it-out\SKILL.md`

New rule: when a user states a product or requirement change that contradicts an
existing wiki rule, invariant, lesson, or guardrail, `knock-it-out` must treat it
as a special case:

- name the old rule, the new product rule, and the narrowed exception;
- keep the old guardrail where it still applies;
- test both the new behavior and the old boundary;
- mark the result as urgent wiki follow-up because stale wiki guidance can
  mislead future agents;
- recommend ingest soon with a small batch containing both the new durable
  record and the old page whose judgment changed.

**Product lesson:**

This is the first dogfood instance where the wiki needed to be updated not
because it lacked an answer, but because a correct old answer had become
incomplete. That distinction matters. A maintained LLM wiki must know when new
evidence adds coverage and when it changes prior judgment.

### 2026-05-08 20:27 +08:00 — Wiki-Query Truth-State Change Guard

**Trigger:** Follow-up review of the B057 loop showed that `wiki-query` should
not only detect missing answers. It also needs to detect when a retrieved old
answer may no longer be true.

**User clarification:** The rule must be generic. Code/documentation wikis often
call this a "requirement change", but a general wiki may see the same shape as a
changed fact, policy, price, schedule, API, version, organization, conclusion,
or world state.

**Skill update:**

- Updated source skill:
  `<workspace>\ai\kata\plugin\skills\wiki-query\SKILL.md`
- Synced installed skill:
  `~\.agents\skills\wiki-query\SKILL.md`
- Updated README's Query-to-ingest closed loop to describe generic changed truth
  states, not only software requirements.

**New `wiki-query` behavior:**

- If the user explicitly says the truth state changed, the answer must name the
  old wiki-backed position, the new stated position, the contradiction, and the
  evidence needed before the new position becomes durable.
- If the user does not say it changed, but the query contradicts an existing
  wiki rule, invariant, lesson, prior answer, or known fact, the agent must ask
  a confirmation question before giving a decisive answer.
- A strong hit on an old page is Medium at best when the query may be changing
  that page's judgment; it is Low/No answer if the wiki only contains the stale
  side of the conflict.
- Once confirmed or solved, recommend timely ingest because stale wiki guidance
  is actively harmful.

**Product lesson:** This turns B057 from a narrow NECallKit rule into a general
llm-wiki design principle: the query layer owns "is this still true?" detection,
while ingest preserves the new evidence and updates the old judgment.

### 2026-05-08 23:58 +08:00 — Auto-Dreaming First Scheduled Run

**Action:** Enabled and observed the first NECallKit wiki auto-dreaming run
through Windows Task Scheduler.

**Configuration:**

- Wiki: `~\.llm-wiki\NECallKit`
- Task: `AK Wiki Dream NECallKit`
- Schedule: daily at 22:00
- Command:
  `C:\Windows\py.exe -3 <workspace>\ai\kata\plugin\scripts\wiki_dream.py --wiki ~\.llm-wiki\NECallKit`
- Memory tier thresholds shortened for dogfood:
  - `active_days: 3`
  - `archived_days: 7`
- Dreaming config:
  - `enabled: true`
  - `cadence: daily`
  - `confidence_threshold: 0.6`

**Observed result:**

- Output file:
  `~\.llm-wiki\NECallKit\dreaming\2026-05-08.md`
- `log.md` appended a `dream | weekly run` entry with watermark
  `2026-05-08`.
- Window: `2026-04-08 -> 2026-05-08`
- Fresh pages this period: `81`
- Resurgent tags: `android`, `camera`, `compatibility`, `flutter`
- Candidate pool: `0` archived/frozen pages
- Candidates emitted: `0`

**Interpretation:**

The scheduled execution path works: Windows Task Scheduler invoked the
deterministic `wiki_dream.py` script and produced the expected dated report.
The empty candidate list is expected because the NECallKit wiki is still new;
even after shortening tier thresholds to 3/7 days, all pages remain active on
2026-05-08.

**Product observations:**

- The local shell could not reliably query scheduled tasks without elevated
  permissions (`schtasks /Query` returned a path error), but the successful
  output file and dream log entry are stronger end-to-end evidence than the
  scheduler metadata.
- The task uses `C:\Windows\py.exe -3`, not `python`, because this Windows
  environment resolves `python` to Python 2 and `wiki_dream.py` contains UTF-8
  source text.
- `wiki_dream.py` logs the entry as `dream | weekly run` even when
  `dreaming.cadence: daily`. The log wording should reflect the configured
  cadence or use neutral wording such as `dream | run`.
- `dreaming/2026-05-08.md` is currently discovered by tier computation as a
  wiki page, increasing the page count from 84 to 85. `dreaming/` should be
  treated like an operational output directory, not normal knowledge pages, and
  should probably be skipped by `discover_pages`, `tier_compute`, query, graph,
  and lint unless explicitly requested.

**Improvement direction:**

Auto-dreaming has the right conservative boundary: scheduled runs generate
candidates only and never apply promotions. The next product work is around
operational polish rather than algorithmic scope: exclude `dreaming/` from
normal page discovery, fix the cadence wording, and provide a first-class
Windows scheduling helper that can create/query tasks without relying on ad hoc
shell quoting.

### 2026-05-09 00:59 +08:00 — Knock-It-Out B059 Cross-Platform State Review

**Action:** Reviewed the next completed `knock-it-out` run from:

- `~\.codex\sessions\2026\05\09\rollout-2026-05-09T00-09-19-019e0859-bbc8-7a90-92de-a92b52d30bc3.jsonl`

**User problem reconstructed from the run:**

- macOS Electron calls Windows Electron in video mode; after macOS switches
  video -> audio -> video, Windows can still show "the other side closed the
  camera".
- Windows Electron calls Android; Windows closes camera, switches to audio
  callType, then switches back to video. After the B057 product rule change,
  Windows should reopen local camera when switching back to video, but Android
  can still show stale closed-camera UI.

**Wiki signal:**

This was a high-confidence wiki hit. The existing B057 page, L013 separation
lesson, and switchCallType guard query directly shaped the investigation:

- `switchCallType`, camera switch/local video preference, RTC
  `videoAvailable`, and RTC `videoMuted` must stay separate.
- B057 adds a narrow exception: non-video -> video resolved switch should
  restore local camera.
- `onVideoAvailable(false)` and `onVideoMuted(true)` cannot be used as a
  fallback signal to switch to audio.

The wiki reduced context cost by preventing the agent from chasing the wrong
native-control hypothesis first. It entered source investigation with the right
state model: NIM control decides callType, RTC events describe stream state,
and closed-camera UI must not be polluted by audio-mode video-stop events.

**Gap discovered:**

The wiki had the B057 Electron/product-rule correction, but not the new
cross-platform receiver-side stale-state rule. B057 said the sender should
restore local camera when non-video resolves to video. B059 adds that receivers
must also clear stale closed-camera state when the callType resolves back to
video:

- Electron runtime must clear stale `remoteVideoAvailable=false` /
  `remoteVideoMuted=true` when the resolved switch is non-video -> video.
- Android SDK recorder state must clear stale
  `currentUser/otherUser.isMuteVideo` after accepted switch resolves to video.
- Android old UI must clear common UI state and both big/small closed-camera
  overlays/tips, otherwise lifecycle or later render passes can repaint the old
  closed-camera state.

**Work output from the run:**

- Added B059 durable docs under:
  `<workspace>\project\NECallKit\docs\bugfix\B059-cross-platform-switch-video-stale-camera-closed\`
- Electron runtime/test change:
  `packages/callkit-runtime-electron/src/runtime.ts`
  `packages/callkit-runtime-electron/test/video-switch-regression.test.ts`
- Android SDK/UI change:
  `Android/call/src/main/java/com/netease/yunxin/kit/call/p2p/internal/NECallEngineImpl.java`
  `Android/call-ui/src/main/java/com/netease/yunxin/nertc/ui/p2p/P2PCallActivity.kt`
  `Android/call-ui/src/main/java/com/netease/yunxin/nertc/ui/view/P2PVideoCallLayout.kt`
- Added Android source contract test:
  `scripts/test/android-switch-video-camera-state.test.js`
- Updated `TRACKER.md` and `TASKS.md`.

**Verification captured in the run:**

- `node --test packages/callkit-runtime-electron/test/video-switch-regression.test.ts packages/callkit-runtime-electron/test/runtime-contract.test.ts scripts/test/android-switch-video-camera-state.test.js`
- Result: 25/25 passing.
- `git diff --check`: no whitespace errors; only CRLF warnings.
- Android Gradle compile did not run because this machine had no `JAVA_HOME`
  and no `java` on `PATH`.

**Repository state at review time:**

The run then received a follow-up instruction: "commit Electron-related changes
first; do not commit mobile yet." The agent correctly avoided `ne-git-commit`
because that script would run `git add -A`. The visible rollout log ended after
the selective staging and commit-message preparation, before the actual commit
command appeared.

Current NECallKit state at review time:

- Final repository check shows the Electron-only B059 commit now exists:
  `3572148d feat: 修复 Electron 切回视频远端摄像头残留`
- The commit contains only:
  `packages/callkit-runtime-electron/src/runtime.ts`
  `packages/callkit-runtime-electron/test/video-switch-regression.test.ts`
- Android, `TRACKER.md`, `TASKS.md`, B059 docs, and the Android source contract
  test remain uncommitted.

This is an important dogfood finding: `knock-it-out` handled investigation and
implementation well, but the handoff from "fix is done" to "selective commit is
done" can be hard to audit from the conversation log alone. Ingest decisions
must therefore check the real target repo state, not rely only on the final
answer.

**Wiki ingest decision:**

Do not ingest full B059 yet. The Electron slice is durable, but the B059
cross-platform record is not durable enough while Android, tracker/task
updates, B059 docs, and the Android source contract test remain uncommitted.

Recommended trigger:

- If another switchCallType issue arrives before mobile is finalized, ingest an
  Electron-only B059 note from commit `3572148d` and the Electron regression
  test.
- Prefer waiting until Android/mobile B059 is committed or explicitly abandoned,
  then ingest one curated cross-platform batch.

Recommended curated batch once durable:

- `docs/bugfix/B059-cross-platform-switch-video-stale-camera-closed/analysis.md`
- `docs/bugfix/B059-cross-platform-switch-video-stale-camera-closed/B059-cross-platform-switch-video-stale-camera-closed-test.md`
- `packages/callkit-runtime-electron/test/video-switch-regression.test.ts`
- `scripts/test/android-switch-video-camera-state.test.js`
- Relevant B057/B045 pages only as context links or update targets, not as a
  broad re-import.

**Query-to-ingest implication:**

This is exactly the "new fact derived during solving" case. The wiki was not
wrong, but it was incomplete: B057 covered sender-side product semantics, while
B059 adds receiver-side stale-state cleanup. If this is not ingested soon after
the fix becomes durable, future agents may over-trust the B057 page and stop
after checking only Electron/local camera behavior.

**Product improvement directions:**

- `knock-it-out` should include a final "durability state" block: committed,
  staged only, uncommitted docs, manual verification pending, and whether the
  result is safe to ingest.
- The skill should warn when a selective commit is requested but the configured
  commit helper stages everything. It did this correctly here; the missing part
  is a guaranteed final state check or explicit "commit not completed" final.
- `wiki-query` confidence should account for cross-platform scope drift. A high
  confidence hit on Electron/B057 became Medium for Android receiver behavior
  until source investigation produced new evidence.
- The next reusable query should extend
  `queries/electron-switchcalltype-regression-merge-guard-query.md` into a
  cross-platform checklist: source bridge, sender local camera restore,
  receiver remote-video state cleanup, Android SDK recorder cleanup, UI overlay
  cleanup, and manual two-device regression.

**Essay value:**

B059 is stronger than a simple retrieval success. It shows llm-wiki as a
compiled judgment system: previous knowledge narrowed the search space, but the
closed loop still discovered a missing cross-platform invariant and produced a
new candidate record. The correct behavior is not "RAG answered it"; it is
"wiki constrained the reasoning, source work found the delta, and ingest should
update the maintained judgment once the fix is durable."

### 2026-05-09 01:14 +08:00 — Generalized Cross-Domain Knowledge Handling

**Trigger:** Follow-up discussion after B059 asked how to handle the generic
case where a query has a valid answer in one domain, but solving reveals a new
cross-domain fact.

**Product rule:**

Treat this as **scope expansion / cross-domain fact surfaced during solving**.
It is not a simple "wiki has answer" case, and it is not a simple "wiki has no
answer" case.

**Generic handling model:**

1. Split confidence by scope:
   - Existing covered scope can remain High confidence.
   - Newly exposed scope should be Medium/Low until verified from source or
     primary evidence.
   - The overall answer should not claim High confidence if the user's real
     task depends on the new scope.
2. Label the gap as a cross-domain gap:
   - The wiki has a partial answer.
   - The missing part is a new platform/module/business domain/fact boundary.
   - This is more dangerous than no answer because old guidance can be
     over-applied.
3. During solving, require durable evidence:
   - Save analysis, test records, reproduction notes, or source-contract tests.
   - Do not leave the new cross-domain fact only in chat history.
4. Ingest narrowly:
   - Do not import the whole new domain.
   - Import the 3-6 durable files that prove the new fact.
   - Prefer bug/fact/query pages first; only promote to lessons after repeated
     reuse.
5. Update old guidance:
   - Link the new page back to the old answer.
   - Revise the old query/page if its wording would mislead future users.

**Reusable loop:**

`query -> partial hit -> cross-domain boundary found -> split confidence ->
source/primary-evidence verification -> durable record -> curated ingest ->
old query/page scope update`

**B059 as example:**

B057 correctly covered Electron sender-side product semantics. B059 revealed a
new receiver-side stale-state cleanup requirement across Electron runtime and
Android SDK/UI. The right response is not to bulk-import Android docs; it is to
ingest the B059 cross-domain evidence once the mobile side becomes durable, and
then update the switchCallType guard query with explicit cross-platform checks.

**Essay value:**

This is a clean argument against "RAG dump" framing. A maintained llm-wiki must
represent answer scope, confidence per scope, and changed/cross-domain facts.
The system's value is not just retrieving the nearest old page; it is detecting
when the old page is only locally true and routing the new evidence back into
the compiled knowledge graph.

### 2026-05-09 01:33 +08:00 — Knock-It-Out B060 Shared-Core/Web Scope Review

**Action:** Reviewed another `knock-it-out` run from:

- `~\.codex\sessions\2026\05\09\rollout-2026-05-09T01-08-04-019e088f-8713-72f0-865e-15a88b06e91f.jsonl`

**User problem reconstructed from the run:**

Electron React/Vue3 on Windows/macOS showed a black video surface after the
camera button was used to close video, but the surface did not show explanatory
text. Product expectation:

- local camera closed: show `你关闭了摄像头`
- remote camera closed: show `对方关闭了摄像头`
- waiting for the first remote frame must remain silent and must not be
  misreported as remote camera closed.

**Wiki signal:**

The run produced a structured wiki checkpoint:

- Confidence: `0.78` / Medium.
- Relevant guidance: L013 and B051/B045 family rules still apply.
- Boundary: keep `switchCallType` separate from camera close/mute state.
- Regression warning: B051 removed/avoided camera-closed text to prevent first
  frame wait from being misreported as "remote closed camera"; the new request
  is a narrowed product-rule change, not permission to reintroduce the old
  false positive.

This is a good Medium result: the wiki did not directly contain B060, but it
provided the exact guardrail needed to make the fix safe.

**Cross-domain / Web scope expansion:**

The original user-facing symptom was Electron, but the implementation point was
not Electron-specific. The agent found the behavior in shared UI core:

- `packages/callkit-react-core/src/components/InCallOverlay.tsx`
- `packages/callkit-vue3-core/src/components/InCallOverlay.ts`

That means Web/shared consumers also enter the blast radius even though the
visible bug report said Electron. The agent correctly checked Web runtime state
mapping before finalizing the shared-core condition:

- Web runtime uses `onVideoMuteOrUnmute` to write `remoteVideoMuted`.
- Electron runtime normalizes `onVideoAvailable(false)` /
  `onVideoMuted(true)` to `remoteVideoMuted=true`.
- Therefore shared core can use `remoteVideoMuted === true` as the explicit
  remote-camera-closed signal, while preserving
  `remoteVideoAvailable=false && remoteVideoMuted=false` as "waiting for first
  frame".

This is the B059 cross-domain rule appearing again in a more general form:
when the code ownership layer is shared, the answer scope must expand from the
reported platform to every consumer of that shared layer. The right response is
not to ingest the whole Web domain; it is to record the shared-core invariant
and the Web mapping check that made the change safe.

**Work output from the run:**

- New B060 docs:
  `<workspace>\project\NECallKit\docs\bugfix\B060-electron-camera-closed-overlay-text\analysis.md`
  `<workspace>\project\NECallKit\docs\bugfix\B060-electron-camera-closed-overlay-text\B060-electron-camera-closed-overlay-text-test.md`
- React shared core and tests updated.
- Vue3 shared core, tests, and generated `es/index.js` / `lib/index.js`
  updated.
- `TASKS.md` and `TRACKER.md` received B060 entries.
- Existing Android/B059 changes were left in place and not deliberately edited.

**Verification captured in the run:**

- `node --test packages/callkit-react-core/test/call-view.test.js`: 21/21
  passing.
- `node --test packages/callkit-vue3-core/test/call-view.test.js`: 21/21
  passing.
- `node --test Electron/react-uikit/test/call-view.test.js`: 7/7 passing.
- `node --test Electron/vue3-uikit/test/call-view.test.js`: 7/7 passing.
- `node --test packages/callkit-runtime-electron/test/runtime-contract.test.ts packages/callkit-runtime-electron/test/video-switch-regression.test.ts`:
  22/22 passing.
- Extra Web runtime smoke:
  `node --test packages/callkit-runtime-web/test/runtime-contract.test.ts`
  hit an existing `lib/index.js` ESM/CJS loading error:
  `SyntaxError: Unexpected token 'export'`.

**Repository state at review time:**

B060 is uncommitted. Current NECallKit working tree includes:

- B060 shared core/source/test/generated changes.
- B060 docs.
- Pre-existing uncommitted Android/B059 changes.
- `TASKS.md` and `TRACKER.md` contain both B059/B060 changes.

**Wiki ingest decision:**

Recommend ingest soon **after B060 is committed**, because it narrows older
B051 behavior. The existing wiki could otherwise continue to imply "camera
closed overlay should not show text", when the new rule is more precise:

- no text/overlay while waiting for first remote frame
- text is required for explicit local camera closed
- text is required for explicit remote camera closed
- use `remoteVideoMuted=true` as the explicit remote closed signal in shared
  core
- do not use `remoteVideoAvailable=false && remoteVideoMuted=false` as remote
  closed

Recommended curated batch once durable:

- `docs/bugfix/B060-electron-camera-closed-overlay-text/analysis.md`
- `docs/bugfix/B060-electron-camera-closed-overlay-text/B060-electron-camera-closed-overlay-text-test.md`
- `packages/callkit-react-core/test/call-view.test.js`
- `packages/callkit-vue3-core/test/call-view.test.js`
- Update or link B051/B060 in the reusable camera/switch query; do not import
  all Web docs.

**Product improvement directions:**

- `wiki-query` confidence should support "reported-platform confidence" versus
  "shared-layer consumer confidence". Here Electron symptom confidence was
  Medium/High after source confirmation, while Web consumer safety was Medium
  until runtime mapping was checked.
- `knock-it-out` should explicitly flag "shared layer touched; enumerate
  consumers" as a source-triage step.
- The query-to-ingest loop should treat shared-layer changes as cross-domain
  evidence even when the user names only one platform.

**Essay value:**

B060 is a compact example of controlled scope expansion. The wiki did not
answer the exact product request, but it preserved the B051 guardrail and
forced the agent to express the new rule narrowly. Then source ownership showed
the fix lived in a shared React/Vue3 core, so Web became a necessary confidence
check without turning the ingest into a Web knowledge dump.

### 2026-05-09 01:50 +08:00 — Call Record Ingest Preflight

**Trigger:** User plans to fix a batch of call-record / 话单 bugs and asked
whether NECallKit `docs/` already contains useful material to ingest first.

**Wiki coverage check:**

The NECallKit wiki currently has scattered mentions of `record provider`,
`onRecordSend`, and Electron API alignment, but no dedicated, reusable call
record knowledge page or query. A Chinese-only search for `话单` also exposed a
search/tokenization weakness: the script reported no usable terms, while English
terms like `record provider onRecordSend` returned broad but non-specific hits.

**Docs reconnaissance:**

The source docs contain a strong, curated call-record cluster:

- `docs/prd/F013-electron-default-call-record-sync/` is the main design and
  verification record for default IM call-record sync.
- `B047-electron-record-provider-runtime-debug` records provider mode,
  runtime/source DLL, and `setCallRecordProvider` synchronization pitfalls.
- `B048-electron-call-record-list-append-compact` records list semantics:
  append each `onRecordSend`, do not aggregate by callId, compact display.
- `B018-desktop-record-state-ios-alignment` records raw status value alignment
  across desktop, iOS, NIM message, and provider payload.
- `B027-desktop-record-durations-null` records default NIM call message
  `durations` compatibility with Android Flutter parsing.

**Recommended ingest shape:**

Use one small curated import, not a broad docs import. Suggested batch:

- `docs/prd/F013-electron-default-call-record-sync/F013-electron-default-call-record-sync.md`
- `docs/prd/F013-electron-default-call-record-sync/F013-electron-default-call-record-sync-test.md`
- `docs/prd/F013-electron-default-call-record-sync/F013-electron-default-call-record-sync-tasks.md`
- `docs/bugfix/B047-electron-record-provider-runtime-debug/analysis.md`
- `docs/bugfix/B047-electron-record-provider-runtime-debug/B047-electron-record-provider-runtime-debug-test.md`
- `docs/bugfix/B048-electron-call-record-list-append-compact/analysis.md`
- `docs/bugfix/B048-electron-call-record-list-append-compact/B048-electron-call-record-list-append-compact-test.md`
- `docs/bugfix/B018-desktop-record-state-ios-alignment/analysis.md`
- `docs/bugfix/B018-desktop-record-state-ios-alignment/B018-desktop-record-state-ios-alignment-test.md`
- `docs/bugfix/B027-desktop-record-durations-null/analysis.md`

**Expected wiki outputs:**

- A feature/module page for Electron default IM call-record sync.
- A bug page for custom provider / `onRecordSend` runtime debug and list
  semantics.
- A compatibility bug page for desktop record status raw values and
  `durations`.
- A reusable query page: "NECallKit 话单 bugfix preflight checklist".

**Important boundaries to preserve:**

- Default IM call records and provider-local `onRecordSend` are two different
  sources.
- `setCallRecordProvider(true)` means host takes over and default NIM call
  record sending is cut off; do not use `onRecordSend` as the default record
  receiver.
- Multi-device sync depends on IM call messages/history, not provider-local
  events.
- Desktop raw call status must use the `1..5` NIM/iOS value space, not a local
  `0..4` enum.
- Default NIM call message `durations` must be non-null for downstream Android
  Flutter parsing.

**Ingest gate:**

Do not start the import until the NECallKit wiki working tree is clean. Current
wiki status still contains uncommitted auto-dreaming changes:

- `SCHEMA.md`
- `log.md`
- `dreaming/`

This is a useful product reminder: even preparatory ingest should obey the same
clean-tree rule as normal imports. Mixing operational dreaming output with a new
knowledge import would make the next wiki commit hard to review.

**Product observations:**

- The call-record cluster probably deserves a schema tag such as `call-record`
  or `record`. Without it, searches fall back to noisy English terms or fail on
  Chinese-only `话单`.
- This is another case where the wiki should compile a domain-specific
  preflight query before code work begins. The goal is to stop future agents
  from rediscovering the same source split: default IM message, provider-local
  callback, history sync, raw status values, and durations compatibility.

### 2026-05-09 02:00 +08:00 — Call Record Batch Ingest Completed

**Input:** User asked to complete the curated NECallKit 话单 / call-record batch
ingest before starting a sequence of call-record bug fixes.

**Wiki hit / gap:**

- Before ingest, the wiki only had scattered broad hits around `record provider`
  and `onRecordSend`.
- Chinese-only `话单` search had already exposed a tokenizer/product gap: the
  search script treated it as no usable terms.
- There was no reusable page that separated default IM call records,
  provider-local callbacks, history sync, raw status values, and durations.

**Curated import:**

Imported exactly 10 source files from `<workspace>/project/NECallKit/docs`:

- F013 default Electron IM call-record sync PRD, test, and tasks.
- B047 provider runtime debug analysis and test record.
- B048 call-record list append/compact analysis and test record.
- B018 desktop raw status iOS/NIM alignment analysis and test record.
- B027 default NIM call-message `durations` compatibility analysis.

**Wiki outputs:**

- `features/electron-default-im-call-record-sync.md`
- `bugs/electron-call-record-provider-and-list-semantics.md`
- `bugs/desktop-call-record-status-and-durations-compatibility.md`
- `queries/necallkit-call-record-bugfix-preflight-query.md`
- `SCHEMA.md` tag taxonomy gained `call-record`.
- Raw evidence saved under `raw/imported/necallkit-call-records/`.

**Query distillation:**

The filed query turns the source cluster into a reusable preflight checklist:

- classify symptom by source: default IM, provider-local, UI/list/cache, raw
  bridge payload, NIM call attachment, or adapter ownership;
- preserve boundaries such as provider mode cutting off default NIM sending;
- require truth-state confirmation when a new requirement/fact contradicts old
  F013/B047/B048/B018/B027 guidance;
- tell future agents what fix/development evidence to save for timely ingest.

**Verification:**

- Search `话单 call record onRecordSend provider durations` now returns the new
  provider/list, durations/status, and preflight query pages at the top.
- Tag search `call-record` returns the 4 new pages exactly.
- Graph stats after ingest: 89 pages / 196 edges / 0 dangling links.
- `wiki-lint` still reports only existing structural/frontmatter/orphan noise;
  no new broken links and no new tag errors from the call-record batch.

**Commit:**

- Wiki commit: `747baf2 wiki-import: call record sync and provider cluster`
- Pushed to `origin/master`; import checkpoint cleared.

**Product observations:**

- Preparatory ingest worked as intended: a planned future bug domain triggered a
  small curated import, not a broad docs dump.
- The `call-record` tag materially improves retrieval quality and is a concrete
  example of schema co-evolving with query failures.
- The filed query should be used as the next `knock-it-out` guard before
  touching call-record code. If a future bug changes any boundary, especially
  provider/default IM separation or raw status/durations contracts, ingest
  should happen soon after the fix rather than waiting for a large batch.

### 2026-05-09 02:45 +08:00 — Knock-it-out: B061 Switch Video Default Microphone Rule Change

**Session:** `~/.codex/sessions/2026/05/09/rollout-2026-05-09T01-32-46-019e08a6-24c8-7922-ab26-f7e506853265.jsonl`

**Input:** User invoked `knock-it-out` for a product-rule change: in video
mode, close microphone, switch to audio, do not adjust microphone, then switch
back to video. New expectation: microphone should automatically open. User
explicitly said this differs from the previous requirement.

**Wiki hit:**

- The agent used wiki first and produced a Medium-confidence answer.
- Relevant pages were the existing Electron camera/switch cluster:
  `electron-camera-switch-microphone-state-regression-bugfix-set`,
  `electron-switch-video-default-camera-on-product-rule-change`,
  `electron-win-mac-camera-switch-microphone-state-query`, L013, and the
  switchCallType merge guard query.
- The wiki was useful because it exposed the old guardrail: switchCallType,
  camera state, microphone state, and RTC video availability must stay
  separate.

**Gap / truth-state change:**

- This was not just a missing implementation detail. It was an explicit
  requirement change that narrows prior wiki guidance.
- Old wiki/B020/B057 position: switching call type should not unconditionally
  restore microphone state; B057 only added the camera-on exception and
  explicitly did not reset microphone.
- New B061 position: non-video -> video should auto-open microphone only if the
  user did not touch microphone while in audio mode.
- Current wiki search for `B061 切回视频 默认开麦 麦克风 switchCallType` still does
  not return a B061 page, so future agents can still be misled by the old
  high-signal pages.

**Source outcome:**

- NECallKit commit: `39dcefda feat: 修复 Electron 切回视频媒体状态`
- Commit scope: Electron / desktop / shared core / docs only.
- New/updated durable docs:
  - `docs/bugfix/B061-electron-switch-video-default-microphone-on/analysis.md`
  - `docs/bugfix/B061-electron-switch-video-default-microphone-on/B061-electron-switch-video-default-microphone-on-test.md`
  - `docs/bugfix/B059-electron-switch-video-stale-camera-closed/*`
  - `docs/bugfix/B060-electron-camera-closed-overlay-text/*`
  - updated B020/B057 wording, `TASKS.md`, and `TRACKER.md`
- Mobile/Android related draft work was deliberately excluded and saved as
  `stash@{0}: mobile switch video media todo`.

**Verification evidence:**

- Electron runtime: 21/21
- desktop switch guard: 6/6
- video switch regression: 2/2
- React/Vue shared core: 42/42
- `npm run build:native:source` passed; manifest confirmed
  `bridgeStrategy=source`.

**Ingest decision:**

Recommend ingest soon / urgent. This meets the truth-state-change threshold:
old wiki guidance would now be stale and potentially harmful for the next
switchCallType/microphone bug. The smallest useful curated batch should include
B061 analysis/test, B059 analysis/test, B060 analysis/test, and the updated
B020/B057 notes or query pages they contradict. The wiki pages to update are
the camera/switch bugfix cluster, B057 product-rule page, L013 if needed, and
the switchCallType/camera/microphone query pages.

**Product observations:**

- `knock-it-out` correctly recognized the "requirement changed" phrase and
  avoided treating old wiki rules as final truth.
- The flow also exposed a practical repository hygiene pattern: when a
  cross-platform investigation creates Android draft changes but the user asks
  for Electron-only submission, the agent should stash or otherwise isolate the
  mobile work and record it as todo before running broad commit scripts.
- This is a strong HN/IP example of llm-wiki as compiled judgment rather than a
  static dump: the wiki supplied the old invariant, the user supplied a changed
  product fact, and the final fix produced a new bounded exception that now
  needs to be compiled back into the wiki.

### 2026-05-09 03:25 +08:00 — Knock-it-out: B062/B063 SwitchCallType Reject Semantics

**Session:** `~/.codex/sessions/2026/05/09/rollout-2026-05-09T02-45-35-019e08e8-cdcc-7bb0-ac38-365ddefab8b4.jsonl`

**Inputs:**

1. B062: Electron win/mac, switch call type confirmation enabled. A requests
   video -> audio, B rejects. B sees A's last video frame; expected "对方关闭了摄像头".
2. B063: Electron win/mac, B receives incoming switch request and locally
   rejects in the confirmation dialog. B should not show "对方拒绝了您的请求";
   that toast only belongs to the initiator when the peer rejects its outgoing
   request.

**Wiki hit:**

- Wiki search strongly hit the existing switchCallType cluster:
  `electron-switchcalltype-regression-merge-guard-query`, L013,
  `electron-camera-switch-microphone-state-regression-bugfix-set`,
  `electron-win-mac-camera-switch-microphone-state-query`, B057, and the
  switchCallType remediation history.
- The hit quality was high for guardrails: switchCallType, camera state,
  remote video availability, confirmation flow, and media toggles must stay
  separate.
- For B063, the agent produced a High-confidence wiki answer: `state=3` must be
  interpreted with direction. It is not globally "the other side rejected me".

**Gap:**

- The wiki did not yet contain B062/B063 as durable pages.
- Current search for `B062 switch reject remote camera closed 最后一帧 state=3`
  and `B063 本端拒绝 incoming switch 对方拒绝 state=3` still returns only the
  older switchCallType pages, not the new fixes.
- The missing concept is not another camera/switch separation rule, but a more
  precise reject-state direction model:
  - pending video -> audio can temporarily suppress remote video stop to avoid
    false "camera closed";
  - if that pending request is rejected and the call remains video, the
    suppressed stop should be converted into remote camera closed to hide the
    stale frame;
  - `state=3` should show "对方拒绝了您的请求" only for matching outgoing switch
    requests.

**Source outcome:**

- B062 durable docs:
  - `docs/bugfix/B062-electron-switch-reject-remote-camera-closed/analysis.md`
  - `docs/bugfix/B062-electron-switch-reject-remote-camera-closed/B062-electron-switch-reject-remote-camera-closed-test.md`
- B063 durable docs:
  - `docs/bugfix/B063-electron-local-reject-switch-no-remote-reject-toast/analysis.md`
  - `docs/bugfix/B063-electron-local-reject-switch-no-remote-reject-toast/B063-electron-local-reject-switch-no-remote-reject-toast-test.md`
- Main logic landed in `packages/callkit-runtime-electron/src/runtime.ts` and
  tests in `packages/callkit-runtime-electron/test/runtime-contract.test.ts`
  plus `packages/callkit-runtime-electron/test/video-switch-regression.test.ts`.
- The session also observed unrelated/previous worktree changes under
  Electron examples and desktop/native bridge/core. Those were not reverted.

**SwitchCallType issue matrix:**

| ID | Problem | Durable rule |
|----|---------|--------------|
| B045 | switchCallType, camera toggle, RTC video availability, and confirm flow were conflated | Keep semantic channels separate; source bridge verification needed for desktop/core |
| B057 | product rule changed: non-video -> video defaults camera on | Narrow exception; duplicate `callType=2` echoes cannot reset user camera choice |
| B059 | switch video after audio could leave remote camera closed state stale | On non-video -> video, clear audio-transition remote closed state |
| B060 | true camera closed lost user-visible text | UI displays text only for explicit local/remote camera closed; waiting first frame is silent |
| B061 | product rule changed: non-video -> video defaults microphone on if audio mode was untouched | Narrow microphone exception; preserve audio-mode user operation |
| B062 | peer rejects video -> audio after remote video stop arrived; receiver saw stale last frame | Convert suppressed pending-audio video stop into remote camera closed when reject keeps call video |
| B063 | local reject of incoming switch showed "peer rejected my request" | `state=3` toast requires matching outgoing switch marker; local reject echo is silent |

**Verification evidence from session:**

- B062: runtime/video-switch regression and React/Vue shared overlay tests passed.
- B063: runtime/video-switch regression passed 25/25, React shared 21/21, Vue3
  shared 21/21, Electron wrapper 14/14.
- No source bridge build was run for the runtime-only B062/B063 path. However,
  the current worktree after the session includes desktop/native bridge/core
  modifications from adjacent work; those require source bridge build before
  any final commit that includes them.

**Ingest decision:**

Recommend combining B061/B062/B063 with B059/B060 into one curated
switchCallType reject/media-state update batch after the current NECallKit
worktree is committed or deliberately staged. This batch should update:

- `bugs/electron-camera-switch-microphone-state-regression-bugfix-set.md`
- `bugs/electron-switch-video-default-camera-on-product-rule-change.md`
- `queries/electron-win-mac-camera-switch-microphone-state-query.md`
- `queries/electron-switchcalltype-regression-merge-guard-query.md`
- L013 only if the lesson needs a short note that `state=3` direction and
  pending-video-stop compensation are now part of the protected matrix.

**Product observations:**

- The wiki did reduce context cost: it immediately framed B062/B063 as reject
  semantics inside the existing switch/camera/confirmation boundary, not as a
  generic UI overlay problem.
- But the old query pages are now too coarse. Future answers need an explicit
  direction table for `state=1/2/3`, outgoing vs incoming markers, and what
  happens to RTC video stop events while a switch request is pending.
- This is another example of the closed loop threshold: when several adjacent
  fixes accumulate in the same protected boundary, a small curated import is
  better than waiting for lessons or dumping all docs.

### 2026-05-09 03:45 +08:00 — Wiki ingest: B059-B063 SwitchCallType Media State Cluster

**Trigger:**

The user asked to ingest the newest existing content before solving more
calltype issues, because the fresh B061/B062/B063 fixes were likely to help the
next round. This was a direct Query-to-ingest closed-loop moment: old wiki
queries were useful, but incomplete for the new reject/media-state rules.

**Batch imported:**

- Source repo: `<workspace>/project/NECallKit/docs`
- Source groups: B059 stale remote camera closed, B060 camera closed text,
  B061 default microphone rule, B062 reject remote last frame, B063 local
  reject toast direction.
- Size: 10 curated markdown files, not a broad docs import.
- Raw evidence copied under
  `raw/imported/necallkit-switchcalltype-media-state-2026-05-09/`.

**Wiki output:**

- Created `bugs/electron-switchcalltype-media-state-and-reject-semantics-2026-05-09.md`.
- Created `queries/electron-switchcalltype-reject-state-and-media-preflight-query.md`.
- Updated the existing camera/switch cluster, B057 product-rule page, L013, and
  the two switchCallType query pages.
- The new query has explicit confidence: High, 0.88. It is high confidence for
  Electron runtime/shared UI/desktop-core guardrails, with current-branch source
  verification still required before code changes.

**Post-import verification:**

- Search for `B063 本端拒绝 incoming switch 对方拒绝 state=3` now returns the new
  B059-B063 bug page and new preflight query near the top.
- Search for `B062 switch reject remote camera closed 最后一帧 state=3` now
  returns the updated switchCallType guard query, new B059-B063 bug page, and
  new preflight query near the top.
- Graph: 91 pages / 211 edges / 0 dangling links.
- Lint: exit 1 from known medium-severity index/orphan/frontmatter noise only;
  no HIGH findings and no new dangling links.
- Import checkpoint was cleared after commit.

**Wiki commit:**

- `6c23480 wiki-import: switchCallType media state reject cluster`
- Pushed to the NECallKit wiki remote.

**Reusable guidance now available:**

Future calltype work should start from
`queries/electron-switchcalltype-reject-state-and-media-preflight-query.md`.
It distills the current switchCallType guard matrix: B045 semantic separation,
B057 camera default exception, B061 microphone default exception, B062 pending
video-stop reject compensation, and B063 `state=3` direction handling.

### 2026-05-09 10:55 +08:00 — Knock-it-out: B064 Kick Offline + mac Packaged Runtime Resolver

**Session:** `~/.codex/sessions/2026/05/09/rollout-2026-05-09T02-55-55-019e08f2-453f-7a31-8b69-dad40fadf568.jsonl`

**Part 1 input:**

Electron win/mac: after multi-login is disabled, desktop logs in account A and
another client logs in account A. The desktop client does not exit login, but
can no longer call. Need to find whether a multi-login kick notification exists
and route it into the logout flow.

**Wiki hit:**

- `wiki-search` returned a Medium-confidence starting point, not a direct
  answer.
- Useful pages were Electron/NIM ownership boundaries, V2-only constraints,
  passive event state-guard lessons, and source bridge verification rules.
- Search for `Electron kickedOffline 多端登录 被踢 下线 回登录页` still does not
  return a direct B064 answer. It returns broad Electron/Web reuse, example
  boundary, L013, and generic passive-event lessons.

**Gap:**

- The wiki had the right guardrails but no durable rule for idle
  `onKickedOffline` propagation.
- Missing answer: native `onKickedOffline` must cross
  `desktop/core -> desktop/bridge -> node-addon -> SDK/runtime -> example host`
  even when no call is active. Active-call-only `callEnd(reason=KICKED)` is not
  enough for idle login state.

**Source outcome:**

- NECallKit commit: `f2858deb feat: 完善 Electron 通话切换与踢下线处理`
- Durable repo docs created:
  - `docs/bugfix/B064-electron-kicked-offline-logout/analysis.md`
  - `docs/bugfix/B064-electron-kicked-offline-logout/B064-electron-kicked-offline-logout-test.md`
- The same commit also included B062/B063 and B065-related switchCallType work,
  so B064 should be ingested carefully from its two docs rather than by blindly
  treating the full commit as one topic.

**Verification evidence for B064:**

- Vue3/React kicked offline shell behavior tests passed.
- SDK event alignment passed.
- bridge required symbol test passed.
- runtime switch/camera regression subset passed.
- `npm run build:native:source` passed and staged manifest confirmed
  `bridgeStrategy=source`.
- Windows native-addon fake bridge case was skipped by the existing platform
  gate (`1..0`), which should remain visible in the wiki evidence.

**B064 ingest decision:**

Recommend ingest soon. This is a cross-layer behavior fix with strong reuse
value for future login/IM ownership problems, and current wiki search is broad
enough that a future agent may miss the exact idle-kick propagation rule. The
smallest safe batch is only the two B064 docs, plus targeted updates to:

- Electron/Web bugfix preflight query, if it should mention kick/logout event
  propagation as a passive-event class.
- L005 only if the lesson is broadened from callStatus guard to "passive
  notifications must not be consumed only in active call state".
- L013 only if we want the source bridge checklist to explicitly cover
  login/kick native events, not just switchCallType/media events.

**Part 2 input:**

mac Vue3 dev login works, but packaged login fails:
`Cannot find module '@xkit-yx/callkit-runtime-electron'` from
`Contents/Resources/scripts/lib/callkit-main-service.js`.

**Wiki / source hit:**

- Wiki did not directly contain this packaged runtime resolver bug.
- The useful source precedent was B025:
  `example-external-nim-session` already uses a packaged-aware resolver pattern
  because scripts live outside the app tree and must resolve from
  `Resources/app`.
- The current wiki search for
  `mac packaged callkit-main-service Resources app node_modules runtime createRequire`
  returns broad Electron packaging/runtime pages, L013, B025-adjacent context,
  and generic lessons, but no direct query or bug page.

**Source outcome:**

- NECallKit commit:
  `c5d22dde feat: 修复 Electron mac 打包后登录 runtime 解析`
- Changed files:
  - `Electron/scripts/lib/callkit-main-service.js`
  - `Electron/scripts/test/callkit-main-service.test.js`
- Fix: packaged main service now resolves runtime from
  `Resources/app/package.json` and from Vue3/React UIKit package roots for
  bundled dependency layouts. It preserves dev fallback, but does not swallow
  real packaged runtime internal dependency failures.

**Verification evidence for packaged runtime resolver:**

- `node --test scripts/test/callkit-main-service.test.js` passed 14/14.
- mac/windows packager targeted layout tests passed.
- relevant React/Vue3 UIKit manifest contract test passed.
- `node --check` and `git diff --check` passed for the two changed files.
- No real mac `.app` runtime verification was available in this session.

**Packaged resolver ingest decision:**

Do not ingest immediately from chat only. The fix is reusable and likely worth
the wiki, but the solving session did not save a durable bugfix markdown record
for it. This is a `knock-it-out` process gap: when the fix is committed and the
root cause is reusable, the agent should create an ingestible repo doc before
final commit or explicitly ask whether to create one. Suggested next step is a
small B066/B0xx doc under `docs/bugfix/` describing packaged
`Resources/scripts` vs `Resources/app/node_modules` runtime resolution, then
ingest that single doc or pair.

**Process observation:**

This session is a good HN/IP dogfood example because it shows both sides of the
closed loop. B064 followed the loop well: Medium wiki hit -> source fix ->
durable docs -> ingest candidate. The packaged runtime resolver fix solved a
real problem but skipped the "save an ingestible record" step, so the wiki
maintainer should not import from transient chat alone. The skill should push
harder when a commit is about to land without a durable bugfix/development
record.

---

## 2026-05-09 — Three-cluster ingest session (B064 / B065-B069 / B070)

**Setup:**

Between the previous session and this one, NECallKit landed `2d19d750`
(B066-B069 archival) and `27c5dc04` (B070 archival), so the bugfix docs that
were just `B064` and `B065` last time are now seven docs (B064 through B070)
covering the entire switch-wait-peer + IPC + stale + mac-IPC arc. Treating
them as one big batch would have violated the 5-10-files curated rule and
mixed unrelated semantics, so they were split into three independent
clusters with three independent wiki commits.

**Cluster 1 — B065+B066+B067+B068+B069 switch-wait + IPC + stale (10 files):**

- Wiki commit `d5f585a wiki-import: B065-B069 switch wait peer + stale video cluster`.
- Created: `bugs/electron-switch-wait-peer-and-stale-video-2026-05-09.md`,
  `queries/electron-switch-wait-peer-and-stale-video-query.md`.
- Updated: `bugs/electron-switchcalltype-media-state-and-reject-semantics-2026-05-09.md`,
  `queries/electron-switchcalltype-reject-state-and-media-preflight-query.md`,
  `lessons/l013-...三层隔离.md`.
- Three brand-new concepts surfaced for future queries:
  `outgoingSwitchCallType` state-machine field (replaces the B063 placeholder
  `outgoingSwitchRequestCallType`), IPC `normalize` / `mergeState` cleared
  signal propagation rule, and `pendingFreshRemoteVideoUntilMs` 2-second
  window with positive-signal-does-not-clear semantics.
- Added `ipc` to `SCHEMA.md` taxonomy (lint LOW dropped to 0).

**Cluster 2 — B064 kicked offline IPC chain (2 files):**

- Wiki commit `ef15c97 wiki-import: B064 kicked offline IPC chain`.
- Created: `bugs/electron-kicked-offline-logout-ipc-chain-2026-05-09.md`.
- Updated:
  `modules/002-electron-callkit-contracts-electron-web-unified-public-contract.md`,
  `bugs/002-electron-callkit-electron-uikit-callback-lifecycle-investigation-2026-04-27.md`,
  `lessons/l005-...callstatus 前置检查.md`.
- Documents the five-layer chain: core broadcast generic event → bridge
  `NE_CALL_BRIDGE_EVENT_KICKED_OFFLINE` (ABI patch 2.1.1 → 2.1.2) → node-addon
  `kickedOffline` mapping → runtime `state.kickedOfflineInfo` → example
  `logoutRuntime()` + remembered-login clear + back to login page.

**Cluster 3 — B070 mac IPC setCallConfig facade bypass (2 files):**

- Wiki commit `4145197 wiki-import: B070 mac IPC setCallConfig facade bypass`.
- Created: `bugs/electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09.md`.
- Updated: `bugs/electron-switch-wait-peer-and-stale-video-2026-05-09.md`,
  `modules/002-electron-callkit-contracts-electron-web-unified-public-contract.md`.
- Recorded as the second concrete case of the mac IPC topology gap (after
  B066's IPC `normalize` cleared-signal fix), explicitly tied to the spec
  `electron-macos-mainthread-native-owner-analysis-2026-05-08.md` §11.2
  "example 直连 `runtime.sdk.*`" risk row. Also flags
  `syncDefaultCallRecordProvider` as the next likely member of the same
  class.

**Wiki state after three commits:**

- Lint: `findings_total=52, HIGH=0, MEDIUM=52, LOW=0`. The 52 medium are all
  pre-existing baseline (SCHEMA / index.md / log.md / dreaming frontmatter,
  plus 47 historical orphan spec/orientation imports). No new dangling links
  introduced by this session.
- Page count: 91 → 94 (3 new bug pages + 1 new query page; existing pages
  updated in place).

**Closed-loop search verification:**

To confirm the new pages would actually surface for plausible future
queries, three searches were run with `plugin/scripts/search_naive.py`:

1. `outgoingSwitchCallType 等待对端 stale 远端视频` →
   `electron-switch-wait-peer-and-stale-video-2026-05-09.md` ranks #1
   (body=11 token hits). The new query page ranks #2. Strong hit.
2. `macOS 二次确认开关 setCallConfig 失效` →
   `electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09.md` ranks #1
   (body=42). Strong hit.
3. `B064 kicked offline` →
   `electron-kicked-offline-logout-ipc-chain-2026-05-09.md` ranks #1 with
   `l005` and `electron-web-unified-public-contract` also ranking. Hit.

**B064 dilution observation (genuine dogfood gap):**

A more natural-language query `Electron 被踢下线 退出登录 logout` did **not**
surface the B064 page. `passes={index:81, frontmatter:83, body:0}` — the
keywords are too common across the rest of the wiki (every reuse-boundary
page mentions logout/被踢下线 in passing), so the dedicated B064 page is
diluted. The same query with literal token `kicked offline` works fine.

This is the second time a cluster has shipped where the durable bugfix page
ranks lower than expected for natural-language queries that share tokens
with high-volume orientation/contract pages. It is not a wiki-format defect
— the page itself is correct and wins on identifier-anchored queries — but
it does mean future natural-language queries about kick/logout may land on
a generic boundary doc first. Two reasonable mitigations:

1. Add a "Symptoms / 自然语言 trigger phrases" section near the top of new
   bug pages so common natural phrasings produce token hits in the body.
2. Add an explicit cross-link from the boundary doc back to B064 so that
   even when search lands on the boundary page first, the next hop is one
   click away.

Neither is urgent for this session — pages still rank #1 on identifier
queries — but worth applying when filing future high-traffic concept pages.

**Process observation:**

The three-cluster split worked well. Each cluster commit is small enough
to revert in isolation, the cluster boundaries match the actual semantic
boundaries (switch state machine vs. login lifecycle vs. mac IPC topology),
and lint stayed clean throughout. The single biggest cost was finding the
right cross-links to existing wiki pages (cluster 1 → B059-B063 reject
state, cluster 2 → L005, cluster 3 → cluster 1's IPC normalize page) —
this is exactly the kind of work that benefits from being done by the same
agent in the same session, and it would be much harder to bolt on after
the fact.

The c5d22dde packaged runtime resolver fix is **still** without a durable
bugfix doc; not ingested in this session. Logged as "暂不处理" pending a
later session that creates `docs/bugfix/B0xx-electron-mac-packaged-runtime-resolver/`.

---

## 2026-05-09 — Dreaming run observation (post-ingest)

22:00 cron-triggered dreaming run produced `dreaming/2026-05-09.md`:

```text
Window: 2026-05-08 → 2026-05-09
Strategy: co-occurrence
Threshold: 0.6
Candidate pool: 0 (archived + frozen)
Fresh pages this period: 93
Resurgent tags: ipc
Candidates (0): _No frozen/archived pages crossed the threshold this run._
```

For comparison, the previous run on 2026-05-08 (the first full dreaming run
since the watermark was introduced) used a 30-day window:

```text
Fresh pages this period: 81
Resurgent tags: android, camera, compatibility, flutter
Candidates: 0
```

**Two observations worth keeping for HN essay material:**

### 1. `resurgent_tags` accurately captured today's focus without being told

The whole purpose of the day was the three-cluster ingest of B064/B065-B069/B070.
The single resurgent tag the algorithm surfaced is `ipc` — which is precisely
the new concept introduced today: B066 (IPC normalize cleared signal) and
B070 (mac IPC topology setCallConfig facade) both carry the `ipc` tag, and
`ipc` was added to `SCHEMA.md` taxonomy in the same session because lint
flagged it as drift. The dreaming algorithm independently surfaced the same
"this is new and high-frequency today" signal that the human work explicitly
recognized.

This is the kind of positive-control evidence that's hard to manufacture
deliberately. The user added cluster pages, the lint suggested a taxonomy
update, and the next dreaming run found the same tag organically. Three
independent paths converging on the same observation is exactly the loop
the wiki is supposed to enable.

### 2. `Candidates: 0` is **not** a failure — it's a boundary condition

Both runs returned zero candidates, which on first read looks like dreaming
"isn't doing anything." It's not. The candidate pool is `archived + frozen`,
and the wiki is currently active-tier-dominated (most pages are <365 days
old by `published_at`/`ingested_at`). For dreaming to surface a candidate,
an old page would need to suddenly become co-relevant to fresh content via
shared tags or citations.

That hasn't happened yet because the wiki is still in its bootstrap phase
(91 → 94 pages). The structural insight here: dreaming's value compounds
as the wiki ages — the more frozen content there is, the more chances for
"this dormant page is suddenly relevant again" to fire.

The `resurgent_tags` row, by contrast, fires every day regardless of pool
size, because it's purely about which tags spiked in fresh content. So
even in the bootstrap phase dreaming gives one usable daily signal (today's
work focus) and is silently building data for the eventual second signal
(dormant-page reactivation) once the wiki accumulates frozen content.

### v1.6 dogfood window status

v1.6 obligation is the 4-week observation of auto-dreaming. Today's run
is day-2 (2026-05-08 was day-1). Already two distinct kinds of evidence
collected:

- Day-1 (2026-05-08): 30-day window proves dreaming runs without crashing
  on a fresh ingest history; resurgent tags reflect the lessons-seed
  import that ran in late April / early May.
- Day-2 (2026-05-09): 1-day window proves the watermark advances correctly
  (window narrowed from 30 days to 1 day); resurgent tags reflect today's
  three-cluster ingest. `ipc` taxonomy update closed a feedback loop.

Two more weeks of observation should accumulate enough runs to characterize:
- Whether `Candidates > 0` ever fires (need archived/frozen content first).
- Whether `resurgent_tags` continues to track real work focus or starts
  drifting / repeating.
- Whether the daily run touches dreaming/ files in a way that would matter
  to v1.8 sync (next cross-machine sync will need to merge dreaming/ daily
  files cleanly — log.md has a custom merge driver, dreaming/ does not).

---

## 2026-05-10 — Four-cluster ingest (B071-B074) plus pending hawk catch-up

Source signal: a knock-it-out triggered by the product change *"switchCallType
完成后本地麦克风/摄像头默认恢复打开"*. NECallKit had four fresh bugfix docs
(B071-B074) in working tree from a single mac-side codex session
(`rollout-2026-05-10T11-19-04-...jsonl`) — still uncommitted on the project
side, but the docs themselves are durable.

### Pre-ingest housekeeping

The wiki repo was dirty when this session started: a previous (unrelated)
session had ingested three hawk-related docs (B-1v1 skill misalignment +
hawk cases migration playbook + hawk result format alignment) and a stray
mac-IPC call effects routing lesson, with index.md / log.md updated, but
nothing committed. The user authorized a single catch-up commit
(`f305f358 wiki-import: hawk skill misalignment + cases migration + result
format alignment`) before the new ingest started. This is a recurring
dogfood pattern: **wiki working tree drift across sessions** → next session
must decide commit-or-stash before its own ingest runs (the ingest script
refuses dirty trees by design).

### Four cluster commits

| Commit | Cluster | New page | Existing pages updated |
|---|---|---|---|
| `361ece9f` | B072 switchCallType resolved → 麦克风/摄像头默认打开 | `electron-switch-calltype-reset-local-media-default-2026-05-10` | 5 (B057/B061 page, media-state-reject, switch-wait-stale, reject query, L013) |
| `19afba82` | B074 mac IPC 空话单 snapshot 不覆盖本地 cache | `electron-mac-ipc-empty-call-record-snapshot-cache-reset-2026-05-10` | 2 (B070 mac-ipc-setcallconfig, public contract) |
| `840202cb` | B071 通话页 timer 从 `onCallConnected` 起算 | `electron-duration-timer-from-onconnect-2026-05-10` | 0 (no prior wiki page covered this) |
| `25e9f6bc` | B073 Win external account switch crash | `electron-win-external-account-switch-crash-2026-05-10` | 1 (B064 kicked-offline page) |

### Search verification

Identifier-anchored queries — all four cluster pages rank #1:

```text
"B072 didSwitchCallType 媒体默认打开 audioModeLocalAudioTouched 移除"
  → bugs/electron-switch-calltype-reset-local-media-default-2026-05-10.md (body=7)
"macOS 重启 demo 话单清空 IPC 空 snapshot"
  → bugs/electron-mac-ipc-empty-call-record-snapshot-cache-reset-2026-05-10.md
"Electron 通话页 计时器 onCallConnected accept 不对齐"
  → bugs/electron-duration-timer-from-onconnect-2026-05-10.md
"Windows external 账号切换登录 crash node-nim 顺序"
  → bugs/electron-win-external-account-switch-crash-2026-05-10.md
```

### Three observations worth keeping

#### 1. B072 is the first **product-rule rollback** ingest

B072 explicitly **reverses** B061's narrow exception ("音频态触碰麦克风后切回视
频不开麦"). That makes B072 the first time a wiki page has had to *unwrite*
a prior rule rather than refine it. The cluster ingest update for
`electron-switch-video-default-camera-on-product-rule-change.md` and
`electron-switchcalltype-reject-state-and-media-preflight-query.md` both
include explicit "B061 已废弃 / stale" markers so future agents read the
right version of the rule even if they land on the older page first.

This is interesting evidence for the HN essay: the wiki is supposed to be
durable, but real product evolution requires explicit rollback semantics.
The current pattern (addendum + "stale" annotation + cross-link to new
page) works for one rule version, but if B072 itself gets revised again
the chain may grow brittle. A future improvement could be a `superseded_by:`
frontmatter field that the wiki-search and wiki-query layers honor
automatically.

#### 2. B074 is the third concrete mac IPC topology case — a recognizable cluster is forming

| Bug | mac IPC topology mistake type |
|---|---|
| B066 | normalize 抹掉 cleared 字段（"显式 set undefined" → "absent"） |
| B070 | example 直连 sdk.setCallConfig（mac sdk=null → 静默失败） |
| B074 | subscribe 初始空 snapshot 被当作"清空信号"（adapter 生命周期 ≠ 业务清空） |

Three independent bugs in three weeks, all caused by *renderer code that
made an assumption that worked under in-renderer runtime topology and
silently broke under mac main-side IPC topology*. This is exactly the
kind of pattern the wiki is supposed to compile out — and now the wiki
has it explicitly, with each bug page cross-linking to the others. The
"unified mac IPC topology gap" risk class is visible in
`electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09.md` after the
2026-05-10 addendum was applied by the B074 ingest script.

Next time someone debugs "mac packaged X silently no-ops, Windows works",
the wiki has three concrete cases as priors. That's the compounding
benefit of the closed-loop design.

#### 3. The pending-commit drift problem keeps recurring

Both 2026-05-09 and 2026-05-10 sessions inherited an uncommitted wiki
working tree from prior sessions. Each time, the choice was the same:
commit the prior session's work (with an authorization gate from the
user) before the current ingest runs. This is benign so far — the prior
session's docs were always legitimate ingest output — but it suggests
the dogfood workflow could benefit from a "wiki-commit-or-stash before
ingest" preflight step that's automatic instead of human-mediated.

For the v1.8 sync window: this is also a real-world signal that
single-machine wiki workflows already accumulate uncommitted state.
Cross-machine sync will hit this *first* when machine B fetches and
finds machine A pushed but B has its own local uncommitted ingest.
The current `wiki-sync` preflight refuses dirty trees, which is the
right default — this dogfood log confirms that the "preflight-refuse,
human-decide-commit-policy" pattern is the right tradeoff for now.

### v1.6 dogfood window status (day 3 of 28)

Day 3's evidence:

- **Workload reality check**: 4 independent bugs in one knock-it-out
  session, plus 3 hawk docs from a prior session, plus a stray lesson —
  one day produced 8 wiki pages of ingest output. The wiki workflow
  scales fine at this throughput; the rate-limit is on the user's
  attention to authorize cluster splits (today: one AskUserQuestion,
  ~30 seconds of human time), not on the script execution.
- **Cluster-split call rate**: today both AskUserQuestion calls (cluster
  division + dirty-tree resolution) used the user's "推荐" answer. If
  this generalizes, the recommended option could become a default-with-
  cancel rather than a blocking question, halving the round-trip time.

---

## 2026-05-10 — Process evidence from the source codex sessions (B071 / B073 / B074)

The four bug docs (B071-B074) ingested above were produced by **four separate
codex sessions run within an 8-minute window** (11:16–11:24 UTC+8 on the
mac), each triggered by a `$knock-it-out` for one symptom. The wiki has the
end states; this section captures the *process* — the wiki-search hits and
misses, the dead ends, the user pushbacks — that the bug docs deliberately
omit. It is the highest-value HN essay material from this batch.

### B071 — Mac→Win timer mis-aligned

**Wiki search was a clean miss but a useful constraint.** Four queries —
`"Electron onConnect timer 接通慢 时间未对齐 通话计时器"`, `"duration onConnect
connect timer callDuration connectedTime"`, `"B012 setInterval drift duration
timer"`, `"onConnect Electron call connected 接通"` — all returned body=0.
Top hits were three orientation/boundary query pages with index-only matches.
Agent self-rated **Low–Medium** and wrote the explicit framing:

> *"wiki 搜索没有直接命中『通话页 timer 从 onConnect 起算』的既有结论…它能约束不要误改 native/RTC 语义，但不能直接给出 UI 计时器修复点。"*

This is exactly the right read of a Low-confidence wiki state — wiki tells
you where *not* to go, source tells you where to land.

**A landing-site dead end.** Initial patch dropped the `wasInActiveCall`
guard into `onReceiveInvited` (which has no such variable), test failed,
agent moved it to `onCallConnected`. Cheap to recover, but a real wrong-
turn that the docs polished out. The session also accidentally tripped a
pre-existing `audioModeLocalAudioTouched` regression test from a dirty
workspace and correctly identified it as unrelated to the timer fix.

**The non-obvious lesson the docs don't keep.** Web runtime already had
`connected===true && callStatus===3` as the timer-start guard; Electron
runtime had only `callStatus===3`. The bug was a divergence, not a fresh
defect. Future debuggers seeing a timer / state-machine bug in one runtime
should diff against the other runtime's guards before assuming local
defect.

**Three `<turn_aborted>` interrupts** appear at the start of this session —
the user kicked off the same prompt three times in a row. This is benign
but worth noting: knock-it-out has a startup-cost tail.

### B074 — Mac restart loses call records

**High-confidence wiki hit nearly led the fix astray.** Search returned
`electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09.md` (B070) at
**0.86 confidence**. B070 says: "macOS Electron 24+ 下 renderer 的
`runtime.sdk === null`，example 中直连 `runtime.sdk.*` 会静默 no-op." The
agent's initial hypothesis fit exactly that template — `setCallConfig`-style
silent failure in `setCallRecordProvider`.

**The hypothesis was wrong.** Source reading at
`Electron/example-vue3/src/renderer/app.js:444` revealed a different shape:
Vue3 subscribes to `subscribeCallRecords` at app create, IPC runtime fires
an *initial empty* snapshot, `shell.setCallRecords([])` writes the empty
array straight into per-account localStorage cache. The bug is **renderer
mishandling adapter lifecycle**, not facade bypass.

This is a sharp failure mode of high-confidence wiki hits: when the wiki
has a strong nearby pattern, the agent anchors on it and may need source
to break the anchor. The wiki is right that "mac IPC topology has facade
gaps"; the wiki is *also* right that this is a different, third gap. The
final B074 doc explicitly catalogs B066/B070/B074 as three distinct types
of mac IPC mistakes — that taxonomy did not exist before this session.

**Numbering accident.** Agent first labeled this fix `B071` in scratch
notes, then discovered the project's TRACKER had already advanced to
B071–B073 from concurrent sessions in the same dirty workspace, and
renumbered to B074 mid-session. This is real cross-session drift visible
to a single agent.

**Python 2 stumble.** Default `python` on this Windows machine is 2.7;
first three search invocations failed with parse errors; agent retried
with `py -3` and continued. Same trip-up the wiki ingest scripts ran into
the day before. The pattern is now reproducible enough to deserve a
README-level note (already present in `dogfood-necallkit-mac-ipc-troubleshooting.md`).

### B073 — Win account-switch crash

**This session has the most user pushback in any session this week.** It
is also the only session where the user *explicitly expanded* the fix
scope mid-session.

After the agent landed an example-layer fix (47/47 + 39/39 tests passing)
and reported done, the user replied:

> *"退出 再登录其他账号的时候，偶现crash，不是必现的。 反复重登一个账号，没有crash。感觉是时机的问题，边缘case"*

The agent integrated this signal — same-account doesn't crash because
fast-relogin path skips `runtime.destroy()`; different-account does because
stale config triggers it after `node-nim login(account2)` already happened.

The user pressed harder:

> *"如果按照底层logout可能有底层短尾，包括其他可能的回调的短尾，有通用的保护和规避方案吗"*

This forced the agent past the example-layer patch into proposing a
**four-layer defense pattern**: (1) lifecycle mutex / queue, (2) generation
or epoch counter on runtime tear-down, (3) detach callbacks before destroy,
(4) drain observables to a quiescent state. The user then ratified scope
expansion:

> *"按照最佳实践来设计，从desktop到uikit都可以纳入修复的范围"*

**But the four-layer hardening was never written into `B073 analysis.md`.**
The session ended with only the example-layer patch shipped; the broader
hardening lives only in the codex transcript. This is a real dogfood gap:
the wiki has the surface fix, the user agreed to a deeper redesign, but no
follow-up doc captures the design intent. If a future session re-encounters
"偶现 crash on account switch", the surface fix in B073 will look complete,
and the four-layer defense will be re-derived from scratch.

This is the kind of evidence the wiki *cannot* compile out by itself —
it depends on the codex agent surfacing "by the way, you authorized scope
expansion but no doc captures the design" before the conversation ends.
A reasonable improvement: knock-it-out should detect "user expanded scope
mid-session" and prompt to file a follow-up design doc separately from
the bug fix doc.

**Non-obvious fact.** `activeRuntimeSetupConfig` survives logout
**on purpose** — same-account fast re-login depends on it. The crash is
the corollary: when account changes, the stale config triggers
`runtime.destroy()` AFTER `node-nim login(account2)` already happened on
the shared Windows native NIM runtime. The B073 doc settles for
"edge-case timing"; the actual mechanism is "intentional shortcut whose
inverse case wasn't covered".

### Cross-session evidence — patterns worth keeping

1. **High-confidence wiki hits can anchor wrong** (B074) — the wiki was
   right that this was a mac IPC topology gap, but wrong about *which*
   one. Anchoring is a known LLM failure mode; here it's a real cost
   from a working wiki.
2. **Low-confidence wiki hits can still be load-bearing as constraints**
   (B071) — body=0 across 4 queries, but the orientation pages told the
   agent not to touch native/RTC. The wiki is useful even when it doesn't
   answer the question.
3. **User pushback is the only mechanism that surfaced scope expansion**
   (B073) — without the user's two follow-up turns, the example-layer
   patch would have shipped as the answer. The wiki cannot detect "this
   fix is too local" by itself.
4. **Cross-session bug numbering drift is real** (B074 numbering accident)
   — multiple agent sessions in one workspace within minutes will collide
   on bug IDs unless the project's TRACKER is the canonical authority.
5. **Documentation discards the most useful debugging evidence** — three
   sessions, three cases where the bug doc captured the conclusion but
   threw away (a) wiki-search confidence framing, (b) hypothesis dead
   ends, (c) ratified-but-unwritten design expansions. The dogfood essay
   needs this evidence; the bug doc doesn't. **They are different
   artifacts.**

These five points are the strongest HN essay material the day produced.

---

## 2026-05-11 — Day of design infrastructure (knock-it-out v2 + PRD v1.10 + F011 + offline-message baseline + kata self-meta wiki)

Day 4 of the v1.6 dogfood window. Unlike days 1-3 which were mostly
firefighting (ingest bugfix clusters as fast as they're produced), day 4
flipped to **infrastructure for the dogfood loop itself**. Five things
shipped:

### 1. knock-it-out skill v2 — closing a real dogfood gap

The B073 four-layer-defense leak (§2026-05-10) was a `knock-it-out` flow
that surfaced a user-ratified scope expansion, but no doc captured it.
This is exactly the kind of failure mode the wiki was supposed to
prevent. Rather than file a bug against `knock-it-out`, I edited the
skill itself: `~\.claude\skills\knock-it-out\SKILL.md`,
+118 lines, 5 changes:

- §2 Wiki first: **open a distillation tracking slot** when wiki returns
  Medium-or-below confidence. Every new fact from this point on is a
  *candidate*.
- §3.5 (new) **Mid-investigation distillation gate**: 5 trigger types
  (user confirms / user supplies missing context / user corrects /
  load-bearing 1-liner / user asks for "best practice" / scope
  expansion) → 4-step response (stop and name the fact / confirm /
  propose smallest filing / do not block the fix). Anti-pattern called
  out explicitly.
- §5 Save an ingestible record: extended to include **all** distillation
  candidates from §3.5, not just the final root cause. Filing the
  *evidence chain*, not the *conclusion*.
- §6.5 (new) **Conversation closure check**: before user-says-OK /
  user-says-exit, walk distillation candidates and force per-item
  decision (file / file later with placeholder / discard with reason).
- §Common mistakes: 4 new anti-patterns including the B073 case
  ("ratified-but-unwritten design expansion").

This is **the skill being improved by its own dogfood evidence**. The
skill that observed the gap, also got patched by the gap. That's a
non-trivial loop and worth keeping as essay material.

### 2. PRD v1.10 — External Searchable Sources

User asked: "can we make wiki-search optionally search external doc
sources for ongoing project docs?" The existing v1.4 plugin mechanism
does ETL (fetch + ingest), but ongoing docs need *federation*
(scan + label).

PRD went through 4 review rounds in one day:

- Round 0: 360-line draft (federated search + 6 open questions).
- Round 1: user closed 5 of 6 (decay, output verbosity, query
  never-federates, always_on, cross-wiki) and reframed Q6 as a stronger
  position: never auto-ingest, **even when threshold crosses**.
- Round 2: I drafted the Validation loop wording (3 steps: observe /
  validate / distill). User pushed back: "不要过于追逐 ingest" — the
  wording was too prescriptive.
- Round 3: rewrote the validation loop as `## Distillation: an optional
  pathway` with the explicit framing **"keep using as external reference
  forever is a fully legitimate end state"**. Threshold-triggered output
  now reads as a quiet observation note ("referenced 4 times… there is
  no requirement to distill"). The decay sentence closes the note so the
  user doesn't feel they need to act to make it stop.
- Round 4: user requested `always_on` default conditional on decay
  (`auto = true iff decay != none`) and a `machine_id` scheme for
  per-machine `paths:` overrides. I designed
  `{hostname_short}-{platform}-{home_hash6}` with full absolute paths
  never entering the id, only a SHA1 prefix of the home dir.

PRD final: 775 lines, 6 closed open questions, 4 deferred to v1.11+.

Most interesting design output: **the relaxed framing of the
distillation pathway**. Three deliberate features of the wording (no
obligation verbs; "long-term as external reference is a fine end state";
decay sentence closes the note) make the wiki *not push* even when it
notices repeated references. This is unusually restrained for an
automation feature and worth keeping as essay material on its own.

### 3. F011 merge-back preflight ingest into NECallKit wiki

User: "我准备对 necall 工程考虑合回主分支，分支差距可能比较大，之前做过一轮预审，
有文档，帮我找到并蒸馏到 llm-wiki 里". The F011 PRD/plan family had been
sitting in `NECallKit/docs/prd/F011-master-low-coupling-sync/` for weeks.
Wiki had partial coverage (`modules/electron-web-api-reuse-and-merge-back-switch-contract`),
but no PRD-level entry point, no Lane E 9-conflict checklist, no Windows
DLL ABI gate evidence, no NIM symbol source URG-05 conclusion.

7-file curated batch (PRD spec/tasks/test/merge-back-plan + Windows DLL
ABI gate recovery + Lane E conflict resolution + NIM URG-05 investigation)
→ 3 new wiki pages (feature + decision + query) + 3 updates. Commit
`8aebfb7` in NECallKit wiki.

What's interesting for the essay: **this is not a bug fix or a real-time
ingest — it's a deliberate preflight ingest before a planned big move
(merge-back)**. The user wanted the wiki to have the merge-back narrative
fully compiled *before* the merge starts, so future sessions can search
"我要合回 master，先看哪？" and get a real answer. Wiki as preflight
checklist.

### 4. Offline-message baseline ingest

User: "需要排查和离线消息有关的问题…设置页面可以勾选是否支持离线消息…尝试 ingest
相关文档". Wiki search returned `body=0` for "离线消息 / offline message"
queries — Low confidence. Per `knock-it-out` §3.5, I opened a
distillation tracking slot and ingested the baseline before troubleshooting:

- 2 source files: `2026-04-16-web-ios-singlecall-api-alignment.md`
  (`§2.6 NECallConfig` 4-platform contract) and
  `specs/001-nim-v10-upgrade/spec.md` (User Story 6 离线消息处理).
- 1 new feature page mapping the Electron 5-layer transit
  (settings UI → `syncCallConfig` → `runtime.setCallConfig` → IPC →
  main service → `ne_call_bridge_set_call_config` → V2NIM SDK).
- 1 query page with platform-classified decision tree.
- Feature page **explicitly opens a "待蒸馏 distillation slot"** at the
  bottom: 5 questions the user should answer during troubleshooting,
  with the expectation that findings get filed back per §3.5.

Confidence labeled Medium 0.62 — the wiki has the contract but not the
real-troubleshooting bug docs yet. **The wiki is honest about its own
gaps.**

### 5. kata self-meta wiki created

The plugin maintainer now also uses the plugin to maintain the plugin.
Created `~/.llm-wiki/kata/` with `wiki_id 95ee9eea-…`, ingested
PRD v1.10 as the first baseline page (feature + query, 1 raw file).
Schema taxonomy extended with `kata`, `plugin`, `design`,
`federation`, `prd`, `sync`, `bindings` etc.

This is the structural shift that day 4 enabled: dogfood-of-dogfood. The
v1.10 federation design itself now lives as a `[wiki page]` in a wiki,
not just as a draft PRD on disk. Future v1.8 / v1.9 PRDs, dogfood essay
itself, multi-machine handbook, knock-it-out reform notes — all
candidates for this wiki.

### Day 4 summary

Day 1-3: ingest bugfix clusters from real codex sessions.
**Day 4: ingest the dogfood loop's own infrastructure** — the PRD that
will improve dogfood next time, the skill that observed the gap and got
patched by the gap, the preflight ingest before a big planned move, the
honest Medium-confidence seed for an unsolved issue, and a wiki for the
plugin itself.

The throughput was higher than day 1-3 (8 sources ingested across 4
wikis), but the **payoff is different**: not "more bugs documented", but
"the loop runs a little more smoothly next time."

---

## 2026-05-12 — kata self-meta wiki goes multi-machine

Single user action: pushed the day-4 self-meta wiki to its own remote
(`<internal>/llm-wiki`). Two commits (`de76a12` PRD v1.10
baseline + `5cb8d7a` schema taxonomy extension) are now reachable from
any machine via `git clone`.

This is a one-liner of git plumbing, but worth keeping for essay
material because it **closes a meta-loop**: kata v1.8 sync, designed
for project wikis, is now used to sync the kata self-meta wiki —
the plugin syncing the plugin's own knowledge base.

Second machine onboarding for kata self-meta is now the same 4-step
flow documented in `docs/necallkit-multi-machine-onboarding-handbook.md`
for NECallKit, just with `kata` as the project name and a different
remote URL. The handbook generalizes.

---

## HN Essay Spine Snapshot — 2026-05-12 (delta over 2026-05-08 snapshot)

The 2026-05-08 spine focused on "wiki as compiled memory" and the
ingest-graph metrics arc. The 4 days since have surfaced new themes
that the essay should now include.

### New themes (not in 2026-05-08 spine)

1. **The wiki must support knowledge rollback, not just refinement.**
   B072 explicitly reversed B061's narrow exception. The current
   addendum + "stale" annotation + cross-link pattern works for one
   rollback; a future `superseded_by:` frontmatter field is on the
   v1.11+ list. Real product evolution requires explicit rollback
   semantics, which most wiki tools ignore.
2. **Pattern detection across sessions is the real value.**
   B066 / B070 / B074 are three independent bugs in three weeks, all
   from the same class (renderer-side assumption that broke under mac
   IPC topology). No single bug doc would have surfaced "mac IPC
   topology is a recurring gap class" — the *cross-page* listing did.
   This is what a curated wiki gives you that a RAG over the same
   sources cannot.
3. **High-confidence wiki hits can anchor wrong.**
   B074 wiki returned B070 at 0.86 confidence, perfectly templated;
   the agent followed it and the hypothesis was wrong. Source reading
   broke the anchor. The wiki was *right* that this was a mac IPC
   topology issue and *also right* that this was a different one —
   but the agent (and a human) had to actively resist the template
   match. Anchoring is a known LLM failure mode; here it's a real
   cost from a working wiki.
4. **Low-confidence wiki hits can still be load-bearing.**
   B071 had body=0 across 4 queries. The wiki couldn't answer the
   question, but its orientation pages told the agent which directions
   *not* to go (don't touch native/RTC, this is a UI timer bug). Useful
   even when it doesn't have the answer.
5. **User pushback is the only mechanism that surfaces scope-fit
   problems.**
   B073 ratified a 4-layer hardening pattern over two pushback turns
   from the user; no automated mechanism would have surfaced "your fix
   is too local". The wiki cannot detect this by itself, and the
   `knock-it-out` skill's §3.5 + §6.5 are direct responses to the
   B073 leak — surfaces ratified scope expansion as a closure-check
   item.
6. **Wikis can stay restrained even when they observe.**
   PRD v1.10's Validation loop is explicit about *not* pushing users
   to ingest, even when a file gets hit repeatedly. The threshold note
   reads as observation, not recommendation. The wiki has data; the
   user has agency. This is the opposite of the "convert every signal
   into a TODO" pattern that most tooling defaults to.
7. **Plugins should maintain their own wikis.**
   Day 4 created `kata` self-meta wiki. Day 5 (2026-05-12) pushed it
   to a remote so it's multi-machine. The plugin author's own wiki is
   produced by the plugin itself, which is the simplest possible
   demonstration that the workflow scales.
8. **Documents and conversations are different artifacts.**
   The bug docs (NECallKit `docs/bugfix/Bxxx/analysis.md`) capture
   conclusions. The codex session transcripts capture process. The
   dogfood essay captures cross-session patterns and ratified-but-
   unwritten decisions. Each artifact serves a different reader. The
   wiki is the medium that lets these artifacts be linked rather than
   merged.

### Suggested structure update for the HN essay draft

The 2026-05-08 spine's 6-step story arc is still good, but should be
followed by a Part 2:

- **Part 1**: "From toy to real" — the original 6-step arc (init →
  import → query → re-import → fix → crossing query). Ends with 70
  pages / 85 edges / 0 dangling.
- **Part 2 (new)**: "The dogfood loop closes". Five vignettes:
  - **Pattern detection** (B066 / B070 / B074 mac IPC class)
  - **Rollback** (B072 reversing B061)
  - **Anchoring vs. low-confidence-still-useful** (B074 vs B071)
  - **Pushback surfaces scope** (B073 → knock-it-out §3.5)
  - **The plugin maintaining itself** (kata self-meta wiki + remote)
- **Part 3 (new)**: "What this is not". Honest section about what does
  NOT work — wiki search ranking is token-frequency-naive,
  natural-language queries often get diluted by orientation pages,
  Python 2 vs 3 on Windows trips up scripts repeatedly, no remote
  source types in v1.10, no auto-ingest. The essay would be stronger
  for naming these.

### Hard evidence accumulated since 2026-05-08

NECallKit wiki commits (in chronological order from 2026-05-09):

- `d5f585a` B065-B069 switch wait + stale video cluster
- `ef15c97` B064 kicked offline IPC chain
- `4145197` B070 mac IPC setCallConfig facade bypass
- `f305f35` hawk skill misalignment + cases migration + result format alignment (catch-up from concurrent session)
- `361ece9` B072 switchCallType local media default reset
- `19afba8` B074 mac IPC empty call record snapshot cache reset
- `840202c` B071 duration timer from onCallConnected
- `25e9f6b` B073 Win external account switch crash
- `af911ca` B073 round2 + mac IPC call-info facade + Android switchCallType auto-agree + L014 native singleton finalize (catch-up)
- `8aebfb7` F011 master merge-back preflight (7-file curated)
- `e1f5645` offline message baseline (Medium-confidence seed)

kata self-meta wiki commits:

- `de76a12` wiki-init + PRD v1.10 baseline
- `5cb8d7a` schema: extend tag taxonomy

skill changes:

- `~/.claude/skills/knock-it-out/SKILL.md` +118 lines: §2 distillation
  tracking slot + §3.5 mid-investigation gate + §5 evidence chain +
  §6.5 closure check + §Common mistakes 4 new anti-patterns

PRD work:

- `docs/PRD-v1.10-external-searchable-sources.md` 775 lines, 6 closed
  open questions, 4 deferred to v1.11+

Wiki state at 2026-05-12 EOD:

- NECallKit wiki: ~110 pages, ahead origin 0 (recently pushed by user)
- kata self-meta wiki: 4 pages, ahead origin 0 (just pushed today)

### What I still need to write up before publishing

Per the §Essay Material Ledger framing (top of file):

- A real "in agent's voice" example of one knock-it-out session start
  to end (B073 is the strongest candidate — user pushback → 4-layer
  hardening → ratified but not yet filed → §6.5 prompts → ingest).
- Screenshots / search output samples showing grouped output, distillation
  hints, validation loop note text.
- The "what is not working" honest section (Part 3 above).

The dogfood essay file itself is now ~3400 lines of evidence; the HN
essay published version should target 2-3k words and link out to this
file for full evidence trail.

## 2026-05-14 — wiki-search natural experiment: archived-heavy hit pattern (v1.6 evidence)

**Context.** Codex Desktop session
`019e2234-61d2-7a13-ad96-bf0388531a42` (started 2026-05-14T00:38:38+08:00,
cwd `<workspace>\project\NECallKit`) ran `knock-it-out` to spec a new
F016 task: Electron Vue2 UIKit reuse aligned with the existing
Web/Electron Vue3 path. The agent followed `knock-it-out`'s
"wiki first, then source" rule and emitted three `search_naive.py`
queries against `~/.llm-wiki/NECallKit` before reading any source.

**Tier hit distribution (3 queries × top 10 results).**

| Query | Active hits | Archived hits |
|---|---|---|
| `Electron Vue2 web-vue3 reuse vue3-uikit` | 0 | 10 |
| `electron web reuse thin wrapper shared core` | 1 | 9 |
| `Web basic-vue2 Vue2 demo callkit-vue2-ui` | 2 | 8 |

Effective: 28 of 30 top-tier-all hits were archived. Two active hits
were `modules/electron-web-api-reuse-and-merge-back-switch-contract.md`
and `decisions/002-electron-callkit-web-master-diff-assessment-2026-04-25.md`.

**Agent self-narration (verbatim, agent message stream).**

- #51: "wiki 命中很强，但多数是归档层资料；这意味着它能给架构边界，
  不足以直接决定今天这条 Vue2 新任务。"
- #76: "Wiki Answer Confidence: 0.66（Medium）. Vue2 没有被 wiki
  明确纳入既有 Electron/Web reuse 主链路，当前资料主要覆盖
  React + Vue3 + 1v1 + external."

The agent then read 5 archived pages individually (handbook, quick
reference, upgrade-readiness review, compat matrix, follow-up plan)
before pivoting to source (`packages/`, `Web/basic-vue2/`,
`Electron/vue3-uikit/`). Final output: a spec proposing
`F016-electron-vue2-uikit-reuse` with a recommended architecture
(`callkit-vue2-core + runtime-electron` thin wrapper) plus 5 explicit
open questions.

**What this proves about the tier model (positive).**

The archived layer was **load-bearing**, not noise. The architecture
boundary "`packages/` carries domain/runtime/framework core; `Web/` and
`Electron/` are thin wrappers; example is consumer template only" came
out of archived pages and shaped every line of the final spec
recommendation. The tier system surfaced the right corpus.

**What this proves about wiki-search ergonomics (negative).**

The agent needed to scan all 10 results in each output to realize the
archived-heavy pattern. There is no aggregate `tier_breakdown` in the
search envelope, so the "low active coverage on Vue2" signal was
inferred page-by-page rather than read once. Cost: ~10 extra shell
calls (read 5 archived pages + 3 source files) before the spec could
be drafted.

Excerpts were also low-value: returned strings like
`"# Electron/Web reuse 在 NECallKit 多平台仓库中的维护边界  ## Question  Electron/We…"`
— title plus section header, almost no body. The agent had to open
each page to see what it actually claimed.

**Surprises (v1.6 dogfood log slot).**

- archived hits were architecturally useful even when not directly
  decision-bearing — the tier signal lets the agent know "this is
  stable history, take it as ground but don't act on it as live state."
  That distinction is doing real work.
- Vue2 was a coverage gap that the wiki never named. The agent
  detected it inductively (all hits archived for vue2-specific terms)
  rather than by an explicit "this domain is uncovered" signal. A
  coverage-matrix dreamer strategy would have flagged the Vue2 ×
  Electron empty cell automatically.

**Tuning thoughts (v1.6 dogfood log slot — for week-4 retrospective).**

1. Add `tier_breakdown: {active: N, archived: M, frozen: K}` to
   `search_naive.py` JSON envelope. One-glance signal, saves the
   per-result scan.
2. Fix `_excerpt()` body-bias: prefer body matches over title matches,
   or skip leading H1/H2 region. Current output is heading-noise.
3. **Do not tune** dreamer weights/thresholds mid-window. These two
   ergonomic fixes are about the search surface, not the v1.6 frozen
   parameters (`entity 0.5 / tag 0.2 / citation 0.4 / threshold 0.6`).

**Coverage-gap as a feature idea (v1.7+ backlog).**

The wiki had full Vue3 × {Web, Electron} coverage, full React × Web
coverage, and zero Vue2 × Electron coverage. Co-occurrence dreaming
does not see absent cells. A "coverage-matrix" dream strategy that
treats stack × platform as an implicit grid could emit candidates of
the form "stack=Vue2 × platform=Electron has 0 active pages but 8
archived hits in last query month — consider creating a current-state
page." See `docs/idea-coverage-matrix-dreamer.md` for the full sketch.

**Bugs / annoyances (v1.6 dogfood log slot).**

- excerpt = title + section header, not body content (see fix #2 above)
- no aggregate tier breakdown (see fix #1 above)
- no signal when a query has 0 active hits but high archived count —
  this is the "low active coverage" hint the agent has to infer manually

**Scenario fit (v1.6 dogfood log slot).**

- Research direction clarified: yes — wiki architecture boundary
  framed the Vue2 spec recommendation.
- Information acquisition improved: partial — archived layer covered
  Vue3 reuse; Vue2 needed source archeology.
- Discussion reuse improved: yes — the agent picked up the unified
  contract decision (`electron-web-unified-public-contract.md`) and
  carried it through to spec open questions.

**Quantitative.**

- 3 queries × 10 results = 30 hits returned
- 28/30 archived, 2/30 active
- 5 archived pages read in full before pivot
- 3 source files read after pivot (`package.json` × 2, `vite.config.ts`)
- ~20 shell calls between first search and final spec
- Final output: 1 spec recommendation + 5 open questions, no source
  edits requested

**Citation handles for the essay.**

- Codex session id: `019e2234-61d2-7a13-ad96-bf0388531a42`
- Session jsonl: `~/.codex/sessions/2026/05/14/rollout-2026-05-14T00-38-38-...jsonl`
- Final spec target path: `docs/prd/F016-electron-vue2-uikit-reuse/`
  (not yet created on NECallKit side)

### 2026-05-14 rerun follow-up — pin + rank-fix evidence

After the 00:42 session and the analysis above, four architecture
pages on `~/.llm-wiki/NECallKit` were pinned to `tier_override: active`
(see `wiki-tier` action) and `search_naive.py` got two fixes
(`tier_breakdown` aggregate + `TIER_RANK` rank tiebreaker) shipped in
commits `48360c8` and `d3a7945` on `surebeli/kata`. A fresh Codex
session was then asked to re-run the same three queries cold (no
prior conversation context) and produce a single new confidence
number — explicitly NOT a new F016 spec.

**Rerun numbers (top-10 active surfaces, before → after):**

| Query | Before | After |
|---|---|---|
| `Electron Vue2 web-vue3 reuse vue3-uikit` | 0 / 10 | 3 / 10 |
| `electron web reuse thin wrapper shared core` | 0 / 10 | 4 / 10 |
| `Web basic-vue2 Vue2 demo callkit-vue2-ui` | 2 / 10 | 5 / 10 |
| **Total** | **2 / 30** | **12 / 30** |

Tier-pool delta (unfiltered): active hits 17 → 20 (per-query top
shows tighter movement because rank now bubbles pinned pages up).

**Confidence rerun.**

- before: 0.66 (Medium) — original 00:42 session, all 28/30
  archived, agent reported labeling gap honestly
- after:  0.82 (High) — rerun session, top-10 surfaces the pinned
  architecture-overview + unified-public-contract + reuse-handbook
- delta:  **+0.16**

**Agent's own justification** (verbatim from rerun output):

> "active tier 现在把架构总览、统一 public contract 和 reuse
> handbook 推到前排，足以支持 shared core + thin wrapper 的 F016
> 推荐，但 Vue2 专项仍主要靠 Vue3/Web 边界外推，所以不是 0.9+。"

**Why this is the right delta size.**

A delta of +0.16 (Medium → High but not Very-High) is the *honest*
number. The fixes raised the surface signal — pinned architecture
pages now lead the rank, so the agent can see the load-bearing
content without scanning 5 archived pages. But the **content gap**
on Vue2 specifically is unchanged: no page describes Vue2 Electron
reuse explicitly. The agent correctly refused to claim 0.9+
confidence. That refusal is the load-bearing observation for the
essay's §⑤ thesis: "the tool's job is to make the agent's
confidence track actual coverage, not maximize it."

**What this leaves on the v1.7+ backlog.**

The coverage-matrix dreamer idea (`docs/idea-coverage-matrix-dreamer.md`)
is the only proposal that could close the Vue2 gap automatically — by
surfacing absent cells in a stack × platform grid as gap candidates
rather than waiting for someone to notice the gap manually. The pin+
rank fixes shipped today are the *surface* layer; the gap-detection
layer is the foreshadow.
