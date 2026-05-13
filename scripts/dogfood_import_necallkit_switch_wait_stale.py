from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "necallkit-electron-switch-wait-stale-2026-05-09"
TODAY = date.today().isoformat()

SOURCE_FILES: tuple[PurePosixPath, ...] = (
    PurePosixPath("docs/bugfix/B065-electron-switch-wait-peer-result/analysis.md"),
    PurePosixPath("docs/bugfix/B065-electron-switch-wait-peer-result/B065-electron-switch-wait-peer-result-test.md"),
    PurePosixPath("docs/bugfix/B066-electron-runtime-ipc-cleared-extension-fields/analysis.md"),
    PurePosixPath("docs/bugfix/B066-electron-runtime-ipc-cleared-extension-fields/B066-electron-runtime-ipc-cleared-extension-fields-test.md"),
    PurePosixPath("docs/bugfix/B067-electron-switch-waiting-hint-visual/analysis.md"),
    PurePosixPath("docs/bugfix/B067-electron-switch-waiting-hint-visual/B067-electron-switch-waiting-hint-visual-test.md"),
    PurePosixPath("docs/bugfix/B068-electron-rtc-init-end-engine-reuse/analysis.md"),
    PurePosixPath("docs/bugfix/B068-electron-rtc-init-end-engine-reuse/B068-electron-rtc-init-end-engine-reuse-test.md"),
    PurePosixPath("docs/bugfix/B069-electron-switch-stale-remote-video-events/analysis.md"),
    PurePosixPath("docs/bugfix/B069-electron-switch-stale-remote-video-events/B069-electron-switch-stale-remote-video-events-test.md"),
)

