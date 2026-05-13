from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

from dogfood_plan_necallkit_lessons_import import build_plan


BUNDLE_NAME = "necallkit-lessons-seed"
TODAY = date.today().isoformat()
PROPOSED_CATEGORY = (
    '  - name: lessons',
    '    purpose: "Lessons learned, prevention strategies, and reusable debugging/review patterns."',
)
PROPOSED_TAGS = ("async", "camera", "lifecycle", "logger", "performance", "state-machine")
CATEGORY_HEADINGS = {
    "platforms": "Platforms",
    "modules": "Modules",
    "features": "Features",
    "bugs": "Bugs",
    "decisions": "Decisions",
    "lessons": "Lessons",
    "queries": "Queries",
}
COMMON_RELATED = (
    "necallkit-docs-index",
    "necallkit-agent-sdd-operating-contract",
    "necallkit-electron-web-reuse-operating-boundary-query",
)
EXTRA_RELATED_BY_ID = {
    "L013": (
        "necallkit-architecture-overview",
        "002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20",
        "002-electron-callkit-example-contract-boundary-query",
    ),
    "L012": (
        "necallkit-feature-bug-tracker",
        "necallkit-current-task-list",
    ),
}


@dataclass(frozen=True)
class LessonSpec:
    source_relative: PurePosixPath
    target_relative: PurePosixPath
    lesson_id: str
    title: str
    source_category: str
    tags: tuple[str, ...]
    summary: str
    related_lessons: tuple[str, ...]
    related_fixes: tuple[str, ...]
    admission_score: int
    admission_reasons: tuple[str, ...]

    @property
    def raw_relative(self) -> PurePosixPath:
        return PurePosixPath("raw") / "imported" / BUNDLE_NAME / self.source_relative

    @property
    def slug(self) -> str:
        return self.target_relative.stem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import the approved NECallKit lessons seed set into the dogfood wiki.")
    parser.add_argument("--wiki", required=True, help="NECallKit wiki root")
    parser.add_argument("--project", required=True, help="NECallKit project root")
    parser.add_argument("--seed-limit", type=int, default=6, help="Seed set size to import")
    parser.add_argument(
        "--checkpoint-script",
        default=str(Path(__file__).resolve().parents[1] / "plugin" / "scripts" / "import_checkpoint.py"),
        help="Path to kata import_checkpoint.py",
    )
    parser.add_argument("--execute", action="store_true", help="Write changes. Default is dry-run only.")
    parser.add_argument("--commit", action="store_true", help="Commit after a successful execute.")
    parser.add_argument("--push", action="store_true", help="Push after commit. Implies --commit.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow execute when wiki git tree is dirty.")
    return parser.parse_args()


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def yaml_quote(value: str) -> str:
    return '"' + value.replace('"', "'") + '"'


def strip_frontmatter(content: str) -> str:
    if not content.startswith("---"):
        return content.strip()
    end = content.find("\n---", 3)
    if end == -1:
        return content.strip()
    return content[end + 4 :].strip()


def source_date(content: str) -> str:
    match = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})\s*$", content, re.MULTILINE)
    if match:
        return match.group(1)
    return TODAY


def run_git(wiki_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(wiki_root), *args],
        text=True,
        capture_output=True,
        check=check,
    )


def git_status_porcelain(wiki_root: Path) -> str:
    completed = run_git(wiki_root, "status", "--porcelain", check=True)
    return completed.stdout.strip()


def checkpoint(script: Path, wiki_root: Path, *args: str) -> None:
    command = [sys.executable, str(script), "--wiki", str(wiki_root), *args]
    completed = subprocess.run(command, text=True, capture_output=True, check=True)
    if completed.stdout.strip():
        print(completed.stdout.strip())


def build_specs(project_root: Path, wiki_root: Path, seed_limit: int) -> tuple[LessonSpec, ...]:
    plan = build_plan(project_root, wiki_root, seed_limit)
    seed_sources = set(plan["recommended_seed_set"]["sources"])
    seed_items = [
        item
        for item in plan["plan"]
        if item["source"] in seed_sources and item["admission"]["decision"] == "admit"
    ]
    order = {source: index for index, source in enumerate(plan["recommended_seed_set"]["sources"])}
    seed_items.sort(key=lambda item: order[item["source"]])
    specs: list[LessonSpec] = []
    for item in seed_items:
        specs.append(
            LessonSpec(
                source_relative=PurePosixPath(item["source"]),
                target_relative=PurePosixPath(item["target"]),
                lesson_id=item["id"],
                title=item["title"],
                source_category=item["source_category"],
                tags=tuple(dict.fromkeys([*item["tags"], *item["proposed_tags"]])),
                summary=item["summary"],
                related_lessons=tuple(item["related_lessons"]),
                related_fixes=tuple(item["related_fixes"]),
                admission_score=int(item["admission"]["score"]),
                admission_reasons=tuple(item["admission"]["reasons"]),
            )
        )
    return tuple(specs)


