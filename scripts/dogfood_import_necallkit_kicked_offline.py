from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "necallkit-electron-kicked-offline-2026-05-09"
TODAY = date.today().isoformat()

SOURCE_FILES: tuple[PurePosixPath, ...] = (
    PurePosixPath("docs/bugfix/B064-electron-kicked-offline-logout/analysis.md"),
    PurePosixPath("docs/bugfix/B064-electron-kicked-offline-logout/B064-electron-kicked-offline-logout-test.md"),
)

NEW_BUG_PATH = PurePosixPath("bugs/electron-kicked-offline-logout-ipc-chain-2026-05-09.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import NECallKit B064 kicked-offline logout IPC chain.")
    parser.add_argument("--wiki", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--checkpoint-script",
        default=str(Path(__file__).resolve().parents[1] / "plugin" / "scripts" / "import_checkpoint.py"),
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    return parser.parse_args()


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
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
    completed = subprocess.run(
        [sys.executable, str(script), "--wiki", str(wiki_root), *args],
        text=True,
        capture_output=True,
        check=True,
    )
    if completed.stdout.strip():
        print(completed.stdout.strip())


def validate_sources(project_root: Path) -> None:
    missing = [source.as_posix() for source in SOURCE_FILES if not (project_root / Path(source.as_posix())).exists()]
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
        "Electron 被踢下线 IPC 链路与退登复用（B064）",
        "bugs",
        ("electron", "desktop", "nim", "callkit", "bridge", "signaling", "regression", "lifecycle", "state-machine", "ipc"),
        raw_source_lines(),
    ) + """# Electron 被踢下线 IPC 链路与退登复用（B064）

## Summary

- B064 修复 NIM V2 `onKickedOffline` 在 idle 状态下 native 已消费但没有跨层广播到 Electron 页面层的问题：account 在其他端登录后，桌面端停留假登录态，无法继续呼叫。
- 关键改动是把 kicked offline 从"通话终态"提升为"独立 generic bridge event"，覆盖 idle 和通话中两种状态。
- 引入 additive generic event `NE_CALL_BRIDGE_EVENT_KICKED_OFFLINE`，bridge ABI patch 从 `2.1.1` 升到 `2.1.2`（major/minor 不变）。
- example renderer 复用既有 `logoutRuntime()` 收口，在 idle/active 两种状态都能清外部 NIM session、清 remembered login、回登录页。

## Issue Matrix

| Layer | Pre-B064 | Post-B064 |
|-------|----------|-----------|
| desktop core `on_kicked_offline` | 仅在活跃通话状态 `FinalizeExternalTerminal(NE_CALL_END_REASON_KICKED, ...)`，idle 直接 return | 任何状态先广播 `NE_CALL_CORE_EVENT_KICKED_OFFLINE`；活跃通话仍保留原有终态收口 |
| desktop bridge | 没有 generic event 传出去 | 新增 `NE_CALL_BRIDGE_EVENT_KICKED_OFFLINE` payload（reason / reasonDesc / clientType / customClientType / timestampMs）|
| Electron node-addon | bridge event 无映射 | 映射为 JS 事件名 `kickedOffline` |
| SDK event mapper | onKickedOffline 已在事件列表（B064 之前的占位） | 既有 mapper 直接转发，无需改 |
| Electron runtime | 已有 `onKickedOffline` 状态收口 | 复用入口，写入 `state.kickedOfflineInfo` |
| Vue3 / React example | 无监听 | 监听 `kickedOfflineInfo` snapshot，触发 `logoutRuntime()` + 清 remembered login + 回登录页 |

## V2-only / Idle-vs-Active Rule

- 本次修复不引入 V1 登录态读取或 V1 login fallback——保持 V2-only 约束。
- idle 状态下 kick 现在是可观察事件，example 会回登录页。
- 通话中 kick 仍保留原有 `NE_CALL_END_REASON_KICKED` 通话终态，**同时**广播退出登录事件。
- React/Vue3 都有 in-flight / handled guard，避免重复 kick / 重复 snapshot 触发多次 logout。

## ABI 升级规则

| 字段 | 之前 | 之后 |
|------|------|------|
| major | 2 | 2 |
| minor | 1 | 1 |
| patch | 1 | 2 |

`NE_CALL_BRIDGE_EVENT_KICKED_OFFLINE` 是 additive generic event，不改既有 event ABI，因此只升 patch。Electron runtime 通过 `getAbiVersion()` 探测 patch 兼容性。

Windows source bridge 必须显式导出 `ne_call_core_emit_kicked_offline`，packaging gate 同步要求该导出。

## 验证矩阵

```text
cd Electron && node --test --test-name-pattern "kicked offline" \\
  example-vue3/test/ui-shell.test.js example-react/test/ui-shell.test.js
cd Electron && node --test sdk/test/event-alignment.test.js sdk/test/ne-call.test.js
cd Electron && node --test --test-concurrency=1 \\
  --test-name-pattern "kicked offline|node-addon maps kicked offline" \\
  scripts/test/native-addon-regressions.test.js
cd Electron && node --test scripts/test/bridge-required-symbols.test.js
node --test packages/callkit-runtime-electron/test/runtime-contract.test.ts \\
  packages/callkit-runtime-electron/test/video-switch-regression.test.ts
cd Electron && npm run build:native:source
dumpbin /exports Electron/out/native/win32-debug/ne_callkit.dll
```

构建产物里必须看到导出：`ne_call_core_emit_kicked_offline`、`ne_call_core_emit_rtc_raw`、`ne_call_bridge_get_abi_version`。
staged `manifest.json` 中 `bridgeStrategy=source`。
通过 staged addon 读取 `getAbiVersion()` 应输出 `{"major":2,"minor":1,"patch":2}`。

## 附带观察

- 单独用 staged addon 创建 bridge 后调用 `addon.destroy()`，本机环境可能在 `%LOCALAPPDATA%/NIM/log/CallKitCore` 触发 xkit 日志初始化 panic。这是 ABI 探测退出阶段的本机环境副作用，不影响 source bridge gate。建议后续独立排查日志目录权限/目录冲突兜底。

## Related wiki pages

- [[002-electron-callkit-contracts-electron-web-unified-public-contract]]
- [[002-electron-callkit-electron-uikit-callback-lifecycle-investigation-2026-04-27]]
- [[l005-信令事件处理回调同样需要入口状态守卫-被动通知的-callstatus-前置检查]]
"""


