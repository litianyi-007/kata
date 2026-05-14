# Essay #2 — "The wiki returned 28 archived results. The bug was mine."

> **Status:** outline / pre-draft · pending user approval
> **Replaces:** the originally-planned cold-baseline experiment opener for Essay #2
> **Style guide:** `docs/essay-style-guide.md` (Dark Terminal locked, same as #1)
> **Date:** 2026-05-14
> **Provenance:** Codex Desktop session `019e2234-61d2-7a13-ad96-bf0388531a42`, 2026-05-14 00:38 +08:00, NECallKit dogfood wiki

---

## Meta

| | |
|---|---|
| Platform (first publish) | **HN** |
| Word target | ~2000 (HN budget) |
| Lens | L2 (design-decision honesty — when the tool exposes its own design error) |
| Continuity with #1 | #1 said "thresholds are the unsolved gap." #2 says "the wiki has unsolved gaps too, but they're cheap to spot if the wiki tells you." |
| Required IDs to surface | F016 (the Vue2 spec that triggered this), v1.6 (the dreaming system whose tier model mis-fired), the 17→20→3-in-top-10 numbers |
| Visual style | Dark Terminal — same as #1 |
| Status | outline |

---

## Why this replaces the cold-baseline experiment

The original Essay #2 plan was: 8 queries × 2 agents × ±wiki = 16 synthetic
runs to produce a magnitude number ("wiki+agent beats agent-alone by X%").

This dogfood loop is stronger evidence for three reasons:

1. **It's not designed to prove kata works.** It's a real production session
   that *exposed* a kata design flaw — and the flaw was fixable in five minutes.
2. **The evidence chain is uncuttable.** Codex jsonl is a frozen snapshot. The
   git history shows the schema pin commit. The rerun shows the rank shift.
3. **The thesis is honest.** A "kata vs no kata" benchmark would look like
   marketing. A "kata surprised me and I fixed it" essay looks like engineering.

---

## Spine

### ① Hook — concrete dated moment (target 100-150 words)

**Anchor:** the moment Codex said "Confidence: 0.66, Medium" about a Vue2
Electron spec.

**Beat sequence:**

1. Open with timestamp: "On 2026-05-14 at 00:42 +08:00, I asked Codex to
   spec a new task: align Electron Vue2 UIKit reuse with our existing
   Vue3 path. Codex did what kata trains it to do — query the wiki
   before the source."
2. Show the verbatim output snippet: "wiki 命中很强，但多数是归档层资料。
   Confidence: 0.66, Medium."
3. The bite: 30 hits returned. 28 archived. The agent inferred "the wiki
   covers this domain historically, not currently" — and was right, and
   couldn't tell me what to do about it.
4. Pivot: I was about to add more documents. Then I realized the wiki
   wasn't under-populated. It was mis-categorizing what it had.

### ② Why I built tier in the first place (target 250 words)

**Goal:** ground the reader in what tier is supposed to do.

- The problem tier solves: a wiki you run for 18 months has hundreds
  of pages. The market moves on. You need a hot surface and a cold
  archive so queries don't drown.
- The original design intent: research wikis. Pages about Mosaic that
  were hot in 2024 are cold in 2026. Pages about "MoE routing" might
  resurface. Dreaming is the bridge.
- Default thresholds: active < 365d, archived 365-730d, frozen >730d.
  Driven by `updated` field, not by content.
- Implicit assumption (this is the bug, foreshadow it): **age is a
  proxy for relevance**.

### ③ Conflict — age is not relevance for architecture (target 400 words)

**Goal:** name the design error in one clean sentence and then unpack it.

The one-line frame:

> **For research wikis, "old" means stale. For architecture wikis, "old"
> means stable.** kata's tier model treated them the same.

Unpack:

1. NECallKit's wiki had ~110 pages. The most load-bearing pages —
   `architecture-overview`, `electron-web-unified-public-contract`,
   `electron-web-reuse-development-handbook` — described **invariants**.
   The kind of fact that won't change for five years.
2. They were dated 2026-04-20. By default policy on 2026-05-14, they
   were active. By 2027-04-20, they would be archived. By 2028, frozen.
3. Nothing about their **content** would change in that span. The
   `packages/` shared core boundary is permanent. The page would be
   archived not because the world moved on, but because nobody opened
   it for a year.
4. **Why Codex couldn't help me see this:** the tier label "archived"
   collapsed two different meanings — "this knowledge has decayed" and
   "no one has touched this lately." The agent reported the surface
   signal (`tier=archived`) and recommended I trust source code, which
   was correct given the label semantics but wasted ~15 minutes of
   agent time.

Pull the rug:

> The wiki didn't have a coverage gap. It had a **labeling gap**. And the
> tool I designed gave the agent exactly enough information to detect
> the labeling gap honestly: "wiki 命中很强，但多数是归档层资料。"

### ④ Five-minute fix — and what it didn't fix (target 350 words)

**Goal:** demonstrate the fix loop and then surface the second-order bug
the fix exposed.

1. Decision: instead of tuning thresholds (which would affect every
   page indiscriminately), use the per-page escape hatch. v1.6 already
   ships `tier_override:` in frontmatter. Set four pages to active.
   Time cost: 5 minutes.
2. Concrete diff:
   ```yaml
   # 4 pages got this added
   tier_override: active
   tier_reason: stable architecture fact, not subject to time decay
   ```
3. Re-run the same three queries. Numbers:
   - Active hits in the unfiltered pool: 17 → 20 (+3 net moved across
     the line; one of the four pins was redundant).
   - `low_active_coverage` flag: still true (20/106 = 19%, threshold 20%).
   - **Pinned pages in top 10: 1 → 1.** No change.

   *Wait, that's not the result I expected.*

4. The second bug surfaces (this is the most important paragraph):

   > I had two design errors, not one. The first was tier semantics —
   > age ≠ relevance for architecture. The second was that **tier
   > wasn't a ranking signal at all**.

5. Look at `rank_key()`. Sort tuple: title-match, tag-match, hub,
   body-match, updated, path. No tier. So even after pinning, an
   archived page with a single extra title-keyword would still beat
   a pinned architecture overview.
6. Second fix: insert tier as a tiebreaker after tag-match, before hub.
   Active > archived > frozen. ~10 lines of Python.
7. Re-run, now driven from a **fresh Codex session** with no prior
   conversation context — the same cold-start shape as the 00:42
   session that produced the 0.66 number. Three queries, top-10 each:

   | Query | Active in top-10 before | Active in top-10 after |
   |---|---|---|
   | "Electron Vue2 web-vue3 reuse vue3-uikit" | 0 | 3 |
   | "electron web reuse thin wrapper shared core" | 0 | 4 |
   | "Web basic-vue2 Vue2 demo callkit-vue2-ui" | 2 | 5 |
   | **Total active surfaces** | **2 / 30** | **12 / 30** |

   Six-fold lift on the metric the original Codex session implicitly
   complained about. Total session time for the rerun: another 10
   minutes including the agent's verification reads.

### ⑤ The real insight — tier semantics are domain-dependent (target 400 words)

**Goal:** zoom out from "I fixed two bugs" to the design observation that
matters.

The fix I made (per-page pins + tier as ranking tiebreaker) is local.
The insight is global:

1. **Memory tier is a system-level lie that needs a system-level
   patch.** A single `compute_tier(date)` function can't serve a
   research wiki and an architecture wiki at once. The same threshold
   that correctly archives last year's MoE paper incorrectly archives
   last year's shared-core boundary description.

2. **Domain shapes the decay function.** Sketch a table:

   | Wiki type | What "archived" should mean |
   |---|---|
   | Research / market | "the world has moved on" — date-based aging fits |
   | Architecture / code | "no longer maintained" — date-based aging is wrong |
   | Personal / journal | "no longer relevant to me" — depends on resurgence |
   | Business / project | "the project shipped or was killed" — status-based, not date |

3. **The cheapest fix is the one I made**: per-page `tier_override` +
   tier-aware rank. The honest fix is **domain-aware tier policy** in
   SCHEMA.md. Future kata schemas need a `tier_policy:` field that
   selects between aging models. I haven't built that yet — it's
   v1.7+.

4. **The deeper pattern**: AI tools surface design errors faster than
   human review does, *because the AI doesn't know what a good answer
   looks like and just reports the surface*. Codex didn't editorialize
   ("most of this is archived but probably still valid"). It said
   "Confidence 0.66" and stopped. That stop was the signal.

   The bar for AI-paired tool design isn't "the agent gives me the
   right answer." It's "the agent reports a surface that lets me see
   when my tool's design is wrong."

5. **The rerun confidence delta — and what it didn't fix.** A fresh
   cold-start Codex session, same three queries, same three reference
   pages, produced a new self-reported confidence:

   > before: 0.66 (Medium) → after: 0.82 (High) → delta: **+0.16**
   >
   > Agent's own one-sentence justification: "active tier 现在把架构
   > 总览、统一 public contract 和 reuse handbook 推到前排，足以支持
   > shared core + thin wrapper 的 F016 推荐，但 Vue2 专项仍主要
   > 靠 Vue3/Web 边界外推，所以不是 0.9+。"

   The honest part is the second half. The fixes raised the **surface
   signal** the agent could see, but the wiki still had a **content
   gap** — Vue2 was never written about explicitly. The agent saw
   that gap, named it, and refused to inflate the confidence above
   what the data supported. That refusal is what the tier-policy +
   rank fixes were really for: not "make the answer more confident,"
   but "make the agent's confidence track the actual coverage."

   A v1.6 dreamer can't fill that Vue2 content gap — only the
   coverage-matrix idea (`docs/idea-coverage-matrix-dreamer.md`) can
   surface absent dimensions as gap candidates. That's v1.7+. The
   surface fixes shipped today; the gap-detection fix is the
   foreshadow.

### ⑥ Resolution — what changed and what didn't (target 250 words)

1. Four commits to kata public main covering the surface fixes:
   `48360c8` (tier_breakdown + excerpt body-bias), `59b9313` (dogfood
   evidence + coverage-matrix idea), `d3a7945` (TIER_RANK rank
   tiebreaker + v2.1.0 manifest bump), `e6cc313` (plugin.json bump
   to 2.1.0 + Codex update path documented). Plus `e8b1271`
   (pre-commit hook now scans author identity — a separate compliance
   leak surfaced during this same session, a meta-instance of the
   pattern: AI agents running my tooling expose every design hole at
   once, not in sequence).
   One commit to NECallKit wiki (`tier_override:` on 4 pages).
2. F016 (the Vue2 spec that triggered this) is **unchanged**. The
   architectural recommendation didn't depend on which tier the
   pages were in — it depended on the content, which I now have
   surfaced correctly.
3. What I'd do differently next time: build the tier system with a
   `tier_policy:` schema field from day one. The defaults should
   advertise which assumption they're making, not hide it.
4. **The bar I'm holding kata to** (and this is the close):
   > Every time an AI agent says "Medium confidence" while using
   > kata, that's not a kata bug. That's a kata signal. The agent
   > is telling me what part of the wiki design hasn't caught up to
   > my actual workflow.
   > 
   > Treat it as instrumentation, not as failure.

### ⑦ Closing — what this means for AI-paired tooling generally (target 200 words)

Generalize one step.

- The cheap version of "AI helps you build software" is "AI writes
  more lines per hour."
- The honest version is "AI runs your tools at higher cadence than
  you can review them, so your tools' design errors show up in
  weeks instead of years."
- A wiki designed by humans, maintained by humans, would not have
  surfaced the tier-semantic mismatch for 18 months — because no
  human queries 30 archived pages in sequence and reports a
  confidence number. An AI does, and reports it honestly.
- kata is therefore not "wiki + AI." It's **a wiki whose design
  errors are observable in real time because the AI surfaces them.**
  That's the actual product.
- One-line outro candidate: "The 28-archived-results moment was
  the most honest review my own tool has ever given me."

---

## Required citations / footnote candidates

- Codex jsonl path (redacted to `~/.codex/sessions/2026/05/14/...`)
- git commit handles `48360c8`, `59b9313`
- `docs/dogfood-necallkit-hn-essay.md` "2026-05-14 — wiki-search natural experiment"
- `docs/idea-coverage-matrix-dreamer.md` (the third design idea this loop spawned)
- `plugin/scripts/search_naive.py:rank_key` (the rank fix)

## Open questions before drafting

1. **Voice match with #1.** Essay #1's hook used B074 with a hard 16:32
   timestamp. This essay uses 00:42. Same structure, different scene.
   Acceptable repetition or change it up?
2. **Should the second-bug reveal be a separate section, or folded into ④?**
   Currently it's the climax of ④. Splitting might dilute it.
3. **Cold-baseline status.** Outline assumes we cancel the 16-run cold-baseline
   experiment. Confirm.
4. **Publish window.** Same Tue-Thu 8-11am PT as #1, or stagger by 2+ weeks
   so #1's HN front-page tail doesn't compete?

## Non-goals

- This essay is NOT about kata's full architecture, NOT about Phase 0-3
  layering, NOT about the F011/F016 merge-back work that triggered the
  session. Those are background — the foreground is "I designed a thing
  badly and the AI noticed before I did."
