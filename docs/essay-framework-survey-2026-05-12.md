# Essay framework survey — 2026-05-12

## Method

I read `docs/dogfood-necallkit-hn-essay.md` (3739 lines, primary source —
running log 2026-05-08 to 2026-05-12), the condensed
`dogfood-necallkit-hn-brief.md`, `dogfood-necallkit-mac-ipc-troubleshooting.md`
(the 8-commit mac IPC arc), `dogfood-necallkit-query-acceptance.md`
(maintainer ratings), and the opening of
`necallkit-multi-machine-onboarding-handbook.md`. A candidate requires: a
story arc with conflict, a sharp hook, cited concrete evidence (commits,
metrics, quotes, failures), a specific HN audience, and a thesis comments
could plausibly argue with. Generic "look at my wiki" pitches were rejected.
Every concrete bullet cites source-file:line; uncitable claims were dropped.

## Lenses applied

Two structural LLM limitations cut across the corpus and shape which frames
are worth publishing:

- **L1 — code quality vs business gap.** Large models cover code quality
  (syntax, common patterns, idiomatic implementations) increasingly well.
  They remain uncertain about project-specific business thresholds,
  lifecycle invariants, and domain conventions — the knowledge that doesn't
  live in the code, it lives in the team's head.
- **L2 — attention mechanism + context limits.** Within a session: the
  known attention-bias failure modes (anchoring, displacement) plus the
  hard cap of the context window. Across sessions: no continuity by
  default.

A third line connects three of the candidates: 2, 3, and 4 all share the
shape "valuable knowledge generated *in conversation* that the default
docs miss." v1.11 wiki-session-ingest
(`docs/PRD-v1.11-session-ingest.md`, Draft v2) is the structural answer to
that shared pattern.

Lens-map per candidate:

- Candidate 2 → L2 across-session — the *class* of mistake only appears
  across three separate sessions; no single LLM session sees itself.
- Candidate 3 → L2 within-session — high-confidence anchoring and
  load-bearing-zero are attention-bias displays inside one window.
- Candidate 4 → L2 context-window-end — transcript-only knowledge dies at
  the session boundary; v1.11 session-ingest is the artifact that closes
  the 2/3/4 thread.
- Candidate 6 (new, below) → L1 — code-correct, business-wrong.

## Candidate frames

### Candidate 1 — "56 pages, 0 edges: when import is not yet memory"

- **Hook:** I imported 56 high-quality pages into an LLM-maintained wiki and
  the graph had zero edges. The pile only became memory after I filed three
  answers back into it.
- **Thesis:** A maintained wiki compounds when synthesis is filed back as a
  citing page; raw import alone is a searchable archive, not project memory.
  RAG retrieves the pile each query; filed queries leave a scar.
- **Story arc:**
  - Point an LLM-maintained filesystem wiki at NECallKit, a real
    multi-platform SDK monorepo, not a toy fixture.
  - First import: 56 pages, 0 graph edges, 0 hubs
    (`dogfood-necallkit-hn-essay.md:228-330`).
  - Conflict: page count looked like progress, no compounding had fired.
  - File two maintainer-decision queries → 26 edges, 2 hubs; file a crossing
    query after the second import → 85 edges, third hub
    (`dogfood-necallkit-hn-essay.md:420-453, 828-868`).
  - Lesson: the durable LLM output is the edited knowledge base, not the chat.
- **Target audience:** HN engineers skeptical of RAG hype and curious about
  the actual shape of LLM-augmented documentation.
- **Evidence in corpus:**
  - 0→26→85→134 edge progression: `dogfood-necallkit-hn-brief.md:40-47`
  - Commit ledger: `dogfood-necallkit-hn-essay.md:905-916`
  - Maintainer acceptance, 4/4 queries 5/5 correctness + retention:
    `dogfood-necallkit-query-acceptance.md:48-82`
  - Six-lesson preflight checklist that "changed what the agent checks before
    writing code": `dogfood-necallkit-hn-brief.md:84-100`
- **Gap to fill:** A cold-baseline comparison (same question without the
  wiki) was flagged but never run
  (`dogfood-necallkit-hn-essay.md:996-999`). Essay can show "wiki compounded"
  but not "wiki beat chat-only on the same question."