def update_existing_pages(wiki_root: Path) -> None:
    contract = wiki_root / "modules" / "002-electron-callkit-contracts-electron-web-unified-public-contract.md"
    text = update_frontmatter(read_text(contract), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-09 onKickedOffline IPC 链路（B064）",
        f"""B064 把 `onKickedOffline` 从"raw additive event"补完整为完整 IPC 链路：

- desktop core 任何状态都先广播 `NE_CALL_CORE_EVENT_KICKED_OFFLINE`，再视情况执行通话终态收口。
- desktop bridge 新增 `NE_CALL_BRIDGE_EVENT_KICKED_OFFLINE`（patch 升 `2.1.2`）。
- Electron node-addon 映射为 `kickedOffline` JS 事件，runtime 写入 `state.kickedOfflineInfo`。
- example renderer 监听 snapshot 后复用 `logoutRuntime()` + 清 remembered login + 回登录页。

详见 [[{NEW_BUG_PATH.stem}]]。""",
    )
    write_text(contract, text)

    callback = wiki_root / "bugs" / "002-electron-callkit-electron-uikit-callback-lifecycle-investigation-2026-04-27.md"
    text = update_frontmatter(read_text(callback), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-09 B064 onKickedOffline IPC 完整链路",
        f"""B064 之前 `onKickedOffline` 只是 callback 列表里的一个名字。修复后它走完整链路：core 广播 generic event → bridge `NE_CALL_BRIDGE_EVENT_KICKED_OFFLINE` → node-addon 映射 → runtime `state.kickedOfflineInfo` → example logout。详见 [[{NEW_BUG_PATH.stem}]]。""",
    )
    write_text(callback, text)

    lesson = wiki_root / "lessons" / "l005-信令事件处理回调同样需要入口状态守卫-被动通知的-callstatus-前置检查.md"
    text = update_frontmatter(read_text(lesson), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-09 B064 Addendum",
        f"""L005 强调"被动通知必须 callStatus 前置检查"——B064 是这条原则在 NIM V2 kick 上的延伸：

- idle 状态收到 kick：不能因 callStatus=idle 就 return，应该至少广播 generic event 让 example 走登出收口。
- 通话中 kick：保留 callStatus 守卫的原有 `NE_CALL_END_REASON_KICKED` 终态，并行广播 logout 事件。
- 重复 kick / 重复 snapshot：example 用 in-flight / handled guard 兜住，不让 logout 多次触发。

详见 [[{NEW_BUG_PATH.stem}]]。""",
    )
    write_text(lesson, text)


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
    bug_entry = f"- [Electron 被踢下线 IPC 链路与退登复用（B064）]({NEW_BUG_PATH.as_posix()}) - core/bridge/addon/runtime/example 五层 V2 kick → logout 完整链路，bridge ABI 升 2.1.2。"
    if bug_entry not in text:
        text = text.replace("## Bugs\n\n", "## Bugs\n\n" + bug_entry + "\n", 1)
    write_text(index_path, text.rstrip() + "\n")


