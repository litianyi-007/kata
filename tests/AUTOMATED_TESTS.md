# Automated tests — writing convention

> Source of truth for **how to write tests that pass on every CI matrix**
> (linux + windows × py3.10 / 3.11 / 3.12 / 3.13). Driven by the 2026-05-14
> Windows-CI postmortem: 4 of 4 Windows jobs went red while every Linux job
> stayed green, because of a single cp1252-vs-UTF-8 encoding mismatch that
> never surfaced on a developer machine.

## TL;DR

If you're adding a new test or a new script that smoke calls into:

1. Set `PYTHONUTF8=1` in any env you control (workflow YAML, pre-commit
   hook, smoke wrapper). Already done at all three entry points.
2. Anywhere you call `subprocess.run(..., text=True)`, ALSO pass
   `encoding="utf-8"` and force `PYTHONIOENCODING=utf-8` in the child env.
   `tests/run_smoke.py:run()` and `tests/run_smoke.py:run_with_env()` do
   this; copy that pattern.
3. Before pushing, run `python tests/run_smoke_ci.py`. If it passes,
   CI will pass. If it fails, fix locally — do NOT push and hope.

The rest of this file is rules + reasoning + the postmortem.

---

## Mandatory rules

### Rule 1 — UTF-8 mode everywhere

**Why.** Python 3.10-3.14 on `windows-latest` defaults to cp1252 locale.
A script printing a single non-ASCII char (e.g. `→` in
`schema_validate.py` error messages) crashes the reader thread of any
`subprocess.run(..., text=True)` capturing its stdout. The crash returns
`result.stdout = None`, which then `json.loads(None)` → `TypeError`.

**How.** Set `PYTHONUTF8=1` at every entry point:

- CI workflow: `.github/workflows/test.yml` → `env: PYTHONUTF8: "1"` on
  the smoke job
- Pre-commit hook: `.githooks/pre-commit` → `export PYTHONUTF8=1` before
  any Python call
- Local CI parity check: `tests/run_smoke_ci.py` → sets it explicitly

PEP 686 makes UTF-8 mode the default in Python 3.15+. Until everyone is
on 3.15, the explicit setting stays.

### Rule 2 — Explicit subprocess encoding