- **Why it lands on HN:** Engineers who built RAG will recognize the
  "retrieve a fresh pile each time" failure mode; edge-count is legible and
  contestable. Comments will argue whether filed queries differ meaningfully
  from a curated FAQ doc.
- **Risk:** Could read as inside-baseball NECallKit talk if not abstracted.
  Hub-count metric is weakly defended — someone will ask why edges matter.

### Candidate 2 — "Three bugs, one class: pattern detection across sessions"

- **Hook:** B066, B070, B074 — three separate bug fixes over three weeks. No
  single bug doc spotted that they're the same class of mistake. The wiki
  cross-linked them, and the fourth instance is now flagged as a known risk
  before it ships.
- **Thesis:** The compounding value of a maintained wiki is *cross-session
  pattern detection*, which is structurally invisible to chat, PR review,
  and per-bug docs. A RAG over the same source bug docs cannot surface the
  class because the *class* lives only in the cross-links.
- **Story arc:**
  - macOS Electron renderers see `runtime.sdk === null` because the SDK lives
    in the main process
    (`dogfood-necallkit-mac-ipc-troubleshooting.md:15-50`).
  - Three independent bugs filed as separate fixes over three weeks: B066
    normalize-cleared-signal, B070 setCallConfig facade bypass, B074 empty
    snapshot cache reset (`dogfood-necallkit-hn-essay.md:3231-3251`).
  - Conflict: each bug doc is locally correct but blind to the class. A future
    debugger searching one bug wouldn't see the other two.
  - Cluster ingest crosslinks them; the wiki page
    `electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09.md` now carries
    an explicit "unified mac IPC topology gap" risk table naming the next
    suspected member, `syncDefaultCallRecordProvider`
    (`dogfood-necallkit-mac-ipc-troubleshooting.md:215-225`).
  - Lesson: the wiki has three concrete priors for "mac silently no-ops,
    Windows works" (`dogfood-necallkit-hn-essay.md:3248-3251`).
- **Target audience:** Engineers who maintain cross-platform native/JS
  bridges, Electron/IPC people, anyone bitten by per-incident-doc blindness.
- **Evidence in corpus:**
  - 3-row mistake-type table: `dogfood-necallkit-hn-essay.md:3233-3251`
  - mac IPC risk clipboard:
    `dogfood-necallkit-mac-ipc-troubleshooting.md:215-225`
  - Cluster commits `d5f585a`, `4145197`, `19afba8`:
    `dogfood-necallkit-hn-essay.md:3691-3700`
  - Anchoring failure: B074 wiki returned B070 at 0.86 confidence and the
    agent's first hypothesis was wrong
    (`dogfood-necallkit-hn-essay.md:3329-3349`).
- **Gap to fill:** No screenshot of the cross-linked page; no quote from a
  future debugger landing on it. The "fourth instance would be caught" is an
  inference, not a demonstration.
- **Why it lands on HN:** Specific, technical (Electron IPC topology), and
  the anti-RAG argument is concrete.
- **Risk:** Heavy domain prerequisite — non-Electron readers may bounce.
  "The wiki noticed" is partly the human noticing while curating; needs
  honest framing.
- **Lens read:** L2 across-session — patterns live across sessions; no
  single LLM session sees itself.

### Candidate 3 — "High-confidence wiki hits can anchor you wrong"

- **Hook:** A wiki hit at 0.86 confidence led the agent into the wrong
  hypothesis. A wiki hit with body=0 across four queries was load-bearing —
  it told the agent where *not* to go. The interesting LLM-wiki failure modes
  aren't "no answer."
- **Thesis:** Confidence isn't proportional to usefulness. Both poles fail
  instructively: high-confidence hits are an anchoring hazard (a known LLM
  failure mode), and low-confidence hits constrain the reasoning space
  without answering. Both deserve product surface.
