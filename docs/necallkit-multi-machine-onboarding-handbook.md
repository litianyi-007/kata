# NECallKit llm-wiki 多端共享与维护操作手册

> 操作手册，不是 PRD。基于 2026-05-09 ~ 2026-05-11 dogfood 实证。
>
> 假设：你已经在主电脑（machine A）跑了一段时间 NECallKit wiki，本手册
> 帮你把它接到第二台电脑（machine B），并在两端共享维护。

---

## 0. 你现在的 wiki 状态（machine A 视角）

| 项 | 值 |
|---|---|
| Wiki 本地路径 | `~/.llm-wiki/NECallKit`（Windows: `~\.llm-wiki\NECallKit`） |
| Remote | `<internal>/necall-wiki` |
| 默认分支（wiki 自己 git repo 的） | `master` |
| `wiki_id`（identity check 用） | `7b52f6df-d7cf-47ab-b980-6042cf3a675c` |
| Sync 配置（SCHEMA.md） | `sync.enabled: true`, `sync.remote: origin`, `sync.branch: master` |

**关键约束：`wiki_id` 不能手改**。两台机器靠它判断"同一份 wiki"，改了 sync 就会拒绝合并。

---

## 1. 把 machine A 准备好（一次性，5 分钟）

在 machine A 上：

```bash
cd ~/.llm-wiki/NECallKit

# 1.1 必须 clean
git status --short
# 期望：空输出。如果有未 commit 的文件，先决策 commit 还是 stash。

# 1.2 必须已 push 到 origin
git log @{u}..HEAD --oneline
# 期望：空输出。如果 ahead 几个 commit，跑：
git push
# 或用 wiki-sync 自动跑：
# /kata:wiki-sync
```

如果 `wiki-sync` 拒绝（preflight 检测到 dirty / import-lock / merge-in-progress），
按提示先解决再 push。

---

## 2. machine B 一键启动（10 分钟）

### 2.1 装好底层环境

| 工具 | 用途 | 验证 |
|---|---|---|
| **Python ≥ 3.9** | wiki-sync / lint / dreaming 脚本 | `py -3 --version`（Windows）或 `python3 --version` |
| **Git** | wiki repo clone & sync | `git --version` |
| **kata plugin (完整 checkout)** | wiki-* skill **运行时**依赖的脚本目录 `plugin/scripts/*` | 见下文 §2.1.1，**不只是 skill 入口** |
| **$KATA_HOME** | wiki-search 等命令解析 `plugin/scripts/search_naive.py` 等 | `echo $KATA_HOME` / `$env:KATA_HOME` 非空且指向 plugin checkout |
| **ne-git-commit**（可选） | 如果你计划在 B 也提交工程代码（不是 wiki）| `~/.git-ai/bin/ne-git-commit.sh` |

**Windows 注意**：默认 `python` 可能是 Python 2.7。用 `py -3` 显式调 Python 3，
或者把 Python 3 放进 PATH 优先位置。

#### 2.1.1 kata plugin 必须完整 clone，不是只拷 SKILL.md

**已踩过的坑（2026-05-12 dogfood）**：第二台机器只把 `wiki-search/SKILL.md`
单文件放到 `~/.agents/skills/` 或 `~/.codex/skills/`，没有 plugin repo 的完整
checkout，**且没有设 `$KATA_HOME`**。结果 `wiki-search` 的命令模板里
`python $KATA_HOME/plugin/scripts/search_naive.py ...` 解析不到脚本，
knock-it-out 的 wiki 阶段直接 skip，措辞类似"本机有 wiki 技能入口但没有可用
wiki 库/搜索脚本"。

正确做法：

```bash
# 1) 在 machine B 选一个稳定路径 clone 完整 plugin repo
git clone https://github.com/<your-org>/kata.git ~/kata
# 或镜像 / 内网路径。machine A 的惯例是 C:\Users\<user>\kata。

# 2) 设并持久化 $KATA_HOME（Bash / Zsh）
echo 'export KATA_HOME=$HOME/kata' >> ~/.bashrc
export KATA_HOME=$HOME/kata

# Windows PowerShell（持久化到 user-scope）
setx KATA_HOME "$HOME\kata"
$env:KATA_HOME = "$HOME\kata"  # 当前 session 立即生效

# 3) 验证脚本可达
python "$KATA_HOME/plugin/scripts/search_naive.py" --help
# 期望：argparse 输出，不应有 "No such file" / "$KATA_HOME 未定义"
```

只有这 3 步全过，`wiki-search` 在 machine B 才真正可用。仅有 SKILL.md
入口可见、`$KATA_HOME` 未设 / plugin checkout 缺失的状态，对 knock-it-out
等上游 skill 等价于"wiki 不可用"。

### 2.2 Clone wiki 到标准布局

