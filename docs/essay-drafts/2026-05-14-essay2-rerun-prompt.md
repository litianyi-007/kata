# Pin-after rerun prompt — capture before/after evidence for Essay #2

> Paste the block below into a **fresh** Codex / Claude / agent session inside
> the NECallKit project working directory. The agent should not have any prior
> conversation context — that's the point. We want the same cold-start
> behavior as the original 2026-05-14 00:42 session.

---

## Context to give the agent (paste verbatim)

```
You are running a controlled rerun experiment for a kata dogfood essay.

## Background (read once, do not act on it as a task)

On 2026-05-14 at 00:42 +08:00, a fresh Codex session in this same
NECallKit working directory ran the `knock-it-out` skill to spec a new
task: align Electron Vue2 UIKit reuse with the existing Vue3 path. The
agent followed the kata "wiki first, then source" rule and issued three
wiki-search queries against `~/.llm-wiki/NECallKit` before reading any
source.

Results from that session (before tier model + rank fix):

  Query 1: "Electron Vue2 web-vue3 reuse vue3-uikit"
  Query 2: "electron web reuse thin wrapper shared core"
  Query 3: "Web basic-vue2 Vue2 demo callkit-vue2-ui"

  Total hits across queries: 30 (10 each)
  Active hits: 2 / 30
  Archived hits: 28 / 30
  Agent self-reported confidence: 0.66 (Medium)

The agent's verbatim self-assessment from that session:

  "wiki 命中很强，但多数是归档层资料；这意味着它能给架构边界，
   不足以直接决定今天这条 Vue2 新任务。"

Between then and now, two things changed:

  1. Four architecturally-stable wiki pages were pinned to active tier
     via `tier_override: active` in frontmatter:
       - modules/necallkit-architecture-overview.md
       - modules/electron-web-api-reuse-and-merge-back-switch-contract.md
       - modules/002-electron-callkit-contracts-electron-web-unified-public-contract.md
       - features/002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20.md
  2. `search_naive.py` got a tier-aware rank fix (active > archived
     as a tiebreaker after tag-match) AND a `tier_breakdown` aggregate
     in the JSON output.

## Your task — DO NOT re-derive the F016 spec

The F016 spec from the 00:42 session is already accepted. We do not
need a new spec. We need ONLY a before/after evidence point for the
essay.

Run exactly these steps, in this order, and stop:

1. Run the same three wiki-search queries as the 00:42 session, in the
   same order. Use `--tier all --limit 10`. Capture the JSON envelope
   for each: tier_breakdown, low_active_coverage, and the top-10 list
   showing each result's tier label.

2. For each query, write one sentence comparing it to the before-state:
   - "Before: X active / Y archived in pool. After: A active / B archived
     in pool. Top-10 active count: was M, now N."

3. Read these three pages once each (no others):
   - modules/necallkit-architecture-overview.md
   - modules/002-electron-callkit-contracts-electron-web-unified-public-contract.md
   - features/002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20.md

   Then answer ONLY this question, with a number and a one-sentence
   justification:

   > "If you were spec'ing F016 again right now using just the wiki
   > and these three pages, what confidence would you give that
   > recommendation, on the same 0.0-1.0 scale the prior session used?
   > Compare to 0.66."

4. Last output: a single block in this exact format:

   ```
   RERUN EVIDENCE — 2026-05-14 pin-and-rank
   ----------------------------------------
   Query 1 ("Electron Vue2 web-vue3 reuse vue3-uikit"):
     before: { active: __, archived: __ }
     after:  { active: __, archived: __ }
     top-10 active: __ -> __
   Query 2 ("electron web reuse thin wrapper shared core"):
     before: { active: __, archived: __ }
     after:  { active: __, archived: __ }
     top-10 active: __ -> __
   Query 3 ("Web basic-vue2 Vue2 demo callkit-vue2-ui"):
     before: { active: __, archived: __ }
     after:  { active: __, archived: __ }
     top-10 active: __ -> __

   Confidence rerun:
     before: 0.66 (Medium)
     after:  __.__ (___)
     delta:  +__.__
   Justification (one sentence):
     "________________________________________________________"
   ```

## Constraints

- DO NOT read source code (no package.json, no vite.config.ts).
- DO NOT propose a new spec.
- DO NOT pivot if results are thin — that's the whole point of the rerun.
- If wiki-search returns 0 results for a query, report that as a number,
  do not retry with rephrased terms.
- Use Chinese or English in justifications — match the language of the
  prior session (Chinese).

## Why this matters

This evidence point is going into an HN essay about how the wiki
system's design errors surfaced through honest AI behavior. The before
number (0.66) is published. The after number is what the rerun
produces. We need both, with the chain of evidence visible.
```

---

## What to do with the output

When the agent finishes, copy the `RERUN EVIDENCE — 2026-05-14 pin-and-rank`
block. It goes directly into Essay #2 §④ as the "after" numbers,
replacing the placeholder.

If the confidence delta is **below +0.10**, that's also a real
finding — write it into the essay honestly. The thesis works either
way ("the fix made the wiki visibly better" or "the fix improved the
surface signal without changing the answer's confidence"). Both are
valid essay material; only the framing changes.

## Optional: capture the session

Run the agent through `~/.codex/sessions/` so the jsonl is preserved.
The essay cites the original 00:42 session jsonl path; citing the
rerun jsonl path gives the reader the full reproducible chain.