- **Story arc:**
  - `wiki-query` returns a confidence score; the agent is supposed to use it
    (`dogfood-necallkit-hn-essay.md:1990-2026`).
  - Anchor-wrong (B074): wiki returns B070 at 0.86 with a perfect template
    match for "mac IPC silently no-ops." Agent commits to it; source reading
    reveals a different mac IPC gap entirely
    (`dogfood-necallkit-hn-essay.md:3329-3349`).
  - Low-confidence-still-useful (B071): four queries return body=0, only
    orientation pages have index-only matches. Agent self-rates Low–Medium
    but the wiki "told you where not to go"
    (`dogfood-necallkit-hn-essay.md:3300-3322`).
  - Resolution: `knock-it-out` skill v2 (§3.5, §6.5) adds a mid-session
    distillation gate and a closure check forcing "name the new fact" before
    exit (`dogfood-necallkit-hn-essay.md:3448-3477`).
  - Lesson: the loop must include "is the wiki anchoring me?" as an explicit
    check, not just "did the wiki answer?"
- **Target audience:** AI tool builders, LLM agent framework authors,
  retrieval-confidence UX designers.
- **Evidence in corpus:**
  - B074 anchor failure with verbatim agent context:
    `dogfood-necallkit-hn-essay.md:3329-3349`
  - B071 four-queries-body-0 with agent self-quote:
    `dogfood-necallkit-hn-essay.md:3300-3308`
  - Cross-session pattern itemization:
    `dogfood-necallkit-hn-essay.md:3415-3435`
  - Skill change scope: `dogfood-necallkit-hn-essay.md:3448-3477`
- **Gap to fill:** Only two named cases; no aggregate measurement of anchor
  rate. Essay would benefit from one more anchor-wrong example.
- **Why it lands on HN:** Specific anti-pattern naming, real LLM failure
  mode, concrete proposed fix.
- **Risk:** Could read as "we found bugs in our tool and patched them"
  unless the thesis frames confidence-as-design-problem hard.
- **Lens read:** L2 within-session — high-confidence anchoring and
  load-bearing-zero are attention-bias displays.

### Candidate 4 — "The bug doc, the transcript, and the dogfood log are three different artifacts"

- **Hook:** The user agreed to a four-layer hardening pattern in the middle
  of a `knock-it-out` session. The fix shipped. The hardening was never
  written down. The bug doc captured the conclusion; the transcript captured
  the dialogue; only the dogfood log captured the ratified-but-unwritten
  design.
- **Thesis:** Conclusions, processes, and cross-session patterns are three
  different artifact types. Most tooling collapses them into "the doc" and
  loses the most valuable bits. Working AI documentation has to detect when
  scope expanded but wasn't filed.
- **Story arc:**
  - B073: a "fix Windows account-switch crash" knock-it-out session
    (`dogfood-necallkit-hn-essay.md:3364-3411`).
  - Agent ships example-layer fix, 47/47 tests passing, reports done. User
    pushes back twice — "偶现 crash" then "通用的保护和规避方案" — and
    ratifies a four-layer defense pattern (lifecycle mutex, generation
    counter, callback detach, observable drain)
    (`dogfood-necallkit-hn-essay.md:3372-3387`).
  - The hardening leaks: B073 analysis.md captures only the surface fix; the
    four-layer pattern lives only in the codex transcript and this dogfood
    log (`dogfood-necallkit-hn-essay.md:3389-3403`).
  - Resolution: `knock-it-out` §6.5 closure check walks distillation
    candidates and forces per-item decisions (file / file-later / discard)
    (`dogfood-necallkit-hn-essay.md:3461-3470`).
  - Lesson: the wiki cannot compile process out of conclusion docs; the agent
    has to surface the gap before the conversation closes.
- **Target audience:** Documentation skeptics, tech writers, AI-agent UX
  designers, senior engineers who have watched design discussions evaporate.
- **Evidence in corpus:**
  - Verbatim Chinese user pushback quotes:
    `dogfood-necallkit-hn-essay.md:3372, 3380, 3388`
  - "Documentation discards the most useful debugging evidence":
    `dogfood-necallkit-hn-essay.md:3430-3436`
  - Skill update scope and 4 new anti-patterns:
    `dogfood-necallkit-hn-essay.md:3448-3477`
  - Three-artifact framing in updated spine:
    `dogfood-necallkit-hn-essay.md:3661-3666`
- **Gap to fill:** No verbatim quote of the *exact* design discussion that
  got lost — the four-layer pattern is summarized, not reproduced.
