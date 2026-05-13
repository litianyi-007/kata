# NECallKit macOS IPC topology 调试套路与修复演进经验

> Dogfood evidence file. Source: codex/Claude Code session
> `<workspace>\project\NECallKit\specs\002-electron-callkit\2026-05-09-162352-necallkit-macos-electron-source-br.txt`
> （macOS 本地复盘，2026-05-09，Overmind ticket <internal-ticket>，
> 贯通 8 commits: `2b44fd87` → `27c5dc04`，对应 wiki cluster 1+3 已 ingest 的
> B066-B070 五个 bug。）
>
> 本文不是 bug 的根因/修复总结（那已经在 wiki 的 B066-B070 page 里），而是
> 收集那些 **bug docs 写不进去但反复有用的调试套路**。下次再有人在 macOS
> 排查 Electron source bridge / IPC 拓扑相关问题时，这是查找路径起点。

---

## 1. macOS Electron 主进程 IPC 拓扑下的"诊断盲区"

`darwin && Electron major >= 24` gate 下，renderer 拿到的是 IPC runtime，
`runtime.sdk === null`。这导致一系列**只在 mac 上发生的诊断盲区**：

### 盲区 1：`getBridgeDiagnostics()` 在 renderer 永远是 null

```js
// macOS DevTools Console
window.$callkit.sdk                         // → null
window.$callkit.sdk.getBridgeDiagnostics()  // TypeError: Cannot read properties of null
```

DebugPanel 里的「Bridge Path」字段在 mac 下**天然为空**——bridge 在主进程
加载，渲染端 sdk 引用是 null，DebugPanel 设计上只读 renderer-side sdk。

历史 e2e log 里 `bridgeDiagnostics: null` 不是 bug，是拓扑差。

### 盲区 2：DebugPanel localStorage key 多了一段 `electron`

```js
// 错（README/老文档里的写法，mac/Windows 都不工作）
localStorage.setItem('necallkit.example-vue3.debug', '1');

// 对（当前 example app.js 重载后的 key）
localStorage.setItem('necallkit.electron.example-vue3.debug', '1');
localStorage.setItem('necallkit.electron.example-react.debug', '1');
```

设完 reload 才生效。Disable cache 也得勾上，避免 reload 走缓存。

### 盲区 3：DebugPanel 没出现 ≠ 修复未生效

DebugPanel 走 renderer，mac 拓扑下哪怕渲染出来 Bridge Path 也是空。
**不要**用 DebugPanel 是否显示作为修复生效的判据。

---

## 2. mac 上验证 source bridge 真的被加载的正确套路

### 套路 A：DevTools Console 读主进程注入的 env（最快）

renderer 开了 `nodeIntegration: true`，可以直接读 `process.env`：

```js
// DevTools Console
process.env.NECALL_DESKTOP_BRIDGE_PATH
process.env.NECALL_NODE_ADDON_PATH
process.env.DYLD_LIBRARY_PATH
```

期望（macOS）：

```text
NECALL_DESKTOP_BRIDGE_PATH = .../Electron/out/native/darwin-debug/libne_callkit.dylib
NECALL_NODE_ADDON_PATH     = .../Electron/out/native/darwin-debug/ne_call_electron.node
DYLD_LIBRARY_PATH 以        .../Electron/out/native/darwin-debug 开头
```

这些 env 由 `Electron/scripts/lib/build-plan.js:1054-1077` 在 `dev:*:source`
启动时注入到子进程，主进程 `host-helper/src/runtime-env.js:131-176` 用它定位
bridge 和 addon。

### 套路 B：直接对 staged dylib 做 strings 验证

native 改动之后想确认"我修的代码进了 dylib 吗"：

```bash
strings Electron/out/native/darwin-debug/libne_callkit.dylib | grep <新事件名>
```

session 里实测对 staged dylib 跑 strings，命中：
- `outgoing_pending_confirm`（B065 新事件）
- `switch_control_auto_agree` / `switch_control_legacy_apply` / `switch_control_peer_response`
- `reuse_engine_emit_rtc_init_end`（B068 新日志行）

`mtime` 和 build 时间一致 + strings 含新符号，等于"native 是最新代码"的硬证据。

### 套路 C：source bridge env 仅在 `:source` 入口注入 — 这是常见误判源

| 命令 | 行为 |
|---|---|
| `npm run dev:vue3:source` | 注入 `NECALL_DESKTOP_BRIDGE_PATH` 等 env，加载 staged source bridge ✓ |
| `npm run dev:vue3` | **不**注入 env，加载 NIM SDK 自带 dylib 或上一次打包残留 ✗ |

`host-helper/src/runtime-env.js:158` 在 `app.isPackaged === false` 时直接返回
原 env，只有 `:source` 入口经过 build-plan 注入。

**常见误判**：用户报"修复未生效"，实际是用了 `dev:vue3` 而不是 `dev:vue3:source`，
加载的根本不是本次修复的 dylib。这次 session 一开始就是这种怀疑（最终排除）。
未来排查必须**先确认入口命令**再深入。

---

## 3. 主进程 stdout 才是 mac 真实日志位置

