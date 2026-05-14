# Compliance retrospective — 2026-05-14

> Postmortem on how `litianyi <litianyi@<corp-domain-redacted>>` ended up as the
> author on every kata commit from `93ee579` (Initial public release —
> Kata v2.0.0, 2026-04-25) through `e6cc313` (2026-05-14 09:55 local).
> Captured before the lessons fade.

## Timeline

| | |
|---|---|
| 2026-04-25 | `93ee579` ships as public initial release. Author email = corp. |
| 2026-04-25 → 2026-05-14 09:55 | 9 more commits land on public `surebeli/kata`. All authored with corp email. |
| 2026-05-14 ~10:30 | First conversation in this session catches the pattern when reading `git log --format='%h %ae'` for unrelated reasons. |
| 2026-05-14 ~10:35 | User picks Option 1 (fix forward + add hook check) over Option 2 (force-push history rewrite) and Option 3 (new repo). |
| 2026-05-14 ~10:40 | `e8b1271` ships: `git config --local user.email surebeli@gmail.com` + extended `.githooks/pre-commit` Stage 0 to scan author identity. |
| 2026-05-14 ~10:42 | `e8b1271` itself becomes the first commit on this repo authored as the public identity. Every commit since is clean. |

## Why it happened

Three independent gaps lined up:

1. **Local git config default was global, not local.** `~/.gitconfig`
   has `user.email = litianyi@<corp-domain-redacted>` (set when the user
   first configured git on this machine for corp work). The kata
   repo's local `.git/config` had no `[user]` override, so commits
   fell through to the global default.

2. **The pre-commit hook scanned *diff content* only, not the
   *author header***. `.compliance-blocklist.txt` explicitly forbids
   the pattern `@corp\.netease\.com`. The pattern would have caught
   the corp email if the email appeared inside a file. It did not
   appear inside any file — it appeared in the git commit author
   metadata, which the hook never inspected.

3. **The author identity is invisible at commit time.** Unlike a
   secret in a diff (visible in `git diff --cached`), the author
   header is set silently from `git config` and only surfaces
   in `git log`. A diff-only hook is structurally blind to it.

## What the fix did

`e8b1271`:

- Extended `.githooks/pre-commit:Stage 0` to read `GIT_AUTHOR_IDENT`
  and `GIT_COMMITTER_IDENT`, then scan both against
  `.compliance-blocklist.txt` using the exact same regex set as the
  diff-content scan.
- Violation reports tell the committer which field tripped the rule
  and how to fix via `git config --local user.email <public-email>`.
- Local git config set to `surebeli <surebeli@gmail.com>` for the
  kata repo only — global config remains untouched (corp work in
  other repos still uses corp identity by design).

`f21d427` (later same day, unrelated to the leak):

- Made the hook always run Stage 0 regardless of `RELEVANT_PATHS`,
  closing a separate early-exit gap. Now a pure-docs commit with a
  corp email is caught.

## What we accepted (the historical leak)

The 10 commits between `93ee579` and `e6cc313` still carry the
corp email on `surebeli/kata` public history. Per Option 1 of the
2026-05-14 decision, we chose **forward fix over history rewrite**
because:

- The data is already published, indexed by GitHub search, and
  cloned by anyone who pulled in the window. Force-push doesn't
  retract any of that.
- The kata repo is the user's personal side project, not corp IP.
  Identifying that the author works at netease while building a
  public side project is not a policy violation in any policy
  surfaced today — it's bad blocklist hygiene, not a leak of
  proprietary data.
- Force-pushing main of a public release branch creates ongoing
  churn for anyone tracking the repo (essay #1 referenced commit
  SHAs that would change; downstream installs would need to
  reset; the marketplace cache would diverge).

The retro accepts this tradeoff explicitly. If a future audit
finds the historical leak unacceptable, Option 2 (rewrite +
force-push) remains available; this doc documents the deferral,
not a permanent decision.

## Other identity vectors — checked, not (yet) leaked

The hook fix catches `author` and `committer`. The audit also
checked the following potential leak channels on public `surebeli/kata`:

| Vector | Status | Notes |
|---|---|---|
| Author email | LEAKED then sealed forward | This retro |
| Committer email | LEAKED then sealed forward | Same root cause; same fix |
| `Signed-off-by:` trailers | Not used in this repo | If introduced, hook scans them via diff content |
| `Co-Authored-By:` trailers | Used (all point to `noreply@anthropic.com`) | Public AI identifier, safe |
| Git notes | One note `26033aa` exists with `git-ai@local` identity | Local-only `git-ai` tool artifact, safe |
| Tag annotations | No tags ship corp identity | Annotated tag check passes |
| Commit message body | No corp host / ticket-ID / personal-path strings | `git log --grep` confirms |
| Author NAME field | `litianyi` | A username, not a corp identifier on its own. Now `surebeli`. |
| `~/.gitconfig` `signingkey` | Not set | If signing gets enabled, key fingerprint would be a new vector |
| GPG signatures | Not currently in use | Adding them would add a new vector |

## Lessons that go beyond this incident

1. **A blocklist that only scans diff content is half a blocklist.**
   Metadata (author, committer, signature, notes, refs) needs its
   own scanner pass. We have one now for author + committer; signing
   and notes need the same treatment IF those features get enabled.

2. **Local config beats global config for public-facing repos.**
   The cleanest separation is `git config --local user.email` per
   repo whose remote is public. Make it part of repo bootstrap.

3. **An identity-blind hook is structurally vulnerable to "default
   wins" failure modes.** The hook didn't catch this because the
   identity was set elsewhere (globally) and inherited silently.
   Any state-bearing field that has a "silent default fallback"
   needs an explicit assertion at hook time, not just at diff
   review.

4. **Public release branches deserve a stricter blocklist than
   personal branches.** Future kata work on a release branch
   could enable additional checks (e.g., reject any commit
   missing `Co-Authored-By` if AI authorship is policy; reject
   any commit with a private-domain email regardless of pattern).

## Pre-commit hook test (manual repro for future verification)

To verify the hook would now catch the leak that escaped:

```bash
# Temporarily flip identity to corp-style
git config --local user.email "litianyi@<corp-domain-redacted>"

# Try to commit any change that touches a RELEVANT_PATH file
# (smoke / drift / etc. — to trigger hook beyond just the early exit)
touch tests/_compliance_probe.txt
git add tests/_compliance_probe.txt
git commit -m "probe"

# Expected: [pre-commit] BLOCKED — compliance violations in staged
# content or author identity, with `+author:` line cited.

# Cleanup
git config --local user.email "surebeli@gmail.com"
git restore --staged tests/_compliance_probe.txt
rm tests/_compliance_probe.txt
```

If the hook does NOT block this, the fix has regressed and the
retro lessons need to re-apply. After `f21d427` (the always-run-
Stage-0 fix), the hook should block this even on commits that don't
touch RELEVANT_PATHS.

## See also

- `.githooks/pre-commit` — Stage 0 scanner (content + identity)
- `.compliance-blocklist.txt` — regex patterns
- Commit `e8b1271` — author identity scan + local config flip
- Commit `f21d427` — always-run Stage 0 fix
