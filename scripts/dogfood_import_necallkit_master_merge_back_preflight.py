from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "necallkit-master-merge-back-preflight-2026-05-11"
TODAY = date.today().isoformat()

SOURCE_FILES: tuple[PurePosixPath, ...] = (
    PurePosixPath("docs/prd/F011-master-low-coupling-sync/F011-master-low-coupling-sync.md"),
    PurePosixPath("docs/prd/F011-master-low-coupling-sync/F011-master-low-coupling-sync-tasks.md"),
    PurePosixPath("docs/prd/F011-master-low-coupling-sync/F011-master-low-coupling-sync-test.md"),
    PurePosixPath("docs/prd/F011-master-low-coupling-sync/F011-master-merge-back-plan.md"),
    PurePosixPath("docs/prd/F011-master-low-coupling-sync/F011-windows-dll-abi-gate-recovery.md"),
    PurePosixPath("docs/plans/2026-04-30-merge-back-conflict-resolution.md"),
    PurePosixPath("docs/plans/2026-04-30-nim-symbol-source-convergence-investigation.md"),
)

NEW_FEATURE_PATH = PurePosixPath("features/necallkit-master-merge-back-preflight-f011-2026-05-11.md")
NEW_DECISION_PATH = PurePosixPath("decisions/necallkit-master-merge-back-lanes-and-conflicts-2026-05-11.md")
NEW_QUERY_PATH = PurePosixPath("queries/necallkit-master-merge-back-preflight-query.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import NECallKit F011 master merge-back preflight cluster.")
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
        "F011 NECallKit 当前分支合回 master 预审特性",
        "features",
        ("electron", "desktop", "flutter", "android", "harmonyos", "callkit", "nim", "rtc", "bridge", "regression", "compatibility", "architecture"),
        raw_source_lines(),
    ) + """# F011 NECallKit 当前分支合回 master 预审特性

## Summary

F011 把"长期背离 master 的特化分支"拉回"可持续追 master、最终能 MR / rebase 回 master"。它不是一次性 rebase，是**持续追逐 master 行为结果 + 把当前分支增量做成可被 master 接纳的 contract** 的特性集。

- **来源分支基线**：当前分支从 `master@61087e93` 拉出，叠加了 Electron native / node-addon / sdk / UIKit 实现 + Electron & Web reuse 结构 + shared `packages/callkit-*` runtime/core + 大量 release / scripts / docs / example 资产。
- **目标分支**：`002-electron-callkit-reuse`（当前已演进为 `002-electron-callkit-reuse-enhance`）
- **master 参考工作树**：`~/Documents/Code/NECallKit-master`
- **状态**：Draft v1.1（2026-04-26）；F011 低耦合迁入已完成，5 个高风险 lane 已落地或保留交付 gate。

## 三大原则

1. **forward-sync**：master 上的新能力和修复继续迁入当前分支，不被结构卡死。
2. **merge-back**：当前分支的新增能力未来能被 master 接纳，不只能停留在私有结构。
3. **contract-first**：对外能力（API / 事件 / 状态 / UI 交互结果）落在 master 可接受的 contract 上，而不是依赖目录形态。

## 唯一冻结的功能例外

**Electron 群呼明确暂不支持**。其他降级必须进 tracker，不允许新增特例。

## 五大执行口径

| 原则 | 口径 |
|------|------|
| upstream-first | master 已验证的修复和交互闭环默认需要迁入或等效实现 |
| structure-adapted | 当前分支保留 shared packages / Electron host/runtime / workspace 结构差异 |
| contract-first | 对外 API / 事件 / 状态 / UI 交互结果必须能表达成 master 可接受的 contract |
| additive merge-back | 当前分支新增资产进入 master 时尽量 additive，不要求 master 先回退旧结构 |
| explicit exception | Electron 群呼是冻结功能例外；其他降级进 tracker |

## In Scope（F011 已迁入）

- Flutter desktop 上层对齐（`desktop_event_mapper.dart` 等）
- Flutter Android 低耦合原生修复（PlatformVideoView / CallKitUIHandler / FloatWindowService 等）
- HarmonyOS / Flutter OHOS 平台隔离改动
- Flutter Dart/UI 低耦合改动
- Flutter 发布与 desktop artifact lane

## Out of Scope（F011 不直接改）

- `desktop/bridge/*`、`desktop/core/src/call_controller.cpp`、`desktop/core/src/call_end_reason.cpp`
- `Electron/node-addon/*`、`Electron/sdk/*`
- `Web/*`

这些高风险边界不在 F011 低耦合迁入批次内，由 5 lane 高风险计划单独处理（详见 [[necallkit-master-merge-back-lanes-and-conflicts-2026-05-11]]）。

## 与 v1.6 dogfood / merge-back rehearsal 的关系

F011 已建立 dry-run 集成验证能力（Lane E）；2026-04-27 基于 `origin/master@8ada7413` 复跑后仍需处理上游冲突，Windows DLL gate 已过。最终 merge back 仍需人工 conflict resolution（参见 [[necallkit-master-merge-back-lanes-and-conflicts-2026-05-11]] §冲突清单）。

## Related wiki pages

- [[necallkit-master-merge-back-lanes-and-conflicts-2026-05-11]]
- [[necallkit-master-merge-back-preflight-query]]
- [[electron-web-api-reuse-and-merge-back-switch-contract]]
- [[necallkit-docs-guides-electron-merge-impact-baseline]]
- [[002-electron-callkit-web-master-diff-assessment-2026-04-25]]
- [[necallkit-docs-guides-electron-flutter-merge-review-checklist]]
"""


