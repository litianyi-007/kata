# Essay Style Guide — kata dogfood essays

> Single source of truth for style / content / visual conventions across
> all HN / 公众号 / 内部论坛 essays derived from kata dogfood work.
>
> Read before writing. Run §Pre-publish checklist before submitting.
> When you discover a new pattern that works, add it to §Changelog and
> bump the version. This guide is the spine of the IP — drift here =
> drift in author identity.

Status: v1.2 — 2026-05-13 (Builder ethos added; brand locked to Kata)
Owner: surebeli
Source: distilled from style discussion 2026-05-13 (see git log of this file)
Related: `docs/essay-framework-survey-2026-05-12.md` (candidate roster)

---

## 1. Purpose

This guide exists because writing essays one-by-one against vague taste
produces drift. After 3 essays your readers should be able to recognize
the IP from the first paragraph and the first diagram. After 10 essays
the recognition should be automatic.

Use it for:
- Drafting any new essay (HN / 公众号 / 内部论坛 / talk slides)
- Reviewing a draft before submitting
- Onboarding a future agent or collaborator to the IP

Update it when:
- A convention you tried worked well — codify it
- A convention bombed in feedback — strike it
- A new platform enters the rotation — add a column

This is a **rule book, not a suggestion list**. If you need to break a
rule, document why in the post-publish reflection.

---

## 2. IP Persona — "AI native dev + 探索"

### What "AI native dev" means here

An engineer whose **primary collaborator is an LLM agent**, not an IDE
or a Stack Overflow tab. The agent writes code, the agent debugs, the
agent files docs. The human shapes the system the agent operates in —
the wiki, the schemas, the skills, the dogfood loop.

Not: "I use Copilot sometimes." Not: "AI changed my workflow."
This is: **the loop runs on agent labor; the human runs the loop**.

### What "探索" means here

Frontier-curious. Treat every dogfood session as an experiment with a
hypothesis, a measurement, and a finding. Report findings even when
they contradict your prior post. **Visible iteration > polished
posture.** Readers should see you revising the model, not pretending
you knew the answer.

### Builder ethos (added v1.2, 2026-05-13)

The product is named **Kata** for a reason. Five values flow from that,
and every essay should carry at least one of them — not as marketing,
as the writer's actual stance:

1. **Every builder creates their own workflow.** Kata is the form you
   inherit; your project's workflow is what you forge from it. Essays
   should show the writer's own kata, not a universal one.
2. **FOMO → builder ladder.** Readers who feel left behind by AI can
   start by adopting a kata; the workflow's success is measured by how
   soon they outgrow it. Each essay should leave at least one reader
   ready to try their own version.
3. **Observe → Think → Act** is the primitive loop. Every skill maps
   to one of these three phases. Essays should make the phase explicit
   when narrating: "I observed X, decided Y, did Z."
4. **Human + AI cooperate, neither replaces the other.** The human
   curates and decides; the AI maintains and compounds. Essays should
   not frame AI as a threat OR as a savior — frame it as a collaborator
   the writer is learning to work with.
5. **Democratize.** Lower the barrier to "having your own workflow."
   The wiki is one ladder; the goal is for new builders to climb it
   and write their own. Avoid jargon walls and "you have to know X
   first" gatekeeping.

In one sentence: **accept all, adapt all, transcend all** — adopt the
kata to start, change it to fit your project, then let the form fade as
your work takes over. Every essay's closing should hint at the next rung
on this ladder.

### Reference benchmarks (compass, not copies)

- **Simon Willison** — short, frequent, evidence-first, links every
  claim. We borrow: cadence + linkability.
- **Karpathy** — long-arc framing essays with iconic visuals
  ("Software 2.0", "RNN unreasonable effectiveness"). We borrow:
  one signature visual per essay + one durable framing per essay.
- **Geoffrey Litt** — design-thinking, "I built a tool for myself
  and learned X" cadence. We borrow: tool-as-probe stance.
- **阮一峰 / 玉伯 / Mr.Wang** (中文圈) — clean structure, dense
  technical, opinionated. We borrow: structure clarity + opinionated
  voice for 中文版本.