def safe_copy_raw(project_root: Path, wiki_root: Path, spec: LessonSpec) -> str:
    source = project_root / Path(spec.source_relative.as_posix())
    destination = wiki_root / Path(spec.raw_relative.as_posix())
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if source.read_bytes() == destination.read_bytes():
            return "unchanged"
        raise RuntimeError(f"Raw file differs and will not be overwritten: {destination}")
    shutil.copy2(source, destination)
    return "created"


def related_slugs(spec: LessonSpec, slug_by_id: dict[str, str]) -> tuple[str, ...]:
    links: list[str] = []
    links.extend(COMMON_RELATED)
    links.extend(EXTRA_RELATED_BY_ID.get(spec.lesson_id, ()))
    for lesson_id in spec.related_lessons:
        if lesson_id in slug_by_id:
            links.append(slug_by_id[lesson_id])
    return tuple(dict.fromkeys(links))


def page_body(spec: LessonSpec, source_path: Path, content: str, slug_by_id: dict[str, str]) -> str:
    tags_block = "\n".join(f"  - {tag}" for tag in spec.tags)
    related_block = "\n".join(f"- [[{slug}]]" for slug in related_slugs(spec, slug_by_id))
    fixes_block = "\n".join(f"- `{fix}`" for fix in spec.related_fixes) or "- None recorded in source metadata"
    reasons_block = "\n".join(f"- {reason}" for reason in spec.admission_reasons)
    imported = strip_frontmatter(content)
    return f"""---
title: {yaml_quote(spec.title)}
type: lessons
tags:
{tags_block}
created: {TODAY}
updated: {TODAY}
published_at: {source_date(content)}
ingested_at: {TODAY}
sources:
  - {spec.raw_relative.as_posix()}
---

# {spec.title}

## Summary

- {spec.summary}
- Source bundle: `{BUNDLE_NAME}`
- Original path: `{spec.source_relative.as_posix()}`
- Lesson ID: `{spec.lesson_id}`
- Source category: `{spec.source_category}`

## Why this is lesson memory

Admission score: `{spec.admission_score}`

{reasons_block}

## Related wiki pages

{related_block}

## Related fix IDs

{fixes_block}

## Imported Content

{imported}
"""


def insert_schema_category(lines: list[str]) -> bool:
    text = "\n".join(lines)
    if "  - name: lessons" in text:
        return False
    in_categories = False
    in_fence = False
    insert_at = None
    last_category_line = None
    for index, line in enumerate(lines):
        if line.strip() == "## Categories":
            in_categories = True
            continue
        if in_categories and line.strip() == "```yaml":
            in_fence = True
            continue
        if in_categories and in_fence and line.strip() == "```":
            insert_at = insert_at or index
            break
        if in_categories and in_fence and line.strip() == "- name: queries":
            insert_at = index
            break
        if in_categories and in_fence and line.strip().startswith("- name:"):
            last_category_line = index
    if insert_at is None and last_category_line is not None:
        insert_at = last_category_line + 2
    if insert_at is None:
        raise RuntimeError("Could not locate SCHEMA.md Categories yaml block")
    lines[insert_at:insert_at] = list(PROPOSED_CATEGORY)
    return True


def insert_schema_tags(lines: list[str]) -> list[str]:
    existing = {line.strip()[2:].strip() for line in lines if line.strip().startswith("- ")}
    missing = [tag for tag in PROPOSED_TAGS if tag not in existing]
    if not missing:
        return []
    in_tags = False
    in_fence = False
    insert_at = None
    for index, line in enumerate(lines):
        if line.strip() == "## Tag taxonomy":
            in_tags = True
            continue
        if in_tags and line.strip() == "```yaml":
            in_fence = True
            continue
        if in_tags and in_fence and line.strip() == "```":
            insert_at = index
            break
    if insert_at is None:
        raise RuntimeError("Could not locate SCHEMA.md tag_taxonomy yaml block")
    lines[insert_at:insert_at] = [f"  - {tag}" for tag in missing]
    return missing