def decision_page() -> str:
    return frontmatter(
        "F011 五 Lane 高风险合回 master 计划与冲突清单",
        "decisions",
        ("electron", "desktop", "flutter", "callkit", "nim", "rtc", "bridge", "regression", "compatibility", "architecture", "ipc"),
        raw_source_lines(),
    ) + """# F011 五 Lane 高风险合回 master 计划与冲突清单

## Summary

F011 主特性把低耦合迁入做完后，剩余高风险差异分成 5 个 lane（A/B/C/D/E）。本页是 lane 总览 + 当前状态 + Windows DLL ABI gate 修复 + Lane E 实测冲突清单 + NIM 符号源收敛调研结论。

## Lane 总览

| Lane | 范围 | 当前结论 | 状态 | 优先级 |
|------|------|----------|------|--------|
| A. Web high-risk | `Web/call-kit`、`packages/callkit-runtime-web`、React/Vue shared core | 不目录覆盖；按 master 行为重落到 reuse runtime/core | 已实施 | P0 |
| B. desktop ABI/runtime | `desktop/bridge`、`desktop/core`、Flutter desktop bridge headers、packaged dylib/dll | ABI additive 升级到 `2.1.1`；macOS Electron native 重建；macOS Flutter packaged dylib 对齐 master；Windows DLL 重建并通过导出符号 gate | 已完成 | P0 |
| C. Electron contract | `Electron/node-addon`、`Electron/sdk`、`packages/callkit-runtime-electron`、Electron UIKit | source/type/UIKit/runtime 链路承接 `state=1/2/3` + native/NIM 事件兜底；剩余为目标 release 的 capability gate 与真机签收 | 已实施（交付 gate 保留） | P0 |
| D. release/scripts/workspace | `scripts`、`release`、`Web` workspace、`Electron` workspace、shared packages | 当前资产 additive 回 master，禁止按 master 旧结构反删 | 已验证 | P1 |
| E. merge-back rehearsal | 当前分支 vs master 的 dry-run 集成验证 | 每个 P0 lane 完成后做局部 dry-run；2026-04-27 基于 `origin/master@8ada7413` 复跑后仍需处理上游冲突；Windows DLL gate 已过 | 策略完成（需最终人工 resolution） | P0 |

## Lane B：Windows DLL ABI Gate 修复（已完成）

### 修复前 5 个缺失导出

```text
ne_call_bridge_emit_call_type_change_with_state
ne_call_core_emit_call_type_change_with_state
ne_call_core_emit_rtc_raw
ne_callkit_get_runtime_state
ne_callkit_refresh_im_ready
```

对应三类能力：

| 能力 | 影响 |
|------|------|
| `callTypeChange.state` | Electron/Web 切换确认里的 `state=1/2/3` native payload 表达 |
| runtime state / IM ready refresh | Electron managed/external readiness、diagnostics 和登录后状态同步 |
| RTC raw event | desktop 运行时向上透传 RTC 细节事件 |

### 修复方式

- `desktop/bridge/CMakeLists.txt` 为 MSVC shared bridge 显式 `/EXPORT` 4 个 core C ABI 符号；`WINDOWS_EXPORT_ALL_SYMBOLS` 继续覆盖 bridge 自身导出
- `scripts/package_windows_callkit_bridge.ps1` 增加纯 PowerShell PE export table fallback，无 `dumpbin` / `llvm-nm` 时也能执行默认 gate

### 修复后

- DLL size: `557056` bytes / SHA256: `4598982FA8DFD4E8E0332D0E43883DFBBA762C3FE70818D94BF535F673022121`
- 导出表数量: `70`
- gate: passed，缺失导出 `none`
- Flutter Windows packaged build 通过；Runner 内 `ne_callkit.dll` hash 与 packaged DLL 一致

## Lane E：实测冲突清单（origin/master..HEAD, 2026-04-30）

| # | 文件 | 差异 | 决议 |
|---|------|------|------|
| 1 | `.gitignore` | HEAD 增加 `.claude/`、`.webmcp/`、`.tmp/`、`.codex/` 以及 Electron/Flutter desktop 构建目录 | 保留 HEAD 新增忽略，合并 master 其他修改 |
| 2 | `AGENTS.md` | HEAD 添加 Desktop/Electron 专属规范、NIM 收敛/B045 防退化硬约束，暂停 GitNexus | 保留 HEAD 侧 Desktop/Electron 规范 + GitNexus 暂停 |
| 3 | `CLAUDE.md` | HEAD 暂停 GitNexus + 新增 Repository Rules（B045）| 保留 HEAD 侧改动 |
| 4 | `Flutter/callkit/windows/Frameworks/ne_callkit.dll` | 二进制不一致 | 按 F011 lane B 决议保留 HEAD（最新 ABI 导出）|
| 5 | `TRACKER.md` | HEAD 增加分支专用跟踪 + F011 高风险 lane tracker | 合并双侧 |
| 6 | `Web/call-kit/package-lock.json` | 双侧依赖版本不一致（如 4.4.4 vs 4.4.2）| 放弃冲突，合并后 `npm install` 重生成 |
| 7 | `desktop/third_party/nim/windows_nim_version.cmake` | master 升级 Windows NIM 到 10.9.80.4833 | 保留 master 升级 |
| 8 | `release/skills/package-windows-cpp-callkit/SKILL.md` | master 补充 DLL 导出验证（`-SkipExportValidation`）和检查清单 | 保留 master 新增 |
| 9 | `scripts/package_windows_callkit_bridge.ps1` | master 新增 `Assert-DllExports` 和 `-SkipExportValidation` | 保留 master 新增 DLL 导出验证逻辑 |

## NIM 符号源收敛（URG-05 调研结论）

### Tarball 内字面量实测（PaaS 独立性硬约束）

| Tarball | `require('node-nim')` | `import 'node-nim'` | `V2NIMClient` | `@loader_path/libnim` | `node-nim` 路径字符串 |
|---------|-----------------------|---------------------|---------------|-----------------------|---------------------|
| `xkit-yx-electron-callkit-sdk-0.1.0.tgz` | 0 | 0 | 0 | 0 | 8 行（仅 `runtime-env.js` 路径发现）|
| `xkit-yx-electron-callkit-react-uikit-0.1.0.tgz` | 0 | 0 | 0 | 0 | 8 行（同上） |
| `xkit-yx-electron-callkit-vue3-uikit-0.1.0.tgz` | 0 | 0 | 0 | 0 | 8 行（同上） |

**结论**：三个 tarball 满足 PaaS 独立性约束。`node-nim` 字符串仅在 `runtime-env.js` 路径发现逻辑，不含顶层 `require('node-nim')` 或 `import 'node-nim'`。客户工程须自装 `node-nim` 并确保 `build/Release/` 在标准路径，或通过 `nimRuntimePath` 选项显式注入。

### 关键发现

- `build-plan.js` **不**把 `nim.dll` / `libnim.dylib` 复制到 staging；而是在 dev/run-example 时通过 env 注入 NIM runtime 路径。staging 只存 bridge (`ne_callkit.dll`) 和 addon (`ne_call_electron.node`)。
- 当前 `bridgeStrategy=source` 满足 B045 要求（不允许 packaged bridge 验收 desktop/core 修复）。
- `runtimeStrategy=upstream-download`（NERTC SDK 与 NIM 无关）。
- workspace 根级 `Electron/node_modules/node-nim` 不存在；`build-plan.js` 寻址 workspace 级路径但只 example 级安装；dev 模式 NIM 供给靠 pub-cache 或 `NE_CALL_NIM_RUNTIME_DIR` 显式注入。

## Lane A 必须补齐的 master 行为（验收口径）

| 项 | 目标位置 | 验收口径 |
|----|----------|----------|
| 通话时长 ticker | `packages/callkit-runtime-web` | `Date.now()` 差值持续更新 `durationSeconds`，不再依赖累计 interval |
| 切音频保留本地静音 | `packages/callkit-runtime-web` | `applyAcceptedCallType()` 不强制 `muteLocalAudio(false)` |
| 对端开关摄像头提示 | runtime + domain + React/Vue core | `onVideoMuteOrUnmute` 进入 shared state，UI 提示 |
| `reasonCode=20` 文案 | `packages/callkit-domain` | "对方网络异常 / 通话已断开"等 master 等效提示 |
| 切换确认弹层 | runtime + React/Vue core | `state=1/2/3` 请求/同意/拒绝闭环可用 |
| React 语音转视频 | `packages/callkit-react-core` | React core 同时具备 `switch-audio` 与 `switch-video` |
| 重连 / 媒体错误提示 | runtime + React/Vue core | runtime 已有状态被 shared UI 消费 |

> Lane A 的 React `state=1/2/3` 切换确认 / 切回视频默认开摄像头 / 默认开麦 / 等待对端响应 等行为已被 B057/B061/B065-B069/B072 系列 bugfix 进一步收紧，详见 switchCallType 系列页面。

## Lane B 当前基线（不能回退）

- ABI minor `2.1`
- ABI patch `2.1.1` 的 `callTypeChange.state` additive payload
- runtime state 查询 / IM ready refresh / RTC raw event
- Electron readiness / diagnostics 依赖的 bridge 能力
- desktop 远端音频播放、callback try/catch、NIM/RTC runtime 收口修复

> macOS Flutter packaged universal dylib 直接使用 `origin/master` artifact 以消除 binary 冲突；Electron native/source ABI `2.1.1` 仍保留。

## Related wiki pages

- [[necallkit-master-merge-back-preflight-f011-2026-05-11]]
- [[necallkit-master-merge-back-preflight-query]]
- [[electron-web-api-reuse-and-merge-back-switch-contract]]
- [[necallkit-docs-guides-electron-merge-impact-baseline]]
- [[002-electron-callkit-web-master-diff-assessment-2026-04-25]]
- [[electron-switchcalltype-remediation-history]]
- [[necallkit-docs-guides-electron-flutter-merge-review-checklist]]
"""


