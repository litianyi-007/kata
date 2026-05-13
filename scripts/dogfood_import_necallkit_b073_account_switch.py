from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "necallkit-electron-win-account-switch-crash-2026-05-10"
TODAY = date.today().isoformat()

SOURCE_FILES: tuple[PurePosixPath, ...] = (
    PurePosixPath("docs/bugfix/B073-electron-win-account-switch-crash/analysis.md"),
    PurePosixPath("docs/bugfix/B073-electron-win-account-switch-crash/B073-electron-win-account-switch-crash-test.md"),
)

NEW_BUG_PATH = PurePosixPath("bugs/electron-win-external-account-switch-crash-2026-05-10.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import NECallKit B073 Win external account switch crash.")
    parser.add_argument("--wiki", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--checkpoint-script", default=str(Path(__file__).resolve().parents[1] / "plugin" / "scripts" / "import_checkpoint.py"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    return parser.parse_args()


def read_text(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def raw_path(source: PurePosixPath) -> PurePosixPath:
    return PurePosixPath("raw") / "imported" / BUNDLE_NAME / source


def yaml_quote(value: str) -> str:
    return '"' + value.replace('"', "'") + '"'


def raw_source_lines() -> list[str]:
    return [f"  - {raw_path(source).as_posix()}" for source in SOURCE_FILES]


def run_git(wiki_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(wiki_root), *args], text=True, capture_output=True, check=check)


def git_status_porcelain(wiki_root: Path) -> str:
    return run_git(wiki_root, "status", "--porcelain", check=True).stdout.strip()


def checkpoint(script: Path, wiki_root: Path, *args: str) -> None:
    completed = subprocess.run([sys.executable, str(script), "--wiki", str(wiki_root), *args], text=True, capture_output=True, check=True)
    if completed.stdout.strip():
        print(completed.stdout.strip())


def validate_sources(project_root: Path) -> None:
    missing = [s.as_posix() for s in SOURCE_FILES if not (project_root / Path(s.as_posix())).exists()]
    if missing:
        raise FileNotFoundError("Missing source files:\n" + "\n".join(missing))


def safe_copy_raw(project_root: Path, wiki_root: Path, source: PurePosixPath) -> str:
    src = project_root / Path(source.as_posix())
    dst = wiki_root / Path(raw_path(source).as_posix())
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if src.read_bytes() == dst.read_bytes():
            return "unchanged"
        raise RuntimeError(f"Raw file differs and will not be overwritten: {dst}")
    shutil.copy2(src, dst)
    return "created"


def frontmatter(title: str, page_type: str, tags: tuple[str, ...], sources: list[str]) -> str:
    return f"""---
title: {yaml_quote(title)}
type: {page_type}
tags:
{chr(10).join(f"  - {tag}" for tag in tags)}
created: {TODAY}
updated: {TODAY}
published_at: {TODAY}
ingested_at: {TODAY}
sources:
{chr(10).join(sources)}
---

"""


def bug_page() -> str:
    return frontmatter(
        "Electron Windows external 账号切换登录 crash 与 stale runtime setup（B073）",
        "bugs",
        ("electron", "desktop", "nim", "callkit", "regression", "lifecycle", "state-machine", "compatibility"),
        raw_source_lines(),
    ) + """# Electron Windows external 账号切换登录 crash 与 stale runtime setup（B073）

## Summary

- B073 修复 Electron Windows external `node-nim` owner 链路下"账号1 logout → 账号2 login"出现 crash / 闪退的问题。
- 根因：external logout 优化路径 `teardownRuntime({ destroyNative: false, destroyExternalSession: false })` 保留了账号1的 `activeRuntimeSetupConfig` + native runtime；账号2 login 时**先**做 `externalSession.login(account2)` → **后**才 `runtime.destroy()` 清旧 runtime，等于"账号2 已通过 node-nim 登录后再去 destroy 旧 CallKit runtime"。Windows external 链路下 CallKit / node-nim 共享 native NIM runtime，destroy 拆掉刚恢复的账号2 native 登录态 → crash。
- 修复：在 external 登录前先做 stale runtime setup 检查；setup config 不一致时先静默 `runtime.destroy()`（不 logout / destroy external NIM session），再走账号2 external login + `runtime.setup`。

## 顺序对比

| 步骤 | 修复前（账号1 logout 后 login 账号2） | 修复后 |
|------|-------------------------------------|--------|
| 1. logout 账号1 | `teardownRuntime({ destroyNative:false, destroyExternalSession:false })`；`activeRuntimeSetupConfig` 保留 | 同左 |
| 2. login 账号2 入口 | 直接 `externalSession.login(account2)` | **先**检查 stale runtime setup config 不一致 → 静默 `runtime.destroy()`（不 logout NIM）|
| 3. 中间 | — | external `node-nim` login(account2) |
| 4. ensureRuntimeSetup(account2) | 发现 setup config 不一致 → `runtime.destroy()` ← **此时 account2 已 native 登录，destroy 拆掉登录态 → crash** | `runtime.setup(account2)`（旧 runtime 已干净，无 race）|

## 三态保留

| 场景 | 行为 |
|------|------|
| 同账号 rapid logout / re-login | 旧 setup config = 新 setup config → 保持快速优化，不 destroy native |
| 异账号切换 | setup config 不一致 → 先 destroy 旧 runtime 再 login，避免危险顺序 |
| `activeRuntimeSetupConfig` 为空 | 保持现状 |

## 影响范围

| 文件 | 说明 |
|------|------|
| `Electron/example-vue3/src/renderer/app.js` | external 登录前先清理不匹配 stale runtime setup |
| `Electron/example-react/src/renderer/main.js` | React controller 同步顺序 |
| `Electron/example-vue3/test/ui-shell.test.js` | 新增账号1退出后账号2登录顺序回归 |
| `Electron/example-react/test/ui-shell.test.js` | 新增 React controller 账号切换顺序回归 |

**不**触碰 managed login、不引入 V1 fallback、不改 native ABI / node-addon / SDK / desktop core，因此不需要 source bridge 构建作为本次代码验收。

## V2-only 约束保留

按既有 V2-only baseline，不读 V1 登录态，不做 V1 login fallback。这条 lesson 仍是 [[necallkit-agent-sdd-operating-contract]] 的核心边界。

## 验证

| ID | 命令 | 结果 |
|----|------|------|
| TC-B073-001 | `node --test Electron/example-vue3/test/ui-shell.test.js` | Vue3: 47 passed / 0 failed |
| TC-B073-002 | `node --test Electron/example-react/test/ui-shell.test.js` | React: 39 passed / 0 failed |

真机仍需在 Windows 上验证：账号1 logout → 账号2 login 不再 crash；同账号 rapid logout / re-login 不退化。

## Related wiki pages

- [[electron-kicked-offline-logout-ipc-chain-2026-05-09]]
- [[002-electron-callkit-electron-nim-integration-draft]]
- [[l005-信令事件处理回调同样需要入口状态守卫-被动通知的-callstatus-前置检查]]
"""


def update_existing_pages(wiki_root: Path) -> None:
    kicked_bug = wiki_root / "bugs" / "electron-kicked-offline-logout-ipc-chain-2026-05-09.md"
    text = update_frontmatter(read_text(kicked_bug), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-10 后续 B073 external 账号切换 crash",
        f"""B064 修了 idle/active kick 广播；B073 修了同链路另一个 race：external `node-nim` login 顺序导致账号2 native 登录态被旧 runtime destroy 拆掉。两者都强调 V2-only baseline 下 `node-nim` external session 与 CallKit native runtime 在 Windows 共享 NIM runtime 的边界——任何 destroy / logout 顺序都必须在 external login 之前完成。详见 [[{NEW_BUG_PATH.stem}]]。""",
    )
    write_text(kicked_bug, text)


def update_frontmatter(text: str, extra_sources: list[str]) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    fm = text[: end + 4]
    body = text[end + 4 :]
    fm = re.sub(r"updated:\s*\d{4}-\d{2}-\d{2}", f"updated: {TODAY}", fm, count=1)
    fm = re.sub(r"ingested_at:\s*\d{4}-\d{2}-\d{2}", f"ingested_at: {TODAY}", fm, count=1)
    for source in extra_sources:
        if source not in fm:
            fm = fm.replace("\n---", f"\n{source}\n---", 1)
    return fm + body


def upsert_section(text: str, heading: str, section: str) -> str:
    pattern = re.compile(rf"\n## {re.escape(heading)}\n.*?(?=\n## |\Z)", re.S)
    block = f"\n## {heading}\n\n{section.strip()}\n"
    if pattern.search(text):
        return pattern.sub(block, text)
    related = "\n## Related wiki pages"
    if related in text:
        return text.replace(related, block + related, 1)
    related2 = "\n## Related"
    if related2 in text:
        return text.replace(related2, block + related2, 1)
    return text.rstrip() + block + "\n"


def update_index(wiki_root: Path, created_bug: bool) -> None:
    index_path = wiki_root / "index.md"
    text = read_text(index_path)
    if created_bug:
        text = re.sub(r"Total pages: (\d+)", lambda m: f"Total pages: {int(m.group(1)) + 1}", text, count=1)
    bug_entry = f"- [Electron Windows external 账号切换登录 crash 与 stale runtime setup（B073）]({NEW_BUG_PATH.as_posix()}) - 账号1 logout 后 login 账号2 闪退；先 destroy 旧 runtime 再 external login 修正顺序。"
    if bug_entry not in text:
        text = text.replace("## Bugs\n\n", "## Bugs\n\n" + bug_entry + "\n", 1)
    write_text(index_path, text.rstrip() + "\n")


def append_log(wiki_root: Path, raw_created: int, raw_unchanged: int) -> None:
    log_path = wiki_root / "log.md"
    text = read_text(log_path).rstrip()
    marker = "import | <workspace>/project/NECallKit docs B073 Win external account switch crash"
    if marker in text:
        return
    entry = f"""

## [{TODAY}] import | <workspace>/project/NECallKit docs B073 Win external account switch crash (2 files)
- Format: curated folder batch
- Created: 1 wiki page
- Updated: 1 existing page
- Raw: raw/imported/{BUNDLE_NAME}/ ({raw_created} created, {raw_unchanged} unchanged)
- Source group: B073 异账号切换 crash；先 destroy 旧 runtime 再 external login；同账号 rapid 优化保留
- Filed: [[electron-win-external-account-switch-crash-2026-05-10]]
- Updated: [[electron-kicked-offline-logout-ipc-chain-2026-05-09]]
- Decision: ingest immediately because B073 暴露 V2-only external session + CallKit native runtime 共享 NIM 的边界 race；与 B064 同链路。
"""
    write_text(log_path, text + entry)


def execute(wiki_root: Path, project_root: Path) -> dict[str, object]:
    raw_counts = {"created": 0, "unchanged": 0}
    for source in SOURCE_FILES:
        raw_counts[safe_copy_raw(project_root, wiki_root, source)] += 1
    bug_full = wiki_root / Path(NEW_BUG_PATH.as_posix())
    created_bug = not bug_full.exists()
    write_text(bug_full, bug_page())
    update_existing_pages(wiki_root)
    update_index(wiki_root, created_bug)
    append_log(wiki_root, raw_counts["created"], raw_counts["unchanged"])
    return {"raw_created": raw_counts["created"], "raw_unchanged": raw_counts["unchanged"], "created": [str(NEW_BUG_PATH)], "updated": ["bugs/electron-kicked-offline-logout-ipc-chain-2026-05-09.md"]}


def main() -> int:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    project_root = Path(args.project).resolve()
    checkpoint_script = Path(args.checkpoint_script).resolve()
    validate_sources(project_root)
    plan = {"bundle": BUNDLE_NAME, "sources": [s.as_posix() for s in SOURCE_FILES], "new_pages": [NEW_BUG_PATH.as_posix()], "updates": 1}
    if not args.execute:
        print(plan)
        return 0
    if not args.allow_dirty:
        status = git_status_porcelain(wiki_root)
        if status:
            raise RuntimeError(f"Wiki git tree is dirty; commit/stash before import:\n{status}")
    checkpoint(checkpoint_script, wiki_root, "lock", "--source", str(project_root / "docs"), "--format", "markdown")
    try:
        checkpoint(checkpoint_script, wiki_root, "init", "--source", str(project_root / "docs"), "--format", "markdown", "--total", str(len(SOURCE_FILES)))
        result = execute(wiki_root, project_root)
        checkpoint(checkpoint_script, wiki_root, "update", "--processed", str(len(SOURCE_FILES)), "--last-file", SOURCE_FILES[-1].as_posix())
        print(result)
        return 0
    finally:
        checkpoint(checkpoint_script, wiki_root, "unlock")


if __name__ == "__main__":
    raise SystemExit(main())
