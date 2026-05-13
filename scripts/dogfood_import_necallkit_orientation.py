from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "necallkit-orientation-guides"
TODAY = date.today().isoformat()

CATEGORY_HEADINGS = {
    "platforms": "Platforms",
    "modules": "Modules",
    "features": "Features",
    "bugs": "Bugs",
    "decisions": "Decisions",
    "queries": "Queries",
}


@dataclass(frozen=True)
class ImportSpec:
    source_relative: PurePosixPath
    target_relative: PurePosixPath
    title: str
    page_type: str
    tags: tuple[str, ...]
    summary: str
    related: tuple[str, ...]

    @property
    def raw_relative(self) -> PurePosixPath:
        return PurePosixPath("raw") / "imported" / BUNDLE_NAME / self.source_relative

    @property
    def slug(self) -> str:
        return self.target_relative.stem


IMPORT_SPECS: tuple[ImportSpec, ...] = (
    ImportSpec(
        source_relative=PurePosixPath("README.md"),
        target_relative=PurePosixPath("platforms/necallkit-platform-matrix-release-entry.md"),
        title="NECallKit 平台矩阵与发布入口",
        page_type="platforms",
        tags=(
            "android",
            "ios",
            "flutter",
            "electron",
            "desktop",
            "web",
            "miniprogram",
            "harmonyos",
            "uniapp",
            "rtc",
            "callkit",
            "calluikit",
            "nim",
            "architecture",
        ),
        summary="仓库级平台矩阵、目录入口、统一出包平台、各端打包验证与发布路径。",
        related=(
            "necallkit-architecture-overview",
            "necallkit-docs-index",
            "002-electron-callkit-electron-web-reuse-upgrade-positioning-query",
            "002-electron-callkit-example-contract-boundary-query",
        ),
    ),
    ImportSpec(
        source_relative=PurePosixPath("ARCHITECTURE.md"),
        target_relative=PurePosixPath("modules/necallkit-architecture-overview.md"),
        title="NECallKit 多平台架构与 Web/Electron 稳定边界",
        page_type="modules",
        tags=("architecture", "android", "ios", "flutter", "electron", "desktop", "web", "rtc", "callkit", "nim"),
        summary="仓库长期架构事实、平台分层、Web/Electron shared 真相源和正式交付边界。",
        related=(
            "necallkit-platform-matrix-release-entry",
            "002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20",
            "002-electron-callkit-electron-web-reuse-upgrade-positioning-query",
            "002-electron-callkit-example-contract-boundary-query",
            "002-electron-callkit-contracts-electron-node-nim-boundary",
        ),
    ),
    ImportSpec(
        source_relative=PurePosixPath("AGENTS.md"),
        target_relative=PurePosixPath("decisions/necallkit-agent-sdd-operating-contract.md"),
        title="NECallKit Agent 与 SDD 操作规范",
        page_type="decisions",
        tags=("architecture", "testing", "callkit"),
        summary="AI agent 在 NECallKit 中的分层加载、SDD、验收、代码规范、Git 与语言约定。",
        related=(
            "necallkit-docs-index",
            "necallkit-feature-bug-tracker",
            "necallkit-current-task-list",
            "002-electron-callkit-electron-web-reuse-upgrade-positioning-query",
        ),
    ),
    ImportSpec(
        source_relative=PurePosixPath("TASKS.md"),
        target_relative=PurePosixPath("decisions/necallkit-current-task-list.md"),
        title="NECallKit 当前任务清单",
        page_type="decisions",
        tags=("electron", "web", "regression", "testing", "callkit"),
        summary="当前分支任务、执行状态、验收入口和待收口事项。",
        related=(
            "necallkit-agent-sdd-operating-contract",
            "necallkit-feature-bug-tracker",
            "002-electron-callkit-electron-web-reuse-upgrade-positioning-query",
            "002-electron-callkit-example-contract-boundary-query",
        ),
    ),
    ImportSpec(
        source_relative=PurePosixPath("TRACKER.md"),
        target_relative=PurePosixPath("decisions/necallkit-feature-bug-tracker.md"),
        title="NECallKit Feature 与 Bug Tracker",
        page_type="decisions",
        tags=("electron", "web", "regression", "testing", "callkit"),
        summary="Feature、bug 与高风险 lane 的仓库级追踪入口。",
        related=(
            "necallkit-current-task-list",
            "necallkit-docs-index",
            "002-electron-callkit-example-contract-boundary-query",
        ),
    ),
    ImportSpec(
        source_relative=PurePosixPath("docs/INDEX.md"),
        target_relative=PurePosixPath("modules/necallkit-docs-index.md"),
        title="NECallKit docs 索引",
        page_type="modules",
        tags=("architecture", "testing", "regression", "callkit"),
        summary="docs/ 下 lessons、bugfix、features、guides、plans、archive 的人工维护索引。",
        related=(
            "necallkit-agent-sdd-operating-contract",
            "necallkit-feature-bug-tracker",
            "002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20",
            "002-electron-callkit-electron-web-reuse-development-quick-reference-2026-04-20",
        ),
    ),
    ImportSpec(
        source_relative=PurePosixPath("docs/guides/electron-merge-impact-baseline.md"),
        target_relative=PurePosixPath("modules/necallkit-docs-guides-electron-merge-impact-baseline.md"),
        title="Electron 合并影响接口基线",
        page_type="modules",
        tags=("electron", "desktop", "web", "bridge", "architecture", "compatibility", "callkit"),
        summary="Electron 合并审查前用于判断 desktop 导出面、Web reuse 共享接口与真实依赖的基线。",
        related=(
            "necallkit-architecture-overview",
            "necallkit-docs-guides-electron-flutter-merge-review-checklist",
            "002-electron-callkit-contracts-electron-node-nim-boundary",
            "002-electron-callkit-example-contract-boundary-query",
        ),
    ),
    ImportSpec(
        source_relative=PurePosixPath("docs/guides/electron-flutter-merge-review-checklist.md"),
        target_relative=PurePosixPath("decisions/necallkit-docs-guides-electron-flutter-merge-review-checklist.md"),
        title="Electron 接入 Flutter/Desktop 合并审查清单",
        page_type="decisions",
        tags=("electron", "desktop", "flutter", "bridge", "regression", "testing", "compatibility", "callkit"),
        summary="Electron 接入 Flutter/Desktop 相关合并时的审查步骤、风险点与结论口径。",
        related=(
            "necallkit-docs-guides-electron-merge-impact-baseline",
            "necallkit-current-task-list",
            "002-electron-callkit-electron-web-reuse-upgrade-positioning-query",
            "002-electron-callkit-example-contract-boundary-query",
        ),
    ),
    ImportSpec(
        source_relative=PurePosixPath("docs/guides/electron-web-reuse-development-handbook.md"),
        target_relative=PurePosixPath("features/002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20.md"),
        title="Web / Electron Reuse 开发工作手册",
        page_type="features",
        tags=("electron", "web", "desktop", "bridge", "architecture", "compatibility", "callkit", "nim", "rtc"),
        summary="reuse 架构下优先通过 packages/ shared 真相源开发，让 Web/Electron 共享语义保持一处维护。",
        related=(
            "necallkit-architecture-overview",
            "002-electron-callkit-electron-web-reuse-development-quick-reference-2026-04-20",
            "002-electron-callkit-electron-web-reuse-upgrade-positioning-query",
            "002-electron-callkit-example-contract-boundary-query",
            "002-electron-callkit-contracts-electron-web-example-platform-baseline",
        ),
    ),
    ImportSpec(
        source_relative=PurePosixPath("docs/guides/electron-web-reuse-development-quick-reference.md"),
        target_relative=PurePosixPath("features/002-electron-callkit-electron-web-reuse-development-quick-reference-2026-04-20.md"),
        title="Web / Electron Reuse 开发落点速查表",
        page_type="features",
        tags=("electron", "web", "desktop", "bridge", "architecture", "compatibility", "callkit", "nim", "rtc"),
        summary="用最短路径判断 Web/Electron reuse 改动应该落在 shared、runtime、wrapper 还是 example 宿主层。",
        related=(
            "necallkit-architecture-overview",
            "002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20",
            "002-electron-callkit-electron-web-reuse-upgrade-positioning-query",
            "002-electron-callkit-example-contract-boundary-query",
            "002-electron-callkit-electron-web-release-delivery-guide",
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dogfood importer for the NECallKit orientation/guides batch."
    )
    parser.add_argument("--wiki", required=True, help="NECallKit wiki root")
    parser.add_argument("--project", required=True, help="NECallKit project root")
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


def extract_published_at(path: Path, content: str) -> str:
    patterns = (
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{4})[./年 -]+(\d{1,2})[./月 -]+(\d{1,2})",
    )
    for line in content.splitlines()[:50]:
        for pattern in patterns:
            match = re.search(pattern, line)
            if not match:
                continue
            if len(match.groups()) == 1:
                return match.group(1)
            year, month, day = match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()


def page_body(spec: ImportSpec, source_path: Path, content: str) -> str:
    tags_block = "\n".join(f"  - {tag}" for tag in spec.tags)
    related_block = "\n".join(f"- [[{slug}]]" for slug in spec.related)
    if related_block:
        related_section = f"## Related wiki pages\n\n{related_block}\n\n"
    else:
        related_section = ""
    return (
        "---\n"
        f"title: {yaml_quote(spec.title)}\n"
        f"type: {spec.page_type}\n"
        f"tags:\n{tags_block}\n"
        f"created: {TODAY}\n"
        f"updated: {TODAY}\n"
        f"published_at: {extract_published_at(source_path, content)}\n"
        f"ingested_at: {TODAY}\n"
        "sources:\n"
        f"  - {spec.raw_relative.as_posix()}\n"
        "---\n\n"
        f"# {spec.title}\n\n"
        "## Summary\n\n"
        f"- {spec.summary}\n"
        f"- Source bundle: `{BUNDLE_NAME}`\n"
        f"- Original path: `{spec.source_relative.as_posix()}`\n\n"
        f"{related_section}"
        "## Imported Content\n\n"
        f"{content.rstrip()}\n"
    )


def run_git(wiki_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=wiki_root,
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


def safe_copy_raw(project_root: Path, wiki_root: Path, spec: ImportSpec) -> str:
    source = project_root / Path(spec.source_relative.as_posix())
    destination = wiki_root / Path(spec.raw_relative.as_posix())
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if source.read_bytes() == destination.read_bytes():
            return "unchanged"
        raise RuntimeError(f"Raw file differs and will not be overwritten: {destination}")
    shutil.copy2(source, destination)
    return "created"


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


def update_index(wiki_root: Path, specs: tuple[ImportSpec, ...]) -> None:
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
        additions = [
            new_entries[spec.target_relative.as_posix()]
            for spec in specs
            if spec.page_type == category
        ]
        entries_by_category[category] = sorted(kept + additions, key=entry_sort_key)

    output: list[str] = ["# Wiki Index", ""]
    total_pages = sum(len(entries) for entries in entries_by_category.values())
    output.append(f"> Content catalog. Last updated: {TODAY} | Total pages: {total_pages}")
    output.append("")
    for category, heading in CATEGORY_HEADINGS.items():
        output.append(f"## {heading}")
        output.append("")
        output.extend(entries_by_category.get(category, []))
        output.append("")
    index_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def append_log(wiki_root: Path, created: int, updated: int, raw_created: int, raw_unchanged: int) -> None:
    log_path = wiki_root / "log.md"
    existing = read_text(log_path).rstrip()
    entry = (
        f"\n\n## [{TODAY}] import | <workspace>/project/NECallKit orientation + docs/guides (10 files)\n"
        "- Format: curated folder batch\n"
        f"- Created: {created} wiki pages\n"
        f"- Updated: {updated} existing pages (deduplicated guide stubs)\n"
        "- Skipped: 0 files\n"
        f"- Raw: raw/imported/{BUNDLE_NAME}/ ({raw_created} created, {raw_unchanged} unchanged)\n"
        "- Tag additions to SCHEMA.md: none\n"
    )
    log_path.write_text(existing + entry, encoding="utf-8")


def build_plan(project_root: Path, wiki_root: Path) -> list[dict[str, str]]:
    plan: list[dict[str, str]] = []
    for spec in IMPORT_SPECS:
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
                "source": spec.source_relative.as_posix(),
                "target": spec.target_relative.as_posix(),
                "type": spec.page_type,
                "title": spec.title,
                "action": action,
            }
        )
    return plan