def query_page() -> str:
    sources = [
        f"  - {NEW_FEATURE_PATH.as_posix()}",
        f"  - {NEW_DECISION_PATH.as_posix()}",
        "  - modules/electron-web-api-reuse-and-merge-back-switch-contract.md",
        "  - modules/necallkit-docs-guides-electron-merge-impact-baseline.md",
        "  - decisions/002-electron-callkit-web-master-diff-assessment-2026-04-25.md",
        "  - decisions/necallkit-docs-guides-electron-flutter-merge-review-checklist.md",
    ]
    return frontmatter(
        "NECallKit 当前分支合回 master 预审排查",
        "queries",
        ("electron", "desktop", "flutter", "callkit", "nim", "rtc", "bridge", "regression", "compatibility", "architecture", "ipc"),
        sources,
    ) + """# NECallKit 当前分支合回 master 预审排查

## Question

我要把 NECallKit 当前分支（`002-electron-callkit-reuse-enhance` 系）合回 master，差距比较大，先看哪些边界、lane、冲突清单和验收口径？

## Answer Confidence

High, 0.88。

F011 已经把"低耦合迁入"做完，剩余高风险差异已分成 5 个 lane（A/B/C/D/E），每个 lane 状态明确、边界清楚。Lane B Windows DLL ABI gate 已通过；Lane E 实测冲突清单已记录；NIM 符号源收敛已调研。剩余只是最终人工 conflict resolution + 真机签收。

## First Classification

| Symptom / 操作 | First branch |
|---|---|
| 我要做整体 merge-back 计划 | 读 [[necallkit-master-merge-back-preflight-f011-2026-05-11]] 主 feature 页 |
| 我要看 5 个 lane 状态 | 读 [[necallkit-master-merge-back-lanes-and-conflicts-2026-05-11]] §Lane 总览 |
| 我要解 9 条 origin/master..HEAD 冲突 | 读 [[necallkit-master-merge-back-lanes-and-conflicts-2026-05-11]] §Lane E 实测冲突清单 |
| 我要确认 Windows DLL ABI 是否通过 gate | 读 [[necallkit-master-merge-back-lanes-and-conflicts-2026-05-11]] §Lane B Windows DLL ABI Gate |
| 我要确认 tarball 满足 PaaS 独立性 | 读 [[necallkit-master-merge-back-lanes-and-conflicts-2026-05-11]] §NIM 符号源收敛 |
| 我要看 Web/Electron 切换合同（state=1/2/3）| 读 [[electron-web-api-reuse-and-merge-back-switch-contract]] |
| 我要看 master diff 评估 | 读 [[002-electron-callkit-web-master-diff-assessment-2026-04-25]] |
| 我要看 merge review checklist | 读 [[necallkit-docs-guides-electron-flutter-merge-review-checklist]] |

## Pre-merge-back checklist（按 lane 顺序）

### Lane A — Web high-risk（已实施）

- [ ] React/Vue shared core 是否承接 `state=1/2/3` 切换确认？
- [ ] 通话时长 ticker 用 `Date.now()` 差值，不依赖 setInterval 累加？
- [ ] `switchCallType` 切音频后保留本地静音（不强制 unmute）？
- [ ] `reasonCode=20` 文案与 master 等效？
- [ ] React core 同时具备 `switch-audio` 与 `switch-video`？

### Lane B — desktop ABI/runtime（已完成）

- [ ] ABI patch 是否 `2.1.1` 或更高？
- [ ] Windows `ne_callkit.dll` 5 个核心导出符号是否齐全？运行 `package_windows_callkit_bridge.ps1` 默认 gate
- [ ] macOS Electron `Electron/out/native/darwin-debug/manifest.json` `bridgeStrategy=source`？
- [ ] macOS Flutter packaged dylib 是否使用 `origin/master` artifact（不再作为 ABI 验证源）？

### Lane C — Electron contract（已实施，交付 gate 保留）

- [ ] `Electron/node-addon` / `Electron/sdk` / `packages/callkit-runtime-electron` 是否承接 `state=1/2/3` + native/NIM 事件兜底？
- [ ] 真机签收口径（capability gate）是否已确认？
- [ ] mac IPC topology 拓扑下的 `runtime.sdk === null` 假设处理是否齐全？（参考 B066 / B070 / B074 mac IPC 簇）

### Lane D — release/scripts/workspace（已验证）

- [ ] 当前资产是否能 additive 回 master，**未要求 master 先回退旧结构**？
- [ ] 没有按 master 旧结构反删 shared packages / Electron host/runtime / workspace？

### Lane E — merge-back rehearsal

- [ ] 已基于最新 `origin/master` 跑 dry-run？
- [ ] 9 条已知冲突按决议处理（详见 [[necallkit-master-merge-back-lanes-and-conflicts-2026-05-11]] §Lane E）？
- [ ] master 侧的 NIM 版本升级、`-SkipExportValidation` 参数、`Assert-DllExports` 函数是否合并？
- [ ] `Web/call-kit/package-lock.json` 重生成？
- [ ] Windows DLL / Flutter packaged dylib 二进制按 lane B 决议保留哪侧已确认？

## What this branch must NOT regress

按 F011 三大原则保留的不可回退能力（Lane B 当前基线）：

- ABI minor `2.1` / patch `2.1.1` `callTypeChange.state` additive payload
- runtime state 查询 / IM ready refresh / RTC raw event
- Electron readiness / diagnostics 依赖的 bridge 能力
- desktop 远端音频播放、callback try/catch、NIM/RTC runtime 收口修复
- 唯一冻结功能例外：Electron 群呼（其他降级必须进 tracker）

## Sources

`raw/imported/necallkit-master-merge-back-preflight-2026-05-11/` 下原始 7 个 PRD/plan 文件提供逐节细节：

- F011-master-low-coupling-sync.md（主 spec）
- F011-master-low-coupling-sync-tasks.md（任务清单）
- F011-master-low-coupling-sync-test.md（验证矩阵）
- F011-master-merge-back-plan.md（5 lane 详细计划）
- F011-windows-dll-abi-gate-recovery.md（Windows DLL ABI gate 完整修复证据）
- 2026-04-30-merge-back-conflict-resolution.md（Lane E 9 条冲突）
- 2026-04-30-nim-symbol-source-convergence-investigation.md（NIM 符号源收敛 URG-05）

## Sources Used

- [[necallkit-master-merge-back-preflight-f011-2026-05-11]]
- [[necallkit-master-merge-back-lanes-and-conflicts-2026-05-11]]
- [[electron-web-api-reuse-and-merge-back-switch-contract]]
- [[necallkit-docs-guides-electron-merge-impact-baseline]]
- [[002-electron-callkit-web-master-diff-assessment-2026-04-25]]
- [[necallkit-docs-guides-electron-flutter-merge-review-checklist]]
"""