def append_log(wiki_root: Path, raw_created: int, raw_unchanged: int) -> None:
    log_path = wiki_root / "log.md"
    text = read_text(log_path).rstrip()
    marker = "import | <workspace>/project/NECallKit docs B064 kicked offline IPC chain"
    if marker in text:
        return
    entry = f"""

## [{TODAY}] import | <workspace>/project/NECallKit docs B064 kicked offline IPC chain (2 files)
- Format: curated folder batch
- Created: 1 wiki page
- Updated: 3 existing pages
- Raw: raw/imported/{BUNDLE_NAME}/ ({raw_created} created, {raw_unchanged} unchanged)
- Source group: B064 NIM V2 kick → core/bridge/addon/runtime/example five-layer logout chain; bridge ABI patch 2.1.1 → 2.1.2
- Filed: [[electron-kicked-offline-logout-ipc-chain-2026-05-09]]
- Updated: [[002-electron-callkit-contracts-electron-web-unified-public-contract]], [[002-electron-callkit-electron-uikit-callback-lifecycle-investigation-2026-04-27]], [[l005-信令事件处理回调同样需要入口状态守卫-被动通知的-callstatus-前置检查]]
- Decision: ingest immediately because B064 turns onKickedOffline from a callback name into a full five-layer IPC chain with bridge ABI implication; old wiki pages only listed it as a raw additive event and would mislead future kick handling.
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
    return {
        "raw_created": raw_counts["created"],
        "raw_unchanged": raw_counts["unchanged"],
        "created": [str(NEW_BUG_PATH)],
        "updated": [
            "modules/002-electron-callkit-contracts-electron-web-unified-public-contract.md",
            "bugs/002-electron-callkit-electron-uikit-callback-lifecycle-investigation-2026-04-27.md",
            "lessons/l005-信令事件处理回调同样需要入口状态守卫-被动通知的-callstatus-前置检查.md",
        ],
    }


def main() -> int:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    project_root = Path(args.project).resolve()
    checkpoint_script = Path(args.checkpoint_script).resolve()
    validate_sources(project_root)
    plan = {
        "bundle": BUNDLE_NAME,
        "sources": [source.as_posix() for source in SOURCE_FILES],
        "new_pages": [NEW_BUG_PATH.as_posix()],
        "updates": 3,
    }
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
