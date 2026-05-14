# F016 dev-launch autonomous prompt — Electron Vue2 UIKit reuse

> Self-contained prompt for a **fresh session** in `<workspace>\project\NECallKit`.
> Paste the block below verbatim. The agent reads the worksheet, asks you 4
> product questions (with default = recommendation), then mechanically promotes
> the wiki decision, materializes the NECallKit PRD, and starts coding
> `packages/callkit-vue2-core`. No file-juggling required from you.

---

## Copy-paste block (paste into a fresh Claude Code or Codex session)

```
你是 F016 (Electron Vue2 UIKit Reuse) 的自主开发驱动 agent。本次任务的目标是把 F016
从"决策待定 + spec 已成"状态，推进到"代码 callkit-vue2-core 1v1 落地"状态。
我（user）只回答 4 个产品决策问题，其他都由你机械执行，不要等我授权。

## 已确定的上下文（不要重新验证）

- F016 spec 已由 Codex session 019e2234-... 在 2026-05-14 00:42 完成
- 经过 wiki-tier pin + search rank fix 后，rerun confidence = 0.82 (High)
- 推荐架构已锁定：Vue2 shared core (callkit-vue2-core) + Web/Electron 双薄 wrapper
- 4 个关键架构页已 pin 为 active：
  - modules/necallkit-architecture-overview
  - modules/electron-web-api-reuse-and-merge-back-switch-contract
  - modules/002-electron-callkit-contracts-electron-web-unified-public-contract
  - features/002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20
- 4 个待决策问题已整理在 wiki 工作表：
  `~/.llm-wiki/NECallKit/queries/F016-electron-vue2-uikit-reuse-open-questions-query.md`
- 当前 NECallKit 仓库 branch: 002-electron-callkit-reuse-enhance（默认沿用）

## 第 1 步 — 读取工作表（自动，无需提问）

Read `~/.llm-wiki/NECallKit/queries/F016-electron-vue2-uikit-reuse-open-questions-query.md`
完整内容。注意其中"Answer / Recommended decisions"表，以及每个 Q 的影响表和
推荐答案。

## 第 2 步 — 问我 4 个决策（一次性，不要碎片化）

把 4 个问题打包到**同一条消息**里，编号清晰（Q1 / Q2 / Q3 / Q4）。每个问题：
- 默认选项 = 工作表推荐
- 推荐选项写"(推荐)"
- 简短描述决策影响
- 答案接受形式：`Q1=A, Q2=B, Q3=A, Q4=A` 或单独逐条 `Q1: 接受推荐`

不要分 4 次问。一次性输出，等我一次性回。

4 个问题：

  Q1: Vue2 是正式 Electron 交付包 OR 内部 demo？
      A. 正式包 (推荐) — 发布矩阵 2 SDK × 6 UIKit
      B. 内部 example only — 矩阵不变
      C. 阶段性 — 先 example 后 promote

  Q2: 是否把 Web/basic-vue2 拉进 electron-web-unified-public-contract？
      A. 拉进合同 — 合同需扩展，工作量 +30%
      B. 不拉入但允许 thin-wrapper 化 (推荐) — 合同不动
      C. 不动 basic-vue2 — wrapper 化也不做

  Q3: 是否新增 Electron/example-vue2？
      A. 新增 (推荐) — clean-consumer 验收 + release artifact 完整
      B. 不新增 — UIKit 自带 sandbox 仅 dev 用

  Q4: Electron Vue2 scope？
      A. 仅 1v1 (推荐) — 与 Electron Vue3 对齐
      B. 1v1 + 群呼 — 打破现网平台分层
      C. 阶段性 — 先 1v1 后续版本扩展

也接受快捷答复：如果用户回复"全部按推荐"或"use all defaults"，自动把 4 个答案锁定为推荐。

## 第 3 步 — 把决策回填进 wiki 工作表（机械操作）

收到答复后立即：

3a. Edit `~/.llm-wiki/NECallKit/queries/F016-electron-vue2-uikit-reuse-open-questions-query.md`，
    填写底部的"Decision capture template"表格。决策者写"user"，日期写今天。

3b. 把文件改名 + 移动到 decisions 目录：
    git mv (或 mv) `queries/F016-electron-vue2-uikit-reuse-open-questions-query.md`
              `decisions/F016-electron-vue2-uikit-reuse-resolved.md`

3c. Edit 新文件 frontmatter：
    - `type: queries` → `type: decisions`
    - `tier_override: active` → 删除整行（decisions 自然 tier，不需要 pin）
    - `tier_reason: ...` → 删除整行
    - 在 description 或 title 末尾 append " — RESOLVED 2026-05-14"

3d. Edit `~/.llm-wiki/NECallKit/index.md`：
    - 把 queries 区那行 F016 移除
    - 在 decisions 区加新条目：
      `- [F016 Electron Vue2 UIKit Reuse — 决策已落定](decisions/F016-electron-vue2-uikit-reuse-resolved.md) - Decision filed 2026-05-14 / 4 个核心决策已锁定，dev 启动 gate 已清`

3e. Append 到 `~/.llm-wiki/NECallKit/log.md` 顶部（紧跟现有 2026-05-14 那条之后）：
    ```
    ## [2026-05-14] promote | F016 Electron Vue2 UIKit Reuse open-questions → resolved
    - Page: [[F016-electron-vue2-uikit-reuse-resolved]] (was queries/F016-...-open-questions-query)
    - Trigger: 4 个产品决策已由 user 回答；dev gate 清除
    - Updated: frontmatter type queries→decisions, tier_override removed
    - Updated: index.md (moved entry from queries section to decisions section)
    - Schema: no change
    ```

## 第 4 步 — 物化 F016 PRD 到 NECallKit 仓库（机械操作）

在 NECallKit 仓库（cwd 应该已经在那）：

4a. mkdir `docs/prd/F016-electron-vue2-uikit-reuse/`

4b. Write `docs/prd/F016-electron-vue2-uikit-reuse/TRACKER.md`，包含：
    - Status: in-progress
    - Created: 2026-05-14
    - 4 locked decisions（Q1-Q4 答案 + 一行 rationale）
    - 关联 wiki: kata wiki `decisions/F016-electron-vue2-uikit-reuse-resolved.md`
    - F016 spec 来源: Codex session 019e2234-..., 2026-05-14 00:42
    - 预估 milestone: callkit-vue2-core (1v1) → Web wrapper → Electron UIKit → example-vue2
      （如 Q3=B 则跳过最后一步）
    - 风险登记: 如 Q2=A 则 +30% 工作量（合同对齐），如 Q4=B 则打破平台分层（建议升级提醒）

4c. Write `docs/prd/F016-electron-vue2-uikit-reuse/TASKS.md`，按 F016 spec 拆解为 6 个 task：
    - [ ] T1: 抽 packages/callkit-vue2-core（仅 1v1 / 仅 vue3-core 对应 surface）
    - [ ] T2: Web/basic-vue2/call-kit-ui 改为 thin wrapper（消费 vue2-core + runtime-web）
    - [ ] T3: 新增 Electron/vue2-uikit（消费 vue2-core + runtime-electron）
    - [ ] T4: (条件) 新增 Electron/example-vue2（仅 Q3=A 时）
    - [ ] T5: 构建脚本 `build/package:electron-vue2-uikit` + Web `package:web-vue2-uikit`
    - [ ] T6: 测试覆盖 — core SSR/render、public surface、wrapper thinness、release artifact、example smoke

## 第 5 步 — 启动编码：T1 packages/callkit-vue2-core

5a. 先用读源码三件套了解参考实现（不要重做 spec 分析，只读）：
    - packages/callkit-vue3-core/src/components/CallView*.ts
    - packages/callkit-vue3-core/src/composables/* (useCall / useCallState / useCallkitRuntime)
    - packages/callkit-runtime-electron/src/runtime.ts

5b. 创建 packages/callkit-vue2-core/ 工程目录：
    - package.json: peer vue@^2, dependencies 沿用 vue3-core 的 callkit-runtime-* 模式
    - tsconfig.json: 沿用 packages/ 现有 ts 配置
    - src/index.ts: 导出公开 surface（与 vue3-core 同形，但 Vue2 API）
    - src/components/CallView.vue: 1v1 主视图，Vue2 Options API（不要用 Composition API plugin）
    - src/composables/use-call.ts → src/use-call.ts: Vue2 用 mixin 或 reactive helper，不用
      @vue/composition-api 插件以减少依赖
    - 拒绝复用 vue3-core 文件（peer Vue3 + Fragment 语义不可移植）

5c. 提交第 1 个 commit:
    `feat(F016): bootstrap packages/callkit-vue2-core (1v1, T1)`
    包含 package.json、tsconfig、index.ts 公开 surface 占位、CallView.vue 骨架

## 不要做的事

❌ 不要重跑 wiki-search 验证 F016 上下文（pinned 页第一次命中即可）
❌ 不要重新分析 F016 spec（已锁定 0.82 confidence）
❌ 不要扩展 scope 到群呼（除非 Q4 = B/C）
❌ 不要修改 electron-web-unified-public-contract.md（除非 Q2 = A）
❌ 不要修改任何 React / Vue3 路径（F016 隔离原则）
❌ 不要使用 git --no-verify 提交（pre-commit hook 用来保护合规）
❌ 不要切换 git 用户身份
❌ **不要运行 `npm install` / `yarn install` / `pnpm install` / `pnpm add` 等
   依赖安装命令**。T1 复用 monorepo 已有的 callkit-runtime-* + Vue2 runtime
   sufficient。如真需要新依赖，STOP 并把"新依赖 + 必要性 + 影响"清单发回给我，
   我审批后再装。这条 ban 防止悄悄拉入 @vue/composition-api / @vue/composition-api
   适配器之类的 Vue3→Vue2 桥接库（明确反对）。

## STOP 并升级的条件

发生以下任一情况，立即 STOP 并把问题发回给我：

- 任何答案触发 Q2=A 的合同扩展，但 callkit-runtime-electron 接口与合同需同步变更
- pre-commit hook 拒绝（不是预知的 Test 17 wiki_init 失败）
- T1 编码过程发现 vue3-core 的某个抽象在 Vue2 下需要 fundamentally 重新设计（不是
  porting）
- 任何超出 F016 scope 的修改提案（如改动 SDK 层、改动其他平台 UIKit）
- 任何 commit 信息草稿包含 @netease 邮箱、F:\\workspace\\ai\\ 类绝对路径
- 需要新依赖（任何 `npm/yarn/pnpm install` 或 `add` 调用）

## 报告格式

每完成一个步骤（第 3a~3e、第 4a~4c、第 5a~5c），用一行简短报告。
完成第 5c 后输出一个"DONE — F016 dev launch complete"总结，列出：

- 4 个决策的最终答案
- 改名为 decisions/ 的 wiki 路径
- 创建的 NECallKit PRD 路径
- 第 1 个 callkit-vue2-core commit 的 SHA
- 下一步建议（T2 还是先做更多 core？）
```

