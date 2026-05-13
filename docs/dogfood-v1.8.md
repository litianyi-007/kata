# v1.8 Dogfood — Multi-machine sync on a real wiki

> Per PRD-v1.8-sync.md §4: ship-readiness gate is **4 weeks** of real
> two-machine use without unrecoverable conflicts, no `--apply` to wrong
> page, < 5 min average human time per conflict resolution. This file
> is the running log.

## Status

**As of 2026-05-07: Pending — sync window has not yet started.**

The setup table below has placeholders. Until the wiki path, both
machines, and `wiki-sync enabled on` date are filled in, **no weekly
retrospective has comparable data**. Public v1.8 announcement and any
v1.8-full work (`merge_index.py`, take-max frontmatter, true concurrent
race barrier) remain blocked by this.

> **Coordination with v1.6 dogfood:** v1.6 auto-dreaming dogfood is also
> Pending. The cleanest plan is to run **both windows in parallel on the
> same wiki** — same 4 weeks observe both dreaming candidate quality AND
> sync churn / conflict rate. Cron line covers both via
> `wiki-sync --auto && wiki-dream`. See `docs/dogfood-v1.6.md` for the
> dreaming half.

Action required from the maintainer:

1. Decide the live wiki path (recommended: `~/.llm-wiki/<project>` —
   v1.7.2 multi-project layout). Same path on both machines.
2. Get a `sync:` block + `wiki_id` into `SCHEMA.md`:
   - **Fresh wiki**: `python plugin/scripts/wiki_init.py --path ...
     --enable-sync` (and `--enable-dreaming` if running v1.6 dogfood
     in parallel; `--template market_research` includes dreaming)
   - **Existing wiki**: `python plugin/scripts/wiki_init.py --refresh-id
     --path ...` to inject `wiki_id` and bring `.gitignore` /
     `.gitattributes` up to v1.8 standard. Then hand-edit SCHEMA.md to
     add a `sync:` block (see "Frozen parameters" below) and
     `schema_validate --wiki ...` to verify.
3. Configure git remote on machine A:
   ```bash
   cd ~/.llm-wiki/<project>
   git init -b main && git add . && git commit -m "wiki: init"
   git remote add origin <your-remote-url>
   git push -u origin main
   ```
4. On machine B: `git clone <remote> ~/.llm-wiki/<project>`. Both
   machines now share `wiki_id` from SCHEMA.md — sync's identity
   check will pass.
5. Schedule `wiki-sync --auto && wiki-dream` weekly (per machine):
   ```bash
   # Cron — Sunday 23:00 on machine A
   0 23 * * 0  cd ~/.llm-wiki/<project> && wiki-sync --auto && wiki-dream
   # Cron — Sunday 23:30 on machine B (staggered to reduce push race)
   30 23 * * 0  cd ~/.llm-wiki/<project> && wiki-sync --auto && wiki-dream
   ```
6. Fill the setup table below with day-1 numbers and the date you
   actually started.

Once started, the 4-week clock runs forward — *do not change v1.8
frozen parameters mid-window*.

## Setup

| | |
|---|---|
| Wiki path | _<fill in: e.g. `~/.llm-wiki/llm-app-innovation`>_ |
| Machine A | _<fill in: hostname / OS / Python / git versions>_ |
| Machine B | _<fill in: hostname / OS / Python / git versions>_ |
| Sync enabled on | _<fill in: YYYY-MM-DD>_ |
| Remote | _<fill in: git@github.com:.../wiki-name.git>_ |
| Dogfood window | 4 weekly runs from sync-enabled date |
| Cadence | weekly · Sunday A=23:00 / B=23:30 (staggered) |
| Cron line | `wiki-sync --auto && wiki-dream` |
| Driver registration | auto on first wiki-sync (PRD §8 Option A) |
| Total wiki pages on day 1 | _<fill in>_ |
| Combined with v1.6 dreaming dogfood? | yes / no |

## Frozen parameters for the window

```yaml
sync:
  enabled: true
  remote: origin
  branch: main
  on_conflict: report-and-exit
  auto_chain_dream: false           # cron string handles chaining
  auto_configure_drivers: true
```

Don't tune mid-window. Especially don't disable
`auto_configure_drivers` (would break the auto-merge for log.md and
silently fall back to git default 3-way).

## How to use this file

After each weekly run, on EACH machine:

1. Open the most recent file under `~/.kata/sync-reports/{slug}/`
   for that machine. Result categories:
   - `up-to-date` (no file written) / `success` / `success-with-driver`
     / `fast-forward` / `pushed` → uneventful, count and move on
   - `conflicts` → user resolution required; record the conflict shape
   - `force-push-detected` / `unrelated-history` / `identity-mismatch`
     → red flag, abort the dogfood window with full notes (these
     should never happen in practice; if one fires it's a real-world
     gap our PRD missed)
   - `aborted` (`import-in-progress` / `lock-held` / etc.) → benign
     preflight refusal, count separately
