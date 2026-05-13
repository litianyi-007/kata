from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "necallkit-electron-mac-ipc-callconfig-2026-05-09"
TODAY = date.today().isoformat()

SOURCE_FILES: tuple[PurePosixPath, ...] = (
    PurePosixPath("docs/bugfix/B070-electron-mac-ipc-call-config-bypass/analysis.md"),
    PurePosixPath("docs/bugfix/B070-electron-mac-ipc-call-config-bypass/B070-electron-mac-ipc-call-config-bypass-test.md"),
)

NEW_BUG_PATH = PurePosixPath("bugs/electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09.md")
PRIOR_CLUSTER_BUG = "bugs/electron-switch-wait-peer-and-stale-video-2026-05-09.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import NECallKit B070 macOS IPC setCallConfig facade bypass.")
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
    sources = raw_source_lines() + [f"  - {PRIOR_CLUSTER_BUG}"]
    return frontmatter(
        "macOS Electron 主进程 IPC 拓扑下 setCallConfig facade 旁路（B070）",
        "bugs",
        ("electron", "desktop", "callkit", "bridge", "regression", "state-machine", "ipc", "compatibility", "testing"),
        sources,
    ) + """# macOS Electron 主进程 IPC 拓扑下 setCallConfig facade 旁路（B070）

## Summary

- B070 修复 macOS 打包应用下勾选"音视频切换二次确认"开关无效的问题：example renderer 直连 `runtime.sdk.setCallConfig`，但 macOS Electron 24+ 拓扑下 renderer 拿到的是 IPC runtime（`runtime.sdk === null`），设置永远没到 main 进程的 native runtime。
- Windows 不命中 `darwin && Electron >= 24` gate，renderer 仍是直连 native 的 in-renderer runtime，行为正常。
- 这是 mac IPC topology 第二个落地的 facade 缺口（第一个是 B066 的 IPC normalize cleared 信号），来自项目 spec `electron-macos-mainthread-native-owner-analysis-2026-05-08.md` §11.2 表格"example 直连 `runtime.sdk.*`"风险条目。
- 修复路径是 5 处一致改造：runtime facade、main service IPC dispatch、IPC runtime adapter method、example renderer 优先 facade fallback sdk、`createRuntimeState` 不预置扩展字段（与 B066 normalize 语义对齐）。

## 命中 gate

只在以下条件同时满足时命中：

```text
process.platform === 'darwin'
process.versions.electron >= 24
```

Windows 路径下 renderer 是直连 native 的 in-renderer runtime，`runtime.sdk` 不为 null，老的"directly call sdk"链路兼容。

## 行为差

| 步骤 | 修复前 | 修复后 |
|------|--------|--------|
| 用户勾选 confirm 选项 | 调 `syncCallConfig()` | 调 `syncCallConfig()` |
| `runtime.setCallConfig` 是否存在 | 不存在 | 存在 → 走 IPC 到 main runtime → native |
| `runtime.sdk` | `null`（IPC 拓扑） | `null`（不变） |
| native `getCallConfig()` | 默认值 `{enableSwitchVideoConfirm: false, ...}` | `{enableSwitchVideoConfirm: true, ...}` |
| 收到对端 switch control(state=1) | `switch_control_auto_agree` 直接 apply | 弹"权限请求"确认框 |

## 修复矩阵

| 层级 | 改动 |
|------|------|
| `packages/callkit-runtime-electron/src/runtime.ts` | 新增 runtime-level `setCallConfig(config)` / `getCallConfig()` facade，main 端 sdk 不为 null 时直连 native |
| `Electron/scripts/lib/callkit-main-service.js` | invoke dispatch 加入 `setCallConfig` / `getCallConfig` |
| `Electron/scripts/lib/ipc-callkit-runtime.js` | renderer IPC runtime 加 `setCallConfig` / `getCallConfig` 方法 |
| `Electron/example-vue3/src/renderer/app.js`、`Electron/example-react/src/renderer/main.js` | `syncCallConfig` / `syncCallTimeout` 优先 `runtime.setCallConfig` / `runtime.setTimeout`，fallback 才走 `runtime.sdk.*` |
| `packages/callkit-runtime-electron/src/runtime.ts` `createRuntimeState` | **去掉** `outgoingSwitchCallType` / `pendingSwitchCallType` 预置 undefined（与 B066 normalize 显式 hasOwnProperty 语义对齐） |

## 与 B066 / B065 的关系

- B066 修的是"扩展字段被清后 IPC 边界丢失 cleared 信号"：normalize 必须显式写 undefined + mergeState 必须 reset absent 字段。
- B070 修的是"扩展字段在初始 state 预置 undefined → normalize 后 snapshot 多 keys → callkit-domain MINIMAL contract test 失败"。
- 两者都是 mac IPC topology 的延伸，B066 / B070 的 normalize / initial state 修复必须配套生效。

## 同类风险条目

`Electron/example-*-renderer/*` 中其它直连 `runtime.sdk.*` 的方法都属于同类风险，目前已知：

- `syncDefaultCallRecordProvider` 调 `runtime.sdk.setCallRecordProvider`（macOS IPC 拓扑下 sdk=null，仍会静默 no-op）。

未来出现"macOS 打包后某项配置失效，Windows 正常"的现象，先排查这一类直连 sdk 的代码路径。

## 验证矩阵

```text
node --test packages/callkit-runtime-electron/test/runtime-contract.test.ts
node --test packages/callkit-runtime-electron/test/video-switch-regression.test.ts
node --test packages/callkit-react-core/test/call-view.test.js
node --test packages/callkit-vue3-core/test/call-view.test.js
node --test Electron/react-uikit/test/call-view.test.js Electron/vue3-uikit/test/call-view.test.js
node --test Electron/scripts/test/main-service.test.js  # IPC dispatch invariants
```

mac packaged 验证：

```js
// DevTools Console (mac packaged build)
window.$callkit.sdk         // 应为 null（IPC 拓扑）
await window.$callkit.getCallConfig()
// 应返回 {enableSwitchVideoConfirm, enableSwitchAudioConfirm, ...} 而非 undefined
```

## Related wiki pages

- [[electron-switch-wait-peer-and-stale-video-2026-05-09]]
- [[electron-switchcalltype-media-state-and-reject-semantics-2026-05-09]]
- [[002-electron-callkit-contracts-electron-web-unified-public-contract]]
- [[002-electron-callkit-electron-uikit-callback-lifecycle-investigation-2026-04-27]]
"""