### Do NOT mimic

- Founder-CEO thought-leadership voice
- "10 things I learned" listicles
- Vendor case-study tone
- Vague "AI is changing everything" essays without anchored
  experiments

---

## 3. Core principles (immutable across platforms)

These never bend regardless of platform / length / topic:

1. **Every concrete claim cites source-file:line, commit SHA, bug ID,
   or PRD section.** No "I found that..." without a pointer.
2. **Every dated moment uses absolute time (ISO + hour when possible).**
   No "last week", "recently", "the other day."
3. **Show iteration, not posture.** Round numbers, version numbers,
   draft labels — make the seams visible.
4. **One signature visual per essay minimum.** Naked text essays don't
   ship from this house. See §6.
5. **One open gap reported per essay.** Always. End with "I haven't
   measured Z yet" or "the next experiment is W."
6. **Bilingual identifiers stay identifiers.** `wiki-session-ingest`
   stays `wiki-session-ingest` in 中文 essays too. B074 stays B074.
   Don't translate code.
7. **No marketing voice.** No "revolutionary", "powerful", "seamless",
   "best-in-class". If you can find the word in a vendor blog, cut it.

---

## 4. The Spine — 7-section structure (every essay)

```
┌─────────────────────────────────────────────────────────────────┐
│ ① Hook              60-120 words / 字   1 concrete moment       │
│ ② Why this matters  120-180             abstract claim          │
│ ③ Setup             200-300             experiment frame        │
│ ④ Conflict          400-800 (+visual)   what surprised you      │
│ ⑤ Resolution        400-800 (+visual)   mechanism / data        │
│ ⑥ Lesson            200-300             name the pattern        │
│ ⑦ Next iteration    150-250             what you're building    │
└─────────────────────────────────────────────────────────────────┘
```

### Section-by-section discipline

**① Hook.** Open with a single concrete moment, not a thesis. Time
stamp + scene + tension. The reader should feel "what happened next?"
within the first 80 words. **No "In this post I will argue..."**

**② Why this matters.** Pivot from the moment to the abstract claim.
This is where the thesis lands. One sentence that comments can argue
with. **If a competent skeptic can't disagree, the thesis is too
soft.**

**③ Setup.** Frame the experiment. What did you try, what did you
expect, what was the prior hypothesis. **Show the prior — without it,
the surprise has nothing to land against.**

**④ Conflict.** What surprised you. This is the heaviest section.
Insert the first signature visual here (data viz, taxonomy, timeline).
Drop in concrete numbers and citations. **Honest about uncertainty:
"I thought X. I was wrong. Here's the evidence."**

**⑤ Resolution.** How the system / mechanism / fix actually works.
Second visual here if needed (architecture, flow). **Don't hide the
ugly parts** — a clean resolution is suspicious. Reference the PRD or
the commit where you locked the decision in.

**⑥ Lesson.** Name the pattern. Give it a 3-5 word label readers can
quote. "Code-correct, business-wrong." "The wiki dreams." Make it
quotable, not just true.

**⑦ Next iteration.** One paragraph. What's the next experiment, where
does the PRD live, what's the open gap. This is the persona's
signature payoff: **the story doesn't end with this essay**.

### Word budgets per platform

| Section | HN (English) | 公众号 (中文) | 内部论坛 (中/英) |
|---|---|---|---|
| ① Hook | 60-120 | 100-150 字 | 100-150 |
| ② Why | 120-180 | 150-220 | 200-300 |
| ③ Setup | 200-300 | 250-350 | 300-500 |
| ④ Conflict | 400-700 | 500-800 | 600-1000 |
| ⑤ Resolution | 400-700 | 500-800 | 600-1000 |
| ⑥ Lesson | 200-300 | 200-300 | 200-400 |
| ⑦ Next iter | 150-250 | 150-250 | 200-400 |
| **Total target** | **~1800** | **~2300** | **~3000** |

---

## 5. Cross-platform adaptation

One essay, three drafts. **Always write HN draft first** — it's the
tightest standard. Then derive the other two by relaxation + reflow.