def execute_import(project_root: Path, wiki_root: Path, checkpoint_script: Path, allow_dirty: bool) -> dict[str, int]:
    status = git_status_porcelain(wiki_root)
    if status and not allow_dirty:
        raise RuntimeError(f"Wiki working tree is dirty; refusing import:\n{status}")

    checkpoint(checkpoint_script, wiki_root, "lock", "--source", str(project_root), "--format", "folder")
    try:
        checkpoint(
            checkpoint_script,
            wiki_root,
            "init",
            "--source",
            str(project_root),
            "--format",
            "folder",
            "--total",
            str(len(IMPORT_SPECS)),
        )

        created = 0
        updated = 0
        raw_created = 0
        raw_unchanged = 0
        for index, spec in enumerate(IMPORT_SPECS, start=1):
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
            target.write_text(page_body(spec, source, content), encoding="utf-8")
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

        update_index(wiki_root, IMPORT_SPECS)
        append_log(wiki_root, created, updated, raw_created, raw_unchanged)
        return {
            "created": created,
            "updated": updated,
            "raw_created": raw_created,
            "raw_unchanged": raw_unchanged,
        }
    except Exception:
        checkpoint(checkpoint_script, wiki_root, "unlock")
        raise


def main() -> None:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    project_root = Path(args.project).resolve()
    checkpoint_script = Path(args.checkpoint_script).resolve()

    plan = build_plan(project_root, wiki_root)
    missing = [item for item in plan if item["action"] == "missing-source"]
    if missing:
        print(json.dumps({"ok": False, "missing": missing}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    if not args.execute:
        print(
            json.dumps(
                {
                    "ok": True,
                    "mode": "dry-run",
                    "bundle": BUNDLE_NAME,
                    "summary": {
                        "create": sum(1 for item in plan if item["action"] == "create"),
                        "update": sum(1 for item in plan if item["action"] == "update"),
                        "total": len(plan),
                    },
                    "plan": plan,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    result = execute_import(project_root, wiki_root, checkpoint_script, args.allow_dirty)

    commit_sha = None
    push_attempted = False
    if args.push:
        args.commit = True
    if args.commit:
        run_git(wiki_root, "add", ".")
        run_git(wiki_root, "commit", "-m", "wiki-import: necallkit orientation guides (10 files)")
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
                "result": result,
                "commit": commit_sha,
                "push_attempted": push_attempted,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
