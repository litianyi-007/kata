from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "necallkit-offline-message-baseline-2026-05-11"
TODAY = date.today().isoformat()

SOURCE_FILES: tuple[PurePosixPath, ...] = (
    PurePosixPath("docs/2026-04-16-web-ios-singlecall-api-alignment.md"),
    PurePosixPath("specs/001-nim-v10-upgrade/spec.md"),
)

NEW_FEATURE_PATH = PurePosixPath("features/necallkit-offline-message-contract-and-electron-link-2026-05-11.md")
NEW_QUERY_PATH = PurePosixPath("queries/necallkit-offline-message-troubleshooting-query.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import NECallKit offline message baseline (enableOffline contract + Electron link).")
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


def feature_page() -> str:
    return frontmatter(
        "NECallKit 离线消息 contract 与 Electron 透传链路",
        "features",
        ("electron", "desktop", "web", "ios", "harmonyos", "callkit", "nim", "signaling", "bridge", "ipc", "architecture", "state-machine"),
        raw_source_lines(),
    ) + """# NECallKit 离线消息 contract 与 Electron 透传链路

## Summary

「离线消息」= 主叫端发起呼叫时被叫处于离线状态，信令经服务端 push queue 暂存，被叫上线后由数据同步触发 `onReceiveInvited`（若呼叫仍有效）。开关是 `enableOffline`，通过 `setCallConfig({enableOffline: true})` 设置，对所有平台（Web / iOS / HarmonyOS / Desktop / Electron）契约对齐。

Electron demo 入口在设置页面的「支持离线消息」勾选，默认 **`enableOffline: true`**。

## 产品 spec（NIM V10 upgrade User Story 6）

> 用户在离线状态下收到的呼叫邀请，在上线（数据同步完成）后能够正确处理：若呼叫仍有效则提示，若已被取消则忽略。
>
> Priority: P6

**Acceptance Scenarios**:

1. **Given** 被叫离线时主叫发起呼叫（未超时），**When** 被叫上线后数据同步完成，**Then** 被叫触发 `onReceiveInvited`（呼叫仍有效）
2. **Given** 被叫离线时主叫发起呼叫，主叫已取消，**When** 被叫上线后数据同步完成，**Then** 被叫不触发 `onReceiveInvited`

## 平台契约对齐（来源：2026-04-16 web/ios singlecall API alignment §2.6）

| 字段 | Web | iOS | HarmonyOS | Desktop | 结论 |
|------|-----|-----|-----------|---------|------|
| `enableOffline` | 支持 | 支持 | 支持 | 支持 | **对齐** |
| `enableSwitchVideoConfirm` | 支持 | 支持 | 支持 | 支持 | 对齐 |
| `enableSwitchAudioConfirm` | 支持 | 支持 | 支持 | 支持 | 对齐 |
| 设置方式 | 传对象 | 传对象 | 传 3 个布尔参数 | 传 `NECallBridgeConfigParam` | Web / iOS / Desktop 更接近 |

## Electron 透传链路（5 层）

```text
[设置页面 UI]                       Electron/example-*/src/renderer/HomeView.js
        |
        v emit('update:enableOffline', value)
[example renderer form]             app.js form.enableOffline (默认 true)
        |
        v syncCallConfig() → runtime.setCallConfig({...})
[runtime facade]                    packages/callkit-runtime-electron/src/runtime.ts setCallConfig
        |
        v IPC (mac main-side topology) 或 直连 sdk (Windows in-renderer)
[main process service / node-addon] Electron/scripts/lib/callkit-main-service.js + Electron/node-addon/src/addon.cc
        |
        v ne_call_bridge_set_call_config(handle, NECallBridgeConfigParam{enableOffline,...})
[desktop bridge → core]             desktop/bridge/src/ne_call_bridge.cpp → desktop/core/src/call_controller.cpp
        |
        v NIM V2NIMSignallingService.callConfig
[NIM V10 native]                    V2NIM SDK
```

## mac IPC topology 风险（B070 / B074 同源）

macOS Electron 24+ 主进程 IPC 拓扑下，renderer `runtime.sdk === null`，example 不能直连 `runtime.sdk.setCallConfig`。**必须**走 runtime-level facade（`runtime.setCallConfig`）→ IPC → main runtime → native。B070 已修这条路径，B074 修了 call records 的同类问题。

如果你在 macOS Electron 24+ packaged 下发现「设置页面勾选了离线消息但行为未生效」，第一嫌疑：

1. DevTools Console 跑 `await window.$callkit.getCallConfig()`，看 `enableOffline` 是否真的下发到 main runtime。若返回 default `false`，说明 facade 没走通——参考 [[electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09]]。
2. 跑 `process.env.NECALL_DESKTOP_BRIDGE_PATH`，确认主进程是否加载本仓库 source bridge（mac 在 renderer 里 `getBridgeDiagnostics()` 永远 null，这是拓扑差，不是 bug）。

详细 mac IPC 调试套路：参考 dogfood log `docs/dogfood-necallkit-mac-ipc-troubleshooting.md`（local）或 [[electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09]] §排查矩阵。

## Electron `reconnect()` 与 Web 语义差异（来源：F011-electron-web-api-reuse-map）

| 平台 | `reconnect()` 语义 |
|------|-------------------|
| Web | IM 断线重连后，调用 `reconnect()` 触发 **离线消息（信令）重新拉取**；内部走 `signalController.reconnect()` |
| Electron | 当前为 **diagnostics / bridge refresh 入口**，不做 IM 离线消息重拉 |

**含义**：Electron 不需要 demo 显式调 `reconnect()` 拉离线消息——native NIM V10 SDK 在网络恢复后由 `V2NIMSignallingService` 通过 `onOnlineEvent` / `onOfflineEvent` 自动派发。如果在 Electron 看到「上线后没收到离线呼叫邀请」，**不要**期望 demo 调 `reconnect()` 能解决，根因在 native event 派发链。

## NIM V10 信令分发机制

call-kit / desktop core 都通过 V10 统一事件分发处理所有信令事件（来源：`spec.md` FR-002）：

| 事件 | 触发时机 |
|------|---------|
| `onOnlineEvent` | 在线时收到信令（包括上线后服务端推送的离线信令）|
| `onOfflineEvent` | 离线缓存的信令在上线后批量分发 |
| `onMultiClientEvent` | 多端登录场景下其他端的操作回声 |

离线消息处理的可靠性保证来自这三个事件**叠加**：上线后 `onOnlineEvent` 派发仍有效的呼叫邀请；已取消的邀请不再派发。

## 排查 checklist（按平台优先级）

### 1. macOS Electron 24+ packaged

- `enableOffline` 是否真的下发到 main runtime？DevTools Console: `await window.$callkit.getCallConfig()`
- 是否命中 B070 同模式 facade 旁路？检查 example renderer 是否直连了 `runtime.sdk.setCallConfig`（B070 已修，应该走 `runtime.setCallConfig`）
- staged native 是否最新？`process.env.NECALL_DESKTOP_BRIDGE_PATH` 指向本仓库 `Electron/out/native/darwin-debug/libne_callkit.dylib`

### 2. Windows Electron

- in-renderer 拓扑下 `runtime.sdk` 非 null，`setCallConfig` 应直达 native
- 检查 `desktop/core` 的 `setCallConfig` 是否真的把 `enableOffline` 透传到 V2NIM SDK
- 检查 native log 中信令发送时是否带 offline flag

### 3. native / NIM 层

- V10 `V2NIMSignallingService.call` 是否携带 offline 配置？
- 服务端是否启用了 push queue（账户配置 / appKey 配置）？
- 被叫端 V10 `onOnlineEvent` 上线后是否真的派发了离线信令？

### 4. 跨平台对齐

- 4 平台同源问题：检查 `2026-04-16-web-ios-singlecall-api-alignment.md` §2.6 `NECallConfig` 对齐表，确认你看到的平台行为是否符合契约

## Related wiki pages

- [[electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09]] — mac IPC topology 设置项 facade 旁路
- [[electron-mac-ipc-empty-call-record-snapshot-cache-reset-2026-05-10]] — mac IPC 簇第三案
- [[002-electron-callkit-electron-nim-integration-draft]] — NIM 集成草案
- [[002-electron-callkit-contracts-electron-node-nim-boundary]] — node-nim 边界
- [[002-electron-callkit-electron-reference-alignment-nim-uikit-electron]] — NIM uikit 参考对齐
- [[electron-kicked-offline-logout-ipc-chain-2026-05-09]] — NIM V2 kick → logout（不是离线消息但同 NIM V10 事件链）
- [[necallkit-master-merge-back-preflight-f011-2026-05-11]] — F011 lane B desktop ABI（含 `reconnect` 语义差异）

## 待蒸馏（distillation slot — 排查产出后回填）

下面这些是当前 wiki 没覆盖、需要排查过程中确认 / 产出 durable docs 后回填的：

- [ ] 被叫离线时主叫发起呼叫的**完整时序**（主叫 → 服务端 push queue → 被叫上线 → `onOnlineEvent` → `onReceiveInvited`）
- [ ] `enableOffline=false` 时的行为：是主叫端跳过 push queue 直接报失败，还是允许信令但不缓存？
- [ ] Electron native（desktop/core）是否真的把 `enableOffline` 透传给 V2NIMSignallingService.call，还是只用作本地 gate？
- [ ] mac IPC 拓扑下 `enableOffline` 实际生效路径的真机抓证（B070 已修 setCallConfig facade，但 `enableOffline` 字段没单独验证过）
- [ ] 排查中如果发现新 bug，filed 回 wiki 走 §3.5 mid-investigation distillation gate
"""