def update_existing_pages(wiki_root: Path) -> None:
    extra_sources = [
        f"  - {NEW_FEATURE_PATH.as_posix()}",
        f"  - {NEW_DECISION_PATH.as_posix()}",
        f"  - {NEW_QUERY_PATH.as_posix()}",
    ]

    contract_page = wiki_root / "modules" / "electron-web-api-reuse-and-merge-back-switch-contract.md"
    text = update_frontmatter(read_text(contract_page), extra_sources)
    text = upsert_section(
        text,
        "2026-05-11 F011 merge-back preflight 全景",
        f"""F011 主特性把当前分支合回 master 的全景已蒸馏到 wiki：

- [[{NEW_FEATURE_PATH.stem}]]：F011 主 feature + 三大原则（forward-sync / merge-back / contract-first）+ 唯一冻结例外（Electron 群呼）
- [[{NEW_DECISION_PATH.stem}]]：5 lane 总览 + Windows DLL ABI gate 修复 + Lane E 9 条实测冲突清单 + NIM 符号源收敛
- [[{NEW_QUERY_PATH.stem}]]：合回 master 前的检查清单和决策树

未来需要把当前分支合回 master 时，先读 query 页。""",
    )
    write_text(contract_page, text)

    baseline_page = wiki_root / "modules" / "necallkit-docs-guides-electron-merge-impact-baseline.md"
    text = update_frontmatter(read_text(baseline_page), extra_sources)
    text = upsert_section(
        text,
        "2026-05-11 F011 merge-back preflight",
        f"""merge-impact-baseline 描述高风险合并的影响评估口径，但不覆盖具体的 lane 拆分和冲突清单。F011 合回 master 的全套预审已建好：feature [[{NEW_FEATURE_PATH.stem}]]、5 lane 决策 [[{NEW_DECISION_PATH.stem}]]、检查清单 [[{NEW_QUERY_PATH.stem}]]。""",
    )
    write_text(baseline_page, text)

    diff_page = wiki_root / "decisions" / "002-electron-callkit-web-master-diff-assessment-2026-04-25.md"
    text = update_frontmatter(read_text(diff_page), extra_sources)
    text = upsert_section(
        text,
        "2026-05-11 F011 lane status & 实测冲突清单",
        f"""master diff assessment 给出 4-25 时点的差异；F011 主特性把"如何把这些差异合回去"分成 5 lane（A/B/C/D/E），并已实测出 9 条具体冲突。Lane B Windows DLL ABI gate 已通过；Lane E 已有冲突决议。

- 全景：[[{NEW_FEATURE_PATH.stem}]]
- 5 lane + 9 条冲突 + Windows DLL gate + NIM 符号源：[[{NEW_DECISION_PATH.stem}]]
- 合回 master 前 query：[[{NEW_QUERY_PATH.stem}]]""",
    )
    write_text(diff_page, text)


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