def update_existing_pages(wiki_root: Path) -> None:
    cluster_bug = wiki_root / Path(PRIOR_CLUSTER_BUG)
    text = update_frontmatter(read_text(cluster_bug), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-09 后续 B070 mac IPC facade 旁路",
        f"""B066 修复 IPC normalize cleared 信号后，B070 暴露同一 mac IPC 拓扑下另一面：example renderer 直连 `runtime.sdk.setCallConfig`，sdk 为 null 时设置永远到不了 main runtime。

修复方式是 runtime + main service + IPC adapter + example renderer 四层一起加 `setCallConfig` / `getCallConfig` facade，并把 `createRuntimeState()` 中扩展字段的 undefined 预置去掉（与 B066 normalize 显式 hasOwnProperty 语义对齐）。

未来 macOS 打包后某项配置失效但 Windows 正常的问题，先排查 example renderer 是否直连 `runtime.sdk.*`。详见 [[{NEW_BUG_PATH.stem}]]。""",
    )
    write_text(cluster_bug, text)

    contract = wiki_root / "modules" / "002-electron-callkit-contracts-electron-web-unified-public-contract.md"
    text = update_frontmatter(read_text(contract), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-09 mac IPC topology setCallConfig facade（B070）",
        f"""macOS Electron 24+ 拓扑下 renderer 拿到的是 IPC runtime（`runtime.sdk === null`）。`setCallConfig` / `getCallConfig` / `setTimeout` 必须通过 runtime-level facade 走 IPC 到 main runtime，example 不能直连 `runtime.sdk.*`。

`createRuntimeState()` 不再预置扩展字段为 undefined，与 B066 normalize 显式 hasOwnProperty 语义对齐。

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
    bug_entry = f"- [macOS Electron 主进程 IPC 拓扑下 setCallConfig facade 旁路（B070）]({NEW_BUG_PATH.as_posix()}) - mac packaged 二次确认开关失效；example renderer 直连 sdk=null 必须改走 runtime-level facade。"
    if bug_entry not in text:
        text = text.replace("## Bugs\n\n", "## Bugs\n\n" + bug_entry + "\n", 1)
    write_text(index_path, text.rstrip() + "\n")


def append_log(wiki_root: Path, raw_created: int, raw_unchanged: int) -> None:
    log_path = wiki_root / "log.md"
    text = read_text(log_path).rstrip()
    marker = "import | <workspace>/project/NECallKit docs B070 mac IPC setCallConfig facade"
    if marker in text:
        return
    entry = f"""

## [{TODAY}] import | <workspace>/project/NECallKit docs B070 mac IPC setCallConfig facade (2 files)
- Format: curated folder batch
- Created: 1 wiki page
- Updated: 2 existing pages
- Raw: raw/imported/{BUNDLE_NAME}/ ({raw_created} created, {raw_unchanged} unchanged)
- Source group: B070 mac IPC topology setCallConfig/getCallConfig facade bypass; runtime + main-service + ipc-runtime + example renderer + createRuntimeState five-layer fix
- Filed: [[electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09]]
- Updated: [[electron-switch-wait-peer-and-stale-video-2026-05-09]], [[002-electron-callkit-contracts-electron-web-unified-public-contract]]
- Decision: ingest immediately because B070 is the second concrete case of mac IPC topology gap (after B066). Future "macOS packaged config silently no-op, Windows works" should land on this page first.
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
            PRIOR_CLUSTER_BUG,
            "modules/002-electron-callkit-contracts-electron-web-unified-public-contract.md",
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
        "updates": 2,
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