---

## When to use this prompt

- Fresh **Codex Desktop** session in `<workspace>\project\NECallKit` (NOT kata repo)
- Codex's `AK_WIKI_HOME` install is still pre-rebrand (task #15 open), but **this prompt does NOT call `wiki-search`** — it reads files directly via paths. So the stale install doesn't taint this run.
- The prompt expects Codex's batched-question pattern (one message with Q1-Q4 labels, you reply once with all answers). If you'd rather break it into 4 separate exchanges, just answer one at a time — the agent will adapt.
- Codex will use its own `shell_command` / `update_plan` tools for file ops; no Claude-specific tooling assumed.

## What happens after you paste it

```
Agent              You
─────              ────
reads worksheet
asks 4 Qs ────────► answer (or "全部按推荐")
3a..3e             (silent — file ops)
4a..4c             (silent — file ops)
5a..5c             (silent — code)
DONE summary ─────► review + decide T2 vs more core
```

Total elapsed: ~15 min (your input) + ~30-45 min (agent work) = roughly an hour to first commit.

## Open questions before you run it

<function_calls>
<invoke name="AskUserQuestion">
<parameter name="questions">[{"question": "Agent for the new session?", "header": "Agent choice", "multiSelect": false, "options": [{"label": "Claude Code (recommended)", "description": "Kata plugin cache is fresh (v2.1.0 after your /plugin reinstall). File ops + bash + AskUserQuestion all work cleanly. Same tooling you're using now."}, {"label": "Codex Desktop", "description": "Stale AK_WIKI_HOME doesn't affect this prompt (no wiki-search call). Works fine. Slightly different UX for AskUserQuestion-style prompts — may unfold sequentially."}, {"label": "Either, you decide on the fly", "description": "Keep the prompt agent-neutral. I'll add no agent-specific guidance, you pick whichever has the file open."}]}, {"question": "Decision-question gate — ask all 4 in one batch, or sequentially?", "header": "Q-flow", "multiSelect": false, "options": [{"label": "All 4 in one AskUserQuestion call (recommended)", "description": "Faster, fewer roundtrips. Defaults to recommendations — you can hit 'accept all' shortcut. Current prompt is written this way."}, {"label": "Sequential, one Q at a time", "description": "Slower but lets you think before each. Useful if you want to flip a recommendation and see whether it changes downstream Qs."}]}, {"question": "Should the prompt also ban running `npm install` / `yarn install` until you approve?", "header": "Dep policy", "multiSelect": false, "options": [{"label": "Ban dep install in this session (recommended)", "description": "T1 bootstrap doesn't need new deps — it reuses callkit-runtime-* already in the monorepo. Adding the ban prevents the agent from pulling in unwanted libs (e.g. @vue/composition-api which the prompt explicitly rejects)."}, {"label": "Allow if the agent justifies it", "description": "Trust the agent to add deps when needed. You'll see them in the commit diff."}]}]