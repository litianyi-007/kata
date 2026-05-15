# v1.6 Dogfood 平台中立执行手册

目标：用 4 周真实工作流验证 auto-dreaming 是否能帮助
“AI / 大模型应用创新”研究。平台不重要，关键是所有有价值的
探索、信息获取、研究综合、讨论结论，最后都要落成 wiki 文件。

## 0. 原则

dogfood 不是 Claude Code dogfood，而是 kata 工作流 dogfood。

- 可以在 Claude Code、Codex CLI、Grok、网页 LLM、Obsidian、浏览器搜索里探索。
- 只有进入 wiki 的文件才会影响 `wiki-search`、`wiki-query`、`wiki-digest`、`wiki-dream`。
- 外部会话记录不要当作“隐式记忆”。需要复用的结论必须导出到 `raw/`、`briefs/`、`discussions/`。
- auto-dreaming 只读 wiki 文件系统，不读任何平台的聊天历史。

## 1. 开始前

1. 用 `templates/market_research/SCHEMA.md` 初始化或更新真实 wiki。
2. 确认 `SCHEMA.md` 里 `dreaming.enabled: true`。
3. 确认 dogfood 期间参数不改：

```yaml
confidence_threshold: 0.6
weights:
  entity: 0.5
  tag: 0.2
  citation: 0.4
resurgence:
  dormancy_window_days: 90
  min_count: 2
max_repromote_per_run: 10
```

4. 在 [dogfood-v1.6.md](dogfood-v1.6.md) 填 Wiki 路径、启动日期、首页页面数、tier 分布。
5. 选择一个执行宿主：Claude Code、Codex CLI、或 standalone prompt。
6. 选择一个调度方式：平台内 schedule、系统 cron / Task Scheduler，或每周手动运行。

## 2. 平台路径

### Claude Code

适合完整插件体验和 `/kata:*` slash command。

```bash
claude /plugin marketplace add surebeli/kata
claude /plugin install kata@kata
```

可选调度：

```bash
claude /schedule "0 23 * * 0" "/kata:wiki-dream"
```

### Codex CLI

适合把 kata 放进一个普通项目目录，用 `AGENTS.md` 和本地 skills 驱动。

在真实 wiki 根目录执行：

```bash
git clone https://github.com/surebeli/kata
cp kata/plugin/AGENTS.md ./AGENTS.md
cp -r kata/plugin/skills ./skills
cp -r kata/plugin/scripts ./scripts
```

之后在 wiki 根目录运行 `codex`。如果 Codex CLI 没有 slash command
路由，就用自然语言点名 skill，例如：

```text
Use the wiki-ingest skill to ingest raw/articles/2026-04-26-mcp-roundup.md.
Use the wiki-dream skill and run the weekly dry run.
Use the wiki-query skill to answer: "What changed in MCP adoption this week?"
```

脚本也可以直接跑，用于 dogfood 的机械步骤：

```bash
python scripts/wiki_dream.py --wiki . --out dreaming/latest.json
python scripts/wiki_watch.py --wiki . status
```

### Standalone / Any LLM

适合 Grok、网页 LLM、临时研究会话。把根目录 `SKILL.md` 作为系统说明或附件给模型，然后要求它把结果输出为可保存的 markdown。

平台外讨论结束后，不要只保留聊天链接；把结果导出到 wiki：

- 原始会话：`raw/transcripts/YYYY-MM-DD-topic.md`
- 研究综合：`briefs/YYYY-MM-DD-topic.md`
- 可复用讨论：`discussions/YYYY-MM-DD-topic.md`
- 外部搜索输出：`raw/external/{tool}/YYYY-MM-DD-topic.md`

## 3. Grok / 外部会话导出规范

如果你在 Grok 或其他平台探索问题，下载 session 记录后按这个格式保存：