2. Fill in the week's section below.
3. **Don't tune mid-window.** Let four weeks run on identical config;
   tune at the retrospective.

## Weekly logs

### Week 1 — YYYY-MM-DD

**Cron runs (per machine)**

| Machine | Result | Driver merged? | Conflicts? | Push retries | Notes |
|---------|--------|----------------|------------|--------------|-------|
| A       |        | yes / no       | yes / no   | 0 / 1+       |       |
| B       |        | yes / no       | yes / no   | 0 / 1+       |       |

**Manual `wiki-sync` (mid-week)**

- Total invocations: A __ / B __
- Reasons: _<e.g. "rebased before pushing", "saw something to share">_

**log.md merge driver disposition**

- Auto-merged via akwiki-log: __ entries
- `Sync-side: ours/theirs` annotations introduced this week: __
- Same-triple-different-body kept-both pairs: __ (note any user-confusing
  ones; this is a v1.9 candidate for "embed wiki_id in entry" UX)

**Conflicts (if any)**

- Files: ____
- Driver path (`AKWIKI-SEMANTIC-CONFLICT` block / git default markers):
- Resolution time: __ min
- Was the recovery command from the report enough? yes / no

**Surprises** — anything sync did differently than expected:

-

**Bugs / annoyances:**

-

**Scenario fit** — multi-machine workflow improved?

- Could keep both machines aligned without manual git: yes / no
- Combined with dreaming (v1.6): both add value? Or stepping on each other?
-

### Week 2 — YYYY-MM-DD

(same template)

### Week 3 — YYYY-MM-DD

(same template)

### Week 4 — YYYY-MM-DD

(same template)

## Cumulative metrics (filled in at week 4)

| Metric | Target | Actual | Pass? |
|--------|--------|--------|-------|
| Total cron sync runs (both machines) | — | __ | — |
| Successful (clean / merged / fast-forward) | — | __ | — |
| Conflicts | — | __ | — |
| `force-push-detected` / `unrelated-history` / `identity-mismatch` | 0 | __ | ☐ |
| Average human time per conflict | ≤ 5 min | __ | ☐ |
| `--apply` (dream) writes that had to be reverted | 0 | __ | ☐ |
| Push race retries triggered | informational | __ | — |

## Retrospective (week 4)

**What worked.**

-

**What didn't.**

-

**Scenario observations.**

- Did sync surface any scenario the synthetic smoke fixture didn't?
  (Specifically: race patterns, identity edge cases, content shapes
  that broke driver assumptions.)
-

## Decisions for v1.8-full backlog (after dogfood)

Tick what to do **after** the dogfood window:

- [ ] Implement `merge_index.py` driver based on observed `index.md`
  conflict shapes — _<note specific bullet/section patterns that hurt>_
- [ ] Implement frontmatter take-max for `updated` / `tier_override_set_at`
- [ ] Adjust push-retry backoff `(1, 2, 4)` to ___. Reason: _____
- [ ] True concurrent-barrier race test (T-sync-16 with subprocess +
  ready files) — yes / no / wait
- [ ] Add v1.9 PRD topic: ____ (e.g., recursive in-process re-merge,
  LFS, cross-machine timestamp drift)
- [ ] Update `docs/PRD-v1.8-sync.md` "Open questions" section based on
  dogfood findings
- [ ] Public v1.8 announcement: yes / hold / fold into v1.8-full

## Known limitations (don't surprise yourself)

- T-sync-16-lite is sequential pre-push hook, not true concurrent
  race — you might see real concurrent races behave slightly
  differently (different stderr wording from git's smart protocol)
- SIGKILL on either machine skips Python finally; sync stale-lock
  detection uses PID liveness — if PIDs get reused on a busy host,
  edge case (acknowledged in PRD §17). Don't kill -9 unless necessary
- The 24h staleness threshold for `.wiki-import-lock` (set in
  `import_checkpoint.py`) means an import that's been running >24h is
  treated as abandoned. If you do legitimate >24h imports, bump the
  threshold or document the expected pattern

## Notes for week-N me

- A `up-to-date` result with no report file is the **most common
  outcome** by week 4 — both machines synced via cron each Sunday and
  there's nothing to merge. That's success, not silence.
- `git log --grep='\[kata sync\]'` shows your sync history. Useful
  for spotting drift if conflict patterns feel arbitrary in retrospect.
- `~/.kata/sync-reports/{slug}/` accumulates over time. After week 4
  retrospective: optionally `rm -r` or archive elsewhere — they're
  pure local audit, no code depends on them
- If you run wiki-import during the window: ensure phase 5 cleanup
  worked. Check `git log -1 --grep='wiki-import:'` and confirm
  `.wiki-import-checkpoint.json` is absent after the import commit
