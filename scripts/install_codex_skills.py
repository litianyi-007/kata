#!/usr/bin/env python3
"""Install kata skills into a Codex skill root.

Codex discovers user-installed skills from a skills directory (typically
~/.codex/skills). kata's source skills live under plugin/skills/ and rely on
shared instructions from plugin/AGENTS.md plus scripts under plugin/scripts/.

This installer materializes Codex-ready skill folders by:
1. copying each plugin/skills/<name>/ directory to the destination
2. injecting the shared kata rules from plugin/AGENTS.md into SKILL.md
3. rewriting {plugin_root} placeholders to $KATA_HOME/plugin

The cloned repo remains the source of truth for scripts and updates.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugin"
SKILLS_ROOT = PLUGIN_ROOT / "skills"
AGENTS_MD = PLUGIN_ROOT / "AGENTS.md"

FRONTMATTER_RE = re.compile(r"^(---\s*\n.*?\n---\s*\n)(.*)$", re.DOTALL)


def default_dest() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "skills"
    return Path.home() / ".codex" / "skills"


def build_shared_prefix() -> str:
    text = AGENTS_MD.read_text(encoding="utf-8")
    if "## Skills" not in text:
        raise ValueError("plugin/AGENTS.md missing ## Skills section")
    common = text.split("## Skills", 1)[0].strip()
    common_lines = common.splitlines()
    if common_lines and common_lines[0].startswith("# "):
        common = "\n".join(common_lines[1:]).strip()

    return (
        "## Shared kata rules for Codex\n\n"
        "This installed skill is generated from `plugin/skills/*/SKILL.md` "
        "plus the shared kata rules from `plugin/AGENTS.md`.\n\n"
        "Set `KATA_HOME` to the cloned kata repo root so commands in "
        "this skill can resolve `plugin/scripts/*` under "
        "`$KATA_HOME/plugin/`.\n\n"
        "Codex discovers skills from its configured skill root "
        "(for example `~/.codex/skills`). Restart Codex after installing or "
        "updating these skills, and do not rely on AGENTS.md to register "
        "skills.\n\n"
        f"{common}\n"
    )


def rewrite_skill_markdown(text: str, shared_prefix: str) -> str:
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("SKILL.md missing YAML frontmatter")

    frontmatter, body = match.groups()
    body = body.replace("{plugin_root}", "$KATA_HOME/plugin")
    body = body.replace(
        "`$KATA_HOME/plugin` resolves to the directory containing "
        "`.claude-plugin/`.",
        "For Codex installs, set `KATA_HOME` to the cloned kata repo "
        "root; commands in this skill resolve scripts under "
        "`$KATA_HOME/plugin/`.",
    )
    body = body.lstrip()
    return frontmatter + shared_prefix + "\n" + body


def install_skill(skill_dir: Path, dest_root: Path, shared_prefix: str) -> str:
    skill_name = skill_dir.name
    target_dir = dest_root / skill_name
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(skill_dir, target_dir)

    skill_md = target_dir / "SKILL.md"
    rewritten = rewrite_skill_markdown(
        skill_md.read_text(encoding="utf-8"), shared_prefix)
    skill_md.write_text(rewritten, encoding="utf-8")
    return skill_name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dest",
        type=Path,
        default=default_dest(),
        help="Codex skill root to install into (default: $CODEX_HOME/skills "
             "or ~/.codex/skills)",
    )
    args = parser.parse_args()

    try:
        if not SKILLS_ROOT.exists():
            raise ValueError(f"missing skills directory: {SKILLS_ROOT}")
        if not AGENTS_MD.exists():
            raise ValueError(f"missing AGENTS.md: {AGENTS_MD}")

        args.dest.mkdir(parents=True, exist_ok=True)
        shared_prefix = build_shared_prefix()
        installed = []
        for skill_dir in sorted(p for p in SKILLS_ROOT.iterdir() if p.is_dir()):
            if not (skill_dir / "SKILL.md").exists():
                continue
            installed.append(install_skill(skill_dir, args.dest, shared_prefix))

        payload = {
            "result": "installed",
            "dest": str(args.dest.resolve()),
            "skill_count": len(installed),
            "skills": installed,
            "repo_root": str(REPO_ROOT.resolve()),
            "plugin_root": str(PLUGIN_ROOT.resolve()),
            "restart_required": True,
            "notes": [
                "Set KATA_HOME to the cloned kata repo root.",
                "Restart Codex to pick up new or updated skills.",
            ],
        }
        print(json.dumps(payload, ensure_ascii=True))
        return 0
    except Exception as exc:  # pragma: no cover - smoke test asserts JSON path
        payload = {
            "result": "error",
            "error": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