NEW_BUG_PATH = PurePosixPath("bugs/electron-switch-wait-peer-and-stale-video-2026-05-09.md")
NEW_QUERY_PATH = PurePosixPath("queries/electron-switch-wait-peer-and-stale-video-query.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import NECallKit B065-B069 switch wait peer + stale remote video cluster.")
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
        "Electron 音视频切换等待对端结果与 stale 远端视频窗口（B065-B069）",
        "bugs",
        ("electron", "desktop", "rtc", "signaling", "callkit", "bridge", "regression", "state-machine", "ipc", "testing"),
        raw_source_lines(),
    ) + """# Electron 音视频切换等待对端结果与 stale 远端视频窗口（B065-B069）

## Summary

- B065-B069 是 B059-B063 之后继续收紧的 switchCallType 高风险簇，引入了三个全新的状态机概念：`outgoingSwitchCallType` 字段、IPC normalize cleared 信号穿透规则、`pendingFreshRemoteVideoUntilMs` 时间窗。
- B065 把"本端主动 switchCallType"从"立即 apply"改为"outgoing pending 直到对端 state=2/3"。
- B066 修复 B065 在 macOS 主进程 IPC 拓扑下的延伸：`normalizeElectronRuntimeStateSnapshot` 之前 skip 掉 cleared (`undefined`) 字段，main 端"显式 set undefined"在 IPC 边界丢失，renderer 永远停在旧值。
- B067 给 B065 引入的等待提示加视觉胶囊和音频模式定位修正。
- B068 修复 EnsureRtcInitialized 复用 engine 不再 emit `rtc_init_end`，导致第二次起通话 `rtcInitCompleted` 永远 false。
- B069 解决切到视频后 NERTC 7ms 内连抖序列击穿前一版 stale guard 的问题，最终方案是 positive 信号也不清窗，让 2 秒 window 自然到期。

## Issue Matrix

| ID | Problem | Durable rule |
|----|---------|--------------|
| B065 | 本端发起 switchCallType 后 UI / callType 立即生效，对端拒绝时无法恢复 | 引入 `outgoingSwitchCallType`，state=1 只发送 native 请求并 mark outgoing；state=2 才 apply；state=3 保持原 callType |
| B066 | macOS IPC 拓扑下 outgoing/pending 字段被清后 renderer 仍残留旧值 | normalize 在 hasOwnProperty 时显式写 undefined；IPC mergeState 在扩展字段 absent 时主动 reset target |
| B067 | 等待提示视频模式无背景胶囊、音频模式遮挡头像 | hint 加半透明深底胶囊；音频模式分支 top:-44px 上移到头像之上 |
| B068 | 第二次起通话 `rtcInitCompleted` 永远 false（EnsureRtcInitialized 复用 engine 分支不 emit） | 复用 engine 分支也 emit 一次 `rtc_init_end`，对齐 runtime "每次通话 RTC 已就绪" 语义 |
| B069 | 切到视频瞬间 NERTC 7ms 内 start→mute→stop 连抖让 InCallOverlay 误显"对方关闭了摄像头" | runtime mark `pendingFreshRemoteVideoUntilMs=now+2000`，window 内 negative skip；positive 信号不清窗，window 自然到期 |

## outgoingSwitchCallType State Machine

新引入的本端 outgoing pending 字段：

| 状态字段 | 含义 |
|----------|------|
| `pendingSwitchCallType` | 收到对端 incoming switch 请求，等待本端确认 |
| `outgoingSwitchCallType` | 本端已发起 switch 请求，等待对端响应（B065 引入） |
| `callType` | 当前已经 resolved 的正式通话类型 |

转移规则：

- `switchCallType(state=1)`：发送 native 请求 + 写 `outgoingSwitchCallType`，**不调用** `applyResolvedCallTypeWithNativeVideo`。
- 本端收到 native / Ark 对 `state=1` 请求的 ACK 回显：识别为 echo，**不清** `outgoingSwitchCallType`，继续等待。
- `onCallTypeChange(state=2)`：清除 outgoing marker 并正式 apply。
- `onCallTypeChange(state=3)` 匹配 outgoing：清除 marker，保留原 callType，提示"对方拒绝了您的请求"。
- 通话结束 / 挂断 / setup / 接听 / 来电 / 新呼叫：统一清理 outgoing marker。

native 侧 `desktop/core/src/call_controller.cpp` 的 `SwitchCallType(state=1)` 同步去掉 `ApplyResolvedSwitchCallType` 调用，只发送 control + 记录 pending outgoing + emit `state=1` 事件。

## IPC Cleared Signal Propagation Rule（B066）

`normalizeElectronRuntimeStateSnapshot` 旧版逻辑：

```ts
ELECTRON_EXTENSION_FIELDS.forEach((fieldName) => {
  if (
    Object.prototype.hasOwnProperty.call(source, fieldName) &&
    hasExtensionValue(source[fieldName])     // ← cleared 时 false → skip
  ) {
    snapshot[fieldName] = source[fieldName];
  }
});
```

main 端清成 `undefined` → snapshot 没有该 key → IPC publish → renderer `Object.assign` 不会覆盖 target 旧值。

修复后两道防线：

1. normalize 在源对象 `hasOwnProperty=true` 时一律写 snapshot，cleared 显式 `undefined`。
2. IPC mergeState 在扩展字段 absent 时主动 reset target 字段为 `undefined`，再 `Object.assign`。

`createRuntimeState()` 同时去掉对扩展字段的预置（之前预置 undefined 会让初始 normalize snapshot 多出两个 keys，破坏 callkit-domain MINIMAL contract）。

## pendingFreshRemoteVideoUntilMs Window（B069）

NERTC 切到视频瞬间 7ms 内会连续抖动：

```text
11.597Z  applyResolvedCallType (切到视频)
11.723Z  onVideoAvailable(true)
11.726Z  onVideoMuted(true) + onVideoAvailable(false)
11.730Z  onVideoAvailable(false)
```

原因：`OnRtcUserVideoMute(muted=true)` 在 native 侧一次回调 emit `video_muted(true)` + `video_available(0)` 两个事件。这是 NERTC 远端流订阅过程中的正常状态报告序列。

最终修复方案（演进过程见 analysis.md）：

- `applyResolvedCallType` 在 `shouldEnableVideoBySwitch=true`（prev !== 2 && new === 2）时 mark `pendingFreshRemoteVideoUntilMs = Date.now() + 2000`。
- `onVideoAvailable(false)` / `onVideoMuted(true)` 在 window 内被识别为 stale 并 skip（日志 `skip_stale_window`）。
- **positive 信号（available=true / muted=false）只更新 state，不清 window**。这是关键修订——早期方案 positive 立即清窗会被 7ms 连抖击穿。让 window 自然 2 秒到期，期间任何 negative 都被忠实拦下。

诊断日志：runtime 关键事件加 `[runtime-electron][video]` 前缀的 stdout 日志，默认开启，可通过 `NECALL_DEBUG_VIDEO_SWITCH=0` / `=false` 关闭。

## RTC Engine Reuse Semantics（B068）

`EnsureRtcInitialized` 复用 engine 分支之前直接 return，不 emit `rtc_init_end`。但 runtime 在每次 `onCallConnected` / `onReceiveInvited` / `call` / `onCallEnd` / `setup` 都把 `rtcInitCompleted` 重置为 false，只有 `onRtcInitEnd` 才设回 true。

行为链：

| 时机 | rtc_engine_ | rtcInitCompleted |
|------|-------------|------------------|
| 进程内首次接通 | nullptr → 创建 + emit | false → true |
| 首次挂断 | 保留（不释放） | 被 onCallEnd 重置 → false |
| 第二次起接通 | 已存在，直接 return，不 emit | 被重置 false，无事件设回 → 永远 false |

事件名 `rtc_init_end` 在 native 侧语义是"engine 对象创建完成"，runtime 侧把它当"每次通话 RTC 已就绪"，两边语义错位。

修复后 native 把语义对齐 runtime：复用 engine 分支也 emit 一次 `rtc_init_end`，runtime 多次接收幂等。

> 这是 B069 的前置修复——B069 早期方案曾以 `rtcInitCompleted=false` 作为"切换瞬间"判据，因为 B068 该判据在第二次起通话永远命中，导致回归。最终 B069 不再依赖此字段，但 B068 仍是必要的状态机修复。

## Switch Waiting Hint Visual Rules（B067）

视频模式：hint 是 `.necall-video-stage` 直接子元素，`top:56px`，半透明深底胶囊 + 毛玻璃 + `pointer-events: none`，与 1280 宽度下 `.necall-small-view`（右上角 [1135, 1260]）不重叠。

音频模式：hint 嵌在 `.necall-in-call-audio` 容器（`top:96px`），通过嵌套选择器 `top: -44px` 上移，落在 96×96 头像之上（视觉 top:52px）。

## Verification Evidence

- B065/B066/B068/B069：runtime / shared UI / Electron wrapper 测试全部通过；B065 还跑了 `lty02 -> lty05` 真实双端 `switch-wait` E2E probe，断言 caller `outgoingSwitchCallType=1` + 双端 `callType=2` 在等待期不变。
- B068：`desktop/core` 改动，已执行 `npm run build:native:source`，staged manifest `bridgeStrategy=source`。
- B069：runtime-only 修复，但 desktop/core / Electron source bridge 在 B068 一同验收时已 source build 通过。
- B067：仅 shared core 样式 + Vue3 `lib/` `es/` 构建产物，无 native 依赖。

## Related wiki pages

- [[electron-switchcalltype-media-state-and-reject-semantics-2026-05-09]]
- [[electron-camera-switch-microphone-state-regression-bugfix-set]]
- [[electron-switch-video-default-camera-on-product-rule-change]]
- [[electron-switchcalltype-regression-merge-guard-query]]
- [[electron-win-mac-camera-switch-microphone-state-query]]
- [[l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离]]
- [[002-electron-callkit-contracts-electron-web-unified-public-contract]]
"""