**Why.** Even with `PYTHONUTF8=1` in the parent's env, child processes
spawned via `subprocess.run(text=True)` may not inherit it cleanly if
you pass `env={...}` (which **replaces** the env, doesn't merge). And
Python's `text=True` decode uses `locale.getencoding()` at parent
import time, not at call time.

**How.** Every `subprocess.run(..., text=True)` should also have:

```python
subprocess.run(
    [...],
    capture_output=True,
    text=True,
    encoding="utf-8",                                       # explicit decode
    env={**os.environ, "PYTHONIOENCODING": "utf-8", ...},   # explicit child encode
    cwd=...,
)
```

The two helpers in `tests/run_smoke.py` do this. **New direct calls
should follow the same shape** or — better — route through the helpers.

### Rule 3 — Path comparisons use pathlib, never raw strings

**Why.** Windows returns `\\` in paths; Linux returns `/`. Tests that
assert `"foo/bar" in output` will fail half the matrix.

**How.**

```python
assert Path("foo/bar") in [Path(p) for p in candidates]   # ok
assert "foo/bar" in output                                 # WRONG
```

For paths produced by `pathlib.Path`, use `.as_posix()` for forward-slash
display, `str()` for native form. Pick one per assertion and stick to it.

### Rule 4 — Git fixtures set identity + autocrlf

**Why.** GitHub Actions runners have **no** global git identity and a
default `core.autocrlf=true` on Windows. Tests that `git init` a fixture
must set both, locally to the fixture.

**How.**

```python
_git(fixture, "init", "-b", "main")
_git(fixture, "config", "user.email", "test@example.com")
_git(fixture, "config", "user.name",  "Test")
_git(fixture, "config", "core.autocrlf", "false")          # ← required
```

The third line prevents LF→CRLF rewriting on checkout, which would
otherwise make byte-exact file content comparisons fail on Windows.

### Rule 5 — Read text files with explicit utf-8

**Why.** `open(path).read()` uses locale encoding. cp1252 / cp936 will
mangle UTF-8 content silently.

**How.**

```python
path.read_text(encoding="utf-8")
path.write_text(content, encoding="utf-8")
open(path, "r", encoding="utf-8")
```

Never bare `open(path)`.

### Rule 6 — Validate with `tests/run_smoke_ci.py` before push

**Why.** Even with all the rules above, the easiest gate is
reproducing CI conditions locally:

```
python tests/run_smoke_ci.py
```

This:
- Creates a fresh fake `HOME` / `USERPROFILE` temp dir
- Strips developer state vars (LLM_WIKI_HOME, KATA_HOME, etc.)
- Empties global git config
- Forces `PYTHONUTF8=1` (matching workflow)
- Runs `tests/run_smoke.py` under those conditions

If smoke-ci passes locally, real CI should match. If it fails, the
fake HOME is preserved for post-mortem (path printed at the end).

---

## Postmortem — 2026-05-14 cp1252 incident

### Symptom

After commits `48360c8`, `59b9313`, `d3a7945`, `e6cc313`, every push
showed CI as red on `windows-latest` × all 4 Python versions, with
`smoke (py3.X on windows-latest)` failing at step 5 ("Run smoke tests")
within ~30 seconds. Linux runners stayed green.

### Why it didn't surface locally

Developer machine had Python locale `cp936` (Chinese), which can decode
the Chinese characters and the `→` arrow that scripts like
`schema_validate.py` emit. CI windows-latest has locale `cp1252`
(Western European), which can not. The bug only manifested in the
intersection of:

- Windows runner (locale = cp1252)
- A non-ASCII char in a captured subprocess stdout
- `subprocess.run(text=True)` decoding by parent locale

### The exact failure

In `tests/run_smoke.py:run()`, `subprocess.run` was invoked with
`text=True` but no explicit `encoding=`. Inside, when the child wrote
JSON containing `→` (`U+2192`):

1. Child's stdout encoding was cp1252 (no UTF-8 mode)
2. cp1252 has no codepoint for `→` — Python writes a replacement byte
3. Parent's `text=True` decode (cp1252 as well) tried to decode the
   resulting bytes
4. The reader thread (in subprocess internals) raised
   `UnicodeDecodeError` and crashed
5. `subprocess.run` returned with `stdout = None`
6. `json.loads(None)` → `TypeError`

### Fix

Three lines of fix:

1. `.github/workflows/test.yml` — `env: PYTHONUTF8: "1"` on smoke job
2. `.githooks/pre-commit` — `export PYTHONUTF8=1` before smoke
3. `tests/run_smoke.py:run/run_with_env` — explicit `encoding="utf-8"`
   + `PYTHONIOENCODING=utf-8` in child env

### Validation

`tests/run_smoke_ci.py` was added as a CI-parity wrapper. Running it
locally reproduces CI conditions. With the fix in place, smoke-ci
passes; without, it fails on Test 8 with the same TypeError CI saw.

---

## File-by-file: existing patterns to follow

| File | Pattern to copy |
|---|---|
| `tests/run_smoke.py:run` | Helper that wraps `subprocess.run` with utf-8 + PYTHONIOENCODING |
| `tests/run_smoke.py:run_with_env` | Same but accepts env overrides |
| `tests/run_smoke_ci.py` | CI-parity wrapper; run before every push |
| `.github/workflows/test.yml` | `env: PYTHONUTF8: "1"` job-level setting |
| `.githooks/pre-commit` | Sets PYTHONUTF8 before invoking Python |

## File-by-file: anti-patterns to NOT introduce

| Anti-pattern | Why it breaks |
|---|---|
| `subprocess.run([...], text=True)` (no `encoding=`) | Decodes by locale, breaks on cp1252 with non-ASCII |
| `print(json.dumps(payload, ensure_ascii=False))` without UTF-8 mode | Child stdout encode may replace or crash |
| `open(path).read()` | Reads as locale encoding |
| `"some/path" in output` | Path separator differs on Windows |
| `_git(fixture, "init")` without `core.autocrlf=false` | LF→CRLF rewrite breaks byte comparisons |
| `cd path && python script.py` in shell | shell vs pwsh quoting differences |

## When to revisit this doc

- Anyone gets a windows-only test failure that wasn't a copy-paste of
  one of the patterns above
- Python 3.15 ships and PEP 686 makes UTF-8 mode default — at that
  point Rule 1 becomes redundant for 3.15+; the rule stays for older
  versions until the matrix drops 3.10-3.14