### Platform matrix

| | HN | 公众号 | 内部论坛 |
|---|---|---|---|
| Language | English | 中文 (identifiers stay English) | 中/英, audience choice |
| Audience | AI tool builders, senior eng, contrarian-tolerant | 技术决策者 + eng 混合; 手机阅读 | 同事、PM、相关 team |
| Reading session | Desktop, 10-20 min, depth | Mobile, 5-8 min, scroll | Desktop, 15-30 min, depth |
| Visual density | 1-2 diagrams + code blocks + tables | Visual every 400-500 字 (more like a magazine) | Diagrams + code + data tables all welcome |
| Tone | Direct, slightly contrarian, evidence-first | Measured, thoughtful, less contrarian | Peer-to-peer, technical |
| Headline | Punchy, specific (`"Code quality is solved. Business thresholds aren't."`) | Same hook, slightly softer (`"AI 写得对，业务想错了——一个 dogfood 实验"`) | Descriptive (`"从 NECallKit dogfood 看 LLM 的业务语义盲点"`) |
| Closing | Open question to invite comments | Takeaway + persona reinforcement ("一个 AI native dev 的探索手记") | Practical implications for similar teams + next-step |
| Forbidden | Marketing voice, listicles, vague claims | Same + emoji overload | Same + excessive jargon assumption |

### Drafting order

1. Write HN draft (English, tightest, most contrarian-allowed)
2. Translate + reflow for 公众号: split paragraphs (mobile), insert
   more visual anchors, soften 1-2 contrarian edges, add narrative
   connective tissue.
3. Translate + expand for 内部论坛: add code references, PRD links,
   internal team implications, longer technical breakdowns.

**Don't auto-translate.** The 公众号 version is a different essay
with the same skeleton. If you find yourself doing word-by-word, stop
and re-frame.

### Publish cadence

- HN: publish during US business hours, typically Tue-Thu 8-11am PT
  for max front-page chance.
- 公众号: 中文工作日 8-10am or 8-9pm window.
- 内部论坛: align with team's reading rhythm, no narrow window.

Default: **stagger by 1-2 days** between platforms so HN feedback
informs the 公众号 final cut.

---

## 6. Signature visual library

Six canonical visuals reusable across essays. **Goal: by essay 3,
readers recognize the visual signature.** Each new essay either reuses
one of these or adds a new one to the library (and updates this doc).

### Visual identity lock — Style 2 (Dark Terminal)

**Locked 2026-05-13** after a 4-variant prove-out on V1
(Flat Icon / Dark Terminal / Claude Official / Notion Clean). Choice
rationale: Dark Terminal carries the strongest engineer-tribe signal
on HN, aligns with the "AI native dev who lives in the terminal"
persona half of §2, and the cyan/orange palette gives a punchy two-
color hierarchy (data line vs highlight) without leaning on Anthropic-
recognizable cream. Reads denser on mobile than Notion Clean but the
公众号 derivative gets larger type to compensate.