def query_page() -> str:
    sources = [
        f"  - {NEW_BUG_PATH.as_posix()}",
        "  - bugs/electron-switchcalltype-media-state-and-reject-semantics-2026-05-09.md",
        "  - queries/electron-switchcalltype-reject-state-and-media-preflight-query.md",
        "  - queries/electron-switchcalltype-regression-merge-guard-query.md",
        "  - queries/electron-win-mac-camera-switch-microphone-state-query.md",
    ]
    return frontmatter(
        "Electron 音视频切换 outgoing 等待与 stale 远端视频排查",
        "queries",
        ("electron", "desktop", "rtc", "signaling", "callkit", "bridge", "regression", "state-machine", "ipc", "testing"),
        sources,
    ) + """# Electron 音视频切换 outgoing 等待与 stale 远端视频排查

## Question

处理 Electron 音视频切换"本端发起后 UI 提前生效 / 等待提示残留 / 切到视频瞬间误显远端关摄像头 / 第二次通话 rtcInitCompleted 永远 false"问题时，应该先看哪些边界、状态机字段和时间窗？

## Answer Confidence

High, 0.86.

This answer is backed by B065/B066/B067/B068/B069 curated bugfix records plus the prior B059-B063 reject-state remediation. It is high confidence for Electron runtime / desktop-core / IPC topology guardrails, but still requires current-branch source verification before code changes.

## First Classification

| Symptom | First branch |
|---|---|
| 本端发起切换后 UI 立即变了 | Check B065 outgoingSwitchCallType state machine |
| 等待提示在对端同意/拒绝后还在残留 | Check B066 IPC normalize cleared signal |
| 等待提示视觉位置不对 | Check B067 hint capsule + audio-mode `top:-44px` |
| 切到视频瞬间闪现"对方关闭了摄像头" | Check B069 pendingFreshRemoteVideoUntilMs window |
| 第二次起通话 rtcInitCompleted 永远 false | Check B068 EnsureRtcInitialized engine reuse |
| 本端拒绝 incoming 却弹"对方拒绝" | Check B063 state=3 direction model（B065 引入 outgoingSwitchCallType 是其官方 marker） |

## outgoing/pending Marker Direction Checklist

1. 本端发起 `switchCallType(state=1)`：mark `outgoingSwitchCallType`，**不**清 `pendingSwitchCallType`，**不**调用 `applyResolvedCallTypeWithNativeVideo`。
2. 本端收到对端 incoming `state=1`：mark `pendingSwitchCallType`，弹"权限请求"确认框。
3. native ACK 本端请求 echo：识别为本端 echo，不动 outgoing 也不动 pending。
4. `onCallTypeChange(state=2)` 匹配 outgoing：清 outgoing + apply 目标 callType。
5. `onCallTypeChange(state=3)` 匹配 outgoing：清 outgoing + 保持原 callType + 提示"对方拒绝了您的请求"。
6. `onCallTypeChange(state=3)` 匹配 local-rejected-incoming marker：consume 静默。
7. 通话结束 / 挂断 / setup / 接听 / 来电 / 新呼叫：统一清两个 marker。

## IPC Cleared Signal Propagation Checklist

main 端 runtime 把扩展字段（`outgoingSwitchCallType` / `pendingSwitchCallType`）清成 undefined 后，IPC 边界要确保 cleared 信号穿透到 renderer：

1. `normalizeElectronRuntimeStateSnapshot`：源对象 `hasOwnProperty=true` 时一律写 snapshot；cleared 显式 `undefined`，**不能** skip。
2. `Electron/scripts/lib/ipc-callkit-runtime.js` 的 `mergeState`：扩展字段在 payload 中 absent 时，主动 reset target 字段为 `undefined`，再 `Object.assign`。
3. `createRuntimeState()`：**不**预置扩展字段，避免 normalize 在初始 snapshot 多出两个 keys，破坏 callkit-domain MINIMAL contract。
4. 全部 in-process 消费者用 `state.outgoingSwitchCallType !== undefined && !== null && !== ''` 判 hint 显示，absent 与 undefined 等价。

只在 macOS Electron 24+ IPC 拓扑下命中（Windows in-renderer runtime 不走 IPC publish）。

## Stale Remote Video Window Checklist（B069）

切到视频瞬间 NERTC 7ms 内可能连抖：

1. `applyResolvedCallType` 在 `shouldEnableVideoBySwitch=true`（prev !== 2 && new === 2）时 mark `pendingFreshRemoteVideoUntilMs = Date.now() + 2000`。
2. `onVideoAvailable(false)` / `onVideoMuted(true)` 在 window 内 skip，日志 `skip_stale_window`。
3. **positive 信号（available=true / muted=false）只更新 state，不清 window**。早期方案让 positive 清窗会被 7ms 连抖击穿。
4. window 不在 `onCallConnected` mark（与 runtime-contract `onCallConnected → onVideoAvailable(false)` 立即 propagate 的预期冲突）。
5. window 期间对端真的关摄像头属于罕见操作（2 秒），到期后 native 仍可能再推稳态 mute。

诊断日志：`[runtime-electron][video]` 前缀，默认开启，`NECALL_DEBUG_VIDEO_SWITCH=0` 关闭。

## RTC Engine Reuse Semantics（B068）

`EnsureRtcInitialized` 复用 engine 分支必须也 emit `rtc_init_end`，不能因为"engine 已存在"就跳过。语义已对齐 runtime "每次通话 RTC 已就绪"。

如果未来又出现 "rtcInitCompleted 第二次通话永远 false"：先确认 native 是否在复用分支跳过 emit。

## Verification Matrix

```text
node --test packages/callkit-runtime-electron/test/runtime-contract.test.ts
node --test packages/callkit-runtime-electron/test/video-switch-regression.test.ts
node --test packages/callkit-react-core/test/call-view.test.js
node --test packages/callkit-vue3-core/test/call-view.test.js
node --test Electron/react-uikit/test/call-view.test.js Electron/vue3-uikit/test/call-view.test.js
node --test Electron/scripts/test/native-addon-regressions.test.js  # B068 / B069 native event 涉及
```

如果命中 `desktop/core` / `desktop/bridge` / `Electron/node-addon`，必须 `cd Electron && npm run build:native:source` 并检查 `Electron/out/native/*/manifest.json` 中 `bridgeStrategy=source`。

如果命中 macOS IPC 拓扑（`darwin && Electron major >= 24`）：
- 必须 DevTools Console 验证 `window.$callkit.sdk === null`（确认走 IPC runtime）。
- 必须验证 outgoing/pending 字段 cleared 后 renderer state 同步消失。

## E2E Probe（B065 引入）

```bash
cd Electron
node ./scripts/run-controlled-electron-probe.js \\
  --framework vue3 --scenario switch-wait --mode Debug \\
  --timeout-ms 180000 \\
  -- --caller lty02 --callee lty05 --token 123456 \\
  --call-type 2 --state-timeout-ms 60000 --connect-timeout-ms 60000
```

断言 caller `callerKeptVideoBeforePeerResponse=true` + `callerOutgoingAudioSwitchPending=true`，callee `calleeKeptVideoBeforeConfirm=true` + `calleePendingAudioSwitch=true`。

## Ingest Guidance

当后续修复触及 outgoing/pending state machine、stale video window、IPC normalize 边界、RTC engine reuse 语义中任意一行，立刻 ingest。这些是新引入的概念，wiki 没有这些就会让未来 query 命中 B059-B063 但漏掉新维度。

## Sources Used

- [[electron-switch-wait-peer-and-stale-video-2026-05-09]]
- [[electron-switchcalltype-media-state-and-reject-semantics-2026-05-09]]
- [[electron-switchcalltype-reject-state-and-media-preflight-query]]
- [[electron-switchcalltype-regression-merge-guard-query]]
- [[electron-win-mac-camera-switch-microphone-state-query]]
"""


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