def query_page() -> str:
    sources = [
        f"  - {NEW_FEATURE_PATH.as_posix()}",
        "  - bugs/electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09.md",
        "  - bugs/electron-mac-ipc-empty-call-record-snapshot-cache-reset-2026-05-10.md",
        "  - decisions/002-electron-callkit-electron-nim-integration-draft.md",
    ]
    return frontmatter(
        "NECallKit 离线消息排查 query",
        "queries",
        ("electron", "desktop", "callkit", "nim", "signaling", "regression", "ipc", "compatibility", "state-machine"),
        sources,
    ) + """# NECallKit 离线消息排查 query

## Question

NECallKit demo 设置页面勾选「支持离线消息」（`enableOffline`），实际表现不符合预期。先看哪些边界、链路和 mac IPC 拓扑风险？

## Answer Confidence

Medium, 0.62。

离线消息的 4 平台契约已对齐（4-16 alignment §2.6），NIM V10 spec 有明确的 User Story 6 acceptance scenarios。但 wiki **没有**专题的离线消息 bugfix 或排查记录——目前只有 B070 / B074 mac IPC 簇可作为同模式参照。排查过程中产出的新事实应回填 [[necallkit-offline-message-contract-and-electron-link-2026-05-11]] 的「待蒸馏」slot。

## First Classification

| Symptom | First branch |
|---|---|
| mac packaged 勾选设置但不生效，Windows 正常 | Check B070 同模式 facade 旁路；`runtime.sdk === null`；`syncCallConfig` 是否走 runtime.setCallConfig 而非 sdk |
| 被叫上线后没收到离线呼叫 | Check NIM V10 `onOnlineEvent` 派发链；不要期望 demo `reconnect()` 能拉（Electron `reconnect()` 不做这事，Web 才做） |
| 主叫端发起呼叫立即失败 | Check `setCallConfig` 是否真的下发 `enableOffline`；DevTools Console `await window.$callkit.getCallConfig()` |
| 被叫上线后收到已取消的呼叫 | Check 服务端 push queue 的取消传播；本地 `onReceiveInvited` 处理应该有 callStatus guard（L005）|
| 跨平台行为不一致 | Check 4-16 alignment §2.6 `NECallConfig`；HarmonyOS 是 3 个 boolean 参数不是对象 |

## Decision tree（按平台）

### macOS Electron 24+ packaged

1. `await window.$callkit.getCallConfig()` 看 `enableOffline` 是不是 demo 设置的值
2. 若不是 → IPC facade 旁路嫌疑（B070 同模式）
3. `process.env.NECALL_DESKTOP_BRIDGE_PATH` 验证主进程加载本仓库 source bridge
4. 主进程 stdout 看 `[runtime-electron]` 日志或 `setCallConfig` 调用
5. 真机验证：被叫离线 → 主叫呼叫 → 被叫上线，看 `onReceiveInvited` 是否触发

### Windows Electron

1. in-renderer 拓扑下 `runtime.sdk` 非 null；`setCallConfig` 应直达 native
2. `desktop/core` 的 `setCallConfig` 是否透传 `enableOffline` 到 V2NIMSignallingService
3. native log 看信令发送时 offline flag

### V10 NIM 事件链

1. `onOnlineEvent` / `onOfflineEvent` / `onMultiClientEvent` 是 V10 统一事件分发（FR-002）
2. 离线信令的派发**靠 native NIM SDK 自动**，demo 不需要 `reconnect()`
3. Web `reconnect()` 才显式拉离线信令；Electron `reconnect()` 是 diagnostics/bridge refresh

## 不要做

- ❌ 不要在 Electron 期望 demo 调 `reconnect()` 能拉离线消息（语义差异，F011 reuse-map 已记录）
- ❌ 不要把 mac packaged 行为外推到 Windows（拓扑差）
- ❌ 不要直接读 V1 NIM 登录态作 fallback（V2-only 约束）

## Verification Matrix（建议）

```text
# macOS Electron 24+ packaged：DevTools Console
window.$callkit.sdk                              # 期望 null（mac IPC topology）
await window.$callkit.getCallConfig()            # 期望含 enableOffline 字段，值为设置页面勾选状态
process.env.NECALL_DESKTOP_BRIDGE_PATH           # 期望指向本仓库 darwin-debug/libne_callkit.dylib

# 真机：A 设备主叫，B 设备被叫
# 1. B 设备断网（模拟离线）
# 2. A 主叫发起呼叫（enableOffline=true）→ 等几秒
# 3. B 设备重连
# 4. 期望 B 触发 onReceiveInvited（呼叫仍有效时）
# 5. 若 A 在 B 重连前取消，期望 B 不触发 onReceiveInvited
```

## Ingest Guidance

排查过程中如果发现：

- mac IPC 拓扑下 `enableOffline` 实际不生效 → file 进 [[necallkit-offline-message-contract-and-electron-link-2026-05-11]] 待蒸馏 slot，bug 单独建 page
- native 层 `enableOffline` 透传 V2NIM 失败 → file 进同上，desktop/core 改动须 source bridge 验证
- Electron `reconnect()` 行为偏移（变成了离线消息拉取） → 检查是否破坏 F011 reuse-map 边界

按 knock-it-out §3.5 mid-investigation distillation gate，**不要等修完才回填 wiki**——排查过程中 user 确认的事实立即蒸馏。

## Sources Used

- [[necallkit-offline-message-contract-and-electron-link-2026-05-11]]
- [[electron-mac-ipc-setcallconfig-facade-bypass-2026-05-09]]
- [[electron-mac-ipc-empty-call-record-snapshot-cache-reset-2026-05-10]]
- [[002-electron-callkit-electron-nim-integration-draft]]
"""


