# Essay #1 (Draft) — "Code quality is solved. Business thresholds aren't."

> Status: first full draft &#183; ~1800 words &#183; HN-first
> Source outline: `docs/essay-drafts/2026-05-13-essay1-code-quality-vs-business-outline.md`
> Style guide: `docs/essay-style-guide.md` v1.2 (Dark Terminal locked, Builder ethos added)
> Date: 2026-05-13
> Platform fit: HN original; 公众号 and 内部论坛 derivatives TBD

---

# Code quality is solved. Business thresholds aren't.

On 2026-05-09 at around 16:32, Claude finished what looked like a clean Electron IPC patch. All 47 tests passed. The mac camera still didn't switch.

The handler was syntactically correct: a `subscribe` callback that, on receiving an empty snapshot, cleared the call-record cache. The bug wasn't in the code. It was in the *meaning* of an empty snapshot. NECallKit's adapter emits an empty snapshot during its own init phase — **before any business clear has happened**. "Adapter not yet initialized" and "data cleared" look identical from the renderer; only the team's local spec distinguishes them.

This wasn't a bug a better LLM would have caught. The code was correct against the spec the LLM had — wrong against the spec only NECallKit's team carried. (Logged as B074 in the dogfood corpus: `dogfood-necallkit-hn-essay.md:3237`.)

## Why this matters

For years, AI tools have been eating code-quality work. First it was formatters and linters. Then type-checkers and code review bots. Now Claude, Codex, and Copilot write whole patches that pass review and merge clean. Each layer was a moat for engineers until the moat became a commodity.

The part that hasn't fallen — and I'd argue won't fall the same way — is the part of "what should this code do" that doesn't live in the code itself. **Project-specific business semantics.** Thresholds. Lifecycle invariants. Domain conventions. The protocol rule that's been in a Slack thread since 2024. The teardown sequence one engineer figured out and never wrote down. The knowledge that gets re-derived every time someone asks "wait, what does this actually *mean* in our system?"

Call this **L1: code-correct, business-wrong**. It's a systematic failure mode of LLMs operating on real projects, and on my dogfood it's the most expensive class of bug we still ship. Not because the LLM is weak — but because the LLM is being asked questions the project never wrote down.

## The experiment

NECallKit is a real Electron + native video-calling SDK — multi-platform, native IPC bridges, mac/win/linux, Java + JS + C++ side by side. Not a toy fixture. Over four weeks (2026-04-25 → 2026-05-13) I ran a paired experiment: route every bug, decision, and filed query for the project through an AI-maintained wiki, and measure what compounds.

The wiki tool is **Kata** (v1.4 → v1.11 over six weeks), built on Karpathy's LLM-Wiki principle. The loop is simple: human curates sources, AI agents read them, summarize, cross-link, file. Pages compile down — synthesis baked in, contradictions flagged, queries filed back as new pages. The wiki is not retrieval; it's **compiled knowledge** that stays current as the project moves. Claude Code and Codex CLI took turns as the maintaining agent across 200+ sessions; I curated.

The hypothesis I started with was modest. The wiki would help with cross-referencing — the LLM already knew Electron and Node and the standard web. Maybe it would speed up onboarding for the second machine I set up halfway through.

What I actually had to write up first wasn't the cross-references. It was this essay.

## The conflict

B074 wasn't a one-off. Over three weeks I shipped three bugs with the same shape:

- **B066** — `normalize()` wipes the `cleared` field on its way through. The protocol treats *absent* and *explicitly-undefined* as different signals (one means "no update", the other means "actively cleared"). The LLM didn't know. It saw two falsy values and folded them.
- **B070** — an Electron renderer calls `sdk.setCallConfig` directly. On Windows that works; on mac the renderer's `sdk` reference is null because the native SDK lives in the main process, not the renderer. The LLM had working Windows code in front of it, cloned the pattern, and shipped a silent no-op on mac. All tests passed. Nothing crashed. The mute toggle just didn't mute.
- **B074** — the adapter snapshot lifecycle case from the intro.

(Source for the cluster: `dogfood-necallkit-hn-essay.md:3231-3251`.)

![L1 / L2 failure taxonomy](../assets/essay/V2-l1-l2-failure-taxonomy.svg)

L1 (left column) is the family I'm naming in this essay. L2 (right column — within-session attention bias, across-session pattern blindness, session-boundary loss) is a separate essay; ignore it for now.

Every one of B066/B070/B074 was **code-correct against the generic Electron spec the LLM had, business-wrong against the local NECallKit spec only the team carried**. Three different sessions, three different agents, three weeks apart. **No single session saw it as one class.** The class was structurally invisible to chat-bound intelligence — every bug fix is local; pattern detection requires standing outside the conversation. Each session left the codebase strictly better and the class fully invisible.

That standing-outside is where the wiki goes. The wiki is not retrieval-on-demand; it's the artifact that exists between sessions, that the next agent reads before it writes a line.

## How the wiki compiles the gap

I measured one number across the dogfood: graph edge count in the compiled wiki over five inflection points.