def update_schema(wiki_root: Path) -> dict[str, object]:
    schema_path = wiki_root / "SCHEMA.md"
    lines = read_text(schema_path).splitlines()
    category_added = insert_schema_category(lines)
    tags_added = insert_schema_tags(lines)
    schema_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"category_added": category_added, "tags_added": tags_added}


def section_bounds(lines: list[str], heading: str) -> tuple[int, int]:
    start = None
    for index, line in enumerate(lines):
        if line.strip() == f"## {heading}":
            start = index
            break
    if start is None:
        lines.extend(["", f"## {heading}", ""])
        start = len(lines) - 2
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return start, end


def entry_sort_key(line: str) -> str:
    match = re.match(r"- \[(.*?)\]", line)
    if match:
        return match.group(1).lower()
    return line.lower()


def update_index(wiki_root: Path, specs: tuple[LessonSpec, ...]) -> None:
    index_path = wiki_root / "index.md"
    lines = read_text(index_path).splitlines()
    entries_by_category: dict[str, list[str]] = {}
    target_paths = {spec.target_relative.as_posix() for spec in specs}
    new_entries = {
        spec.target_relative.as_posix(): f"- [{spec.title}]({spec.target_relative.as_posix()}) - {spec.summary}"
        for spec in specs
    }
    for category, heading in CATEGORY_HEADINGS.items():
        start, end = section_bounds(lines, heading)
        body = lines[start + 1 : end]
        kept: list[str] = []
        for line in body:
            if not line.startswith("- "):
                continue
            path_match = re.search(r"\]\(([^)]+)\)", line)
            if path_match and path_match.group(1) in target_paths:
                continue
            kept.append(line)
        additions = [new_entries[spec.target_relative.as_posix()] for spec in specs if category == "lessons"]
        entries_by_category[category] = sorted(kept + additions, key=entry_sort_key)
    output: list[str] = ["# Wiki Index", ""]
    total_pages = sum(len(entries) for entries in entries_by_category.values())
    output.append(f"> Content catalog. Last updated: {TODAY} | Total pages: {total_pages}")
    output.append("")
    for _category, heading in CATEGORY_HEADINGS.items():
        output.append(f"## {heading}")
        output.append("")
        output.extend(entries_by_category.get(_category, []))
        output.append("")
    index_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def append_log(wiki_root: Path, specs: tuple[LessonSpec, ...], result: dict[str, int], schema_result: dict[str, object]) -> None:
    log_path = wiki_root / "log.md"
    existing = read_text(log_path).rstrip()
    ids = ", ".join(spec.lesson_id for spec in specs)
    tags = ", ".join(schema_result["tags_added"]) if schema_result["tags_added"] else "none"
    category = "lessons" if schema_result["category_added"] else "none"
    entry = (
        f"\n\n## [{TODAY}] import | <workspace>/project/NECallKit docs/lessons seed set ({len(specs)} files)\n"
        "- Format: curated folder seed set\n"
        f"- Lesson IDs: {ids}\n"
        f"- Created: {result['created']} wiki pages\n"
        f"- Updated: {result['updated']} existing pages\n"
        "- Skipped: 0 files\n"
        f"- Raw: raw/imported/{BUNDLE_NAME}/ ({result['raw_created']} created, {result['raw_unchanged']} unchanged)\n"
        f"- Category additions to SCHEMA.md: {category}\n"
        f"- Tag additions to SCHEMA.md: {tags}\n"
    )
    log_path.write_text(existing + entry, encoding="utf-8")