```bash
# 创建 multi-project 父目录
mkdir -p ~/.llm-wiki

# clone 到 NECallKit 子目录（名字必须是 NECallKit，跟 machine A 一致）
cd ~/.llm-wiki
git clone <internal>/necall-wiki NECallKit

# 验证 wiki_id 已带过来（不要手改）
grep wiki_id NECallKit/SCHEMA.md
# 期望输出：wiki_id: 7b52f6df-d7cf-47ab-b980-6042cf3a675c
```

### 2.3 绑定到本机 NECallKit 工程目录

如果你这台电脑上也有 NECallKit 工程 checkout（例如
`~/Documents/Code/NECallKit`），让 kata 知道它对应这个 wiki。**二选一：**

**方式 A — 工程根的 `.llm-wiki.yaml`（推荐，per-project）**

```bash
echo "wiki_path: ~/.llm-wiki/NECallKit" > /path/to/NECallKit/.llm-wiki.yaml
# 立刻加入 .gitignore：这是本机本人的 binding，跨机/跨人会冲突
echo ".llm-wiki.yaml" >> /path/to/NECallKit/.gitignore
```

**方式 B — 全局 registry**

```bash
mkdir -p ~/.llm-wiki
cat >> ~/.llm-wiki/registry.yaml <<'EOF'
projects:
  NECallKit:
    wiki_path: ~/.llm-wiki/NECallKit
EOF
```

如果 machine B 上没有 NECallKit 工程 checkout（只想读 wiki），可以跳过这步。

> 多 wiki 共存提示：`.llm-wiki.yaml` 是单路径缓存——每个文件只指向一个
> wiki。如果这台机器上同时还托管别的 wiki（例如 `~/.llm-wiki/research`、
> `~/.llm-wiki/playground`），方式 B 的 `registry.yaml` 可以堆多条
> `projects:` entry；方式 A 的 `.llm-wiki.yaml` 则在每个工程根各放一份
> 即可（子目录的 binding 优先于父目录）。完整模式参考 README → "Multiple
> wikis on one machine"。

### 2.4 验证第一次 sync

```bash
cd ~/.llm-wiki/NECallKit
/kata:wiki-sync --dry-run
# 期望输出：up-to-date
```

副作用（自动完成）：
- `merge_log.py` 注册为 `log.md` 的 custom merge driver（写到 `.git/config`）
- per-machine sync 报告目录：`~/.kata/sync-reports/NECallKit/`

---

## 3. 日常多端工作流

### 3.1 开始工作前（任何一端）

```bash
cd ~/.llm-wiki/NECallKit
/kata:wiki-sync --dry-run    # 看看对端是否推了新东西
# 如果 "would-fast-forward"：
/kata:wiki-sync               # 拉过来
```

### 3.2 工作中（ingest / 修改 wiki 之后）

```bash
# 提交本地工作（commit 必须是干净状态才能 sync）
cd ~/.llm-wiki/NECallKit
git status --short              # 看看改了什么
git add -A
git commit -m "wiki-import: ..."

# 推送到 origin（让对端能拉到）
/kata:wiki-sync               # 触发 lock + driver + fetch + merge + push
```

### 3.3 cron 自动化（可选，推荐 1 台机器跑）

```bash
# 每天 23:00 自动 sync + dream
0 23 * * * cd ~/.llm-wiki/NECallKit && /kata:wiki-sync --auto && /kata:wiki-dream
```

**关键决策**：dreaming cron **只在一台机器跑**（machine A 即可）。原因见 §5。

---

## 4. 冲突处理

### 4.1 `log.md` 冲突

自动通过 `merge_log.py` 解决（union + sort + canonical hash dedup）。同一三元组
不同 body 的会保留两边，标 `Sync-side: ours/theirs`，需要时人工合一下。

### 4.2 其他文件冲突

走标准 git 流程：

```bash
# 看 conflicts 报告
ls ~/.kata/sync-reports/NECallKit/ | tail -3

# 在编辑器里改完冲突标记
git add <resolved-files>
git commit
git push

# 恢复 stash（用 sync 报告里给的 SHA，不要用 stash@{0}）
git stash apply <sha-from-report>
git stash drop stash@{N}
```

### 4.3 `dreaming/YYYY-MM-DD.md` 冲突

如果两台机器同一天都跑了 `wiki-dream`，会撞同一个日期文件名。**没有 merge driver**
（v1.8-full / v1.9 backlog）。解决：手动选一份保留，或合并两边的 resurgent tags。

→ **真正的解决办法是只在一台机器跑 dream cron**。

### 4.4 `wiki_id` 不匹配（identity check 拒绝）

`SCHEMA.md` 里两台机器的 `wiki_id` 不同时，sync 会硬停。**原因几乎只有一个：
有人手改了 `wiki_id`**。从 git 历史恢复原值即可。

