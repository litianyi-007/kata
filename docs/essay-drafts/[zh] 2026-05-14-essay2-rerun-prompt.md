# 重新运行提示后置顶 — 为论文 #2 收集前后对比证据

将以下代码块粘贴到 NECallKit 项目工作目录下新建的 Codex / Claude / agent 会话中。该 agent 不应有任何先前的

对话上下文——这正是关键所在。我们希望它与 2026-05-14 00:42 的原始会话具有相同的冷启动行为。

---

## 提供给代理的背景信息（逐字粘贴）

```
你正在进行一项受控的重复实验，用于撰写一篇关于kata狗粮的文章。

## 背景介绍（只需阅读一遍，无需执行）

2026年5月14日00:42 +08:00，在同一NECallKit工作目录中，一个新的Codex会话运行了`knock-it-out`技能，以指定一个新的
任务：将Electron Vue2 UIKit的重用与现有的Vue3路径对齐。

代理遵循kata“先看wiki，后看源代码”的规则，在读取任何
源代码之前，针对`~/.llm-wiki/NECallKit`发出了三个

wiki搜索查询。

该会话的结果（分级模型和排名修复之前）：

查询 1：“Electron Vue2 web-vue3 reuse vue3-uikit”

查询 2：“electron web reuse thin wrapper shared core”

查询 3：“Web basic-vue2 Vue2 demo callkit-vue2-ui”

查询总命中数：30（每个查询 10 次）

有效命中数：2 / 30

已存档命中数：28 / 30

客服人员自评信心：0.66（中等）

该代理人在那次会议中的自我评估原文：

  "wiki 命中很强，但多数是归档层资料；这意味着它能给架构边界，
   不足以直接决定今天这条 Vue2 新任务。"

从那时到现在，两件事发生了变化：

1. 四个架构稳定的 wiki 页面被固定到活动层级

通过 frontmatter 中的 `tier_override: active`：

- modules/necallkit-architecture-overview.md

- modules/electron-web-api-reuse-and-merge-back-switch-contract.md

- modules/002-electron-callkit-contracts-electron-web-unified-public-contract.md

- features/002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20.md

2. `search_naive.py` 获得了层级感知排名修复（活动层级 > 已归档层级

作为标签匹配后的平局决胜因素）以及 JSON 输出中的 `tier_breakdown` 聚合



你的任务——不要重新推导 F016 规范

00:42 会议中提出的 F016 规范已被接受。我们不需要新的规范。我们只需要论文中一个前后对比的证据点。



严格按照以下步骤操作，顺序不变，然后停止：

1. 按照与 00:42 会话相同的顺序运行三个 wiki 搜索查询。

使用 `--tier all --limit 10`。捕获 JSON 信封，

分别针对：tier_breakdown、low_active_coverage 和前 10 名列表，

显示每个结果的层级标签。

2. 对于每个查询，请用一句话将其与之前的状态进行比较：

- “之前：X 处于活动状态 / Y 已归档到池中。之后：A 处于活动状态 / B 已归档

到池中。前 10 个活跃查询的数量：之前为 M，现在为 N。”

3. 请分别阅读以下三页内容（无需阅读其他内容）：

- modules/necallkit-architecture-overview.md

- modules/002-electron-callkit-contracts-electron-web-unified-public-contract.md

- features/002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20.md

请仅回答以下问题，答案需包含一个数字和一句简短的理由。



“如果您现在仅使用维基百科和这三页内容重新制定 F016 的规格，您对该建议的信心程度如何？

（使用与上次会议相同的 0.0-1.0 评分标准）

与 0.66 相比。”

4. 最后输出：一个格式完全相同的单个数据块：

```

重新运行证据 — 2026-05-14 pin-and-rank

----------------------------------------

查询 1 ("Electron Vue2 web-vue3 reuse vue3-uikit"):

之前: { active: __, archived: __ }

之后: { active: __, archived: __ }

前 10 名 active: __ -> __

查询 2 ("electron web reuse thin wrapper shared core"):

之前: { active: __, archived: __ }

之后: { active: __, archived: __ }

前 10 名 active: __ -> __

查询 3 ("Web basic-vue2 Vue2 demo callkit-vue2-ui"):

之前: { active: __, archived: __ }

之后: { active: __, archived: __ }

前 10 名 active: __ -> __

置信度重测：

之前：0.66（中等）

之后：__.__（___）

增量：+__.__

理由（一句话）：

“________________________________________________________”

```

## 约束条件

- 请勿阅读源代码（包括 package.json 和 vite.config.ts）。

- 请勿提出新的规范。

- 如果结果较少，请勿进行方向调整——这正是重新运行的目的。

- 如果维基搜索返回 0 个结果，请以数字形式报告，

请勿尝试使用重新措辞的关键词。

- 解释说明可以使用中文或英文——请与上一会话的语言保持一致（中文）。



## 为什么这很重要

这条证据将用于一篇HN文章，文章探讨了维基系统的设计缺陷是如何通过AI的诚实行为暴露出来的。之前的数字（0.66）已经公布。之后的数字是重新运行的结果。我们需要这两个数字，并且要保证证据链的完整性。



---

## 如何处理输出

特工完成后，复制“RERUN EVIDENCE — 2026-05-14 pin-and-rank”
块。它直接作为“后缀”编号插入到论文#2 §④中，

替换占位符。

如果置信度变化值**低于 +0.10**，这也是一项真实的发现——请如实将其写进文章中。论点两种写法都适用，

（“修复使维基百科明显更好”或“修复改善了表面信号，但并未改变答案的置信度”）。两者都是有效的论文素材；只是表述方式不同。

## 可选：捕获会话

通过 `~/.codex/sessions/` 运行代理，以便保留 jsonl 文件。

文章引用了原始 00:42 会话的 jsonl 文件路径；引用重新运行的 jsonl 文件路径，可以为读者提供完整的可复现步骤。

