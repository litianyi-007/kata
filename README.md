# Kata

**给 AI 结对编程用的项目记忆——一次编译、持续更新，人类提问、AI 维护。**

[![tests](https://github.com/litianyi-007/kata/actions/workflows/test.yml/badge.svg)](https://github.com/litianyi-007/kata/actions/workflows/test.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-22d3ee.svg)](LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude_Code-plugin-22d3ee.svg)](https://github.com/litianyi-007/kata#installation)

![Kata — compile business semantics for AI-paired engineering. An AI-maintained wiki for project memory.](docs/assets/readme/kata-hero-banner.svg)

## 它解决什么

项目积累的判断——为什么这个阈值是这个数、上一次这个方案被否是因为什么——散在聊天记录、
散在没人再打开的文档里。每次换一个 agent 会话，这些东西都要重新现学一遍，或者干脆没学到，
然后同一个错误又踩一遍。

kata 是一个 **AI 维护、人类提问的 wiki**：源自
[Karpathy 的 LLM-Wiki 构想](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)——
「不像 RAG，wiki 是编译一次然后保持更新的」「你（人类）负责挑素材、问好问题，剩下的交给 LLM」。
kata 在这个构想之上加了一个**自我闭环**：ingest → 交叉链接 → 有价值的问题被归档成 hub 页 →
下一个 session 直接读 hub 再动手。

一次实测：在 NECallKit（多平台 Electron + native SDK）的 4 周 dogfood 里，一次被归档的问题
（filed query）让 wiki 多长出 **17 条边**——而普通 import 平均每页只带来 5 条边。三个真实
bug（B066/B070/B074）、一个 wiki。细节见
[Essay #1 草稿](docs/essay-drafts/2026-05-13-essay1-code-quality-vs-business-DRAFT.md)。

![One filed query, +17 edges. Imports averaged 5 edges per page. The wiki grows when you ask it questions, not when you load it.](docs/assets/essay/V1-wiki-compounding.svg)

### 跟邻居们比

|                        | kata                             | Obsidian Copilot / Smart Connections | MCP memory servers | RAG / 向量库        |
|------------------------|-----------------------------------|---------------------------------------|---------------------|----------------------|
| 真相落在哪             | 你的 markdown 文件                | 你的 markdown 文件                    | server 端存储       | embedding 索引        |
| 编译一次还是每查一次   | 编译一次，持续更新                | 每次查询现算                          | 每次查询现算        | 每次查询现算          |
| 交叉引用               | ingest 时写进页面                 | 从 embedding 现算                     | 无或 schema 定型     | 无                    |
| 离线可用               | 是（不需要 embedding 模型）        | 需要 embedding 模型                    | 需要 server         | 需要 embedding 模型    |

kata 把综合结果**烤进了 wiki 本体**；RAG 和聊天记忆每次都要重新现算一遍——对流动检索来说很好，
但交叉引用从来没有落地，所以不会越用越厚。

## 快速开始

前置条件：Git ≥ 2.20（v1.8 sync 自定义 merge driver 需要）；Python 3.10+（纯 stdlib，
`plugin/scripts/` 下的脚本不需要 `pip install`）。

kata 有**四条并行的安装路径**——挑一条匹配你的 LLM 工具。四条路径产出**同样的 18 个
skill**和**同样的 wiki 文件系统布局**；wiki 内容本身永远单独放在 `~/.llm-wiki/<project>/`，
跟你选哪条安装路径无关。

| 路径 | 工具 | 安装位置 | 范围 |
|---|---|---|---|
| A | Claude Code（推荐） | `~/.claude/plugins/`（由 `claude /plugin install` 管理） | 全局 |
| B | Codex CLI | `~/.codex/skills/` + `~/kata/`（生成的 skills + 环境变量） | 全局 |
| C | Standalone（任意 LLM） | 粘贴进会话作为 system prompt | 单次会话 |
| D | GitHub Copilot CLI（v2.15.2+） | `~/.config/github-copilot/copilot-cli/`（由 `copilot plugin install` 管理） | 全局 |

**Path A — Claude Code：**

```bash
claude /plugin marketplace add litianyi-007/kata
claude /plugin install kata@kata
```

本地 clone 上直接改插件：`claude /plugin marketplace add .` 之后 `./plugin/skills/` 里的
改动无需重装即可生效。更新/卸载：`claude /plugin update kata` / `claude /plugin uninstall kata`
（wiki 内容不受影响）。

**Path B — Codex CLI**（Codex 没有插件市场，靠生成 skills 到发现目录）：

```bash
git clone https://github.com/litianyi-007/kata ~/kata
echo 'export KATA_HOME="$HOME/kata"' >> ~/.zshrc   # 或 ~/.bashrc
python ~/kata/scripts/install_codex_skills.py
```

装完/更新后重启 Codex 才会加载新 session。`plugin/AGENTS.md` **不是** Codex 的 skill
注册表——它是安装器注入进每个生成 skill 的共享说明。只想在单个项目里用不同版本？加
`--dest <project>/.codex/skills`。

**Path C — Standalone（任意 LLM）：**

```bash
cat SKILL.md | pbcopy   # macOS；Linux 用 xclip，Windows 用 clip
```

`SKILL.md` 自包含——每个 skill 的说明、每条守卫、每条已知限制。跟 A/B 产出同样的 schema
和 wiki 布局，代价是没有确定性 Python 脚本（LLM 得每次现算排序/图查询），也没有 `wiki-sync`
的自动合并驱动。

**Path D — GitHub Copilot CLI：**

```bash
copilot plugin install litianyi-007/kata
```

Copilot CLI 读仓库根目录的 `plugin.json`（v2.15.2 加的，Copilot 只找顶层清单，不递归子目录），
它指向 `plugin/skills/`——跟 Claude Code 用的是同一批 SKILL.md 文件。

### 跑第一个 wiki

```bash
# 1. 初始化——交互式，会问你的领域，提出适配的分类
/kata:wiki-init --path=~/.llm-wiki/my-project --domain="Electron + native SDK"

# 2. 摄入第一个来源——图片自动存到 raw/assets/，交叉引用自动写入
/kata:wiki-ingest docs/ARCHITECTURE.md

# 3. 看看编译出了什么——新建的页、新增的边、建议的下一批 ingest
/kata:wiki-digest

# 4. 问一个真正的决策问题——回答会归档成 hub 页，未来的 agent 先读它再动手
/kata:wiki-query "Electron renderer 和 native SDK 之间的 IPC 拓扑是什么？"

# 5. 探索图（BFS 走 [[wikilinks]]）
/kata:wiki-graph --neighbors attention --depth=2 --format=mermaid

# 6. 周期性体检
/kata:wiki-lint
```

## 18 个 skill 一览

| Skill | 调用 | 一句话 |
|---|---|---|
| wiki-init | `/kata:wiki-init` | 交互式启动：问域、提分类、写 SCHEMA.md、建 index.md/log.md |
| wiki-import | `/kata:wiki-import <path>` | 批量导入已有文档系统（Obsidian/Notion/Confluence/文件夹），去重、断点续传，5 阶段 |
| wiki-ingest | `/kata:wiki-ingest <source>` | 单条来源入库：存原文+图片、按 SCHEMA.md 建/改页、更新 index.md 和 log.md |
| wiki-search | `/kata:wiki-search <query>` | 关键词/标签/类型排序检索，默认只看 active 层，可扩展到 qmd/MCP |
| wiki-graph | `/kata:wiki-graph [模式]` | 把 wiki 当图查：邻居遍历、最短路径、hub/孤儿检测、frontmatter 过滤——不维护图数据库 |
| wiki-tier | `/kata:wiki-tier` | 查看/调整 active-archived-frozen 三层记忆阈值，手动 pin 覆盖 |
| wiki-digest | `/kata:wiki-digest` | 每周体检：活跃度、分层分布、内容缺口、跨簇综合、建议下一步 |
| wiki-query | `/kata:wiki-query <question>` | 带引用回答，报告显式置信度，可回填成页面，本地 miss 时可回退外部插件 |
| wiki-lint | `/kata:wiki-lint` | 结构检查（孤儿/断链/frontmatter/陈旧/分层/维度完整性）+ 内容缺口 + SCHEMA.md 演进建议 |
| wiki-config | `/kata:wiki-config` | SCHEMA.md 的统一读写口——`--show`/`--get`/`--set`/`--explain`/`--validate`，按路径操作 |
| wiki-dream | `/kata:wiki-dream` | auto-dreaming：重新评估冻结/归档页，相关性回升就建议复活，只读文件系统 |
| wiki-watch | `/kata:wiki-watch` | 监听 `raw/` 下的新文件排队；drain 才真正 ingest——自己绝不调用 wiki-ingest |
| wiki-sync | `/kata:wiki-sync` | 多机 git 同步：log.md 自定义合并驱动 + 本地锁 + force-push 检测 + wiki_id 身份校验 |
| wiki-spec | `/kata:wiki-spec preflight <path>` | 新 spec 起草前扫描关联旧 spec，让作者声明关系，防止 spec 语料内耗 |
| wiki-session-ingest | `/kata:wiki-session-ingest` | 把当前 AI CLI 会话里的洞察挑出来、蒸馏进 wiki（增量，只看上次之后的新消息） |
| wiki-mcp-server | `/kata:wiki-mcp-server` | 把这个 wiki 起成只读 MCP server，供其它 MCP client 或另一个 kata 联邦查询 |
| wiki-federate | `/kata:wiki-federate search <query>` | 跨 wiki 联邦查询：向 `.federation.yaml` 里的 peer kata 只读查询，按来源合并结果 |
| wiki-skill-create | `/kata:wiki-skill-create` | 生成项目本地 skill，把 kata 的 query/ingest 接进这个项目真实的写代码/测试/验证流水线 |

日常怎么串起来用（四个循环，不是四条独立命令）：

- **每日循环** — 素材丢进 `raw/` → `wiki-ingest` → 扫一眼 `wiki-digest --since=1d`。
- **提问循环** — `wiki-search`（或 `wiki-graph --neighbors`）定位 → `wiki-query` 回答；
  有价值的回答自动回填成 `queries/*.md`，变成图里的新节点。
- **探索循环** — `wiki-graph --shortest-path A,B` 找两个实体之间你没意识到的桥接概念。
- **每周循环** — `wiki-digest` 看整体状态，`wiki-lint` 找结构/内容缺口和 schema 演进建议。

## 它做不到什么 / 边界的真实情况

这一节不是免责声明——以下每一条要么是已兑现的安全边界（卖点），要么是如实的限制。

**已兑现的边界：**

- **联邦查询跨边界只读**——kata 从不写 peer wiki。`wiki-mcp-server` 只暴露
  `wiki-search` / `wiki-graph` 的只读子集 / `wiki-spec-preflight`（只给候选，不暴露
  `--enforce`）；`wiki-ingest`、`wiki-import`、`wiki-tier --pin`、`wiki-dream --apply`
  从不通过 MCP 暴露。
- **`wiki-watch` 自己绝不调用 `wiki-ingest`**（源码注释原话）——drain 永远是显式的人工步骤，
  一个配置错误的 watcher 不可能静默改动 wiki 页面。
- **外部兜底插件拒绝 `command_template` 与 shell 元字符**——v1.4 起只认 `argv:` 令牌数组，
  不经过 shell；`auto_run` 默认要求人工确认才执行。
- **`wiki-sync` 的 `wiki_id` 一旦不一致就 abort**，import 进行中会拦住 sync，force-push
  会被检测出来（不会静默吞掉历史重写）。
- **spec 自动传播（Phase 3）是 opt-in 的 preview，默认关闭**——因为它还不能在源 spec
  后来被编辑撤销 supersession 时自动反向撤销。

**如实的限制（不粉饰）：**

- **wiki 根路径解析没有天花板。** 无论是找带 `SCHEMA.md` + `log.md` 的祖先目录，还是找
  `.llm-wiki.yaml` / `.kata.yaml` 绑定文件，`plugin/scripts/wiki_lib.py` 里的实现都是
  `for cur in (start, *start.parents)`——一路走到文件系统根，没有类似 git 的
  `GIT_CEILING_DIRECTORIES` 天花板。一个放错位置的绑定文件会静默地把深层项目重定向到别的
  wiki。这条**不是笔误而是被依赖的行为**——「同一台机器，多个 wiki」里的嵌套覆盖用法
  正是靠它从任意深的子目录找到 monorepo 根上的绑定，所以本轮没有加天花板，
  只登记在 `docs/ISSUE-project-binding-unbounded-ancestor-walk.md`。
  代价是真实的：kata 自己的测试套件曾因此在任何装了 kata 的机器上跑不完（v2.16.0 前），
  修法是把测试 fixture 挪出项目祖先链，而不是给解析器加天花板。
- **dogfood 的 retrospective 从未回填。** `docs/dogfood-v1.6.md` / `docs/dogfood-v1.8.md`
  里的 retrospective、累计指标、GA 决策章节全是没填的模板占位符，从 v1.6 一路到 v2.15.5
  都没人回填过。有 dogfood 记录，但不要把它读成有 GA 结论。

## 核心概念

### 分层模型

| 层 | 是什么 |
|---|---|
| **Base** | [Karpathy 的 LLM-Wiki 构想](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)——编译一次、保持更新；人类策展，LLM 维护；一切都可选、可拼装。 |
| **Core** | 一个**自我演化的知识系统**：(1) 自闭环——ingest → 交叉链接 → 归档问题 → 复合增长的页面；(2) auto-dreaming——冻结页在相关性回归时重新浮现。 |
| **Phase 1**（当前） | **AI 结对编程。** 用 core wiki 编译项目的业务语义——阈值、生命周期不变量、领域惯例——让 AI agent 动手前先读懂项目惯例。v1.4 → v1.13 都在做这件事。 |
| **Phase 1+**（已发布） | **Spec History Management（v1.13）** 与 **Work-Loop Bridge（v1.15）**——见下面「接进你的工作流」。 |
| **Phase 2**（已设计，未实现） | **团队 spec 起草 + 分歧裁决。** 让未来的决策不用重新打一遍已经打过的架。 |
| **Phase 3+** | 开放。核心随着我们摸清楚什么会复合而继续扩展边界。 |

**产品**是 Core + 各 Phase 的延伸，Phase 1 只是第一个具体边界，不是 kata 的定义。

### SCHEMA.md 是唯一权威配置

所有约定——页面类型、frontmatter 字段、标签分类法、页面创建策略、交叉引用策略、页面大小
限制、日志滚动、**自定义维度**、**记忆分层阈值**——都活在 `{wiki_path}/SCHEMA.md`。插件
读取并执行 SCHEMA.md，而不是把意见硬编码进代码。

```text
{wiki_path}/
├── SCHEMA.md          # 约定 + 维度 + 分层策略（用户可编辑）
├── index.md           # 内容目录，一行摘要
├── log.md             # 追加式操作日志
├── raw/                # 不可变原始素材（articles/papers/transcripts/assets/imported/external）
└── {categories}/       # 由 SCHEMA.md 定义，贴合你的领域
                        # 研究: entities/ concepts/ comparisons/ queries/
                        # 业务: people/ projects/ decisions/ meetings/
```

`wiki-config` 是它的通用读写口（`show`/`get --path`/`set --path --value`/`explain --path`/
`validate`），只做既有标量键的手术式替换，schema 校验失败自动回滚；新增键或新增 YAML 块
仍需手改 SCHEMA.md 或重跑 `wiki-init`。`wiki-tier`、`wiki-init` 各自的领域快捷方式仍然存在，
`wiki-config` 补的是长尾场景。

### 记忆分层（active / archived / frozen）

| 层 | 默认窗口 | 行为 |
|---|---|---|
| **active** | < 1 年 | 默认查询面——所有 skill 都返回 active 层结果 |
| **archived** | 1–2 年 | 通过 `--tier=archived` 或 `--tier=all` 访问 |
| **frozen** | > 2 年 | 冷存储——auto-dreaming 定期回访 |

分层是从 `published_at`（兜底 `ingested_at`）**实时计算**的，从不写进 frontmatter——阈值一改
立刻生效。一个页面的层 = 它引用的所有来源里最新的那个层。`tier_override:` 支持手动 pin。

```bash
/kata:wiki-tier --show
/kata:wiki-tier --preview --set-active=540d
/kata:wiki-tier --pin=concepts/attention.md:active
```

### 自定义 frontmatter 维度

SCHEMA.md 的 `custom_dimensions:` 块声明领域专属的 frontmatter 字段——软件项目的 `version:`、
研究论文的 `venue:`。每个维度有类型、说明、`refresh_on` 调度（何时该重新问用户这个值）：

```yaml
custom_dimensions:
  - name: version
    type: string
    required: true
    refresh_on: [ingest, import]
```

`wiki-ingest`/`wiki-import` 按 `refresh_on` 提示（`--set key=value` 跳过提示）；`wiki-digest`
标出陈旧值；`wiki-lint` 校验完整性和枚举范围；`wiki-graph --query` / Obsidian Dataview 把它们
当普通 frontmatter 查询。

### auto-dreaming：睡着的时候 wiki 在干嘛

冻结内容不必永远冻着——收购的公司、复活的架构、被重新引用的经典论文。`wiki-dream` 按周期
（或你设的节奏）跑，只读 `log.md` + 页面 frontmatter 日期（`ingested_at`/`updated`），**从不
读文件 mtime 或聊天会话**，所以 `git clone` 到任何机器都能复现同样的 dreamer 行为。
v1.6 用 `co-occurrence` 策略，Precision ≥ 0.7、recall ≥ 0.5 在 CI 里被 gate 住。其它策略
（citational/structural/temporal）留给 v1.8+。有 dogfood 记录见 `docs/dogfood-v1.6.md`，但
它的 retrospective 章节从未回填——见上面「它做不到什么」。

```bash
/kata:wiki-dream                          # 落在 dreaming/{date}.md
/kata:wiki-dream --apply --pages 1,3,5    # 复活选中的候选
```

### 外部兜底插件

`wiki-query` 本地找不到答案时，可以调用 `.wiki-plugins.yaml` 里注册的外部工具：

```yaml
plugins:
  - name: deepwiki-cli
    trigger: on_empty
    auto_run: false          # 默认展示 argv 并要求确认
    argv: ["deepwiki-cli", "search", "--repo={repo_path}", "--query={query}"]
```

流程：query miss → 插件命令 → stdout 存进 `raw/external/` → `wiki-ingest` 处理 → wiki 页面
增长 → 未来的查询先命中本地。完整清单格式见 [`plugin/PLUGINS.md`](plugin/PLUGINS.md)。

### 设计谱系：源自 Karpathy，这个插件加了什么

| 扩展 | 加了什么 |
|---|---|
| **SCHEMA.md 作为权威配置** | 所有约定归一到一个文件，agent 读取并执行，而不是硬编码 |
| **交互式领域启动** | `wiki-init` 按领域（研究/书籍/业务/个人）提出适配的分类 |
| **批量导入**（`wiki-import`） | 5 阶段从 Obsidian/Notion/Confluence/文件夹迁移，支持断点续传 |
| **结构化图查询**（`wiki-graph`） | frontmatter 过滤、BFS 邻居、最短路径、hub/孤儿——不维护持久图数据库 |
| **三层记忆老化** | active/archived/frozen，从来源日期实时计算 |
| **外部兜底插件** | 任意 CLI 工具注册为 `wiki-query` 的兜底，走闭环 ingest |
| **多格式查询输出** | markdown / table / slides（Marp）/ chart（matplotlib）/ canvas（Obsidian） |

刻意没做的事：**持久图数据库**（文件系统就是图，扫描几百页只要毫秒级）；**冻结内容自动
清除**（frozen = 暂存，不是删除）；**基于 embedding 的语义搜索**（交给 qmd，内置的 3-pass
扫描覆盖 Karpathy 说的 ~100 源的甜蜜点）；**多用户权限控制**（wiki 就是个 git 仓库，用分支和
PR 协作）。

## 接进你的工作流

kata 的文档闭环（ingest → 交叉链接 → query → 回填）本身是闭的，但三条延伸线各自解决一个
「闭环之外还漏了什么」的问题。

### 会话结束后别让洞察烂在 chat 里（wiki-session-ingest）

两小时调试之后，真正值钱的东西——根因、被否决的备选方案、决策边界——都在会话记录里，
等你想起来写下来时已经忘了一半。`wiki-session-ingest` 读当前会话，按置信度给候选知识点
排序，让你多选想留的，逐个走标准 `wiki-ingest` 流水线蒸馏进 wiki。

```bash
/kata:wiki-session-ingest          # 增量：只看上次捕获之后的新消息（v2.14.0+）
/kata:wiki-session-ingest --full   # 强制从第一条消息重新扫
```

支持 Claude Code / Codex CLI（JSONL transcript 适配器，自动）以及 Gemini / Copilot /
OpenCode / Kimi 等任意其它 CLI（LLM-dump 兜底）。原始会话 dump 是 wiki 仓库里的 markdown，
会跟着 `wiki-sync` 走——如果会话涉及密钥，同步前自己看一眼。

### 别让 spec 语料互相打架（wiki-spec）

Spec-driven development 走上半年之后，没人说得清某个领域现在哪份 spec 是权威的，新 spec
悄悄跟旧的重叠，早该归档的旧 spec 还在被引用。`wiki-spec` 在 ingest 流程里加两个检查点：

```bash
/kata:wiki-spec preflight raw/new-spec.md   # Phase 0：扫描关联旧 spec，advisory
/kata:wiki-ingest raw/new-spec.md           # 自动跑 preflight + Phase 2 enforcement
```

作者在新 spec 的 frontmatter 里用一套词汇声明关系——`supersedes`/`refines`/`extends`/
`parallel`/`contradicts`——这些关系进入可查询的图，`wiki-graph --mode spec-history` 能把
血缘渲成 ASCII 树/JSON/Mermaid。**Phase 3（自动传播）默认关闭**，见上面「它做不到什么」。
跨 wiki 的 spec 关系可以用 `kata://<peer>/<path>` 指向联邦 peer（见下一节）。

### 把 kata 接进真正的写代码流水线（wiki-skill-create）

kata 的文档闭环会自己合上，但**真正的工作**——搜代码、改代码、跑测试、验证——发生在闭环
之外，要不要带着 kata 的知识回去全靠个人自觉。`wiki-skill-create` 生成一个**项目本地
skill**，把 kata 的 query/ingest 跟这个项目的实际工作流水线焊在一起：

```bash
/kata:wiki-skill-create
```

四个 MVP 模式，挑一个贴合项目里工作实际发生的形状：

| 模式 | 编码的循环 |
|---|---|
| `issue-fix` | 问题 → kata 查询 → 源码搜索 → 最小改动 → 测试 → 人工验证 → wiki-ingest |
| `feature-build` | 需求 → kata 查询 → spec 草稿 → `wiki-spec preflight` → 实现 → 验证 → 把 spec 和实现两边的经验都回填 |
| `bug-debug` | Bug → 复现 → kata 搜索（按症状也按机制）→ 根因 → 修复+回归测试 → 回填为以根因为主的经验 |
| `custom` | 描述你自己的循环 → kata 用 query / 人工确认 / 回填三段包住它 |

**补充信息去哪儿找（v2.15.1）。** 当项目工作流里查到一半、kata 本地又给不了答案时，
`--supplement-action <source-search|web-search|doc-lookup|custom>` 决定下一步去哪儿找：
`source-search` 查项目源码，`web-search` 联网搜，`doc-lookup` 查项目文档，`custom` 需要
通过 `--var` 传 `CUSTOM_SUPPLEMENT_*` 变量自定义。不传时用 `suggested_supplement_action`
启发式挑默认值——检测到编程语言栈就推荐 `source-search`，有 `docs/` 目录就推荐
`doc-lookup`，纯 markdown 项目推荐 `web-search`，都不满足就不推荐、交给用户选。这一步在
四个模式里插的位置不同——orchestrator 把它叫 **Phase 2.5**：`issue-fix` 第 3 步、
`bug-debug` 第 3.5 步、`feature-build` 和 `custom` 第 2.5 步，通常卡在 kata 查询之后、
真正动手改代码之前。

生成的 SKILL.md 落在 `<project>/.claude/skills/<name>/SKILL.md`（`--target codex` 改写到
`~/.codex/skills/`），自动侦测的技术栈（npm/cargo/pytest/go test 等）和项目名写进它的
7 步循环。渲染后跑 **9 项静态校验**（frontmatter 能解析、必填字段齐全、name 格式、
frontmatter ≤ 1024 字符、description 以 "Use when" 开头、第三人称、sentinel 注释存在、
无未解析的 `{{VAR}}`、`argument-hint` 在 user-invocable 时存在）——校验不过不会自动修，
交给用户看着改。

## 多机与跨 wiki

### 同一个 wiki，多台机器（wiki-sync）

v1.8 加了 `wiki-sync`：`log.md` 的自定义 merge driver（union+sort，带 canonical hash 去重），
本地同步锁，force-push 检测（比对 fetch 前后 `origin/<branch>` 的 SHA 祖先关系），wiki
身份校验（`wiki_id` UUID 不一致直接 abort），以及仓库外的 per-machine 同步报告
（`~/.kata/sync-reports/`，永远不在 wiki 仓库里以免自我冲突）。

```bash
/kata:wiki-init --path ~/.llm-wiki/myproject --enable-sync
cd ~/.llm-wiki/myproject && git init -b main && git add . && git commit -m "wiki: init"
git remote add origin git@github.com:you/myproject-wiki.git && git push -u origin main

# 第二台机器
git clone git@github.com:you/myproject-wiki.git ~/.llm-wiki/myproject

/kata:wiki-sync              # 交互式：锁 + driver + fetch + merge + push
/kata:wiki-sync --dry-run    # 预览，无副作用
```

设计过程见 [`docs/PRD-v1.8-sync.md`](docs/PRD-v1.8-sync.md)（v1 初稿 + v2~v7 六轮跨 LLM
复审，42 条 finding 收敛，2026-05-07 MVP ready）。`dreaming/` 目前还没有 merge driver——两台
机器同一天都跑 `wiki-dream` 会产生正常的 git 冲突，避免方法是只在一台机器跑 dream cron。

### 同一台机器，多个 wiki

```
~/.llm-wiki/
├── common/     # 默认兜底
├── necall/     # 项目 A
└── research/   # 项目 B
```

路径解析优先级（从高到低）：显式 `--path`/`--wiki` → `WIKI_PATH` 环境变量 → 当前目录已经
在某个 wiki 根内 → `LLM_WIKI_PROJECT` → 项目根最近的 `.llm-wiki.yaml`/`.kata.yaml` 绑定
文件 → 全局 `~/.llm-wiki/registry.yaml` → git 仓库名兜底 → legacy 配置 → `~/.llm-wiki/common`。

`.llm-wiki.yaml` 是**单路径缓存**——一个文件只绑定一个 wiki 根，写多条 `wiki_path:` 无效，
只认最后一条。多 wiki 共存推荐两种做法之一：每个项目仓库自己放一个 `.llm-wiki.yaml`
（monorepo 套 submodule 时，离 cwd 更近的绑定赢），或者维护一份全局
`~/.llm-wiki/registry.yaml`。`.llm-wiki.yaml` 属于每台机器的本地状态，git 仓库里应该
`.gitignore` 它；registry.yaml 同理放在仓库外。

**这条解析链没有天花板**——见上面「它做不到什么」。

### 跨 wiki 只读联邦查询（federation）

v1.12 让 kata 既能当 MCP server（`wiki-mcp-server`），也能当 MCP client 查询别的 kata
（`wiki-federate`）。每个 wiki 在自己的根目录声明 peer：

```yaml
# {wiki_path}/.federation.yaml
peers:
  - name: necallkit
    wiki_id: 7b52f6df-d7cf-47ab-b980-6042cf3a675c
    endpoint: stdio
    command: ["py", "-3", "path/to/kata/plugin/scripts/mcp_server.py", "--wiki", "~/.llm-wiki/NECallKit"]
    enabled: true
    timeout_seconds: 5
```

```bash
/kata:wiki-federate search "F011 merge-back"   # 先跑本地，再并行 fan-out 到已启用的 peer
/kata:wiki-federate peers                       # 列出注册的 peer
/kata:wiki-federate resolve "kata://necallkit/decisions/F011.md"
```

结果按 `kata://<peer-name-或-wiki_id>/<path>` 的 URI 引用，日常用名字形式（可读），跨机器
长期引用（比如 `spec_relationships:` 里）用 wiki_id 形式（更抗 peer 改名）。安全边界：
**跨边界只读**——peer 的 MCP server 只暴露 `wiki-search`/`wiki-graph` 只读子集/
`wiki-spec-preflight`，任何写 skill 都不会跨联邦暴露；**每次连接都做身份校验**——peer 报的
`wiki_id` 跟 `.federation.yaml` 里登记的不一致就拒绝这个 peer；**没有传递解析**——A 引用 B、
B 又引用 C，A 不会自动追到 C；peer 不可达/超时/`wiki_id` 不匹配都不会让本地查询失败，只在
返回结果的 `federation` 诊断块里体现。查询内容会原样发给每个 peer——敏感查询用
`--no-federate`。

## 参考

**Works with：** Claude Code（`.claude-plugin/`）、Codex CLI（生成的 skills）、任意 LLM
（`SKILL.md` 作为 system prompt）、GitHub Copilot CLI（根目录 `plugin.json`）、Obsidian
（wiki 就是一个 vault：`[[wikilinks]]`、Graph view、Dataview 查 frontmatter、Web Clipper
存 `raw/articles/`、Marp 渲染 `wiki-query --format=slides`）。wiki 默认是 git 仓库，
`wiki-init` 最后一步会建议 `git init`。

**Scaling：** < 100 页用内置 `wiki-search`；100–500 页记得常跑 `wiki-lint` 保持 `index.md`
新鲜；500–2000 页装 [qmd](https://github.com/tobi/qmd)（BM25 + 向量混合 + LLM 重排，
`wiki-search` 会自动探测并 shell out）；2000+ 页用 qmd 的 MCP server 模式。

**文档索引：**

- [`docs/PRD-v1.8-sync.md`](docs/PRD-v1.8-sync.md) — 多机同步设计
- [`docs/PRD-v1.12-cross-wiki-federation.md`](docs/PRD-v1.12-cross-wiki-federation.md) — 联邦设计
- [`docs/PRD-v1.13-spec-history-management.md`](docs/PRD-v1.13-spec-history-management.md)、
  [`docs/PRD-v1.14-spec-propagation-reconcile.md`](docs/PRD-v1.14-spec-propagation-reconcile.md) — spec 历史管理
- [`docs/PRD-v1.15-work-loop-bridge.md`](docs/PRD-v1.15-work-loop-bridge.md) — work-loop bridge
- [`docs/dreaming.md`](docs/dreaming.md)、[`docs/watcher.md`](docs/watcher.md) — auto-dreaming / watcher 设计
- [`plugin/PLUGINS.md`](plugin/PLUGINS.md) — 外部兜底插件清单格式
- 每个 skill 的完整行为以其 `plugin/skills/<name>/SKILL.md` 为准——README 只讲定位和常用姿势

**Contributing：**

```bash
git config --local core.hooksPath .githooks   # 启用 pre-commit smoke test
python tests/run_smoke.py                      # 手动跑一遍，跟 CI 一致
python scripts/build_skill_md.py               # 加了新 skill 后重新生成 SKILL.md 汇总表
```

## Origin

概念来自 [Andrej Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
（2025 年 5 月）。插件设计范式参考
[SpecTeam](https://github.com/litianyi-007/SpecTeam)。

这个插件的目标是做 Karpathy 那个刻意留白的构想的一份**忠实、有主张的实现**。原文说「上面
提到的一切都是可选、可拼装的」，我们做了具体的选择（SCHEMA.md 作为单一配置、交互式领域
启动、三层记忆老化），同时保留核心不变量：文件系统是唯一真相源、raw 不可变、人类策展/LLM
维护、知识编译一次然后持续复合。

License: MIT. 见 [LICENSE](LICENSE)。
