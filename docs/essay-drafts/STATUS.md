# Essay pipeline status — 2026-05-14

> One-page dashboard for the kata essay program. Updated on landing
> changes; the source of truth for "what's the state of essay #N
> and what's the next concrete move." Scan first, dig second.

## Essay #1 — "Code quality is solved. Business thresholds aren't."

| | |
|---|---|
| Lens | L1 (code quality vs business gap) |
| Platform | HN (English) + 公众号 (Chinese derivative) |
| EN draft | `docs/essay-drafts/2026-05-13-essay1-code-quality-vs-business-DRAFT.md` |
| ZH draft | `docs/essay-drafts/[zh] 2026-05-13-essay1-code-quality-vs-business-DRAFT.md` |
| Outline | `docs/essay-drafts/2026-05-13-essay1-code-quality-vs-business-outline.md` |
| Review A | Applied. `docs/essay-drafts/2026-05-13-essay1-review-A.md` |
| Review B | Codex adversarial review — **deferred** (Windows sandbox bug `CreateProcessWithLogonW failed: 1056`; retry on mac/Linux or with `-s untrusted`) |
| Shipped | `882599c` essay#1: apply review A fixes (Tier 1 + selected Tier 2) + add LICENSE |
| Publish window | Tue/Thu 8-11am PT (style guide §5) |
| **Submit date (LOCKED 2026-05-14)** | **2026-05-15 Friday — Beijing 23:00 Fri → 02:00 Sat = PT Fri 08:00 → 11:00** |
| Pre-publish checklist (§10) | ✓ All 12 items PASS — verified 2026-05-14 EOD |
| **Status** | **LOCKED-FOR-SUBMIT 2026-05-15 PT morning window** |

### Why Friday (off-pattern)

Style guide recommends Tue/Thu for HN, but Friday is a "submit now"
decision over a "wait until next Tue (2026-05-19)" 4-more-day slide.
The slip-cost (data freshness, momentum, cold-baseline-experiment
sequencing) outweighs the Tue/Thu cadence preference for #1.

For Essay #2 publish, return to Tue/Thu cadence (Essay #1 reception
data will inform timing).

### Submission inputs (ready to paste into HN)

- **Title (≤80 chars):** `Code quality is solved. Business thresholds aren't.`
- **URL:** Direct draft URL on github (raw markdown) OR a cleaner host
  if a markdown→HTML pass is preferred. Default: paste raw github
  link to the draft file.
  - Github raw: `https://github.com/surebeli/kata/blob/main/docs/essay-drafts/2026-05-13-essay1-code-quality-vs-business-DRAFT.md`
- **No `text` field** — HN submission is link-only (the essay's full body
  is at the URL).
- **Tags / category:** N/A on HN (no built-in tags); first comment can
  set context if needed.

### Closeout once submitted

Post back to this STATUS.md (and to the dogfood log):
- HN submission URL
- Front-page peak rank + timestamp
- Comment-thread notes (top 5 substantive comments + author replies)
- Reception-driven tone calibration for Essay #2

---

## Essay #2 — "The wiki returned 28 archived results. The bug was mine."

| | |
|---|---|
| Lens | L2 (design-decision honesty — AI surfaces my tool's design errors) |
| Platform | HN (English) — same shape as #1 |
| Outline | `docs/essay-drafts/2026-05-14-essay2-tier-mismatch-outline.md` (locked, real numbers in §④/§⑤) |
| Replaces | Originally-planned 16-run synthetic cold-baseline experiment (canceled) |
| Evidence chain | `48360c8` + `59b9313` + `d3a7945` + `36bc0e4` (rerun evidence) |
| Confidence data | `0.66 → 0.82 (+0.16)` from 2026-05-14 rerun, agent justification verbatim |
| Top-10 active surfaces | `2/30 → 12/30` (six-fold lift) across 3 wiki-search queries |
| EN draft | NOT STARTED |
| ZH draft | NOT PLANNED — decide at publish week |
| Publish target | ~2026-05-28 onward (T+2 weeks after #1, so reception doesn't compete) |
| **Status** | **OUTLINE-LOCKED, DRAFTING-PENDING** |

### Decision needed

Defer drafting until **after Essay #1 actually submits**. The HN
reception data on #1 will inform tone calibration for #2 (e.g., if
#1 lands with a "you're being too philosophical" critique, #2's
§⑦ generalization section needs softening).

---

## Backlog — essay candidates beyond #1, #2

Captured for future-self; **not committed** to drafting any of these.

| Candidate | Source material exists? | Notes |
|---|---|---|
| Coverage-matrix dreamer essay | `docs/idea-coverage-matrix-dreamer.md` (idea note) | Premature — v1.7+ scope, no implementation evidence yet |
| Compliance-leak retrospective | `docs/compliance-retro-2026-05-14.md` (just landed) | Has the meta-narrative arc ("tool exposes its own author's identity gap"). Possibly works as a short post, not HN. |
| Windows-CI postmortem | `tests/AUTOMATED_TESTS.md` postmortem section | Niche audience. Could be a developer-tools blog post. Not HN. |
| Multi-machine sync after 1 month of dogfood | None yet | Wait until v1.6 dogfood window closes (~2026-06-05) and the v1.8 sync usage data is real. |
| Pre-PRD ideation → coded feature loop | None yet | Wait until coverage-matrix or another idea note crosses into a shipped PRD + implementation. |
| Essay #1 followup ("if X readers liked Y, here's why Z") | Depends on #1 reception | Holding pattern — don't draft until reception data exists |

---

## Publication tooling state

| Tool / process | Status |
|---|---|
| Style guide v1.2 | Locked, in `docs/essay-style-guide.md`. Used for #1 + #2 |
| Pre-publish §10 checklist | 12-item, mechanical, applies to every essay |
| Visual identity | Dark Terminal palette, `$` title prefix |
| Footer template | Established with #1 (links to dogfood log) |
| HN submission username | Public surebeli identity |
| 公众号 publication flow | Established with #1 |

---

## Citations format convention

(For future essays / public artifacts that reference today's work.)

- All commit citations use the public hash on `surebeli/kata`:
  `48360c8`, `59b9313`, `d3a7945`, `e6cc313`, `e8b1271`, `36bc0e4`,
  `f21d427`
- Session jsonl paths use `~/.codex/sessions/...` form, never absolute
- Wiki paths use `~/.llm-wiki/<project>/...` form, never absolute
- File paths inside repo: relative from repo root

These rules are enforced by `.compliance-blocklist.txt` for code
artifacts; for essay drafts they're style convention not blocklist-
enforced. If essay drafts ever hit a release branch (vs personal
drafts), `compliance-blocklist.txt` will block them on the same
absolute-path rules.

---

## Update policy for this file

Update this file:
- When an essay moves between status states (outline → drafting →
  shipped → published)
- When publication windows shift
- When the backlog gains or loses a candidate
- When tooling state changes

**Do not** update this file just for individual draft revision notes —
those belong in the draft file's commit history.