session 里 runtime 加了 `[runtime-electron][video]` 前缀诊断日志，问"在 DevTools
还是终端看？"答案：**先看主进程终端 stdout**（跑 `npm run dev:vue3:source`
那个终端）。如果 stdout 没有，说明 runtime 实际跑在 renderer（沿用旧链路），
那就在 DevTools Console 看。

mac main-side IPC 模式下 runtime 跑在主进程 → 日志在主进程 stdout；
Windows in-renderer 模式 → 日志在 DevTools Console。

诊断日志默认开启，关闭：

```bash
export NECALL_DEBUG_VIDEO_SWITCH=0   # mac/linux
set NECALL_DEBUG_VIDEO_SWITCH=0      # Windows
```

---

## 4. NERTC 远端视频 7ms 内连抖序列（native 实测证据）

切换到视频后 7ms 内 NERTC 连续推 3 拍事件序列，是 channel 切换 / 远端流
重新订阅过程的"正常"状态报告，不是 bug：

```text
11.723Z  OnRtcUserVideoStart       → onVideoAvailable(true)
11.726Z  OnRtcUserVideoMute(true)  → onVideoMuted(true) + onVideoAvailable(false)
11.730Z  OnRtcUserVideoStop        → onVideoAvailable(false)
```

source 在 `desktop/core/src/call_controller.cpp:5005-5052`
（`OnRtcUserVideoStart` / `Stop` / `Mute`）。
`OnRtcUserVideoMute(muted=true)` 一次回调内 emit 两个事件
（`video_muted(true)` + `video_available(0)`）。

如果未来再看到"切到视频瞬间 InCallOverlay 闪现/持续显示对方关闭摄像头"——
这是同样的连抖序列被错误处理。runtime 必须在 `applyResolvedCallType` 进入
视频模式时开 2 秒 window，期间 negative 信号 skip。

---

## 5. B068/B069 修复演进的"两次回滚"教训

这次 session 在修 B069 时**回滚了两次**，每次都被前一阶段的"看似合理的判据"
反过来打脸：

### 阶段 1：用 `rtcInitCompleted=false` 当判据（被回滚）

直觉：切换瞬间还没 init 完，negative 信号 stale，应该忽略。
代码：`!available && callType===2 && rtcInitCompleted===false → skip`

被反问 "RTC 通话能正常使用，为什么这个字段是 false？"——揭穿 B068：
`onRtcInitEnd` 整个进程生命周期只 emit 一次（首次 engine 创建）；
runtime 每次接通重置 `rtcInitCompleted=false`，所以**第二次起的通话**这条
判据永远命中——会把对端真的关摄像头也吃掉，是回归 bug。

→ 回滚 + 提出方案 A（native 修 emit 语义）vs 方案 B（runtime 标志位时间窗）。
用户选 A："真正的 bug 在 native，字段语义对齐之后整个状态机更可信"。

### 阶段 2：positive 信号到达立即清窗（被 7ms 连抖击穿）

修了 B068 之后加 `pendingFreshRemoteVideoUntilMs` 2 秒窗：apply 时打开窗口，
positive 信号一到立即清窗（"对端真的 ready 了"）。

用户跑日志一贴——窗口在 11.723Z 被 `onVideoAvailable(true)` 立即清掉，
紧接着 11.726Z + 11.730Z 两拍 stale negative 直接通过，UI 又显示
"对方关闭了摄像头"。

→ positive **不代表稳态**，只代表 NERTC 连抖序列的第一拍。

### 阶段 3：positive 不清窗，让 window 自然 2 秒到期（终态 `7a332b93`）

期间任何 negative 都被忠实拦下，UI 维持 apply 时写入的 `Muted=false /
Available=true`。Window 到期后 native 已稳态，后续事件可信。

### 教训

1. **runtime 字段语义如果跨次通话错位，不要在 runtime 写 guard 绕过——回到 native 修语义**。
2. **不要在 native 设计内噪声面前自作聪明地"信任 positive"**——除非有独立的稳态信号，否则用时间窗到期作为唯一解除条件。
3. 加日志默认开是这次找到 7ms 连抖证据的关键。**可观察性 > stdout 噪声**。

---

## 6. mac IPC topology 是 sdk facade 缺口的"放大器"

session 后段触发 B070：用户报 mac 勾选"二次确认"无效，Windows 同代码包正常。

根因：`Electron/example-vue3/src/renderer/app.js:482` /
`Electron/example-react/src/renderer/main.js:598`：

```js
function syncCallConfig() {
  if (!runtime.sdk || typeof runtime.sdk.setCallConfig !== 'function') {
    return false;       // 静默 no-op
  }
  runtime.sdk.setCallConfig(nextCallConfig);
}
```

mac IPC 拓扑下 `runtime.sdk === null`，guard 直接 return，设置永远没到 main
进程的 native runtime。Windows in-renderer 拓扑 sdk 不为 null，行为正常。

`electron-macos-mainthread-native-owner-analysis-2026-05-08.md` §11.2 表格的
"example 直连 `runtime.sdk.*`" 风险条目早就预见了这一类问题——这次踩到的
是 `setCallConfig` 这一个具体方法。

