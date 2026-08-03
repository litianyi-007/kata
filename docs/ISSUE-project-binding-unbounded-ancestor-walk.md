# ISSUE: `.llm-wiki.yaml` / `.kata.yaml` project-binding lookup has no ceiling — unlike the git-root lookup in the same resolver

- Found: 2026-08-03, while fixing `tests/run_smoke.py` Test 17
  ("multi-project wiki root resolver") for non-hermeticity — see that fix
  for the reproduction that surfaced this.
- Status: **documented, not fixed.** The test-side fix (isolate Test 17's
  cwd under `tempfile.mkdtemp()`) removed the need to touch resolver
  semantics, so this round left `wiki_lib.py` untouched. This file is the
  record the task required regardless of whether the code changed.
- Severity: low-to-medium. Not a crash, not data loss. It is a **silent
  wrong answer**: a wiki maintenance action can run against the wrong
  wiki root with no error and no warning.
- Code: `plugin/scripts/wiki_lib.py`, `find_wiki_root()` priority chain
  (see docstring at line ~550).

## The asymmetry

`find_wiki_root()` walks from `cwd` up through ancestor directories at two
separate priority steps, looking for two different kinds of marker file.
Only one of the two walks respects a ceiling:

```python
def _find_git_root(start: Path) -> Path | None:
    ceilings = {
        Path(p).expanduser().resolve()
        for p in os.environ.get("GIT_CEILING_DIRECTORIES", "").split(os.pathsep)
        if p
    }
    for cur in (start, *start.parents):
        if (cur / ".git").exists():
            return cur.resolve()
        if cur.resolve() in ceilings:
            break          # <-- stops here
    return None


def _read_nearest_project_binding(start: Path) -> dict | None:
    for cur in (start, *start.parents):
        for name in (".llm-wiki.yaml", ".kata.yaml"):
            path = cur / name
            if path.exists():
                data = _read_simple_yaml(path)
                data["_base"] = cur
                return data
    return None            # <-- walks all the way to filesystem root, always
```

`_read_nearest_project_binding()` has no equivalent of
`GIT_CEILING_DIRECTORIES` (or any ceiling at all). It walks `(start,
*start.parents)` unconditionally to `/`.

## Real-world evidence

This project (`test-harnessloop`) dogfoods kata on itself and keeps a
top-level binding at
`/Users/litianyi/Documents/Code/_ai-goods/test-harnessloop/.llm-wiki.yaml`
(`wiki_path: /Users/litianyi/.llm-wiki/test-harnessloop`), which is exactly
the documented, supported "bind a project repo" pattern (README →
"Multiple wikis on one machine" → Pattern A/C).

Before the Test 17 fix, that file sat as an **unrelated ancestor** of
`kata/tests/_resolver/**` (the resolver test's fixture tree, which lives
inside this repo checkout). Any cwd under the fixture — including the one
specifically constructed to hit the final `~/.llm-wiki/common` fallback —
walked past the fixture boundary, past `kata/`, past `test-harnessloop/`,
and returned `~/.llm-wiki/test-harnessloop` instead of the fixture's
`common/`. That is: **on any machine with kata installed and a project
binding anywhere above the checkout, the test suite aborted at Test 17**
(92/~267 assertions run) and everything after it — including the version/
skill-count consistency guards (Test 62/62b) — silently never executed.
CI stayed green only because GitHub's runners have no such ancestor file.

The fix applied this round keeps the test's fixture tree under
`tempfile.mkdtemp()` (no ancestor relationship to any real project), which
sidesteps the issue for the test without touching resolver behavior. See
`tests/run_smoke.py`, Test 17, for the comment and implementation.

## Risk of "just add a ceiling" (why this round didn't)

The unbounded walk is not accidental scope creep — it is the mechanism
behind a **documented, supported feature**. README → "Multiple wikis on
one machine" → **Pattern C ("hybrid with nested override")** explicitly
relies on walking arbitrarily far up from a deeply nested directory (e.g.
a submodule several levels inside a monorepo) to find a *parent* binding,
with the nearest one winning:

> "A monorepo binds the default wiki, but a submodule binds its own. The
> resolver walks up from cwd and takes the **innermost** binding (parent
> bindings only apply when no closer one exists)... The same precedence
> applies to git submodules."

If `_read_nearest_project_binding()` gained a `GIT_CEILING_DIRECTORIES`-
style ceiling that defaulted to *unset* (matching `_find_git_root()`'s
current default), this would be a no-op for users who don't set the env
var — so the change itself would be low-risk *in isolation*. But:

1. It would add a second, independently-configured ceiling variable (or
   silently repurpose `GIT_CEILING_DIRECTORIES`, which is a **git**
   convention with different semantics/callers) — this needs its own
   design decision (new env var name? shared with git's? documented
   where?), not a drive-by one-line change.
2. Any real user relying on Pattern C from a directory *deeper* than
   whatever default ceiling a future change might introduce (if someone
   later decides a ceiling should be on by default, e.g. tied to
   `_find_git_root`'s own ceiling reuse) would have their monorepo-root
   binding silently stop resolving — the exact class of regression this
   whole exercise is about avoiding.
3. This project's own dogfood setup (a project-root `.llm-wiki.yaml`
   several directories above a nested `kata/` submodule checkout) is
   itself a live instance of the pattern the walk exists to support —
   changing the walk's semantics changes how this very project resolves,
   which is a bigger blast radius than fixing one test's hermeticity.

Given the task's explicit priority ("prefer fixing the test; only touch
`wiki_lib.py` if hermeticity is provably impossible without it" — and it
was not impossible here), this round left the resolver as-is and confined
the fix to test isolation.

## If this is revisited later

A plausible, opt-in-only fix: give `_read_nearest_project_binding()` an
env-var-gated ceiling (e.g. reusing `GIT_CEILING_DIRECTORIES` since both
walks are "stop walking up at this directory" in spirit, or a new
`LLM_WIKI_CEILING_DIRECTORIES` if conflating with git's variable is
considered confusing), defaulting to unset/unbounded so no existing
Pattern A/B/C setup changes behavior unless a user opts in. That would
close the asymmetry without breaking the documented monorepo-override use
case. Out of scope for this round; recorded here so the next person
touching `find_wiki_root()` doesn't have to re-derive this from scratch.
