# NECallKit Dogfood HN Brief

> Condensed writing brief from the first real kata dogfood run on
> `<workspace>\project\NECallKit`.

## Core Thesis

The useful LLM output was not the chat answer. It was the edited knowledge
base: cited pages, backlinks, graph position, health checks, and git history.

Short version:

> RAG retrieves prior context. A maintained wiki changes the next workflow.

## Best Story Arc

1. Start with a real SDK monorepo, not a toy fixture.
2. Import one Electron/Web feature dossier and discover that page count alone is
   not memory: 56 pages, 0 edges.
3. File maintainer-grade query answers back into the wiki. The graph starts to
   compound: 61 pages, 26 edges.
4. Import repository operating context: architecture, platform matrix, agent
   rules, tracker, docs index, and guides. Project-level anchors appear.
5. Import only a curated `lessons/` seed set after adding a higher admission
   bar. The wiki turns history into a bugfix preflight checklist.

## Evidence Timeline

| Stage | Evidence |
| --- | --- |
| Initial import | `bb89cfc wiki-import: 002-electron-callkit (56 pages)` |
| First filed query | `3826ff6 wiki-query: file electron web upgrade positioning` |
| Second filed query | `63ec617 wiki-query: file example contract boundaries` |
| Orientation import | `e3769c7 wiki-import: necallkit orientation guides (10 files)` |
| Operating-boundary query | `8acdbe1 wiki-query: file electron web operating boundary` |
| Lessons seed import | `06c6edc wiki-import: necallkit lessons seed set (6 files)` |
| Lessons preflight query | `cac98d5 wiki-query: file electron web bugfix lessons preflight` |

Graph arc:

| Moment | Pages | Edges | Dangling links |
| --- | ---: | ---: | ---: |
| Feature dossier imported | 56 | 0 | 0 |
| Two filed maintainer decisions | 61 | 26 | 0 |
| Project operating context imported | 69 | 68 | 0 |
| Operating-boundary query filed | 70 | 85 | 0 |
| Lessons seed + preflight query | 77 | 134 | 0 |

## Strongest Product Proof

The strongest proof is the `lessons/` loop.

The user pushed back that `lessons/` should not become an unbounded bucket for
every small incident. The workflow adapted:

- added an explicit admission policy,
- rejected runbook-like or one-off facts from the seed,
- imported only six high-signal lessons,
- filed a query that turned them into a reusable Electron/Web bugfix preflight.

The final query, `queries/necallkit-electron-web-bugfix-preflight-lessons-query.md`,
entered the hub list with inbound 7, outbound 9, score 11.5. This is the essay's
clearest "wiki compounds" moment: six old lessons became the checklist for the
next agent before code is written.

## Maintainer Acceptance Signal

The maintainer rated all four filed query pages:

| Query | Correctness | Usefulness | Retention |
| --- | ---: | ---: | ---: |
| Upgrade positioning | 5 | 4 | 5 |
| Example boundary | 5 | 4 | 5 |
| Operating boundary | 5 | 5 | 5 |
| Lessons preflight | 5 | 5 | 5 |

Summary:

- 4/4 queries rated 5 for correctness.
- 4/4 queries rated 5 for retention.
- The two later cross-corpus queries rated 5/5/5.

## What The Preflight Checklist Proved

The query converted imported pages into operational checks:

- Async race: every `await` boundary must be checked against reset / clear /
  dispose.
- State-machine boundary: distinguish illegal state, repeated call, and already
  in target state.
- Passive signal guard: validate `callStatus` for NIM / RTC / signaling events,
  not only active APIs.
- Lifecycle split: enumerate OS / host entry paths before fixing background or
  floating-window regressions.
- Electron bridge boundary: verify source bridge, staged native artifact, and
  manifest before trusting demo/package behavior.
- Logger / SDK boundary: sanitize complex objects before passing them to vendor
  logger or SDK code.

This is stronger than "the answer cited sources." It changes the next workflow.

## Real Friction

These are useful because they make the essay credible:

- Windows `python plugin\scripts\wiki_init.py --help` failed; `py -3` worked.
- Skill names and script names are not always discoverable: `wiki-digest` maps
  to `digest.py`, `wiki-lint` maps to `lint_naive.py`.
- Chinese-only search failed once with `query has no usable terms`; English
  probes worked.
- `SCHEMA.md`, `index.md`, and `log.md` are counted as content by lint / graph /
  digest.
- `log.md` appears as a graph hub because log entries contain wikilinks.
- Dry-run did not originally validate post-dedup wikilink resolution; lint
  caught five broken links after the orientation import.
- `rg` was unavailable on this Windows machine.
- AK repo staging remains blocked by a `.git/index.lock` ACL issue, so evidence
  capture is currently file-level, not committed in the AK repo.

## Honest Limits

Do not overclaim:

- This has not been compared against a fresh cold repo read on the same question.
- Multi-machine `wiki-sync` has not been tested in this NECallKit wiki.
- The lint tool still reports structural-file noise on `SCHEMA.md`, `index.md`,
  and `log.md`.
- Only a seed set of lessons was imported; the rest of `docs/lessons/` is
  intentionally not admitted yet.

## Candidate Opening

I pointed an LLM-maintained filesystem wiki at a real multi-platform SDK
monorepo. The first import created 56 pages and zero links. It looked like
progress, but it was not yet memory.

The turning point came later, when a curated set of six old bug lessons became a
pre-flight checklist for the next Electron/Web bugfix. The wiki did not just
retrieve context. It changed what the next agent should inspect before writing
code.

## Candidate Closing

Chat answers disappear into transcripts. RAG retrieves a fresh pile of context
each time. A maintained wiki leaves a scar: a page, a backlink, a graph edge, a
lint result, a commit.

That scar is what the next agent can stand on.
