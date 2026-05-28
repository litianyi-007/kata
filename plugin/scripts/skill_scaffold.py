#!/usr/bin/env python3
"""Skill scaffolding helper — v1.15 work-loop bridge.

Deterministic engine for the `wiki-skill-create` skill. The agent in
the skill orchestrates the user-facing flow (pattern choice via
AskUserQuestion, name + description capture, optional final
wiki-ingest). This script covers the mechanical parts:

- Discover project context: project root, git root, tech stack,
  test/build/lint commands, kata wiki binding.
- Render: substitute {{VAR}} placeholders in a template against a
  variable map; write to a target path (creating parent dirs).
- Verify: static check on a generated SKILL.md (frontmatter parses,
  required fields, name format, description quality, sentinel comment
  present, no unresolved placeholders).
- list-patterns: enumerate template files in the templates dir.

Subcommands:

    skill_scaffold.py discover [--project-root <path>] [--templates-dir <path>]
        Inspect the project + kata binding + tech stack. Emit JSON
        envelope used by the orchestrator to populate the render.

    skill_scaffold.py render --pattern <name> --skill-name <kebab>
                             [--target <path-or-symbolic>]
                             [--templates-dir <path>]
                             [--dry-run]
                             [--var KEY=VALUE ...]
        Render a template against the given variables and write to
        the target. `--target` accepts a symbolic value
        (`claude-code` / `codex` / `wiki`) or an explicit path. When
        symbolic, the path is computed from discover output + the
        skill name.

    skill_scaffold.py verify <skill-path>
        Static check on a rendered SKILL.md. Emits a JSON envelope
        with `ok: true/false`, `checks: [...]`, and `failures: [...]`.

    skill_scaffold.py list-patterns [--templates-dir <path>]
        Print available pattern names and their template paths.

Exit codes:
    0 — success
    1 — invalid input or expected failure (verify failure, missing
        template, etc.)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from wiki_lib import emit, find_wiki_root, parse_frontmatter


# Anthropic SKILL.md frontmatter limit per spec.
FRONTMATTER_MAX_CHARS = 1024

# Where templates live by default — alongside the skill that owns them.
DEFAULT_TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent
    / "skills" / "wiki-skill-create" / "templates"
)

# Sentinel comment marker that identifies kata-generated skills.
SENTINEL_PREFIX = "<!-- kata:generated-skill"

# Default ingest page types per pattern (used when rendering for
# patterns that wire wiki-ingest defaults — currently only custom uses
# {{INGEST_PAGE_TYPE}} directly).
PATTERN_DEFAULT_INGEST_TYPE = {
    "issue-fix": "lesson",
    "feature-build": "decision",
    "bug-debug": "lesson",
    "custom": "lesson",
}


# ---------------------------------------------------------------------------
# Discover
# ---------------------------------------------------------------------------

def _detect_git_root(start: Path) -> Path | None:
    """Walk upward from `start` looking for a .git directory."""
    cur = start.resolve()
    for parent in [cur] + list(cur.parents):
        if (parent / ".git").exists():
            return parent
    return None


def _detect_tech_stack(project_root: Path) -> tuple[list[str], dict, str | None]:
    """Heuristic stack detection. Returns (stacks, commands, project_name).

    `stacks` is the ordered list of detected stack identifiers.
    `commands` is a dict with default `test_command`, `build_command`,
    `lint_command` keys, populated from the FIRST stack that supplies
    each.
    `project_name` is the canonical project name declared in the first
    detected manifest (e.g. package.json `name`, Cargo.toml `[package].name`,
    go.mod `module`), or None if no manifest declares one.
    """
    stacks: list[str] = []
    commands: dict[str, str] = {}
    project_name: str | None = None

    # Node.js / TS
    pkg_json = project_root / "package.json"
    if pkg_json.is_file():
        stacks.append("nodejs")
        try:
            pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {}) if isinstance(pkg.get("scripts"), dict) else {}
        except (OSError, json.JSONDecodeError):
            pkg = {}
            scripts = {}
        # Prefer explicit npm scripts; fall back to standard names.
        if "test" in scripts:
            commands.setdefault("test_command", "npm test")
        if "build" in scripts:
            commands.setdefault("build_command", "npm run build")
        for lint_name in ("lint", "lint:check", "eslint"):
            if lint_name in scripts:
                commands.setdefault("lint_command", f"npm run {lint_name}")
                break
        # Also peek at devDependencies for typescript signal.
        deps = pkg.get("devDependencies", {}) if isinstance(pkg.get("devDependencies"), dict) else {}
        if "typescript" in deps and "typescript" not in stacks:
            stacks.append("typescript")
        # npm package name (scoped names like @foo/bar render as-is)
        name_field = pkg.get("name")
        if isinstance(name_field, str) and name_field.strip():
            project_name = project_name or name_field.strip()

    # Python
    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file() or (project_root / "setup.py").is_file():
        stacks.append("python")
        commands.setdefault("test_command", "pytest")
        commands.setdefault("build_command", "python -m build")
        commands.setdefault("lint_command", "ruff check .")
        # Cheap regex peek at [project] name (avoids tomllib for stdlib subset).
        if pyproject.is_file() and project_name is None:
            try:
                txt = pyproject.read_text(encoding="utf-8")
            except OSError:
                txt = ""
            m = re.search(
                r"^\[project\]\s*[\r\n]+(?:.*\n)*?\s*name\s*=\s*[\"']([^\"']+)[\"']",
                txt, re.MULTILINE,
            )
            if m:
                project_name = m.group(1).strip()

    # Rust
    cargo = project_root / "Cargo.toml"
    if cargo.is_file():
        stacks.append("rust")
        commands.setdefault("test_command", "cargo test")
        commands.setdefault("build_command", "cargo build")
        commands.setdefault("lint_command", "cargo clippy --all-targets -- -D warnings")
        if project_name is None:
            try:
                txt = cargo.read_text(encoding="utf-8")
            except OSError:
                txt = ""
            m = re.search(
                r"^\[package\]\s*[\r\n]+(?:.*\n)*?\s*name\s*=\s*[\"']([^\"']+)[\"']",
                txt, re.MULTILINE,
            )
            if m:
                project_name = m.group(1).strip()

    # Go
    go_mod = project_root / "go.mod"
    if go_mod.is_file():
        stacks.append("go")
        commands.setdefault("test_command", "go test ./...")
        commands.setdefault("build_command", "go build ./...")
        commands.setdefault("lint_command", "go vet ./...")
        if project_name is None:
            try:
                txt = go_mod.read_text(encoding="utf-8")
            except OSError:
                txt = ""
            m = re.search(r"^module\s+([^\s]+)", txt, re.MULTILINE)
            if m:
                # `module github.com/user/repo` → repo
                project_name = m.group(1).rsplit("/", 1)[-1]

    # Java/Kotlin via Gradle or Maven
    if (project_root / "build.gradle").is_file() or (project_root / "build.gradle.kts").is_file():
        stacks.append("gradle")
        commands.setdefault("test_command", "./gradlew test")
        commands.setdefault("build_command", "./gradlew build")
    if (project_root / "pom.xml").is_file():
        stacks.append("maven")
        commands.setdefault("test_command", "mvn test")
        commands.setdefault("build_command", "mvn package")

    # Fill placeholders for any unset commands.
    for k in ("test_command", "build_command", "lint_command"):
        commands.setdefault(k, f"<your-{k.replace('_', '-')}>")

    return stacks, commands, project_name


def _detect_skill_homes(project_root: Path) -> list[str]:
    """Find which skill-home directories already exist in this project."""
    homes: list[str] = []
    candidates = [
        ".claude/skills",
        ".codex/skills",
        ".agents/skills",
        ".cursor/skills",
    ]
    for c in candidates:
        if (project_root / c).is_dir():
            homes.append(c)
    return homes


def _existing_kata_generated_skills(project_root: Path) -> list[dict]:
    """List skills under .claude/skills that carry our sentinel comment."""
    out: list[dict] = []
    skill_dir = project_root / ".claude" / "skills"
    if not skill_dir.is_dir():
        return out
    for sub in skill_dir.iterdir():
        if not sub.is_dir():
            continue
        skill_md = sub / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r"<!--\s*kata:generated-skill\s+([^>]+?)-->", text)
        if not m:
            continue
        meta = {}
        for kv in m.group(1).split():
            if "=" in kv:
                k, v = kv.split("=", 1)
                meta[k.strip()] = v.strip()
        out.append({"name": sub.name, "path": str(skill_md), **meta})
    return out


def _read_kata_version() -> str:
    """Read kata version from plugin.json (single source of truth)."""
    try:
        plugin_json = (
            Path(__file__).resolve().parent.parent
            / ".claude-plugin" / "plugin.json"
        )
        return str(json.loads(plugin_json.read_text(encoding="utf-8")).get("version", "unknown"))
    except (OSError, ValueError):
        return "unknown"


def cmd_discover(args) -> int:
    project_root = Path(args.project_root or os.getcwd()).resolve()
    if not project_root.is_dir():
        emit({"error": f"project_root not found: {project_root}"})
        return 1

    git_root = _detect_git_root(project_root)
    stacks, commands, manifest_name = _detect_tech_stack(project_root)
    project_name = manifest_name or (git_root or project_root).name
    skill_homes = _detect_skill_homes(project_root)
    existing = _existing_kata_generated_skills(git_root or project_root)

    # Kata wiki binding — same resolution as every other kata skill.
    wiki_path: str | None = None
    wiki_id: str | None = None
    try:
        root = find_wiki_root(None)
        if root and root.is_dir():
            wiki_path = str(root)
            schema_md = root / "SCHEMA.md"
            if schema_md.is_file():
                # Cheap regex peek — full parse is in wiki_lib, but this
                # only needs the wiki_id line.
                try:
                    txt = schema_md.read_text(encoding="utf-8")
                    m = re.search(
                        r"^wiki_id:\s*([0-9a-f-]{36})", txt, re.MULTILINE
                    )
                    if m:
                        wiki_id = m.group(1)
                except OSError:
                    pass
    except Exception:
        # find_wiki_root may raise on unbound state — that's fine, treat
        # as no binding.
        pass

    templates_dir = Path(args.templates_dir).resolve() if args.templates_dir \
        else DEFAULT_TEMPLATES_DIR
    available_patterns = _list_patterns_from_dir(templates_dir)

    emit({
        "project_root": str(project_root),
        "git_root": str(git_root) if git_root else None,
        "project_name": project_name,
        "kata_wiki_path": wiki_path,
        "kata_wiki_id": wiki_id,
        "tech_stack": stacks,
        "test_command": commands.get("test_command"),
        "build_command": commands.get("build_command"),
        "lint_command": commands.get("lint_command"),
        "existing_skill_homes": skill_homes,
        "existing_generated_skills": existing,
        "kata_version": _read_kata_version(),
        "available_patterns": available_patterns,
        "templates_dir": str(templates_dir),
    })
    return 0


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def _list_patterns_from_dir(templates_dir: Path) -> list[str]:
    if not templates_dir.is_dir():
        return []
    return sorted(p.stem.replace(".md", "") for p in templates_dir.glob("*.md.tmpl"))


def _template_path(templates_dir: Path, pattern: str) -> Path:
    return templates_dir / f"{pattern}.md.tmpl"


def _resolve_target_path(target: str, skill_name: str,
                         project_root: Path, wiki_path: Path | None) -> Path:
    """Resolve --target into an absolute SKILL.md path.

    Symbolic values:
      - claude-code → <project_root>/.claude/skills/<skill_name>/SKILL.md
      - codex       → ~/.codex/skills/<skill_name>/SKILL.md
      - wiki        → <wiki_path>/skills/<skill_name>/SKILL.md  (requires wiki binding)
    Otherwise treat `target` as a literal path — if it ends in
    `SKILL.md` use as-is, else append `<skill_name>/SKILL.md`.
    """
    SYMBOLIC = {"claude-code", "codex", "wiki"}
    if target == "claude-code":
        return project_root / ".claude" / "skills" / skill_name / "SKILL.md"
    if target == "codex":
        return Path.home() / ".codex" / "skills" / skill_name / "SKILL.md"
    if target == "wiki":
        if wiki_path is None:
            raise ValueError(
                "target=wiki requires a bound kata wiki; run /kata:wiki-init first"
            )
        return wiki_path / "skills" / skill_name / "SKILL.md"
    if target in SYMBOLIC:
        # Defensive — should not reach here.
        raise ValueError(f"unhandled symbolic target: {target}")
    # Literal path
    p = Path(os.path.expanduser(target)).resolve()
    if p.name == "SKILL.md":
        return p
    return p / skill_name / "SKILL.md"


# Reserved variable names — passed in by render directly, not via --var.
_RESERVED_VARS = {
    "SKILL_NAME", "SKILL_DISPLAY_NAME", "PATTERN_NAME",
    "PROJECT_NAME", "PROJECT_ROOT", "WIKI_PATH", "TECH_STACK",
    "TEST_COMMAND", "BUILD_COMMAND", "LINT_COMMAND",
    "KATA_VERSION", "GENERATED_AT",
}


def _kebab_to_display(name: str) -> str:
    """feature-ship-loop → Feature Ship Loop"""
    return " ".join(w.capitalize() for w in name.split("-"))


def _substitute(template_text: str, vars_map: dict) -> str:
    """Replace {{KEY}} with vars_map[KEY]. Unknown keys raise."""
    pattern = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")

    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key not in vars_map:
            raise KeyError(key)
        v = vars_map[key]
        return str(v if v is not None else "")
    return pattern.sub(repl, template_text)


def cmd_render(args) -> int:
    templates_dir = Path(args.templates_dir).resolve() if args.templates_dir \
        else DEFAULT_TEMPLATES_DIR
    pattern = args.pattern
    tmpl_path = _template_path(templates_dir, pattern)
    if not tmpl_path.is_file():
        emit({
            "error": f"template not found for pattern={pattern}",
            "templates_dir": str(templates_dir),
            "available": _list_patterns_from_dir(templates_dir),
        })
        return 1

    skill_name = args.skill_name.strip()
    if not re.match(r"^[a-z][a-z0-9-]*$", skill_name):
        emit({"error": "skill_name must be kebab-case (letters/digits/hyphen, "
                       "lowercase, start with letter)", "given": skill_name})
        return 1

    project_root = Path(args.project_root or os.getcwd()).resolve()
    git_root = _detect_git_root(project_root)
    stacks, commands, manifest_name = _detect_tech_stack(project_root)
    project_name = manifest_name or (git_root or project_root).name

    # Kata wiki binding (optional)
    wiki_path_obj: Path | None = None
    wiki_path_str = "<bind-a-kata-wiki-via-wiki-init-first>"
    try:
        root = find_wiki_root(None)
        if root and root.is_dir():
            wiki_path_obj = root
            wiki_path_str = str(root)
    except Exception:
        pass

    # Build the variable map
    vars_map: dict[str, str] = {
        "SKILL_NAME": skill_name,
        "SKILL_DISPLAY_NAME": _kebab_to_display(skill_name),
        "PATTERN_NAME": pattern,
        "PROJECT_NAME": project_name,
        "PROJECT_ROOT": str(git_root or project_root),
        "WIKI_PATH": wiki_path_str,
        "TECH_STACK": ", ".join(stacks) if stacks else "<not detected>",
        "TEST_COMMAND": commands["test_command"],
        "BUILD_COMMAND": commands["build_command"],
        "LINT_COMMAND": commands["lint_command"],
        "KATA_VERSION": _read_kata_version(),
        "GENERATED_AT": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # Apply --var overrides on top
    for raw in (args.var or []):
        if "=" not in raw:
            emit({"error": f"--var must be KEY=VALUE; got: {raw!r}"})
            return 1
        k, v = raw.split("=", 1)
        vars_map[k.strip()] = v

    # Custom pattern needs a few extra defaults if user didn't supply them
    if pattern == "custom":
        vars_map.setdefault("DESCRIPTION",
                            "Use when the project needs a custom kata-integrated work loop.")
        vars_map.setdefault("ARGUMENT_HINT", "<task-statement>")
        vars_map.setdefault("WHEN_TO_USE",
                            "<describe the triggering conditions>")
        vars_map.setdefault("WHEN_NOT_TO_USE",
                            "<describe when an existing kata loop fits better>")
        vars_map.setdefault("CUSTOM_STEPS",
                            "<list the user-defined steps for this loop>")
        vars_map.setdefault("MANUAL_VERIFICATION",
                            "<describe what the user should check>")
        vars_map.setdefault(
            "INGEST_PAGE_TYPE",
            PATTERN_DEFAULT_INGEST_TYPE.get(pattern, "lesson"),
        )

    tmpl_text = tmpl_path.read_text(encoding="utf-8")
    try:
        rendered = _substitute(tmpl_text, vars_map)
    except KeyError as e:
        emit({
            "error": f"template references unknown variable {{{{{e.args[0]}}}}}",
            "pattern": pattern,
            "template_path": str(tmpl_path),
            "hint": "supply with --var KEY=VALUE",
        })
        return 1

    # Compute target path
    try:
        target_path = _resolve_target_path(
            args.target, skill_name, project_root, wiki_path_obj,
        )
    except ValueError as e:
        emit({"error": str(e), "target": args.target})
        return 1

    if args.dry_run:
        emit({
            "dry_run": True,
            "pattern": pattern,
            "skill_name": skill_name,
            "target_path": str(target_path),
            "rendered_length": len(rendered),
            "rendered_preview": rendered[:500],
        })
        return 0

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(rendered, encoding="utf-8")

    emit({
        "pattern": pattern,
        "skill_name": skill_name,
        "target_path": str(target_path),
        "size_bytes": target_path.stat().st_size,
        "wiki_path": wiki_path_str,
        "tech_stack": stacks,
        "advisory": (
            "Run `skill_scaffold.py verify` against the target path "
            "to confirm frontmatter validity + no unresolved placeholders."
        ),
    })
    return 0


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

# Regex for first-person pronouns in description (CSO guidance).
_FIRST_PERSON_RE = re.compile(r"\b(I|me|my|mine|we|us|our|ours)\b")
_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def _verify_skill_md(skill_path: Path) -> dict:
    """Run all 9 verification checks on a SKILL.md.

    Returns dict: {ok: bool, checks: [...], failures: [...]}.
    Each check entry: {name, passed: bool, detail: str}.
    """
    if not skill_path.is_file():
        return {
            "ok": False,
            "checks": [],
            "failures": [f"file not found: {skill_path}"],
        }

    text = skill_path.read_text(encoding="utf-8")
    checks: list[dict] = []

    # 1 + 2 + 3 + 4: Frontmatter parses, required fields, name format, length
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        checks.append({"name": "frontmatter-parses", "passed": False,
                       "detail": "no YAML frontmatter block found"})
    else:
        fm_text = m.group(1)
        try:
            fm, _ = parse_frontmatter(text)
            parsed_ok = isinstance(fm, dict)
        except Exception as e:
            fm = {}
            parsed_ok = False
            checks.append({"name": "frontmatter-parses", "passed": False,
                           "detail": f"parse error: {e}"})
        if parsed_ok:
            checks.append({"name": "frontmatter-parses", "passed": True,
                           "detail": f"{len(fm)} keys"})
        # Required fields
        for field in ("name", "description"):
            checks.append({
                "name": f"frontmatter-has-{field}",
                "passed": field in fm and bool(str(fm.get(field) or "").strip()),
                "detail": f"present={bool(fm.get(field))}",
            })
        # Name format
        name_val = str(fm.get("name") or "")
        checks.append({
            "name": "name-format-valid",
            "passed": bool(_NAME_RE.match(name_val)),
            "detail": f"name={name_val!r} (pattern: lowercase letters/digits/hyphen)",
        })
        # Frontmatter length
        fm_len = len(fm_text)
        checks.append({
            "name": "frontmatter-length-ok",
            "passed": fm_len <= FRONTMATTER_MAX_CHARS,
            "detail": f"{fm_len}/{FRONTMATTER_MAX_CHARS} chars",
        })

        desc_val = str(fm.get("description") or "")
        # 5. Description starts with "Use when"
        checks.append({
            "name": "description-starts-with-use-when",
            "passed": desc_val.strip().lower().startswith("use when"),
            "detail": (f"first 60 chars: {desc_val[:60]!r}"
                       if desc_val else "(empty)"),
        })
        # 6. Description in third person
        first_person_hits = _FIRST_PERSON_RE.findall(desc_val)
        checks.append({
            "name": "description-third-person",
            "passed": not first_person_hits,
            "detail": (f"first-person pronouns found: {first_person_hits}"
                       if first_person_hits else "no first-person pronouns"),
        })
        # 9. argument-hint required when user-invocable
        if fm.get("user-invocable") is True:
            checks.append({
                "name": "argument-hint-when-invocable",
                "passed": bool(str(fm.get("argument-hint") or "").strip()),
                "detail": f"user-invocable=true, argument-hint={fm.get('argument-hint')!r}",
            })

    # 7. Sentinel comment present
    checks.append({
        "name": "sentinel-present",
        "passed": SENTINEL_PREFIX in text,
        "detail": f"looking for {SENTINEL_PREFIX!r}",
    })

    # 8. No unresolved {{VAR}}
    unresolved = re.findall(r"\{\{([A-Z][A-Z0-9_]*)\}\}", text)
    checks.append({
        "name": "no-unresolved-placeholders",
        "passed": not unresolved,
        "detail": (f"unresolved: {sorted(set(unresolved))}"
                   if unresolved else "none"),
    })

    failures = [c for c in checks if not c["passed"]]
    return {
        "ok": not failures,
        "skill_path": str(skill_path),
        "checks": checks,
        "failures": [f["name"] for f in failures],
    }


def cmd_verify(args) -> int:
    result = _verify_skill_md(Path(args.skill_path).expanduser().resolve())
    emit(result)
    return 0 if result["ok"] else 1


# ---------------------------------------------------------------------------
# list-patterns
# ---------------------------------------------------------------------------

def cmd_list_patterns(args) -> int:
    templates_dir = Path(args.templates_dir).resolve() if args.templates_dir \
        else DEFAULT_TEMPLATES_DIR
    if not templates_dir.is_dir():
        emit({"error": f"templates dir not found: {templates_dir}"})
        return 1
    patterns = _list_patterns_from_dir(templates_dir)
    detail = []
    for p in patterns:
        tp = _template_path(templates_dir, p)
        size = tp.stat().st_size if tp.is_file() else None
        detail.append({"pattern": p, "template_path": str(tp), "size_bytes": size})
    emit({
        "templates_dir": str(templates_dir),
        "patterns": patterns,
        "detail": detail,
    })
    return 0


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description="kata wiki-skill-create scaffolding helper (v1.15)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # discover
    pd = sub.add_parser("discover", help="emit project + kata + tech-stack context")
    pd.add_argument("--project-root", default=None,
                    help="override project root (default: os.getcwd())")
    pd.add_argument("--templates-dir", default=None,
                    help="override templates dir (default: ../skills/wiki-skill-create/templates/)")
    pd.set_defaults(func=cmd_discover)

    # render
    pr = sub.add_parser("render", help="render a pattern template to a SKILL.md")
    pr.add_argument("--pattern", required=True,
                    help="pattern name (one of `list-patterns` output)")
    pr.add_argument("--skill-name", required=True,
                    help="kebab-case name of the generated skill")
    pr.add_argument("--target", default="claude-code",
                    help="symbolic (claude-code|codex|wiki) or absolute path")
    pr.add_argument("--templates-dir", default=None)
    pr.add_argument("--project-root", default=None)
    pr.add_argument("--dry-run", action="store_true",
                    help="render but do not write; emit preview")
    pr.add_argument("--var", action="append", default=[],
                    help="extra variable: KEY=VALUE (repeatable). For "
                         "`custom` pattern, supply DESCRIPTION / WHEN_TO_USE / etc.")
    pr.set_defaults(func=cmd_render)

    # verify
    pv = sub.add_parser("verify", help="static check on a rendered SKILL.md")
    pv.add_argument("skill_path", help="path to the SKILL.md to verify")
    pv.set_defaults(func=cmd_verify)

    # list-patterns
    pl = sub.add_parser("list-patterns", help="enumerate available pattern templates")
    pl.add_argument("--templates-dir", default=None)
    pl.set_defaults(func=cmd_list_patterns)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
