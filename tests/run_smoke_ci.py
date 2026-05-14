#!/usr/bin/env python3
"""Run smoke tests under conditions that mimic GitHub Actions windows-latest.

The kata pre-commit hook runs `tests/run_smoke.py` directly, which inherits
the developer's local shell environment (global git identity, PYTHONUTF8,
configured locale, etc.). CI runners have none of that. The result:

    Works locally on Windows → red on CI Windows.

This wrapper closes that gap. It clears every state-bearing env var that a
fresh GitHub Actions windows-latest runner would lack, then invokes
`run_smoke.py` in a subprocess. If smoke passes here, CI should pass too.

Run before pushing if you've touched anything in plugin/scripts/, tests/,
or scripts/.

What we strip / override:

- HOME / USERPROFILE → fresh temp dir (no developer kata caches in path)
- TEMP / TMP        → inside that fresh temp (no shared state)
- PYTHONUTF8        → unset (CI runners don't set this; Windows
                       <3.15 defaults to locale codepage)
- PYTHONIOENCODING  → unset
- LANG / LC_ALL     → unset
- GIT_CONFIG_GLOBAL → /dev/null (no global git identity)
- GIT_CONFIG_SYSTEM → /dev/null
- core.autocrlf     → true (default on Windows; LF→CRLF on checkout)

Usage:

    python tests/run_smoke_ci.py           # run smoke under CI env
    python tests/run_smoke_ci.py --keep    # keep the temp HOME after run
                                            (for post-mortem inspection)

Exit code is forwarded from run_smoke.py.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SMOKE = REPO_ROOT / "tests" / "run_smoke.py"


# Env vars that a fresh CI runner would NOT have set. We unset these so a
# developer machine doesn't accidentally hide a CI failure. We intentionally
# do NOT strip PYTHONUTF8 because the CI workflow sets it explicitly — see
# .github/workflows/test.yml. The wrapper's default mirrors current CI.
STRIP_ENV_VARS = [
    "PYTHONIOENCODING",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "AK_WIKI_HOME",
    "KATA_HOME",
    "LLM_WIKI_HOME",
    "LLM_WIKI_PROJECT",
    "WIKI_PATH",
    # gstack / git-ai / personal-tool envs that may interfere
    "GSTACK_HOME",
    "GIT_AI_HOME",
]


def make_ci_like_env(fake_home: Path) -> dict:
    """Build a subprocess env that resembles windows-latest GitHub Actions."""
    env = dict(os.environ)
    for var in STRIP_ENV_VARS:
        env.pop(var, None)

    # Redirect home + temp into the fake dir
    env["HOME"] = str(fake_home)
    env["USERPROFILE"] = str(fake_home)
    env["TEMP"] = str(fake_home / "tmp")
    env["TMP"] = str(fake_home / "tmp")
    (fake_home / "tmp").mkdir(parents=True, exist_ok=True)

    # Strip global git config so tests can't accidentally inherit identity
    # from the developer machine. CI runners have no global git config.
    # Use a path that exists but is empty.
    null_config = fake_home / ".empty-gitconfig"
    null_config.write_text("", encoding="utf-8")
    env["GIT_CONFIG_GLOBAL"] = str(null_config)
    env["GIT_CONFIG_SYSTEM"] = str(null_config)

    # On Windows-latest, git's autocrlf default is true. Force it at the
    # process level so any `git init` in a test fixture inherits the CI
    # default rather than the developer's `core.autocrlf=input` or false.
    env["GIT_AUTOCRLF"] = "true"

    # Match the CI workflow's PYTHONUTF8=1 default. Setting it here
    # explicitly (rather than relying on developer inheritance) ensures
    # that if a future commit removes UTF-8 mode from the workflow,
    # this wrapper catches the resulting regression locally.
    env["PYTHONUTF8"] = "1"

    # Make sure we don't pick up the developer's `.kata` / `.gstack` state
    # via any fallback path that walks parents of HOME.
    env.pop("USERNAME", None)
    env.pop("LOGNAME", None)

    return env


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--keep", action="store_true",
                   help="Keep the fake HOME after the run (for inspection)")
    p.add_argument("--smoke-args", nargs=argparse.REMAINDER,
                   help="Args forwarded to run_smoke.py after `--`")
    args = p.parse_args()

    if not SMOKE.exists():
        print(f"FAIL: smoke runner not found at {SMOKE}", file=sys.stderr)
        return 2

    fake_home = Path(tempfile.mkdtemp(prefix="kata-smoke-ci-"))
    print(f"[smoke-ci] fake HOME: {fake_home}")
    print(f"[smoke-ci] stripping env: {', '.join(sorted(STRIP_ENV_VARS))}")
    print(f"[smoke-ci] running: {SMOKE}")
    print(f"[smoke-ci] {'-' * 60}")

    env = make_ci_like_env(fake_home)
    smoke_argv = [sys.executable, str(SMOKE)]
    if args.smoke_args:
        smoke_argv.extend(args.smoke_args)

    rc = subprocess.run(smoke_argv, env=env, cwd=str(REPO_ROOT)).returncode

    print(f"[smoke-ci] {'-' * 60}")
    print(f"[smoke-ci] exit code: {rc}")
    if rc == 0:
        print("[smoke-ci] PASS — CI Windows should match")
    else:
        print("[smoke-ci] FAIL — the first test that printed FAIL above is "
              "the same one breaking on CI")
        print(f"[smoke-ci] fake HOME preserved at: {fake_home}")
        # Force keep on failure so the user can inspect the fixture state
        args.keep = True

    if not args.keep:
        try:
            shutil.rmtree(fake_home, ignore_errors=True)
        except OSError:
            pass

    return rc


if __name__ == "__main__":
    sys.exit(main())