def update_existing_pages(wiki_root: Path) -> None:
    nim_page = wiki_root / "decisions" / "002-electron-callkit-electron-nim-integration-draft.md"
    text = update_frontmatter(read_text(nim_page), [f"  - {NEW_FEATURE_PATH.as_posix()}", f"  - {NEW_QUERY_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-11 离线消息 contract & Electron 透传",
        f"""离线消息 baseline 已蒸馏到 wiki：[[{NEW_FEATURE_PATH.stem}]] 覆盖 `enableOffline` 设置 → setCallConfig → IPC facade → native bridge → NIM V10 信令的 5 层透传，附 mac IPC topology 风险（B070 / B074 同源）和排查 checklist。排查 query: [[{NEW_QUERY_PATH.stem}]]。""",
    )
    write_text(nim_page, text)


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


def update_index(wiki_root: Path, created_feature: bool, created_query: bool) -> None:
    index_path = wiki_root / "index.md"
    text = read_text(index_path)
    increment = int(created_feature) + int(created_query)
    if increment:
        text = re.sub(r"Total pages: (\d+)", lambda m: f"Total pages: {int(m.group(1)) + increment}", text, count=1)
    feature_entry = f"- [NECallKit 离线消息 contract 与 Electron 透传链路]({NEW_FEATURE_PATH.as_posix()}) - enableOffline 设置 → setCallConfig → IPC facade → native bridge → NIM V10 信令的 5 层透传；mac IPC topology 风险（B070/B074 同源）+ Electron vs Web reconnect 语义差异 + 排查 checklist。"
    query_entry = f"- [NECallKit 离线消息排查 query]({NEW_QUERY_PATH.as_posix()}) - Query filed 2026-05-11 / 离线消息 demo 表现异常时的平台分类 + decision tree + verification matrix。"
    if feature_entry not in text:
        text = text.replace("## Features\n\n", "## Features\n\n" + feature_entry + "\n", 1)
    if query_entry not in text:
        text = text.replace("## Queries\n\n", "## Queries\n\n" + query_entry + "\n", 1)
    write_text(index_path, text.rstrip() + "\n")


def append_log(wiki_root: Path, raw_created: int, raw_unchanged: int) -> None:
    log_path = wiki_root / "log.md"
    text = read_text(log_path).rstrip()
    marker = "import | <workspace>/project/NECallKit docs offline message baseline"
    if marker in text:
        return
    entry = f"""

## [{TODAY}] import | <workspace>/project/NECallKit docs offline message baseline (2 files)
- Format: curated baseline batch (low-confidence wiki state → seed feature page)
- Created: 2 wiki pages (feature + query)
- Updated: 1 existing page
- Raw: raw/imported/{BUNDLE_NAME}/ ({raw_created} created, {raw_unchanged} unchanged)
- Source group: 2026-04-16 web/ios singlecall API alignment §2.6 NECallConfig + NIM V10 upgrade User Story 6 离线消息处理
- Filed: [[necallkit-offline-message-contract-and-electron-link-2026-05-11]], [[necallkit-offline-message-troubleshooting-query]]
- Updated: [[002-electron-callkit-electron-nim-integration-draft]]
- Decision: ingest now to give the user a wiki baseline before troubleshooting offline message issues. Wiki search returned body=0 for "离线消息 / offline message" queries; only B064 kicked-offline (different topic) and node-nim-boundary (too general) surfaced. The new feature page seeds the contract and links to B070/B074 mac IPC facade priors. Per knock-it-out §3.5, the troubleshooting query page also opens a distillation slot for the user's actual findings during repro.
"""
    write_text(log_path, text + entry)


def execute(wiki_root: Path, project_root: Path) -> dict[str, object]:
    raw_counts = {"created": 0, "unchanged": 0}
    for source in SOURCE_FILES:
        raw_counts[safe_copy_raw(project_root, wiki_root, source)] += 1
    feature_full = wiki_root / Path(NEW_FEATURE_PATH.as_posix())
    query_full = wiki_root / Path(NEW_QUERY_PATH.as_posix())
    created_feature = not feature_full.exists()
    created_query = not query_full.exists()
    write_text(feature_full, feature_page())
    write_text(query_full, query_page())
    update_existing_pages(wiki_root)
    update_index(wiki_root, created_feature, created_query)
    append_log(wiki_root, raw_counts["created"], raw_counts["unchanged"])
    return {
        "raw_created": raw_counts["created"],
        "raw_unchanged": raw_counts["unchanged"],
        "created": [str(NEW_FEATURE_PATH), str(NEW_QUERY_PATH)],
        "updated": ["decisions/002-electron-callkit-electron-nim-integration-draft.md"],
    }


def main() -> int:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    project_root = Path(args.project).resolve()
    checkpoint_script = Path(args.checkpoint_script).resolve()
    validate_sources(project_root)
    plan = {"bundle": BUNDLE_NAME, "sources": [s.as_posix() for s in SOURCE_FILES], "new_pages": [NEW_FEATURE_PATH.as_posix(), NEW_QUERY_PATH.as_posix()], "updates": 1}
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