def update_index(wiki_root: Path, created_feature: bool, created_decision: bool, created_query: bool) -> None:
    index_path = wiki_root / "index.md"
    text = read_text(index_path)
    increment = int(created_feature) + int(created_decision) + int(created_query)
    if increment:
        text = re.sub(r"Total pages: (\d+)", lambda m: f"Total pages: {int(m.group(1)) + increment}", text, count=1)
    feature_entry = f"- [F011 NECallKit 当前分支合回 master 预审特性]({NEW_FEATURE_PATH.as_posix()}) - F011 把「长期背离 master 的特化分支」拉回「可持续追 master、可 MR/rebase 回去」。三原则 + 唯一冻结例外 + 5 lane。"
    decision_entry = f"- [F011 五 Lane 高风险合回 master 计划与冲突清单]({NEW_DECISION_PATH.as_posix()}) - 5 lane（A/B/C/D/E）总览 + Windows DLL ABI gate 修复 + Lane E 9 条实测冲突 + NIM 符号源 URG-05 调研。"
    query_entry = f"- [NECallKit 当前分支合回 master 预审排查]({NEW_QUERY_PATH.as_posix()}) - Query filed 2026-05-11 / 合回 master 前的 lane checklist + 9 条冲突决议 + 不可回退 ABI 基线。"
    if feature_entry not in text:
        text = text.replace("## Features\n\n", "## Features\n\n" + feature_entry + "\n", 1)
    if decision_entry not in text:
        text = text.replace("## Decisions\n\n", "## Decisions\n\n" + decision_entry + "\n", 1)
    if query_entry not in text:
        text = text.replace("## Queries\n\n", "## Queries\n\n" + query_entry + "\n", 1)
    write_text(index_path, text.rstrip() + "\n")


