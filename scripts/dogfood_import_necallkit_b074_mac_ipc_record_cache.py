from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "necallkit-electron-mac-ipc-call-record-cache-2026-05-10"
TODAY = date.today().isoformat()

SOURCE_FILES: tuple[PurePosixPath, ...] = (
    PurePosixPath("docs/bugfix/B074-electron-mac-ipc-call-record-cache-reset/analysis.md"),
    PurePosixPath("docs/bugfix/B074-electron-mac-ipc-call-record-cache-reset/B074-electron-mac-ipc-call-record-cache-reset-test.md"),
)

NEW_BUG_PATH = PurePosixPath("bugs/electron-mac-ipc-empty-call-record-snapshot-cache-reset-2026-05-10.md")
PRIOR_MAC_IPC_BUG = "bugs/electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import NECallKit B074 mac IPC empty call record cache.")
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
    sources = raw_source_lines() + [f"  - {PRIOR_MAC_IPC_BUG}"]
    return frontmatter(
        "macOS Electron IPC 拓扑下空话单 snapshot 覆盖本地持久化缓存（B074）",
        "bugs",
        ("electron", "desktop", "callkit", "regression", "ipc", "compatibility", "call-record", "state-machine", "testing"),
        sources,
    ) + """# macOS Electron IPC 拓扑下空话单 snapshot 覆盖本地持久化缓存（B074）

## Summary

- B074 是 mac IPC topology 簇的第三个具体 case（前两个是 B066 IPC normalize cleared 信号、B070 setCallConfig facade 旁路）。
- 现象：macOS Electron demo 关闭再打开，已有话单记录的账号默认列表被清空。
- 根因：`subscribeCallRecords()` 订阅时 IPC runtime 立即派发当前 snapshot，初始空数组 `[]` 通过 `shell.setCallRecords([])` → `writeStoredCallRecords()` 把本地持久化 cache 也覆盖成空。
- 修复：renderer 引入 `applyMainSideCallRecordSnapshot()`，**`records.length === 0` 时只更新 adapterState、不调用会写持久化的 `setCallRecords([])`**。

## 命中 gate

只在 macOS Electron 24+ 主进程 IPC 拓扑下命中（renderer 通过 `ipc-callkit-runtime` 拿数据，main 进程是 native owner）。Windows in-renderer 拓扑命中概率低（renderer 直读 native，初始 snapshot 行为不同）。

## 行为差

| 时机 | 修复前 | 修复后 |
|------|--------|--------|
| 重启后 main-side 初始空 snapshot 推送 | `setCallRecords([])` → 写空 localStorage → 持久化丢失 | 只更新 adapterState，本地 cache 保留 |
| main-side 收到 IM history / message event 返回非空 records | 用 main-side records 更新（不变） | 用 main-side records 更新（不变） |
| logout / destroy / 切账号 | 走 `clearCallRecordsView()` / `resetAfterTeardown()`（不变） | 走同样路径（不变） |

## 三个语义边界

- **adapter 初始空 snapshot ≠ 清空持久化话单**：本次刻意不让空 snapshot 擦写 cache。
- **多账号串号保护**：`loadCachedCallRecords(accountId)` 仍按账号 key 读取；切账号时先加载目标账号 cache，空 snapshot 不会污染上一个账号的 key。
- **provider-local 话单边界保留**：`normalizeDefaultCallRecords()` 仍只允许默认 IM 来源，不混入 provider-local `onRecordSend`。

## 影响范围

| 层级 | 文件 | 影响 |
|------|------|------|
| Vue3 example renderer | `Electron/example-vue3/src/renderer/app.js` | `subscribeCallRecords` 回调改用 `applyMainSideCallRecordSnapshot` |
| React example renderer | `Electron/example-react/src/renderer/main.js` | `startCallRecordAdapter` 中读 main-side snapshot 时同样 |
| IPC runtime | `Electron/scripts/lib/ipc-callkit-runtime.js` | `subscribeCallRecords()` 立即派发空 snapshot 是合理 adapter 生命周期信号，不改 |

## 与 B070 / B066 的关联

`electron-macos-mainthread-native-owner-analysis-2026-05-08.md` §11.2 表格"example 直连 `runtime.sdk.*`"风险条目 + 类似 IPC 边界语义错位的样板已经在 B066/B070 出现。B074 把这一类风险扩展到**订阅 callback 初始 snapshot** 的语义错位：

| 簇成员 | IPC 语义错位类型 |
|--------|----------------|
| B066 | normalize 抹掉 cleared 字段（"显式 set undefined" → "absent"） |
| B070 | example 直连 sdk.setCallConfig（mac sdk=null → 静默失败） |
| B074 | subscribe 初始空 snapshot 被当作"清空信号"（adapter 生命周期 ≠ 业务清空） |

未来 mac IPC 拓扑下出现"打开 demo 后某状态被空 snapshot 误覆盖"——这是同类风险点。

## 验证

| ID | 命令 | 结果 |
|----|------|------|
| TC-B074-001 | `node --test Electron/example-vue3/test/ui-shell.test.js` | 48/48 |
| TC-B074-002 | `node --test Electron/example-react/test/ui-shell.test.js` | 40/40 |

新增用例：`vue3 IPC runtime initial empty call record snapshot preserves cached records` / `external setup with IPC runtime does not replace cached records with empty main snapshot`。

## Related wiki pages

- [[electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09]]
- [[electron-switch-wait-peer-and-stale-video-2026-05-09]]
- [[electron-call-record-provider-and-list-semantics]]
- [[002-electron-callkit-contracts-electron-web-unified-public-contract]]
"""