**Reject reasons (recorded so we don't re-litigate):**
- Flat Icon — too generic, no signature
- Claude Official — too visually associated with Anthropic; risks
  reading as derivative
- Notion Clean — clean but monochrome lacks the t3-style accent
  needed for "synthesis bonus" punch

#### Palette — locked tokens

```
Background:        linear-gradient(#0f0f1a → #1a1a2e)
Panel fill:        #0f172a
Panel stroke:      #334155
Grid (subtle):     #1e293b

Text primary:      #e2e8f0  (slate-200)
Text secondary:    #94a3b8  (slate-400)
Text muted:        #64748b  (slate-500)

Data line:         #22d3ee  (cyan-400) — the wiki signature line
Highlight accent:  #f97316  (orange-500) — t3, BOUNDARY, anchor moments
                   alt: #fb923c (orange-400) for callout text on dark
Scope accents:
  - WITHIN-SESSION: #7c3aed  (violet-600)
  - ACROSS-SESSION: #10b981  (emerald-500)
  - BOUNDARY:       #f97316  (orange-500) — deliberately equals V1 t3
                                              so boundary failures and
                                              "synthesis bonus" share a
                                              color signature
```

#### Typography — locked

```
font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', 'Microsoft YaHei', monospace
font-sizes:  22px title / 14px subtitle / 13px labels / 11px sub-labels
letter-spacing: 0.02em title, 0.04em axis, 0.08em ALL-CAPS section labels
```

Monospace is intentional: it signals dogfood / lab-notebook / terminal
authority. The system-sans fallback at the end keeps 中文 legible.

#### Title affordance — the `$` prompt prefix

Every essay diagram's main title starts with `$ ` (dollar + space).
Subtitle starts with `// `. This is the **single most distinctive
signature marker** — readers see it twice and remember it.

```
$ wiki compounding — edges grow fastest when synthesis is filed back
// NECallKit dogfood — 2026-05-07 to 2026-05-08
```

Footer / source citations start with `# ` (comment marker).

#### Canonical V1 + V2 reference renders

- `docs/assets/essay/V1-wiki-compounding.svg` (Dark Terminal)
- `docs/assets/essay/V2-l1-l2-failure-taxonomy.svg` (Dark Terminal)
- Style-prove-out variants kept for record:
  `V1-style2-dark-terminal.svg` (same as canonical V1),
  `V1-style4-notion-clean.svg`, `V1-style6-claude-official.svg`

When generating V3+ in this library, **always cite this section** and
match the palette + typography. Don't introduce a new accent color
without bumping this guide's version.

### V1 — Edge / count progression

**Shape:** line chart or stepped bar, x-axis = time / event, y-axis =
quantity. Markers on the x-axis call out each "filed query" /
inflection moment.

**Canonical instance:** wiki edges 0 → 26 → 85 → 134 across the
NECallKit dogfood, marked by each filed maintainer-decision query.

**Use in:** Candidate 1 (compounding thesis), Candidate 6
(code-vs-business — show the rate of business-knowledge accretion).

**Skill:** `fireworks-tech-graph`.

### V2 — L1 / L2 failure taxonomy

**Shape:** 2×3 grid or tree. Top axis: failure dimension (code-
quality / attention / context-window). Left axis: scope (within-
session / across-session / boundary). Each cell carries a concrete
bug ID.

**Canonical instance:** L1 = B074 code-correct-business-wrong; L2-
within = anchor-wrong B074-followup; L2-across = mac IPC class
B066/B070/B074; L2-boundary = B073 transcript-only hardening.

**Use in:** Candidates 2, 3, 4, 6 — anywhere the failure-mode
abstraction needs to be visible.

**Skill:** `fireworks-tech-graph`.

### V3 — Three-artifact diagram (bug doc / transcript / dogfood log)

**Shape:** three labeled containers, with arrows showing which kind
of information lands in which container. Some arrows hit two, some
only one. Hand-drawn feel is appropriate — these are observations,
not schemas.

**Canonical instance:** B073 four-layer hardening case, showing the
ratified design ending up in transcript + dogfood log but not in
bug doc.

**Use in:** Candidate 4 primarily, possibly Candidate 3's resolution.

**Skill:** `excalidraw-diagram-generator` (hand-drawn signals
"observation, not architecture").

### V4 — wiki-session-ingest fan-in

**Shape:** 6 CLI sources (Claude Code / Codex / Gemini / Copilot /
OpenCode / Kimi) → unified pipeline (AI extract → multi-select →
wiki-ingest) → wiki pages + raw/sessions/ dump. Highlight the two
detection modes (jsonl-read vs llm-dump).

**Use in:** Candidate 4 tail (v1.11 announce), and the eventual
v1.11-ship essay.

**Skill:** `fireworks-tech-graph`.

### V5 — kata layered architecture

**Shape:** stacked layers — raw (immutable) / wiki pages (compounding)
/ SCHEMA.md (conventions) / skills (capabilities). Annotate which
layer compounding lives at, which is human-writable, which is
agent-writable.

**Use in:** Candidate 1, 5, 6 — wherever the system structure needs
to be visible.

**Skill:** `fireworks-tech-graph`.

### V6 — Anchor-failure timeline

**Shape:** horizontal timeline of an agent's reasoning steps:
receive query → wiki returns 0.86 → commits to wrong hypothesis →
runs experiments → fails → re-reads source → finds the real cause.
Mark where the wrong anchor pulled the path.

**Use in:** Candidate 3 (high-confidence-anchors-you-wrong).

**Skill:** `fireworks-tech-graph`.

### Rules for adding a new signature visual

Before adding V7+ to this library:
1. The visual must be **reusable in at least 2 essays** (otherwise
   it's a one-off, not a signature).
2. It must have a **canonical instance** with citations.
3. Skill choice (fireworks vs excalidraw) must be justified by the
   "is this architecture or observation" criterion (fireworks for
   schema-shaped things; excalidraw for human-observed things).
4. Update this doc and bump the guide version.

---

## 7. IP persona — 8 writing conventions

Apply every one in every essay. Skip one → the IP weakens.

1. **Absolute time stamps.** "On 2026-05-09 at 16:32..." not "last
   weekend". Pin the moment in real time.
2. **Bug/PRD/version ID references.** B074, PRD-v1.11, v1.6 shipped
   — at least 3 per essay. Signals "I have a backlog and it's
   public."
3. **Version + status pairs.** "v1.6 (shipped)", "v1.11 (Draft v2)".
   Reader instantly knows you ship.
4. **Clickable trail.** Every diagram + every claim links to the
   GitHub file / commit / PRD. Readers who want to dig should be able
   to dig without asking.
5. **Visible iteration record.** "Round 1 said X. Round 4 saw Y.
   Round 6 closed Z." Iteration is the persona's product, don't hide
   it.
6. **Honest gap report.** End every essay with one specific thing
   you have not yet measured / done / verified. Invites the
   audience into the next experiment.
7. **First-person + occasional "you" pivot.** "I expected X" is the
   main voice. Occasional "you've probably seen this in your own
   codebase" pulls the reader in. **No "we" unless it's a real team.**
8. **Next experiment named.** The closing paragraph names the next
   thing you're building or testing. The persona is a serial; each
   essay is one episode.

---

## 8. Tool stack

| Skill | When to use | Output | Platform fit |
|---|---|---|---|
| `fireworks-tech-graph` | All structural / schema / flow diagrams (V1, V2, V4, V5, V6) | SVG + PNG | All three |
| `excalidraw-diagram-generator` | Hand-drawn / observation diagrams (V3) | `.excalidraw` JSON | Convert to PNG for 公众号 / 内部论坛 |
| `make-pdf` | 内部论坛 mirror, internal-only deep version | PDF | 内部论坛 only |
| `wiki-ingest` (after publish) | File the essay back into the wiki | Wiki page | (internal, post-publish) |

**Don't use other diagramming tools.** Consistency in visual tooling =
consistency in visual signature.

---

## 9. Voice samples — do / don't

### Hook (opening line)

**Do:** "On 2026-05-09 at 16:32, Claude finished a clean Electron IPC
patch, all 47 tests passed, and the mac camera still didn't switch."

**Don't:** "AI-assisted development is changing how we debug."

---

### Thesis statement

**Do:** "As code-quality commoditizes into AI tools, the remaining
moat for senior engineers is project-specific business semantics."

**Don't:** "The wiki is a powerful tool that helps developers."

---

### Data callout

**Do:** "56 pages, 0 edges. Two filed queries later: 26 edges and 2
hubs. After the third filed query: 85 edges. The graph compounds when
you file synthesis back, not when you import."

**Don't:** "After using the wiki for a while, the structure became
quite rich."

---

### Honest gap

**Do:** "I haven't run a cold-baseline comparison — same question
without the wiki — yet. That's the next experiment."

**Don't:** "There are some areas where future work could explore..."

---

### Closing

**Do:** "v1.11 wiki-session-ingest PRD is at Draft v2 (link). I'll
ship Phase 0 next week and write up whether the multi-select UX
actually catches the patterns I think it will."

**Don't:** "Stay tuned for more updates on this journey."

---

## 10. Pre-publish checklist

Run all 12 before submitting to any platform. If any fails, fix
before publishing — **do not publish degraded essays**, they damage
the IP more than the missed publish window costs.

```
[ ] 1.  Hook is a concrete dated moment, not a thesis.
[ ] 2.  Thesis is one sentence a competent skeptic could disagree with.
[ ] 3.  At least one signature visual present (V1-V6 or a new V7+).
[ ] 4.  All concrete claims cite source-file:line / commit / PRD.
[ ] 5.  Iteration trail visible (round numbers, version labels).
[ ] 6.  One open gap reported in the closing.
[ ] 7.  Next experiment / next essay teased.
[ ] 8.  3+ bug/PRD/version IDs referenced.
[ ] 9.  No marketing words (revolutionary, powerful, seamless...).
[ ] 10. Word budget within ±15% of platform target (§4).
[ ] 11. Visual skill choice justified per §6 rules.
[ ] 12. Headline + lede tested by reading aloud — would I click?
```

---

## 11. Post-publish reflection (when to update this guide)

After each publish, log to §Changelog if:

- A new pattern worked unexpectedly well → codify it
- A convention bombed in feedback → strike or revise
- A new platform entered the rotation → add a matrix column
- A new signature visual is reused once → graduate it to the library
- Reader feedback exposed a blind spot → add a §9 do/don't entry

Don't update for one-off tweaks. **The guide is the contract — drift
in the contract is drift in the IP.**

---

## 12. Glossary (canonical terms)

| Term | Meaning |
|---|---|
| L1 | Code-quality vs business-threshold gap (LLM covers former, misses latter) |
| L2 | Attention-mechanism + context-window limits (within-session, across-session, boundary) |
| Compounding | The wiki growing structurally (edges, hubs) through filed queries, not raw imports |
| Filed query | A maintainer-decision query whose answer is written back to the wiki as a page |
| Session-boundary loss | Knowledge generated in agent conversation that doesn't survive past the session jsonl |
| Dogfood-of-dogfood | The plugin maintaining its own wiki using its own primitives |
| AI native dev | Engineer whose primary collaborator is an LLM agent, shapes the system the agent operates in |

Extend this glossary when introducing a new coined term that appears
in 2+ essays.

---

## Changelog

### v1.2 — 2026-05-13
- **Brand locked to Kata.** Rebrand from ak-wiki → Kata; positioning
  shifts from "Karpathy-app" to "workflow + project memory layer on a
  Karpathy substrate." All references updated repo-wide; slash command
  prefix is now `/kata:*`.
- **Builder ethos section** added under §2 IP Persona. Five values:
  every-builder-own-workflow, FOMO→builder ladder, Observe→Think→Act
  primitive, human+AI cooperation, AI democratization. One-sentence
  summary: "accept all, adapt all, transcend all."
- Every future essay's closing should hint at the next rung of the
  accept-adapt-transcend ladder for its reader.

### v1.1 — 2026-05-13
- **Visual identity locked to Style 2 (Dark Terminal).** Chose after a
  4-variant prove-out on V1 (Flat Icon / Dark Terminal / Claude
  Official / Notion Clean). Rejected reasons recorded inline in §6.
- Locked palette tokens, typography, `$ ` title prefix convention,
  `// ` subtitle prefix, `# ` footer comment convention.
- Locked: BOUNDARY accent (`#f97316`) equals V1's t3 highlight by
  design — boundary failures and "synthesis bonus" share one color
  story.
- Canonical V1 + V2 renders point to `docs/assets/essay/V1-wiki-compounding.svg`
  and `V2-l1-l2-failure-taxonomy.svg` in Dark Terminal style.

### v1.0 — 2026-05-13
- Initial guide established from style discussion 2026-05-13.
- Seeded with 6 signature visuals (V1-V6), 8 persona conventions,
  3-platform adaptation matrix.
- First essay following this guide: TBD (selected from
  `docs/essay-framework-survey-2026-05-12.md`).