### mac IPC 风险清单（同类 facade 缺口）

任何 example renderer 直连 `runtime.sdk.*` 的方法都属于同类风险。已知：

- `setCallConfig` ✓ 已修（B070, e37c7de6）
- `setTimeout` ✓ 已修（B070 顺手）
- `setCallRecordProvider`（`syncDefaultCallRecordProvider`）— **未修**，已知风险点

未来"mac 打包后某项配置失效，Windows 正常"现象 → 第一嫌疑是 `runtime.sdk.X`
直连。修复模板：runtime-level facade + main service IPC dispatch + IPC runtime
adapter + example renderer 优先 facade fallback sdk。

### 顺带踩的连带 contract test 失败

B070 修复时把 `createRuntimeState()` 中扩展字段的 `undefined` 预置删掉了——
这是被 B066 的 normalize 修复**间接拉爆**的：B066 让 normalize 在 hasOwnProperty
时显式写 undefined，所以预置 undefined 会让初始 snapshot 多出两个 keys，
破坏 callkit-domain MINIMAL contract（`runtime-contract.test.ts:130`）。

**教训**：state-machine 字段在跨包 contract 里有 minimal-keys 约束时，
"显式 set undefined" 和 "absent" 不能混用。修一头要查另一头。

---

## 7. knock-it-out 流程在这次 session 的真实形态

回看 8 个 commit 的产出节奏：

```text
[用户报现象] → [Claude 假设排查路径] → [复现验证] → [发现新 bug]
   ↓                                                       ↓
[修复尝试] ← [用户贴 state/log] ← [测试不通过 → 回滚] ←──┘
   ↓
[修复合入 + 边发现新现象 / 新 bug 或同类风险点]
   ↓
... 重复 5 次 ...
   ↓
[用户："整理成文档记录下来"] → [B066-B069 docs commit]
   ↓
[再发现一个新 bug B070] → [修 + docs commit]
```

观察：

1. **单一 ticket（<internal-ticket>）贯通整条修复链**——commit 全部挂同一 ticket，
   方便回溯整轮修复的 narrative。
2. **docs 在末尾整理**——边修边写 docs 会让 docs 反复改写，等修复链稳定后
   一次性归档更干净。这次先把 5 个 fix commit 推完，再 `2d19d750` docs 一次
   commit 归档 B066-B069。B070 后修后归档同样模式。
3. **commit 拆分**：5 个修改文件 + 4 篇新增 docs 自动合并时，Claude 用
   `git stash push -u --message "stash docs for split commit"` 拆成两次提交
   （一次 feat 修复、一次 docs 归档），主题独立，diff 干净。这是个有用的
   workflow patten 模板。
4. **从 wiki ingest 的视角看**：5 个 bug 中**有 4 个**是这次 session 才被
   发现/修完/有 docs 的（B066/B067/B068/B069+B070），只有 B065 是上一轮
   遗留待 ingest 的。说明在 mac 复盘上的"一次复盘揭穿一连串问题"是高产模式。

---

## 8. 复盘 query 命中度（dogfood evidence）

如果这些套路被以后的 query 命中，说明 wiki 闭环成立。本文不是 wiki 主页，
但应作为 mac IPC 类问题的**参考索引**。建议：

- 本文未 ingest 进 wiki（依规则：只有 NECallKit repo 内的 docs/bugfix 才 ingest）。
- 但如果未来 user 在 mac 上再次遭遇 `runtime.sdk===null` / DebugPanel 空 / source
  vs packaged bridge 误用——这些套路能直接用，省 30+ 分钟摸索时间。
- HN essay 写"AI 写 wiki，AI 维护 wiki" 故事时，§5 的"两次回滚"段是
  最具体的 evidence material。

---

## Appendix: session 关键事件抓取的"决定性 state"

### B065 验证用的双端 state（pending 期）

```text
caller: callType=2, callInfo.callType=2, outgoingSwitchCallType=1, callStatus=3
callee: callType=2, callInfo.callType=2, pendingSwitchCallType=1,  callStatus=3
```

### B066 错误现场（修前）

```text
B 同意:
  A: { callType:1, callInfo_callType:1, outgoingSwitchCallType:1, callStatus:3 }   ← outgoing 残留
  B: { callType:1, callInfo_callType:1, callStatus:3 }                              ← pending 字段被 stringify 省略 (实际残留)

B 拒绝:
  A: { callType:2, callInfo_callType:2, outgoingSwitchCallType:1, callStatus:3 }   ← outgoing 残留
```

### B069 错误现场（修前）

```text
{
  "callType": 2, "callInfo_callType": 2, "callStatus": 3,
  "connected": true,
  "remoteVideoAvailable": false, "remoteVideoMuted": true,
  "localVideoEnabled": true, "rtcInitCompleted": true
}
```

`callType=2 && rtcInitCompleted=true` 都已稳态，但 `remoteVideoMuted=true /
Available=false` 残留——`InCallOverlay` 中 `remoteVideoClosed = connected &&
callType===2 && remoteVideoMuted` 判据命中误显。