def dry_run_plan(project_root: Path, wiki_root: Path, specs: tuple[LessonSpec, ...]) -> dict[str, object]:
    plan: list[dict[str, str]] = []
    for spec in specs:
        source = project_root / Path(spec.source_relative.as_posix())
        target = wiki_root / Path(spec.target_relative.as_posix())
        if not source.exists():
            action = "missing-source"
        elif target.exists():
            action = "update"
        else:
            action = "create"
        plan.append(
            {
                "id": spec.lesson_id,
                "source": spec.source_relative.as_posix(),
                "target": spec.target_relative.as_posix(),
                "type": "lessons",
                "title": spec.title,
                "action": action,
            }
        )
    return {
        "ok": all(item["action"] != "missing-source" for item in plan),
        "mode": "dry-run",
        "bundle": BUNDLE_NAME,
        "schema_changes": {
            "add_category": "lessons",
            "add_tags": list(PROPOSED_TAGS),
        },
        "summary": {
            "create": sum(1 for item in plan if item["action"] == "create"),
            "update": sum(1 for item in plan if item["action"] == "update"),
            "total": len(plan),
            "would_update_files_minimum": len(plan) + 3,
            "mass_update_confirmation_required": len(plan) + 3 >= 10,
        },
        "plan": plan,
    }


def execute_import(project_root: Path, wiki_root: Path, checkpoint_script: Path, specs: tuple[LessonSpec, ...], allow_dirty: bool) -> dict[str, object]:
    status = git_status_porcelain(wiki_root)
    if status and not allow_dirty:
        raise RuntimeError(f"Wiki working tree is dirty; refusing import:\n{status}")
    checkpoint(checkpoint_script, wiki_root, "lock", "--source", str(project_root / "docs" / "lessons"), "--format", "folder")
    try:
        checkpoint(
            checkpoint_script,
            wiki_root,
            "init",
            "--source",
            str(project_root / "docs" / "lessons"),
            "--format",
            "folder",
            "--total",
            str(len(specs)),
        )
        created = 0
        updated = 0
        raw_created = 0
        raw_unchanged = 0
        slug_by_id = {spec.lesson_id: spec.slug for spec in specs}
        for index, spec in enumerate(specs, start=1):
            source = project_root / Path(spec.source_relative.as_posix())
            if not source.exists():
                checkpoint(checkpoint_script, wiki_root, "error", "--file", spec.source_relative.as_posix(), "--message", "missing source")
                raise FileNotFoundError(source)
            raw_state = safe_copy_raw(project_root, wiki_root, spec)
            raw_created += 1 if raw_state == "created" else 0
            raw_unchanged += 1 if raw_state == "unchanged" else 0
            target = wiki_root / Path(spec.target_relative.as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            existed = target.exists()
            content = read_text(source)
            target.write_text(page_body(spec, source, content, slug_by_id), encoding="utf-8")
            created += 0 if existed else 1
            updated += 1 if existed else 0
            checkpoint(
                checkpoint_script,
                wiki_root,
                "update",
                "--processed",
                str(index),
                "--last-file",
                spec.source_relative.as_posix(),
            )
        schema_result = update_schema(wiki_root)
        update_index(wiki_root, specs)
        result = {
            "created": created,
            "updated": updated,
            "raw_created": raw_created,
            "raw_unchanged": raw_unchanged,
        }
        append_log(wiki_root, specs, result, schema_result)
        return {"result": result, "schema": schema_result}
    except Exception:
        checkpoint(checkpoint_script, wiki_root, "unlock")
        raise


def main() -> None:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    project_root = Path(args.project).resolve()
    checkpoint_script = Path(args.checkpoint_script).resolve()
    specs = build_specs(project_root, wiki_root, max(args.seed_limit, 0))
    plan = dry_run_plan(project_root, wiki_root, specs)
    if not plan["ok"]:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    if not args.execute:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    output = execute_import(project_root, wiki_root, checkpoint_script, specs, args.allow_dirty)
    commit_sha = None
    push_attempted = False
    if args.push:
        args.commit = True
    if args.commit:
        run_git(wiki_root, "add", ".")
        run_git(wiki_root, "commit", "-m", f"wiki-import: necallkit lessons seed set ({len(specs)} files)")
        commit_sha = run_git(wiki_root, "rev-parse", "--short", "HEAD").stdout.strip()
        checkpoint(checkpoint_script, wiki_root, "clear")
        checkpoint(checkpoint_script, wiki_root, "unlock")
        if args.push:
            push_attempted = True
            run_git(wiki_root, "push")
    else:
        checkpoint(checkpoint_script, wiki_root, "clear")
        checkpoint(checkpoint_script, wiki_root, "unlock")
    print(
        json.dumps(
            {
                "ok": True,
                "mode": "execute",
                "bundle": BUNDLE_NAME,
                **output,
                "commit": commit_sha,
                "push_attempted": push_attempted,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