- **Why it lands on HN:** Every senior engineer has watched a design decision
  evaporate. Specific failure mode named, specific UX response prescribed.
- **Risk:** Reads as a process essay rather than a code essay; HN engagement
  skews technical. Mitigate by leading with the crash story.
- **Lens read:** L2 context-window-end — transcript-only knowledge dies at
  the session boundary; v1.11 is the structural response.

### Candidate 5 — "The plugin maintains its own wiki, then syncs it across machines"

- **Hook:** Day 5: the LLM-wiki plugin's design docs now live in an LLM-wiki
  produced by the plugin. The PRD for the next feature is a wiki page in a
  wiki the plugin built. Two machines, one git push.
- **Thesis:** A documentation system is only credible if the author uses it
  on their own product. The smallest possible proof isn't dogfood — it's
  dogfood-of-dogfood: the plugin's own design lifecycle flows through its
  own primitives.
- **Story arc:**
  - 4 weeks of NECallKit dogfood on someone else's codebase, deliberately
    "real not toy" (`dogfood-necallkit-hn-essay.md:37-49`).
  - Cross-cutting infrastructure day: v1.10 federation PRD goes through 4
    review rounds; v1.8 sync ships; `knock-it-out` v2 closes the B073 leak
    (`dogfood-necallkit-hn-essay.md:3441-3585`).
  - Self-meta wiki created (`~/.llm-wiki/kata/`), PRD v1.10 ingested as
    first page, schema extends with `kata`, `federation`, `prd`, `sync`
    (`dogfood-necallkit-hn-essay.md:3560-3571`).
  - 2026-05-12: v1.8 sync, designed for project wikis, pushes the self-meta
    wiki to a remote. Same handbook works
    (`dogfood-necallkit-hn-essay.md:3588-3603`).
  - Lesson: the plugin author's own knowledge base is the simplest scaling
    demonstration.
- **Target audience:** Founders / indie-hackers / dev-tool builders; people
  who buy "dogfood is the discriminator" framing.
- **Evidence in corpus:**
  - 8 commits across 4 days on NECallKit wiki:
    `dogfood-necallkit-hn-essay.md:3691-3704`
  - Self-meta commits `de76a12`, `5cb8d7a`:
    `dogfood-necallkit-hn-essay.md:3705-3708`
  - Multi-machine push: `dogfood-necallkit-hn-essay.md:3588-3603`
  - "不要过于追逐 ingest" design quote:
    `dogfood-necallkit-hn-essay.md:3493-3500`
- **Gap to fill:** Only 4 pages in the self-meta wiki — too thin to argue
  scale. No screenshot of the multi-machine sync working.
- **Why it lands on HN:** Recursive eat-your-own-dog-food has natural
  appeal. PRD-as-wiki-page inverts the typical "PRD then ship" loop.
- **Risk:** Most niche. Could read as a personal project update without
  sharp argumentation. Probably weakest standalone, possibly strongest as a
  closing section for any of the others.

### Candidate 6 — "Code quality is solved. Business thresholds aren't."

- **Hook:** The LLM wrote syntactically clean Electron IPC code and a
  three-line subscribe handler. It just didn't know that an empty initial
  snapshot meant "adapter not yet initialized," not "data was cleared."
  Code-correct, business-wrong (`dogfood-necallkit-hn-essay.md:3237`).
- **Thesis:** As code quality commoditizes into AI tools (formatters,
  linters, type-checkers, Claude itself), the remaining technical moat for
  senior engineers and maintainers is project-specific business semantics
  — thresholds, lifecycle invariants, domain conventions. The wiki's job
  is to compile that gap explicitly so future LLM sessions can read it
  back.
- **Story arc:**
  - B074: subscribe handler treats `snapshot=[]` as "clear" and resets the
    cache. The adapter actually emits an empty snapshot during its own
    init phase before any business clear has happened
    (`dogfood-necallkit-hn-essay.md:3237`).
  - Same shape as B066 (normalize wipes the "cleared" signal) and B070
    (renderer bypasses the facade and hits a null mac sdk) — three bugs,
    three weeks, every one of them is *code-correct against the spec the
    LLM had, business-wrong against the spec only the team carried*
    (`dogfood-necallkit-hn-essay.md:3231-3251`).
  - Inflection: the maintainer writes, "the wiki should compile a
    domain-specific preflight query before code work begins"
    (`dogfood-necallkit-hn-essay.md:2526`).
  - Maintainer query-acceptance ratings: 4/4 queries score 5/5 on
    correctness *and* retention, anchored on domain-correctness rather
    than syntactic plausibility
    (`dogfood-necallkit-query-acceptance.md:48-82`).