| Event | Pages | Edges | Δ |
|---|---:|---:|---|
| t0 — feature dossier imported | 56 | 0 | baseline |
| t1 — 2 maintainer-decision queries filed | 61 | 26 | +26 from 5 pages |
| t2 — project operating context imported | 69 | 68 | +42 from 8 pages |
| **t3 — operating-boundary query filed** | **70** | **85** | **+17 from 1 page** |
| t4 — lessons seed + preflight query | 77 | 134 | +49 from 7 pages |

(Source: `dogfood-necallkit-hn-brief.md:40-47`.)

![Edge progression — synthesis vs import](../assets/essay/V1-wiki-compounding.svg)

t3 is the punchline. **One filed query. One new page. +17 edges.** Imports give you about 5 edges per page on average. A filed maintainer-decision query gives you 17. The wiki doesn't grow when you load it; it grows when someone asks a maintainer-decision question and the answer goes back in *with cross-links to the existing pages it touches*.

A maintainer-decision query has a specific shape. It's not "what does this function do" — that's spec-shaped, the LLM already knows. It's "what's NECallKit's mac IPC topology around adapter lifecycle, and which of our modules depend on that contract?" The AI writes the answer as a wiki page, cross-referenced to every affected module, every prior bug in the same neighborhood, every test that protects the boundary. The page becomes a hub. Future sessions land on it before they touch code.

I rated four such filed queries along three axes — correctness, usefulness, retention. All four hit 5/5 on correctness and retention; two of four on usefulness (`dogfood-necallkit-query-acceptance.md:48-82`). The criterion the maintainer was applying was **domain-correctness**, not syntactic plausibility. The queries are useful because they encode the part of the spec the LLM *cannot* infer from the code — they encode the team's running judgment about how things work.

Halfway through the dogfood I wrote a sentence in the log that turned into this essay's thesis:

> "the wiki should compile a domain-specific preflight query before code work begins."

(`dogfood-necallkit-hn-essay.md:2526-2527`.) That's what the +17-from-one-page moment is. The wiki is not reference. It's **business-semantic compilation**.

## The lesson

Three words, quotable: **code-correct, business-wrong**.

Generalized: AI tools are very good at **spec-shaped** knowledge — the kind typed into the language, the framework, the public API documentation, the standard library, the conventions GitHub has already chewed on for a decade. The model knows what `subscribe` looks like in JavaScript; it knows what an Electron renderer can and can't reach; it knows what a `null` reference does. That part is solved, and it's going to get more solved.

What the model doesn't know is the **spec-unshaped** part. The local truths. The mac vs main process partition for *your* SDK. The protocol field that means three different things at three lifecycle phases. The 3.5-second timeout your previous engineer settled on after a customer outage. None of that is in the language. None of it is in the framework. It lives in three engineers' heads and gets re-derived every time someone new asks the wrong question first.

The economic prediction is uncomfortable but straightforward: as code-quality work keeps falling into AI, senior engineers' durable contribution shifts from *writing code* to *compiling the business spec*. The work goes from "produce the artifact" to "produce the rule the artifact must obey." The wiki is one form of that compilation. There will be others — schema repositories, contract-test suites, decision logs, machine-readable invariant declarations. Pick one. Or invent one.

This isn't a story about AI being weak. AI is strong exactly where the spec is written down. The bug is that we never wrote down the part that wasn't a language feature, because for fifteen years there was no urgency to. Now there is.

The ladder up is to pick a kata for compiling business semantics — adopt one, adapt it to your project, then transcend the form. Kata (the workflow described in this essay) is one such ladder; your project's may look different. The point isn't the wiki. The point is having *any* compiled business-spec layer at all.

## What's next

**Open gap.** I haven't run the cold-baseline comparison — same question, same agent, no wiki. I think compounding is the right framing, but I owe the test before I call it proven. The slot is flagged in the dogfood log (`dogfood-necallkit-hn-essay.md:996-999`); next experiment.

**Scope note.** This essay is Kata's **Phase 1 reach** — AI-paired engineering. Kata's core is a self-evolving wiki with auto-dreaming on Karpathy's substrate; Phase 1 applies the core to project memory. **Phase 2** — team spec authoring + dispute resolution as a self-closing loop — is designed, not yet implemented. The compounding thesis here generalizes; the specific moves don't.

**Next experiment.** v1.11 `wiki-session-ingest` (PRD Draft v2: `docs/PRD-v1.11-session-ingest.md`) — a skill that reads the current CLI session, extracts knowledge points, lets the user multi-select which to file. It's the structural answer to a different failure mode (L2 — knowledge born in conversation, dying at session boundary) that the next essay will cover.

You don't need to use Kata to do this. Pick a kata for your team — fork ours, write your own, or adopt a different one entirely. The point isn't the tool; it's the layer.

---

**Clickable trail:**

- Kata repo: https://github.com/surebeli/kata
- Dogfood log (full evidence chain): `docs/dogfood-necallkit-hn-essay.md`
- B074 anchor: line 3237
- v1.11 session-ingest PRD: `docs/PRD-v1.11-session-ingest.md`
- Style guide (how this essay was written): `docs/essay-style-guide.md`

---

*— a build log entry from an AI-native dev exploring the frontier. Accept what works. Adapt what fits. Transcend the form.*