def update_existing_pages(wiki_root: Path) -> None:
    source_lines = raw_source_lines()

    media_bug = wiki_root / "bugs" / "electron-switchcalltype-media-state-and-reject-semantics-2026-05-09.md"
    text = update_frontmatter(read_text(media_bug), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-09 后续 B065-B069 outgoing / IPC / window 扩展",
        f"""B065-B069 在 B059-B063 的 reject state 模型上又新增三个独立维度:

| 维度 | 关键改动 |
|------|----------|
| `outgoingSwitchCallType` 字段（B065） | 本端 state=1 不再立即 apply；`onCallTypeChange(state=2)` 才 apply；`state=3` 保持原 callType |
| IPC normalize cleared 信号（B066） | macOS 主进程 IPC 拓扑下，`normalizeElectronRuntimeStateSnapshot` 必须显式写 undefined；`mergeState` absent 时 reset |
| `pendingFreshRemoteVideoUntilMs` 窗口（B069） | 切到视频后 2 秒内 negative 信号 skip；positive 信号不清窗，window 自然到期 |

后续切换 / 远端视频 / outgoing pending 类问题先读 [[{NEW_BUG_PATH.stem}]] 与 [[{NEW_QUERY_PATH.stem}]]。B063 提到的 `outgoingSwitchRequestCallType` marker 在 B065 实现时统一命名为 `outgoingSwitchCallType`。""",
    )
    write_text(media_bug, text)

    media_query = wiki_root / "queries" / "electron-switchcalltype-reject-state-and-media-preflight-query.md"
    text = update_frontmatter(read_text(media_query), [f"  - {NEW_BUG_PATH.as_posix()}", f"  - {NEW_QUERY_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-09 后续 outgoing / IPC / window 排查矩阵",
        f"""B065-B069 后排查矩阵新增三行:

| Symptom | First branch |
|---|---|
| 本端发起切换后 UI 立即变 | Check B065 `outgoingSwitchCallType` 不再调用 applyResolvedCallTypeWithNativeVideo |
| 对端响应后 hint 持续显示（macOS） | Check B066 IPC normalize / mergeState cleared 信号 |
| 切到视频瞬间误显"对方关闭了摄像头" | Check B069 `pendingFreshRemoteVideoUntilMs` window，positive 不清窗 |
| 第二次起通话 `rtcInitCompleted` 永远 false | Check B068 EnsureRtcInitialized 复用 engine 分支必须 emit `rtc_init_end` |

State=3 Direction Checklist 的 step 1 应改为匹配 `state.outgoingSwitchCallType`（B065 实装的字段名），而不是早先 B063 草拟的 `outgoingSwitchRequestCallType`。详见 [[{NEW_BUG_PATH.stem}]] 与 [[{NEW_QUERY_PATH.stem}]]。""",
    )
    write_text(media_query, text)

    lesson = wiki_root / "lessons" / "l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离.md"
    text = update_frontmatter(read_text(lesson), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-09 B065-B069 Addendum",
        f"""B065-B069 不推翻三层隔离原则，而是把"主动发起 switch"提升为独立状态机：

- `switchCallType(state=1)` 只发送 native 请求 + 写 `outgoingSwitchCallType`；不再调用 `applyResolvedCallTypeWithNativeVideo`。
- desktop/core `SwitchCallType(state=1)` 同步去掉 `ApplyResolvedSwitchCallType`，只发送 control + 记录 pending outgoing。
- 任何 in-process / IPC / source bridge 修改"outgoing pending 状态"都必须三层一致，并通过 source bridge build + manifest verify。
- 切到视频瞬间的 RTC 抖动（NERTC 7ms 内 start→mute→stop）属于设计内噪声，runtime 层用 2 秒时间窗 guard，positive 信号不清窗。
- 第二次起通话 `rtcInitCompleted` 字段语义错位（native engine reuse 不 emit）必须 native 修，不能在 runtime 用"忽略首次 negative"绕过。

详细排查走 [[{NEW_QUERY_PATH.stem}]]。""",
    )
    write_text(lesson, text)


def update_index(wiki_root: Path, created_bug: bool, created_query: bool) -> None:
    index_path = wiki_root / "index.md"
    text = read_text(index_path)
    increment = int(created_bug) + int(created_query)
    if increment:
        text = re.sub(r"Total pages: (\d+)", lambda m: f"Total pages: {int(m.group(1)) + increment}", text, count=1)
    bug_entry = f"- [Electron 音视频切换等待对端结果与 stale 远端视频窗口（B065-B069）]({NEW_BUG_PATH.as_posix()}) - B065 outgoing pending 字段、B066 IPC cleared 信号、B067 hint 视觉、B068 RTC engine reuse、B069 stale video window。"
    query_entry = f"- [Electron 音视频切换 outgoing 等待与 stale 远端视频排查]({NEW_QUERY_PATH.as_posix()}) - Query filed 2026-05-09 / outgoing/pending marker、IPC cleared、stale video window、RTC engine reuse 排查矩阵。"
    if bug_entry not in text:
        text = text.replace("## Bugs\n\n", "## Bugs\n\n" + bug_entry + "\n", 1)
    if query_entry not in text:
        text = text.replace("## Queries\n\n", "## Queries\n\n" + query_entry + "\n", 1)
    write_text(index_path, text.rstrip() + "\n")


def append_log(wiki_root: Path, raw_created: int, raw_unchanged: int) -> None:
    log_path = wiki_root / "log.md"
    text = read_text(log_path).rstrip()
    marker = "import | <workspace>/project/NECallKit docs B065-B069 switch wait peer + stale video cluster"
    if marker in text:
        return
    entry = f"""

## [{TODAY}] import | <workspace>/project/NECallKit docs B065-B069 switch wait peer + stale video cluster (10 files)
- Format: curated folder batch
- Created: 2 wiki pages
- Updated: 3 existing pages
- Raw: raw/imported/{BUNDLE_NAME}/ ({raw_created} created, {raw_unchanged} unchanged)
- Source groups: B065 outgoingSwitchCallType state machine; B066 IPC normalize cleared signal; B067 hint visual; B068 RTC engine reuse; B069 stale fresh-video window
- Filed: [[electron-switch-wait-peer-and-stale-video-2026-05-09]], [[electron-switch-wait-peer-and-stale-video-query]]
- Updated: [[electron-switchcalltype-media-state-and-reject-semantics-2026-05-09]], [[electron-switchcalltype-reject-state-and-media-preflight-query]], [[l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离]]
- Decision: ingest immediately because the cluster introduces three brand-new concepts (outgoingSwitchCallType field, IPC cleared signal propagation, pendingFreshRemoteVideoUntilMs window) that the existing B059-B063 reject-state pages would otherwise mislead.
"""
    write_text(log_path, text + entry)


def execute(wiki_root: Path, project_root: Path) -> dict[str, object]:
    raw_counts = {"created": 0, "unchanged": 0}
    for source in SOURCE_FILES:
        raw_counts[safe_copy_raw(project_root, wiki_root, source)] += 1

    bug_full = wiki_root / Path(NEW_BUG_PATH.as_posix())
    query_full = wiki_root / Path(NEW_QUERY_PATH.as_posix())
    created_bug = not bug_full.exists()
    created_query = not query_full.exists()
    write_text(bug_full, bug_page())
    write_text(query_full, query_page())
    update_existing_pages(wiki_root)
    update_index(wiki_root, created_bug, created_query)
    append_log(wiki_root, raw_counts["created"], raw_counts["unchanged"])
    return {
        "raw_created": raw_counts["created"],
        "raw_unchanged": raw_counts["unchanged"],
        "created": [str(NEW_BUG_PATH), str(NEW_QUERY_PATH)],
        "updated": [
            "bugs/electron-switchcalltype-media-state-and-reject-semantics-2026-05-09.md",
            "queries/electron-switchcalltype-reject-state-and-media-preflight-query.md",
            "lessons/l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离.md",
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
        "new_pages": [NEW_BUG_PATH.as_posix(), NEW_QUERY_PATH.as_posix()],
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