如果你真的要重置 wiki ID（极少见），用 `wiki-init --refresh-id` 然后在**所有**
对端跑一次。

---

## 5. 限制 & 常见坑（dogfood 实证）

### 5.1 wiki 不区分 NECallKit 工程分支（v1.9 暂未实装）

当前 wiki 是按 project 定位（`~/.llm-wiki/NECallKit`），不按你 NECallKit 工程的分支。
所有 NECallKit 分支共享一份 wiki。如果某些 page 只对 `specs/002-electron-callkit`
分支成立，在 page 里写明即可。

未来 v1.9 实装后会有 `wiki-repo switch necallkit master` / `wiki-repo promote`
等命令把 branch-scoped 知识晋升到 canonical。设计在
`docs/PRD-v1.9-repository-bindings.md`。

### 5.2 Python 2 vs Python 3（Windows 反复踩）

Windows 默认 `python` 经常是 2.7，wiki 脚本会语法报错。所有命令用 `py -3`，
或把 Python 3 放进 PATH 优先位置。dogfood 已经在 5/9 / 5/10 至少踩过 3 次。

### 5.3 跨 session 的 pending-commit drift

多个 codex / Claude 会话同时跑 ingest，但**只**修改 wiki 内容、**不**自动 commit。
新的 ingest 跑前 wiki tree 是 dirty，ingest script 默认拒绝。

每次开新 session 第一件事：

```bash
cd ~/.llm-wiki/NECallKit
git status --short
# 如果有 ?? 或 M：决策 commit 还是 stash 再继续
```

### 5.4 双端**同时**写入会触发 push race

wiki-sync 有 3 次重试（1/2/4s backoff），超过就会 `race-exhausted`。重跑即可。
日常避免：A 和 B 不要在同一分钟跑大量 ingest。

### 5.5 `~/.kata/` 是 per-machine，不要同步

```text
~/.kata/
├── sync-{slug}.lock           # 每台机器自己的 lock
├── sync-reports/{slug}/        # 每台机器自己的报告
└── ...
```

这些刻意在 wiki repo 外，每台机器独立。需要时 `rm -r ~/.kata/sync-reports/NECallKit/`
清理，不会影响内容。

### 5.6 `raw/` 是 immutable 来源材料

`raw/imported/` 下是 ingest 原始材料，**永远不要手改**。要修正知识改 wiki page。
sync 不会区别对待，但你和未来 agent 都需要遵守。

### 5.7 wiki-import 锁会阻塞 sync

A 端跑 `wiki-import`（大批量导入）期间 `.wiki-import-lock` /
`.wiki-import-checkpoint.json` 存在，sync 会拒绝。如果 A 端 import 中断没清理，
B 端 sync 也会拒绝。处理：在 A 端跑 `wiki-import --resume` 或人工删 checkpoint。

---

## 6. 远端 wiki 内容的隐私问题

NECallKit wiki 的 `raw/imported/` 下含 NECallKit 项目源码摘录（PRD、bugfix 分析、
ingest 时间线）。当前 remote 是 `<internal>/necall-wiki`
（公司内网）。

**不要**把 wiki remote 改成公共 GitHub。需要外网共享时另起一个 wiki。

---

## 7. 一页 cheat sheet

```text
# 第二台电脑首次启动
mkdir -p ~/.llm-wiki && cd ~/.llm-wiki
git clone <internal>/necall-wiki NECallKit
echo "wiki_path: ~/.llm-wiki/NECallKit" > /path/to/NECallKit/.llm-wiki.yaml
cd ~/.llm-wiki/NECallKit
/kata:wiki-sync --dry-run        # expect up-to-date

# 每次开工
cd ~/.llm-wiki/NECallKit && /kata:wiki-sync --dry-run

# 每次收工
cd ~/.llm-wiki/NECallKit
git status --short                  # commit pending ingest
git add -A && git commit -m "wiki-import: ..."
/kata:wiki-sync                  # push

# 出问题
cat ~/.kata/sync-reports/NECallKit/$(ls -t ~/.kata/sync-reports/NECallKit | head -1)
```

---

## 8. 不要做的事（速查）

- ❌ 不要手改 `SCHEMA.md` 里的 `wiki_id`
- ❌ 不要修改 `raw/imported/` 下任何文件
- ❌ 不要在两台机器同一天都跑 `wiki-dream`（除非接受同一天的 dreaming 文件需要手解冲突）
- ❌ 不要在 wiki-import 进行中跑 wiki-sync（preflight 会拒绝，但别强行 unlock）
- ❌ 不要 force-push wiki repo（sync 的 ancestry 检查会硬停后续合并）
- ❌ 不要把 wiki remote 改成公共仓库（含项目源码摘录）
- ❌ 不要在 conversation 结束前留 dirty tree 不管（下次 session 会被卡住，参见 §5.3）