def append_log(wiki_root: Path, raw_created: int, raw_unchanged: int) -> None:
    log_path = wiki_root / "log.md"
    text = read_text(log_path).rstrip()
    marker = "import | <workspace>/project/NECallKit docs F011 master merge-back preflight"
    if marker in text:
        return
    entry = f"""

## [{TODAY}] import | <workspace>/project/NECallKit docs F011 master merge-back preflight (7 files)
- Format: curated PRD/plan batch
- Created: 3 wiki pages (feature + decision + query)
- Updated: 3 existing pages
- Raw: raw/imported/{BUNDLE_NAME}/ ({raw_created} created, {raw_unchanged} unchanged)
- Source group: F011 main spec/tasks/test + merge-back-plan + Windows DLL ABI gate recovery + Lane E 实测冲突 + NIM 符号源 URG-05
- Filed: [[necallkit-master-merge-back-preflight-f011-2026-05-11]], [[necallkit-master-merge-back-lanes-and-conflicts-2026-05-11]], [[necallkit-master-merge-back-preflight-query]]
- Updated: [[electron-web-api-reuse-and-merge-back-switch-contract]], [[necallkit-docs-guides-electron-merge-impact-baseline]], [[002-electron-callkit-web-master-diff-assessment-2026-04-25]]
- Decision: ingest now because user is preparing actual merge-back work; previous wiki pages knew about partial F011 outputs (switch-contract module, master-diff-assessment) but had no PRD-level entry point + no Lane E 9-conflict checklist + no Windows DLL ABI gate evidence + no NIM symbol source URG-05 conclusion. The query page is the new front door for "I'm about to merge back, what do I check first?"
"""
    write_text(log_path, text + entry)