- **Target audience:** Senior engineers and tech leads watching AI eat
  code-quality work and wondering what their durable contribution looks
  like in two years.
- **Evidence in corpus:**
  - B074 anchor: `dogfood-necallkit-hn-essay.md:3237`
  - 3-bug L1 cluster: `dogfood-necallkit-hn-essay.md:3231-3251`
  - "wiki should compile a domain-specific preflight" inflection:
    `dogfood-necallkit-hn-essay.md:2526`
  - Maintainer ratings anchored on domain-correctness:
    `dogfood-necallkit-query-acceptance.md:48-82`
- **Gap to fill:** No aggregate count of how often the LLM hits this. A
  small quantitative tally across the dogfood corpus (n bugs where the
  code was clean but the business spec was missed) would harden the
  thesis.
- **Why it lands on HN:** The "what will AI not eat?" question is live.
  Naming "project-specific business semantics" with three concrete bugs
  and a maintainer quote gives commenters something to contest.
- **Risk:** Needs more than one "LLM missed business" anecdote; B074
  alone may read as cherry-picked. The 3-bug cluster (B066/B070/B074)
  helps, but skeptics will ask whether they're really the same class.
- **Lens read:** L1 — code-correct, business-wrong; the wiki is the
  compiled answer to the part that doesn't live in code.

## Cross-cutting themes (not yet candidates)

**Rollback semantics.** B061 was overruled by B072
(`dogfood-necallkit-hn-essay.md:3214-3229`). The current pattern (addendum +
"stale" annotation + cross-link) works for one rollback but is brittle. A
`superseded_by:` frontmatter field is on the v1.11+ list. Interesting but
only one rollback in the corpus — probably folds into Candidate 2 or 4.

**Friction is not the story.** Windows Python 2 vs 3, missing `rg`, AK repo
`.git/index.lock` ACL, CJK tokenization failure, structural-file lint noise
(`dogfood-necallkit-hn-brief.md:103-118`). These belong in a Part-3 "what
doesn't work" section of any candidate — mention them, don't headline.

**Wikis can stay restrained.** PRD v1.10's distillation pathway explicitly
avoids pushing users to ingest, even when thresholds cross
(`dogfood-necallkit-hn-essay.md:3510-3515, 3649-3654`). Unusual product
stance worth a paragraph in Candidate 1 or 5; not standalone.

**Dreaming as long-arc memory — hold for post-dogfood essay.** kata
has shipped v1.6 auto-dreaming (re-promote frozen pages whose relevance
returns), PRD at `docs/PRD-v1.6-autodreaming.md`, mechanism exercised by
the synthetic fixture at `tests/build_dreaming_fixture.py`. But the
real-world evidence is thin: per `dogfood-necallkit-hn-essay.md:2065`,
"even after shortening tier thresholds to 3/7 days, all pages remain
active on" 2026-05-08 — no page has actually been promoted from frozen
in the dogfood corpus yet. The 4-week observation window
(2026-04-25 → ~2026-05-23) is still running. A dreaming essay would
currently read as "I built a thing, it hasn't saved me yet." Defer until
at least one concrete promotion story exists.

## Sequencing notes (descriptive, not prescriptive)

Candidates 1 and 5 share the "wiki compounds / dogfood proves it" core;
publishing both would feel redundant — 5 reads as an epilogue to 1.
Candidates 2, 3, and 4 are rooted in *different* dogfood vignettes (mac IPC
class / confidence anchoring / B073 scope expansion) and are largely
independent. Candidate 1 could run first as the foundational arc, then any
one of 2/3/4 back-to-back without repeating evidence. Candidates 3 and 4
both touch the same `knock-it-out` skill update, so running them adjacent
forces shared framing — slot Candidate 2 between them if both publish.