def update_existing_pages(wiki_root: Path) -> None:
    mac_ipc_bug = wiki_root / Path(PRIOR_MAC_IPC_BUG)
    text = update_frontmatter(read_text(mac_ipc_bug), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-10 后续 B074 mac IPC 空话单 cache 覆盖",
        f"""B074 是 mac IPC topology 簇的第三个具体 case：

- B066 抹掉 cleared 字段
- B070 example 直连 sdk facade 旁路
- B074 subscribe 初始空 snapshot 被当作"清空信号"

未来"mac 打开 demo 后某状态被空 snapshot 误覆盖"——同类风险点。详见 [[{NEW_BUG_PATH.stem}]]。""",
    )
    write_text(mac_ipc_bug, text)

    contract = wiki_root / "modules" / "002-electron-callkit-contracts-electron-web-unified-public-contract.md"
    text = update_frontmatter(read_text(contract), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-10 mac IPC subscribe 初始空 snapshot 语义（B074）",
        f"""mac IPC topology 下，IPC adapter `subscribeCallRecords()` 订阅时立即派发当前 snapshot 是合理的生命周期信号。renderer 不能把"adapter 当前 records 为 0"等同于"业务清空话单"。

`applyMainSideCallRecordSnapshot()` 模板：`records.length > 0` 才更新 UI/cache；空 snapshot 只更新 adapterState。

详见 [[{NEW_BUG_PATH.stem}]]。""",
    )
    write_text(contract, text)


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
    bug_entry = f"- [macOS Electron IPC 拓扑下空话单 snapshot 覆盖本地持久化缓存（B074）]({NEW_BUG_PATH.as_posix()}) - mac IPC 簇第三案；renderer 引入 applyMainSideCallRecordSnapshot 区分 adapter 生命周期空 snapshot 与业务清空。"
    if bug_entry not in text:
        text = text.replace("## Bugs\n\n", "## Bugs\n\n" + bug_entry + "\n", 1)
    write_text(index_path, text.rstrip() + "\n")


def append_log(wiki_root: Path, raw_created: int, raw_unchanged: int) -> None:
    log_path = wiki_root / "log.md"
    text = read_text(log_path).rstrip()
    marker = "import | <workspace>/project/NECallKit docs B074 mac IPC empty call record"
    if marker in text:
        return
    entry = f"""

## [{TODAY}] import | <workspace>/project/NECallKit docs B074 mac IPC empty call record snapshot cache reset (2 files)
- Format: curated folder batch
- Created: 1 wiki page
- Updated: 2 existing pages
- Raw: raw/imported/{BUNDLE_NAME}/ ({raw_created} created, {raw_unchanged} unchanged)
- Source group: B074 mac IPC adapter 初始空 snapshot 不再覆盖本地 cache；applyMainSideCallRecordSnapshot 模板
- Filed: [[electron-mac-ipc-empty-call-record-snapshot-cache-reset-2026-05-10]]
- Updated: [[electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09]], [[002-electron-callkit-contracts-electron-web-unified-public-contract]]
- Decision: ingest immediately because B074 is the third concrete mac IPC topology case (after B066 normalize / B070 facade). Pattern: subscribe 初始空 snapshot 被误读成"业务清空信号"。
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
        "updated": [PRIOR_MAC_IPC_BUG, "modules/002-electron-callkit-contracts-electron-web-unified-public-contract.md"],
    }


def main() -> int:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    project_root = Path(args.project).resolve()
    checkpoint_script = Path(args.checkpoint_script).resolve()
    validate_sources(project_root)
    plan = {"bundle": BUNDLE_NAME, "sources": [s.as_posix() for s in SOURCE_FILES], "new_pages": [NEW_BUG_PATH.as_posix()], "updates": 2}
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