def execute(wiki_root: Path, project_root: Path) -> dict[str, object]:
    raw_counts = {"created": 0, "unchanged": 0}
    for source in SOURCE_FILES:
        raw_counts[safe_copy_raw(project_root, wiki_root, source)] += 1
    feature_full = wiki_root / Path(NEW_FEATURE_PATH.as_posix())
    decision_full = wiki_root / Path(NEW_DECISION_PATH.as_posix())
    query_full = wiki_root / Path(NEW_QUERY_PATH.as_posix())
    created_feature = not feature_full.exists()
    created_decision = not decision_full.exists()
    created_query = not query_full.exists()
    write_text(feature_full, feature_page())
    write_text(decision_full, decision_page())
    write_text(query_full, query_page())
    update_existing_pages(wiki_root)
    update_index(wiki_root, created_feature, created_decision, created_query)
    append_log(wiki_root, raw_counts["created"], raw_counts["unchanged"])
    return {
        "raw_created": raw_counts["created"],
        "raw_unchanged": raw_counts["unchanged"],
        "created": [str(NEW_FEATURE_PATH), str(NEW_DECISION_PATH), str(NEW_QUERY_PATH)],
        "updated": [
            "modules/electron-web-api-reuse-and-merge-back-switch-contract.md",
            "modules/necallkit-docs-guides-electron-merge-impact-baseline.md",
            "decisions/002-electron-callkit-web-master-diff-assessment-2026-04-25.md",
        ],
    }


def main() -> int:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    project_root = Path(args.project).resolve()
    checkpoint_script = Path(args.checkpoint_script).resolve()
    validate_sources(project_root)
    plan = {"bundle": BUNDLE_NAME, "sources": [s.as_posix() for s in SOURCE_FILES], "new_pages": [NEW_FEATURE_PATH.as_posix(), NEW_DECISION_PATH.as_posix(), NEW_QUERY_PATH.as_posix()], "updates": 3}
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