```markdown
---
title: "Grok session: MCP adoption questions"
type: discussion
tags: [discussion, mcp, agents, research-question]
created: 2026-04-26
source_platform: grok
signal_type: discussion
evidence_level: speculative
---

# Context

这次会话要解决的问题是什么？

# Useful Claims

- 结论 1：...
- 结论 2：...

# Sources Mentioned

- URL / paper / product page

# Decisions

- 之后要追踪什么？
- 哪些判断需要回到原始资料验证？

# Follow-ups

- [ ] 后续问题 1
- [ ] 后续问题 2

# Transcript

粘贴或链接导出的原始 session 内容。
```

判断规则：

- 如果只是原始聊天记录，放 `raw/transcripts/`，再 ingest。
- 如果已经整理成可复用研究结论，直接放 `briefs/` 或 `discussions/`。
- 如果有未经验证的推断，标 `evidence_level: speculative`，不要写成事实。
- 如果会话里引用了外部来源，优先把来源本身也放进 `raw/articles/` 或 `raw/external/`。

## 4. 每周输入

每周至少让 wiki 看到三类真实输入：

- 信息获取：文章、论文、访谈、网页搜索、Grok/Codex/Claude 外部探索结果。
- 研究综合：阶段性分析写入 `briefs/`、`trends/`、`comparisons/`。
- 讨论沉淀：有复用价值的结论、假设、分歧、后续问题写入 `discussions/`。

不要只喂新闻链接。这个 dogfood 要验证“研究 + 信息获取 + 讨论”是否能形成闭环。

## 5. 每周运行

推荐节奏：

1. 收集本周来源到 `raw/`。
2. 对新来源执行 ingest，或用 watcher drain。
3. 把外部平台讨论整理进 `briefs/` / `discussions/`。
4. 运行 dry-run dream。
5. 周一审阅 `dreaming/{YYYY-MM-DD}.md`。

Claude Code：

```bash
/kata:wiki-watch --status
/kata:wiki-watch --drain
/kata:wiki-dream
```

Codex CLI / 脚本直跑：

```bash
python scripts/wiki_watch.py --wiki . status
python scripts/wiki_dream.py --wiki .
```

如果平台没有 watcher skill，就手动把文件放入 `raw/` 后让 agent 执行 `wiki-ingest`；watcher 不是 dogfood 的硬依赖。

## 6. 每周审阅

1. 打开 `dreaming/{YYYY-MM-DD}.md`。
2. 对每个候选页做三类判断：
   - accept：确实应该回到 active，执行 `--apply --pages N`。
   - reject：不该回来，不执行 apply。
   - unsure：暂不 apply，但在备注里写为什么犹豫。
3. 把每个候选页记录到 [dogfood-v1.6.md](dogfood-v1.6.md) 的当周表格。
4. 对“意外有用”的候选，写清楚触发价值：旧模式、旧框架、旧讨论，还是补足了新研究上下文。
5. 对“噪音”候选，写清楚误报类型：同名实体、泛标签、旧讨论过期、引用关系太弱等。

## 7. 判定标准

4 周结束后看这些指标：

- 接受率 >= 60%。
- 单次候选 <= 10。
- `--apply` 错页次数 = 0。
- 至少出现若干个“如果没有 dreamer 我不会想起来”的候选。
- 信息获取、研究综合、讨论沉淀三类输入中，至少有两类能产生有价值的候选。
- 至少有一次来自非 Claude Code 平台的 session 导出进入 wiki，并在搜索、查询或 dreaming 中产生复用价值。

没有候选不算失败；候选很多但大多没用才是失败信号。

## 8. 期间禁止

- 不改 dreaming 权重、阈值、resurgence 参数。
- 不启用 auto-apply。
- 不把场景扩到个人笔记、纯论文库、代码知识库。
- 不把平台聊天历史当成默认可用记忆。
- 不因为一周结果差就调参；写进备注，周 4 统一复盘。

## 9. 复盘输出

周 4 结束后产出三件事：

- 参数建议：阈值、权重、dormancy、min_count 是否调整。
- 场景建议：哪些页面类型最有价值，哪些应该少建或不建。
- 平台建议：Claude Code、Codex CLI、Grok / 外部会话导出各自的摩擦点。
- 产品建议：v1.7/v1.8 是否需要 reject feedback、第二策略、session-import helper、或者更强的讨论页处理。
