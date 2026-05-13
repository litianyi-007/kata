# PRD / Design — v1.8 Multi-machine sync via git

**Status:** Draft v7 · 2026-05-07
**Author:** litianyi (with Claude Opus 4.7)
**Targets:** kata v1.8
**Owner:** kata maintainer

> 这一版合并了 PRD（why / what）+ TRD（how）。等 MVP 实现完，要再拆
> dogfood / TASKS 文档时再分开。

## Revision history

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2026-05-07 | Initial design (commit `cbf87331`)。锁定 driver Option A、import-lock、per-project repo |
| **v2** | **2026-05-07** | **跨 LLM 复审 (15 项发现) 整改**: <br>• **B1** sync 报告生命周期: 改为 local-only 路径 `~/.kata/sync-reports/{slug}/`，避免被下次 sync 当 untracked 处理 (§6 / §9 全节重写)<br>• **B2** force-push 检测之前是恒真 tautology: 改为 fetch 前后比对 `origin/<branch>` ref 的祖先关系 (§6.6.d.ii)<br>• **B3** akwiki-log 不再以 `(date,action,subject)` 三元组去重: 改为按完整 entry 内容哈希，body 不同的同三元组保留两份 (§8)<br>• **H1** 显式 try/finally 状态机: lock 释放、stash 处理、cleanup 在 §6/§18 标准化<br>• **H2** sync lock 改名为「local sync lock」: 跨机争用走 push rejection + bounded retry (§3 US-5 / §11 / §14 改测试)<br>• **H3** wiki-import 必须改为 phase 5 单次 commit/push (而不是 wave-by-wave): 进 v1.8 MVP 必做项 (§13)<br>• **H4** `.wiki-plugins.yaml` 进 per-machine gitignore (§7 / §10)<br>• **H5** akwiki-index section 名变更触发 exit 非零 (§8)<br>• **H6** akwiki-index prose 三方不完全相同时 exit 非零，不静默重写 (§8)<br>• **H7** SCHEMA.md 新增 `wiki_id` (UUID) 字段，sync 前先比对 identity (§11 第 9 条 / §12)<br>• **M1** `--dry-run` 在副作用之前分叉，不取 lock / 不写 config / 不 stash (§6)<br>• **M2** `sync.auto_configure_drivers` 开关，区分「失效自愈」与「用户主动 unset」(§12 / §16)<br>• **M3** §7 矩阵加 「MVP 行为 / v1.8-full 行为」两列<br>• **M4** §7 矩阵新增 control files 行 (`.gitattributes`, `.gitignore`, `templates/`)<br>• 新增 T-sync-14..19 覆盖打穿性场景<br>• **L1** §16 加 cleanup 子节，明确 sync 报告残留处理 |
| **v7** | **2026-05-07** | **第六轮跨 LLM 复审 (1 项 LOW) 整改 — 收敛到 MVP-ready**: <br>• **L4 round 6** T-sync-20 子场景 (b) commit-OK / push-fail 反测的 hook lifecycle 含糊: 用 pre-receive hook 拒收 import 的 push,但随后又要 wiki-sync "正常推送" — 若 hook 还在,wiki-sync 也会被拒。改成: **harness 显式管理 hook lifecycle** (1) 安装 hook → 跑 wiki-import (commit OK / push fail) → assertion 1 "checkpoint 已删"; (2) **harness 移除 hook** → 跑 wiki-sync → assertion 2a "preflight 不被 checkpoint 卡" + 2b "local-ahead-only 路径 push 成功"。两个 assertion 分别证明不同性质,避免 conflate (§14)<br>• Round-6 reviewer 明确 "其余 4 条整改链路闭合,未见新的架构级问题",v7 是 MVP-ready 候选 |
| **v6** | **2026-05-07** | **第五轮跨 LLM 复审 (4 项 follow-up) 整改**: <br>• **M6 round 5** wiki-import checkpoint 漏掉 commit-success-push-fail 中间态: v5 §13 写"commit + push 全成功后删 checkpoint",但若 push 失败 (网络挂 / remote reject), 本地已有完整 import commit 但 checkpoint 还在 → 下次 sync 被 §6.3.6 卡死。**新设计: commit 成功就删 checkpoint** (不等 push);若 push 失败,wiki-import 打印明确提示让用户跑 wiki-sync 或手 `git push`。理由: commit 后本地状态已经是合法 git repo,push 失败只是同步问题,不是 import 问题;后续 wiki-sync "local-ahead-only" 路径自然会处理。T-sync-20 增加 commit-success/push-fail 反测 (§13 / §14)<br>• **M5 round 5** merge_log render_body_with_side 调用范围不一致: §4 隐含只对 duplicate entries 用,§6 又说"每条 body 都 render"。明确为: **仅当 entry 是 same-triple-different-body 的 duplicate (来自 ours 或 theirs)** 才追加 Sync-side 行;**common entries** (三方都有 / ours+base / base+theirs 共有) 不加 Sync-side。canonicalize_body_line 仍 unconditionally 剥所有现存 Sync-side 行 (用于 hash + 用于 render-time 清理) (§8)<br>• **M-x round 5** §17 风险表残留 v3/v4 双路径说法 ("textual 调 git merge-file / semantic 写 AKWIKI-SEMANTIC"),与 v5 single failure path 矛盾。改为 v5 contract 描述,并补一行 "marker block 嵌三方原文可能让大文件三倍膨胀;接受,因为人工 resolve 时三方原文是最有用的上下文" (§17)<br>• **L3 round 5** T-sync-16 role + barrier dir 传递未定: 显式约定环境变量 `AKWIKI_SYNC_TEST_ROLE=A\|B` 和 `AKWIKI_SYNC_BARRIER_DIR=...` 由测试 harness 注入到 subprocess;pre-push hook 内部用这两个 env 知道写哪个 ready 文件;hook 内 timeout 退出非零;父进程 wait + 超时 kill (§14) |
| **v5** | **2026-05-07** | **第四轮跨 LLM 复审 (5 项 follow-up) 整改**: <br>• **H4 round 4** TextualUnmergeable 分支仍写 `sys.exit(rc if rc != 0 else 1)`,merge-file 返回 0 时变成"无 marker 但 unmerged"。**简化设计**: driver 任何失败路径**统一走 `write_semantic_marker()` + exit 1**,放弃 textual fallback;driver 不再尝试调 `git merge-file` (因为我们的 wiki 文件结构化语义比文本 3-way 更重要,文本 clean merge 不能保证语义有效) (§8)<br>• **H4 round 4 (cont.)** §8 merge_index 仍引用旧 `fallback_to_git_merge_file`: 全部改为 `write_semantic_marker(reason=...)`,section rename / prose 不一致都明确走 semantic 路径 (§8)<br>• **M5 round 4** Sync-side render 未定义幂等性: 增加显式 `render_body_lines(body, side)` 规则 — 先剥所有现存 `Sync-side:` 行,再追加单条新行;保证多轮 sync 不重复追加,git diff 不 churn (§8)<br>• **M6 round 4** wiki-import 成功后未明确删 checkpoint: §6.3.6 preflight 检测 checkpoint 存在就 abort;但 §13 没说 phase 5 成功后 delete checkpoint → 成功 import 后第一次 sync false positive。新增 §13 wiki-import 子任务"phase 5 success: delete .wiki-import-checkpoint.json";新增 T-sync-20 覆盖 (§13 / §14)<br>• **L2 round 4** T-sync-16 barrier append PID 在 Windows 不稳: 改为两个 role-specific ready 文件 (`tests/_sync/barrier-{ts}/A.ready` + `B.ready`),各 subprocess 只写自己那个,双方都 poll 两个文件存在;避免并发写同文件的锁语义问题 (§14) |
| **v4** | **2026-05-07** | **第三轮跨 LLM 复审 (6 项 follow-up) 整改**: <br>• **H1b round 3** stash drop 仍用 stash@{0} 漂移: cleanup 改成先 `git stash list --format=%H` 找 SHA 匹配的 `stash@{n}` 再 drop;找不到只记录不 drop。recovery command 全部用 SHA (§6.2 / §9.3)<br>• **H4 round 3** driver fallback 仍漏:`git merge-file` 在 clean textual merge 时 rc=0,但 driver 强制 exit 非零会留无 marker 的 unmerged 文件。新设计: 语义冲突时 driver 自己写 `AKWIKI-SEMANTIC-CONFLICT` 标注 marker,不依赖 git rc。同步删 §17 风险表里"git 会回退 default"的旧说法 (§8 / §17)<br>• **H5 round 3** merge_log side 标签写进 subject 导致下一轮 hash 不再相等: side 信息从 subject 移到 body 行 `- Sync-side: ours/theirs`,canonical hash 主动剥离这条;每次 sync 重新生成,不累积 (§8)<br>• **M1 round 3** canonical hash 自相矛盾 (revision history 说"保留顺序"伪码却 `sorted()`): 默认**保留** body 行顺序,只对已知无序的 `Files:`/`Created:`/`Updated:`/`Promoted:`/`Linked to:` 行的逗号列表内部 canonicalize (§8)<br>• **M2 round 3** import 失败留 untracked 页 sync 无视: §6.3.6 preflight 检测 `.wiki-import-checkpoint.json` 存在 → 提示 resume/clean 后再 sync,exit 非零;不依赖 stash (§6 / §13)<br>• **M3 round 3** T-sync-16 sleep 不是 barrier: 改成共享 barrier 文件 + counter,两个 subprocess 写入 ready 后等 counter==2 才放行;加 timeout 防死锁 (§14) |
| **v3** | **2026-05-07** | **第二轮跨 LLM 复审 (11 项 follow-up) 整改**: <br>• **H1a unrelated-history 漏检** (v2 §6.9): old_origin 不存在时直接跳过 force-push detect → fetch 后另用 `git merge-base HEAD origin/<branch>` 空集判定为 unrelated-history 单独 abort (§6.9 / T-sync-18)<br>• **H1b stash@{0} ref 漂移**: stash 后立即 `git rev-parse refs/stash` 取 SHA，所有 cleanup / 报告 / recovery command 都用 SHA (§6.1 / §6.2 / §9.3)<br>• **H2 cleanup 内部不分层**: lock release 必须不依赖 report write 成功;cleanup 内部再 try/finally，report 写失败降级 stderr (§6.2 重写)<br>• **H3 stash 只在 diverge 分支**: fast-forward 也改工作树，但 v2 没 stash → 把 stash 提到 `compare` 之前，任何会改工作树的路径前都先 stash (§6 整体顺序调整)<br>• **H4 driver 退出非零 ≠ git 默认 fallback**: driver 失败时必须自己写 conflict marker (调 `git merge-file` 生成) 后 exit 非零，不能空着 %A (§8 全节重写)<br>• **H5 merge_log machine slug 不可知**: driver 只看到 ours/base/theirs 三个临时文件，没有 machine 元数据 → 改成 `(side: ours)` / `(side: theirs)` 标签;wiki_id 嵌入 log entry 留 v1.9 (§8)<br>• **M1 哈希 canonical form 未定义**: 明确 hash 输入 = SHA-256 of `f"{date}\|{action}\|{subject}\n"` + 规范化 body 行 (strip 空白、保留顺序、丢空行) (§8)<br>• **M2 wiki-import refactor 无子任务**: §13 MVP 拆出 import-lock / dirty-tree policy / phase 5 single commit / failure rollback 四个子项<br>• **M3 T-sync-16 race test 缺 barrier**: 改为两个 subprocess + pre-push sleep hook 形成可重复 race (§14)<br>• **M4 T-sync-17 跨平台语义未定**: 拆 T-sync-17a (graceful SIGINT，验 finally 跑) + T-sync-17b (hard SIGKILL/TerminateProcess，验下次 sync 自清 stale lock) (§14)<br>• **M5 wiki_id immutable 不能靠单文件 schema_validate 证明**: 改为 sync-time identity mismatch hard stop;schema_validate 只验 UUID 格式;immutability 是运行期约定，不入 v1.8 MVP (§17 / §12 调整)<br>• **L1 §18 ASCII 状态机仍写旧 path**: 改为 "write local sync report"，不让实现时抄回 wiki repo 路径 |

---

## 1. Problem

v1.7.2 的多项目 resolver 让 `~/.llm-wiki/{project}` 在单台机器上很顺，
但**没有跨机器同步**。典型痛点：

- 笔记本周三 ingest 了 3 个 source，桌面周六 ingest 了 5 个；周日想看
  统一的 wiki 没有任何机制能合
- 出差 2 周回来，要手动从另一台机 pull 才能继续工作
- 多机各自跑 auto-dreaming 会独立挑候选 promote，同一页可能被 promote
  两次（M9 dedup 兜得住但前提是合在一起）

git 是天然答案，但**柔顺**两个字才是设计难点：日常 ingest 撞 `log.md`
和 `index.md` 几乎是必然，靠 git 默认 3-way merge 会大量产生 conflict
marker 让用户自己解，违反"humans abandon wikis because the maintenance
burden grows"的原则。

## 2. Goal & non-goals

**Goal:** 一个 `wiki-sync` skill，对 resolved wiki root 做 pull / merge /
push，对 `log.md` / `index.md` 这类 append-and-union 文件**自动合**，
对页面 body / SCHEMA.md 这类**策略冲突**显式停下来写报告，**保住
auto-dreaming 的 filesystem-only 不变量**，每次运行都向 `dreaming/`
落一份 sync 报告。

**Non-goals:**

- 跨项目批量同步（每个 `~/.llm-wiki/<project>` 独立 repo / 独立 remote）
- 实时同步（无 inotify-on-push、无 long-poll）
- 冲突解决 UI（LLM 可以建议，最终人工拍板）
- 通过中央服务器协调多机（git 是协调，没有别的）
- 加密 wiki 内容上云（用户自己选择 remote）
- 自动注册 git remote / 自动 SSH 配置（一次性 setup 由人做）

## 3. Personas / user stories

主要 persona：v1.7.2 已经在用 `~/.llm-wiki/<project>` 多项目布局的
maintainer P1，2-3 台个人设备，单人使用，**不是团队协作**（团队场景
延后到 v1.10）。

| # | 故事 |
|---|------|
| US-1 | P1 笔记本周三 ingest 3 source，桌面周六 ingest 5 source。周日凌晨 cron `wiki-sync --auto && wiki-dream` 在桌面跑，桌面应当看到笔记本的内容；下次笔记本开机 sync 也能看到双向最新 |
| US-2 | P1 出差 2 周回来。`/wiki-sync` 一条命令，2 周的远端活动 fast-forward 进本地，无冲突 |
| US-3 | P1 在 A 机改 SCHEMA.md `dreaming.confidence_threshold = 0.55`，B 机从 baseline 0.6 没动。Sync 应当自动取 A 的改动 |
| US-4 | P1 在 A 改 dreaming threshold 到 0.55，B 改到 0.65（双向都改了）。Sync 应当**停下来**写 sync-conflicts report，不自动选边 |
| US-5 | 两个 cron 窗口重叠（笔记本和桌面恰好都在 23:00）。第二个 sync 看到 per-wiki lock，干净退出，本地状态不变 |
| US-6 | 远端被 force-push 重写历史（误操作）。Sync 检测到 ancestor 不一致，**拒绝合**，让人工干预，避免覆盖本地 |
| US-7 | P1 跑了 `wiki-import` 中途断电，`.wiki-import-checkpoint.json` 留在 wiki root。Sync 不应该把这个 per-machine 状态推到远端 |

## 4. Success metrics

**Quantitative (CI gate):**
- `wiki-sync` 在 500-page repo + 10 commits divergence 上 ≤ 30 s（p99）
- 当唯一 divergence 是 log.md / index.md 时，auto-merge 成功率 ≥ 95%
  (smoke test 模拟)

**Qualitative (4-week dogfood):**
- 0 起"sync 静默 merge 错"事故（所有 auto-merge 留 sync report 可审计）
- 冲突报告人工解决耗时 ≤ 5 min（不需要 grep diff）
- 0 起 force-push 后被静默 reset 事故

**Anti-metrics（故意不优化）:**
- sync 频率：sync 不是越频繁越好；周一次足够
- 合并的 commit 数：少一点反而说明 divergence 小

## 5. Architecture

```
~/.llm-wiki/<project>/                 ← 每个 project 独立 git repo
├── .git/
│   └── config                         ← 含 merge.akwiki-log / akwiki-index driver
├── .gitattributes                     ← NEW: 把 log.md / index.md 绑到 driver
├── .gitignore                         ← 加 per-machine 状态
├── SCHEMA.md
├── log.md                             ← merge=akwiki-log
├── index.md                           ← merge=akwiki-index
├── dreaming/                          ← sync 报告 + dream 候选都在这
│   ├── 2026-05-03.md                  ← dream 输出（已有）
│   ├── sync-2026-05-07.md             ← NEW: sync 摘要
│   └── sync-conflicts-2026-05-07.md   ← NEW: 仅冲突时存在
└── ...

per-machine 状态（被新加的 .gitignore 排除）：
├── .wiki-ingest-queue.json            ← watcher 队列，每台机独立
├── .wiki-import-checkpoint.json       ← 大批 import 中断恢复用，独立
└── .kata-stash-tag                 ← 临时 stash 标记（如有）

per-machine 全局状态（在 ~/.kata/，已经在 repo 外）：
├── watcher-{slug}.pid / .log          ← 不动
└── sync-{slug}.lock                   ← NEW: sync 锁
```

**Skills:**

| Skill | 状态 | 职责 |
|-------|------|------|
| `wiki-sync` | **NEW** | 对 resolved wiki 做 pull / merge / push + 写报告 |
| `wiki-dream` | **不变** | filesystem-only，read log.md + frontmatter 日期 |
| `wiki-config` | **可能加 sync.* 解释** | 已经支持读写 SCHEMA.md scalar |

**调用形态:**

```bash
# 人工，交互式：有冲突就停下让人解
/kata:wiki-sync

# cron / 自动化：有冲突写报告并非零退出（链式 dream 不会跑）
/kata:wiki-sync --auto

# 预演：fetch + 比较 + 模拟 merge，但不写不推
/kata:wiki-sync --dry-run

# 串联（cron 推荐）
0 23 * * 0  /kata:wiki-sync --auto && /kata:wiki-dream
```

## 6. Sync 算法（wiki_sync.py 伪码）

整个流程包在 try/finally 里。任何早退路径都进 `cleanup`，不能跳过 lock
释放、stash 处理、报告生成。**v3 修订:** 把 stash 从「diverge 分支专属」
提前到「任何修改工作树前」(H3);用 stash commit SHA 代替漂移的 stash@{0}
(H1b);cleanup 内部分层 try/finally,lock release 不依赖 report write 成功
(H2 round 2)。

### 6.1 通用入口 + 状态对象

```
state = {
    "lock_acquired": False,
    "stash_sha": None,            # H1b: 真 commit SHA, 不是 stash@{0}
    "stash_msg": None,            # 报告里展示的人读字符串
    "old_origin_sha": None,       # H1a/B2: fetch 前的 origin ref SHA
    "new_origin_sha": None,
    "auto_configured_drivers": False,
    "result": "unknown",          # 见 §9.1 result 枚举
    "report_lines": [],
}
```

### 6.2 cleanup(state) — 分层 try/finally (H2 round 2 + H1b round 3)

```
def find_stash_index_by_sha(target_sha):
    """Find stash@{n} whose commit SHA equals target_sha. None if not found."""
    out = subprocess.check_output(
        ["git", "stash", "list", "--format=%H"], text=True
    )
    for i, line in enumerate(out.splitlines()):
        if line.strip() == target_sha:
            return i
    return None


def cleanup(state):
    # 第 1 层: stash 处理 (允许失败)
    try:
        if state.stash_sha:
            if working_tree_clean() and no_unmerged_paths():
                # apply 用 SHA, 不依赖 stash@{0}
                run("git stash apply " + state.stash_sha)
                # drop 时主动找 SHA 匹配的 stash@{n} (H1b round 3):
                # 上一版直接 drop stash@{0} 在并发 stash 场景下会 drop 错
                idx = find_stash_index_by_sha(state.stash_sha)
                if idx is not None:
                    try: run(f"git stash drop stash@{{{idx}}}")
                    except: pass
                else:
                    state.report_lines.append(
                        f"stash {state.stash_sha[:8]} applied but not found "
                        f"in stash list (likely already dropped or rebased); "
                        f"data preserved as commit, no further action needed")
            else:
                state.report_lines.append(
                    f"stash kept at commit {state.stash_sha}; "
                    f"recovery: `git stash apply {state.stash_sha}` "
                    f"after resolving merge conflicts. "
                    f"To clean up later: find with `git stash list --format='%gd %H'`, "
                    f"then `git stash drop` the matching index")
    except Exception as e:
        # 第 2 层: report write (允许失败)
        sys.stderr.write(f"[wiki-sync] stash cleanup failed: {e}\n")

    try:
        write_local_sync_report(state)   # ~/.kata/sync-reports/{slug}/...
    except Exception as e:
        # report 写失败必须 不能 阻塞 lock release
        sys.stderr.write(f"[wiki-sync] failed to write sync report: {e}\n")
        sys.stderr.write(f"[wiki-sync] dumping summary: {state.result} / "
                          f"{state.stash_sha} / {state.old_origin_sha}\n")

    # 第 3 层: lock release — 不能依赖前两步成功 (H2 round 2)
    if state.lock_acquired:
        try: release_lock()
        except Exception as e:
            sys.stderr.write(f"[wiki-sync] failed to release lock: {e}; "
                             f"manually rm ~/.kata/sync-{slug}.lock\n")
```

### 6.3 主流程入口

```
try:
    6.3.1  find_wiki_root() → root
    6.3.2  读 SCHEMA.md sync.* 配置;若 sync.enabled = false → exit 0
    6.3.3  本地 wiki_id 校验:
           - 读本地 SCHEMA.md `wiki_id`
           - 缺失 → 提示运行 `wiki-init --refresh-id`;
             --auto 模式 exit 非零
    6.3.4  --dry-run 分叉 (M1):
           - 在副作用之前: 不 acquire lock / 不 stash /
             不 register driver / 不 modify log / 不 commit
           - 仅: git fetch origin <branch> (写 .git/refs/remotes/),
             计算 §6.6 判断,输出 preview
           - exit 0,绕过 cleanup (因为没什么需要 cleanup)
    6.3.5  acquire local sync lock (H2):
           - ~/.kata/sync-{slug}.lock 是同机重入保护,不是跨机互斥
           - stale: lock.pid not alive → 自动清;alive 且不是自己 → 友好退
           - state.lock_acquired = True
    6.3.6  前置校验:
           - root/.git 存在;origin remote 已配
           - 无 .git/MERGE_HEAD / REBASE_HEAD / CHERRY_PICK_HEAD
           - .wiki-import-lock 检查 (alive → 友好退;dead → 清后继续)
           - **`.wiki-import-checkpoint.json` 检查 (M2 round 3)**:
             checkpoint 文件存在 → 上次 import 中途断了,可能留下
             untracked 的半成品页;sync 的 stash --include-untracked=no
             无视它们,可能撞 merge → exit 非零,提示用户:
             "wiki-import was interrupted; resume with `wiki-import
             --resume` or clean checkpoint + working tree before sync"
    6.3.7  检查/注册 merge driver (M2):
           - sync.auto_configure_drivers = false → 跳过
           - 当前 driver 已配且路径仍指向存在脚本 → 跳过
           - 未配或路径失效 → git config --local 写入;
             state.auto_configured_drivers = True
           - log.md 暂不追加,等 commit 阶段一起写

    6.4   **stash 必须在任何修改工作树之前 (H3 round 2)**:
          - 检查 tracked 文件是否有 uncommitted 改动 (含 staged + unstaged)
            untracked 不管 (--include-untracked=no)
          - 有 → `git stash push --keep-index=false --include-untracked=no
                 -m "[kata sync] auto-stash {ISO ts}"`
          - 立即 `state.stash_sha = git rev-parse refs/stash` 把 commit
            SHA 锁住 (H1b round 2)
          - state.stash_msg = "[kata sync] auto-stash {ISO ts}"
          - **stash 提到这里 = fast-forward / merge / no-op 三种路径都
            统一适用**
          - 工作树脏但 stash 失败 → exit 非零,不能继续

    [核心同步流程 6.5 - 6.11,见下方]

except KeyboardInterrupt:
    state.result = "interrupted"
    state.report_lines.append("[user interrupted]")
    raise   # 让 finally 跑

finally:
    cleanup(state)
```

### 6.5 — 6.10 fetch + 三层 ancestry 检测 (H1a / B2)

```
6.5  state.old_origin_sha = git rev-parse --verify origin/<branch>
                            # 可能不存在 (首次本机 fetch); 不存在记 None
6.6  git fetch origin <branch>
6.7  state.new_origin_sha = git rev-parse --verify origin/<branch>
                            # fetch 后 ref 必须存在;不存在 = origin 不见了
6.8  Ancestry case 分类 (H1a / B2 共同处理):

  case (i):  state.old_origin_sha is None
             AND `git merge-base HEAD origin/<branch>` 返回**非空** SHA
             → 首次本机 fetch 但有共同祖先 → 正常,继续
  case (ii): state.old_origin_sha is None
             AND `git merge-base HEAD origin/<branch>` 返回**空** (无共祖)
             → **unrelated histories** (T-sync-18) → state.result =
             "unrelated-history"; report.add("local and remote have no
             common ancestor; this is usually identity mismatch or two
             machines independently ran wiki-init"); exit 1
  case (iii): state.old_origin_sha == state.new_origin_sha
             → origin 没变,继续按 §6.11 比较 HEAD 与 origin
  case (iv): old != new
             AND `git merge-base --is-ancestor old new` is **True**
             → 正常远端 fast-forward,继续
  case (v):  old != new
             AND `git merge-base --is-ancestor old new` is **False**
             → **force-push / history rewrite** (B2);
             state.result = "force-push-detected";
             report.add("Remote rewrote history. old=<sha> new=<sha> "
                       "If intentional, manually fetch + reset --hard "
                       "origin/<branch> after backing up local commits.");
             exit 1
6.9  Identity 校验 (H7,fetch 后):
     - `git show origin/<branch>:SCHEMA.md` → 解析 remote wiki_id
     - 与本地不一致 → state.result = "identity-mismatch"; exit 1
     - remote SCHEMA.md 不存在或无 wiki_id → warn 但允许继续 (旧 wiki
       未升级);记到 report
```

### 6.11 比较与合并 (stash 已在 6.4 处理过)

```
6.11 比较 HEAD 与 origin/<branch>:
   a. 完全相等 → state.result = "up-to-date"; **不写报告** (减少 noise)
                cleanup 仅释 lock + 处理 stash; exit 0
   b. local 仅前进 → push (见 6.12); state.result = "pushed"; exit 0
   c. origin 仅前进 → fast-forward (`git merge --ff-only`);
                     state.result = "fast-forward"; exit 0
   d. 双向 diverge:
      i.   `git merge --no-commit --no-ff origin/<branch>`
           (driver 已注册,git 自动调用)
      ii.  检查 .git/index 中 unmerged 路径:
        - 有 unmerged → state.result = "conflicts";
          写 conflict 报告 (§9.3,含 stash SHA 给 recovery 用 H1b);
          --auto 模式 exit 非零;
          交互模式 exit 0 但 report 提示用户;
          **保留 .git/MERGE_HEAD 给用户继续解;
          cleanup 不会 pop stash (working_tree_clean() 返回 False)**
        - 无 unmerged → 写 driver 审计行进 log.md,commit
          "[kata sync] merge origin/<branch> at {ISO ts}"
      iii. commit 成功 → push (见 6.12); state.result = "merged"; exit 0
6.12 push retry (跨机 race 兜底,H2):
   - 第一次 push
   - 失败 (non-fast-forward) → fetch + 重新算 §6.11;
     若仍 diverge 走 (d);若变 (b/c) fast-forward
   - bounded retry 3 次,backoff 1s/2s/4s
   - 超出 → state.result = "race-exhausted"; exit 非零
```

## 7. 冲突矩阵（核心决策表）

矩阵分两列描述行为：**MVP 行为** = v1.8 第一次发布要做到的；**v1.8-full
行为** = 在 MVP 完成后陆续完善的。MVP 阶段不能用 full 列误导验收 (M3)。

| 文件 / 字段 | 冲突频率 | MVP 行为 | v1.8-full 行为 |
|-------------|----------|----------|----------------|
| `log.md` | 每次操作 | **akwiki-log** driver: 全 entry 文本哈希去重，body 不同的同三元组保留多份，按日期/action 排序 (B3) | 同 MVP |
| `index.md` | 每次 ingest | git 默认 3-way；冲突走 conflict report | **akwiki-index** driver: section-aware union；section rename 触发 exit 非零，prose 三方不一致 exit 非零 (H5/H6) |
| `dreaming/{date}.md` | 周一次 | filename 含日期天然 namespace；真撞了取 candidates 多的 | 同 MVP |
| `raw/**` (immutable) | append-only | 文件名不撞就不撞；真撞了 abort | 同 MVP |
| `entities/`, `concepts/`, `comparisons/`, `queries/`, … 页面 body | 中 | 内容级冲突走 git 默认；写到 sync-conflicts | 同 MVP |
| `SCHEMA.md` | 罕见 | git 默认；任何冲突都人工 (策略变化) | 同 MVP；外加 wiki_id 字段 fetch-time 比对 (H7) |
| `_archive/` | 偶尔 | 同页面 body | 同 MVP |
| frontmatter `updated`, `tier_override_set_at` | 中 | git 默认 (即冲突就 report) | take-max date 辅助 |
| `tier_override_reason` | 中 | git 默认 | 配合 `_set_at` take-max |
| **`.gitattributes`** (control file, M4) | 罕见 | **任何冲突 abort，sync 自身控制面不该自动改** | 同 MVP |
| **`.gitignore`** (control file, M4) | 罕见 | 同 `.gitattributes` | 同 MVP |
| **`templates/`** (用户级 template, M4) | 罕见 | 普通 page body 处理 (用户自定义内容)；若不支持用户在 wiki 内放 templates，文档需说明 out of scope | 同 MVP |
| **`.wiki-plugins.yaml`** (H4) | per-user | **gitignore by default** (含本机绝对路径、外部工具 vars，可能有敏感字段) | 同 MVP；用户若要部分共享，自己维护 `.wiki-plugins.shared.yaml` (out of v1.8 scope) |
| `.wiki-ingest-queue.json` | 经常 | gitignore | 同 MVP |
| `.wiki-import-checkpoint.json` | 偶尔 | gitignore | 同 MVP |
| `.wiki-import-lock` | 暂时 | gitignore；wiki-sync 检测 (§11.8) | 同 MVP |

## 8. 自定义 merge driver

两个独立脚本,git 调用契约:`%A`(ours) `%O`(base) `%B`(theirs)。

### Driver 失败语义 (H4 round 4 — 简化为单失败路径)

**v3/v4 都尝试同时支持 `textual fallback (调 git merge-file)` + `semantic
marker` 两种 driver 失败语义,但 round-4 复审指出 textual 路径有难解的
exit code 选择问题: 如果 driver raise `TextualUnmergeable` 但 merge-file
返回 0 (文本能 clean merge),既不能 exit 0 (driver 已放弃) 也不能 exit 1
(强制 unmerged 但无 marker)。**

**v5 的解法: 砍掉 textual fallback 这一整条路径。** 我们的 wiki 文件 (log.md /
index.md) 的**结构化语义** 比 git 的纯文本 3-way 重要 — 即使文本能 clean
merge,**driver 拿不准**就该把它当真冲突给用户。文本 3-way 在结构文件上常常
产生看似 clean 但语义已破的结果 (e.g. log entry 顺序被打乱)。

新契约 (v5 simplified):

- **exit 0** = driver 真的合得出结果,把已合并内容写入 %A,git 接受
- **exit 非零** = driver **统一调** `write_semantic_marker(reason=...)`
  把 `AKWIKI-SEMANTIC-CONFLICT` 块写进 %A,内含原因 + 三方原文;exit 1
- **不再调 `git merge-file`,不再有 TextualUnmergeable 路径**

实现层面:

```python
def write_semantic_marker(a_path, o_path, b_path, reason: str):
    """统一的 driver 失败处理: 写 AKWIKI-SEMANTIC marker 块到 %A,
    包含原因说明和三方原文供用户参考。永远 exit 1。"""
    ours = read(a_path); base = read(o_path); theirs = read(b_path)
    block = (
        f"<<<<<<< AKWIKI-SEMANTIC-CONFLICT: {reason}\n"
        f"# Driver could not auto-merge this file.\n"
        f"# Reason: {reason}\n"
        f"# Resolve manually then `git add` and `git commit`.\n"
        f"# (Three versions below are for your reference; replace the entire\n"
        f"#  block with your resolved content.)\n"
        f"#\n"
        f"# --- ours (your local) ---\n"
        f"{ours}\n"
        f"# --- base (common ancestor) ---\n"
        f"{base}\n"
        f"# --- theirs (remote) ---\n"
        f"{theirs}\n"
        f">>>>>>> AKWIKI-SEMANTIC-CONFLICT-END\n"
    )
    write(a_path, block)

# Driver 主流程示例 (统一形态):
try:
    result = smart_merge(ours, base, theirs)
    write(a_path, result)
    sys.exit(0)
except CannotAutoMerge as e:
    # 任何 driver 决定放弃的情形 (parse failure / section rename / prose
    # 不一致 / structural ambiguity / ...) 都走这里
    write_semantic_marker(a_path, o_path, b_path, str(e))
    sys.exit(1)
```

**关键点:**
1. driver 永远负责 %A 内容 (H4 round 2/3 不变量),不假设 git 会做什么
2. 不依赖 `git merge-file` 的 rc — 我们的 driver 不去问 git "你能不能合"
3. 用户视角永远清晰: 看到 `AKWIKI-SEMANTIC-CONFLICT` 块就知道这是 driver
   主动放弃,需要人工 resolve;参考三方原文写最终内容
4. **代价**: 失去 git 文本 3-way 在简单情况下的"自动 clean merge"能力。
   接受 — 因为我们的文件是结构化的,文本 clean ≠ 语义 OK

### `plugin/scripts/merge_log.py`  (B3 + M1 round 3 + H5 round 3)

**Canonical hash form (M1 round 3 修订)** — v3 在 revision history
说"保留顺序"但伪码用 `sorted(...)`,自相矛盾;round-3 reviewer 10/10
catch。新原则: **默认保留 body 行顺序**,只对已知"无序集合"的字段
内部 canonicalize。

```python
# 已知"无序集合"字段:这些行的逗号列表内部 sort,行本身位置不动
UNORDERED_LIST_FIELDS = ("Files:", "Created:", "Updated:",
                         "Promoted:", "Linked to:", "Skipped:")

# 标签前缀: hash 时主动剥离, 以免 (side: ours) 进入下一轮 hash 累积
SIDE_LABEL_RE = re.compile(r"\s*\(side:\s*(ours|theirs)\s*\)\s*$")
SYNC_BODY_RE = re.compile(r"^\s*-\s*Sync-side:\s*(ours|theirs)\s*$")

def canonicalize_subject(subject: str) -> str:
    """剥离 (side: ...) 标签 + strip 空白。
    保证下一轮 sync 时同 entry 的 hash 仍稳定 (H5 round 3)。"""
    return SIDE_LABEL_RE.sub("", subject).strip()

def canonicalize_body_line(line: str) -> str:
    """无序字段 -> 内部 sort;Sync-side 行剥掉;其他行保留原样。"""
    s = line.rstrip()
    if SYNC_BODY_RE.match(s):
        return None  # 完全过滤掉 Sync-side body 行
    for prefix in UNORDERED_LIST_FIELDS:
        # 匹配 "  - Files: a.md, b.md" 或 "Files: a, b" 等
        m = re.match(rf"^(\s*-?\s*{re.escape(prefix)})\s*(.*)$", s)
        if m:
            head, tail = m.groups()
            items = sorted(x.strip() for x in tail.split(",") if x.strip())
            return f"{head} {', '.join(items)}"
    return s

def entry_hash(entry: LogEntry) -> str:
    """Hash entry by date / action / canonical subject / canonical body.
    Header 不参与;空行丢掉;Sync-side 行剥掉;无序字段内部 sort。"""
    canon_subject = canonicalize_subject(entry.subject)
    canon_body_lines = []
    for line in entry.body_lines:
        c = canonicalize_body_line(line)
        if c and c.strip():  # 丢空行 + None
            canon_body_lines.append(c)
    payload = (f"{entry.date.isoformat()}|{entry.action}|{canon_subject}\n"
               + "\n".join(canon_body_lines))  # 保留行顺序
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

**为什么这样:**

- `Files: a.md, b.md` vs `Files: b.md, a.md` → 同 hash (canonicalize 后
  内部 sort)
- "Step 1: …" + "Step 2: …" vs "Step 2: …" + "Step 1: …" → **不同** hash
  (行顺序保留;用户 step 顺序是有意义的)
- 之前版本 `(side: ours)` 标签和 `Sync-side: theirs` body 行: hash 时
  剥离, 不进 canonical,避免 round-trip 中 dedup 失效

**Driver 流程**:

```
1. 读 ours/base/theirs 三份 log.md (driver 收到 git 传的 %A %O %B 路径)
2. 用 wiki_lib.parse_log 解析成 LogEntry 列表;每条 entry 标记来源
   (origin = 'ours' | 'base' | 'theirs')
3. 计算每条 entry 的 entry_hash(); 求三方合集
4. **分类 (M5 round 5 修订 — render_body_with_side 调用范围明确):**
   - **Common entries**: 三方都有相同 hash, 或 ours+base 共有 (theirs
     删了) / base+theirs 共有 (ours 删了) / 任意两侧共有但同 hash —
     **不加 Sync-side 行** (这些 entry 不存在 body divergence,无需
     标记来源)
   - **Unique-side entries**: 仅 ours 有 (theirs/base 都没有相同 hash) →
     render_body_with_side(body, "ours")
     仅 theirs 有 (ours/base 都没有) → render_body_with_side(body, "theirs")
     这些是真正"新增"的 entry, 来源单一明确
   - **Same-triple-different-body duplicates**: (date, action,
     canonical_subject) 三元组相同但 entry_hash 不同 → 来自 ours 的
     用 render_body_with_side(body, "ours"); 来自 theirs 的用
     render_body_with_side(body, "theirs"); base 那一份 (若存在)
     不渲染 (它是被改之前的版本, 已被 ours/theirs 各自的版本取代)。
     **两份都保留** (B3 不变)

   渲染辅助函数:
```python
def render_body_with_side(body_lines, side: str) -> list[str]:
    """Idempotent: 先剥所有现存 Sync-side 行,再追加 ONE 新行。
    多轮 sync 反复调用不会累积重复标签 (M5 round 4)。"""
    cleaned = [l for l in body_lines if not SYNC_BODY_RE.match(l)]
    cleaned.append(f"- Sync-side: {side}")
    return cleaned

def render_body_clean(body_lines) -> list[str]:
    """For common entries: 只剥旧 Sync-side, 不加新; 因为 common entry
    不需要标记来源 (没有 divergence)。"""
    return [l for l in body_lines if not SYNC_BODY_RE.match(l)]
```

   两个辅助函数都 unconditional 剥 Sync-side, 保证从 v3/v4 老 log.md
   迁移时旧 side 标签也会被清理。
5. 排序:
   - 主键: date asc
   - 次键: action 字母序 (init < ingest < query < lint < ...)
   - 末键: entry_hash (确保跨机重现稳定)
6. 重写 log.md:
   - header_block (起始到第一个 `## [` 之前): 三方相同 → 保留;
     不同 → 取 ours
   - body: 按 §4 分类调用 render_body_with_side / render_body_clean,
     不再"无差别"对每条 body 加 Sync-side
7. exit 0 — 此 driver 没有 semantic conflict 概念,所有冲突都是 union
   能解决的;真出错 (parse fail / IO 错) 走 §8 通用
   `write_semantic_marker()` + exit 1
```

**已知边界:**
- 用户手改某条历史 entry → merge 保留两个版本 (改前 / 改后),接受
  这个代价换 zero data loss
- 跨大时间窗 (一台机离线 6 个月) 排序后量大但线性,几千条 entry 无
  性能问题
- "Sync-side: ours/theirs" body 行的语义在用户视角是次要信息;**v1.9
  backlog**: 让每个 wiki-* 操作在写 log entry 时嵌入 machine
  wiki_id 后缀,driver 直接读,给出更可读的 machine 标识

### `plugin/scripts/merge_index.py`  (H5 / H6 + H4 round 4 统一 semantic-marker)

```
1. 读 ours/base/theirs 三份 index.md
2. 解析成结构化:
   - header_block: 文件起始到第一个 `## ` 之前的所有内容
   - sections: [(title, [content_lines]), ...],保留出现顺序
3. **Section rename 检测 (H5)**:
   - 计算 base 的 section title 集合 vs ours 的 vs theirs 的
   - 若 ours 删了 X 加了 Y (Y ∉ base),theirs 同时改了 X 的 bullets →
     section rename 检测命中,**调 `write_semantic_marker(reason=
     "section rename: ours renamed '{X}' to '{Y}'; theirs modified "
     "bullets under '{X}'")` + exit 1** (H4 round 4: 不再走 textual
     fallback,driver 自己写 AKWIKI-SEMANTIC marker)
4. **Prose 三方一致性 (H6)**:
   - 每个 section 拆成 bullet 行 (`- ` / `* ` / `1.` 起始) 和 prose 行
   - 三方 prose 完全相同 → 原样保留
   - 不同 → `write_semantic_marker(reason="prose lines differ in
     section '{title}'") + exit 1`
5. parse 失败 (e.g. 文件不是合法 markdown 结构):
   - `write_semantic_marker(reason="failed to parse index.md: <error>")
     + exit 1`
6. §3 §4 §5 都通过才走 union:
   - 每个 section 内 bullet 行三方 union;保留 base 出现顺序,新增的
     按字母序加在节末
   - section 顺序: ours / base / theirs 三方 union,按出现位置稳定排序
7. header_block:
   - 三方完全相同 → 保留;不同 → 取 ours
   - "Last updated" / "Total pages" 这类动态字段 driver 不重算 (这是
     wiki-lint / wiki-init 的责任),原样保留
8. exit 0 仅当 §3 §4 §5 §6 §7 全部 OK;任一步触发
   `write_semantic_marker()` 后 exit 1
```

**为什么这样:** 与 §Driver 失败语义一致 — 我们的 wiki 文件结构语义
比 git 的纯文本 3-way 重要。即使 prose 文本能 clean merge,我们的
driver 拿不准就该交给用户。所有失败路径都走 `write_semantic_marker`,
exit code 永远是 0 (成功) 或 1 (语义放弃)。**没有第三种 driver 失败模式**。

### Driver 注册 — 自动写入策略 (Option A,带三条护栏)

git driver 的命令是机器相关的,**不能 commit**,每个 clone 必须本地配。
我们选择 **wiki-sync 首次运行时自动 set**,而不是要求用户跑 `--setup`,
理由:用户 forget setup 后 git 会用 default merge 处理 log.md 产生
conflict markers,**静默退化** 比 explicit 的"missing config"错误更难
debug。三条护栏让自动方案安全:

1. **每次 sync 启动都 verify** — 当前 `merge.akwiki-log.driver` 指的
   脚本路径是否仍存在;不存在(plugin 被搬到别处) → 自动重写
2. **写入留痕** — driver 一旦被设置或更新,往 log.md 追加一行
   `## [date] sync | configured merge drivers` + 路径,审计可见
3. **Rollback 文档化** — §16 列出 `git config --unset` 流程,
   `wiki-sync` 看到 `sync.enabled: false` 也会跳过自动 set

`.gitattributes` (committed,与 driver 命令解耦):
```
log.md   merge=akwiki-log
index.md merge=akwiki-index
```

git config 自动写入(per-clone,首次 sync / 路径失效时触发):
```
git config --local merge.akwiki-log.driver  "<python> <plugin_root>/scripts/merge_log.py %A %O %B"
git config --local merge.akwiki-log.name    "kata log union+sort merge"
git config --local merge.akwiki-index.driver "<python> <plugin_root>/scripts/merge_index.py %A %O %B"
git config --local merge.akwiki-index.name   "kata index section-aware merge"
```

`<python>` = `sys.executable` (优先 `py -3` on Windows 等价物);
`<plugin_root>` = 当前 wiki-sync 调用上下文里 `.claude-plugin/` 所在
目录的绝对路径。**两者跨机不可移植** —— 这是 git driver 的天然限制,
不是我们的设计 bug,但护栏 1 让它在同机重装时自愈。

## 9. Sync 报告 (B1 修正)

**报告路径变更:** v1 设计把报告写在 `dreaming/sync-{date}.md`，是 wiki
repo 内的 tracked 文件 — 但 §6 算法顺序是 push-then-write，**报告永远
赶不上自己的 commit**，下一次 sync 又会把它当 untracked 改动处理 →
循环。

v2 修正: **报告写到 `~/.kata/sync-reports/{slug}/` (local-only)**,
跟 watcher PID/log 同一目录树。每台机器有独立审计日志,**不进 git**,
不会自冲突。

### 9.1 本地报告路径

```
~/.kata/
├── watcher-{slug}.pid       (已有)
├── watcher-{slug}.log       (已有)
├── sync-{slug}.lock         (NEW: per-machine sync lock)
└── sync-reports/
    └── {slug}/
        ├── 2026-05-07T23-00-12Z-success.md
        ├── 2026-05-07T23-15-44Z-conflicts.md
        └── 2026-05-08T08-32-01Z-fast-forward.md
```

文件名包含 ISO 时间戳 (秒级) 避免同日多次 sync 冲名。后缀指明 result:
`success` / `conflicts` / `fast-forward` / `up-to-date` / `force-push-detected` /
`identity-mismatch` / `aborted`。

`sync-reports/` 与 sync 算法本身无 git 交互 — sync 不会去 commit 它,
不会去 fetch 它,不会去 push 它。**纯审计**。Rollback 时 §16 提供
`rm -r ~/.kata/sync-reports/{slug}/` 命令。

### 9.2 成功 sync 报告样本

```markdown
# Sync · 2026-05-07T23:00:12Z

- Wiki: ~/.llm-wiki/necall  (wiki_id: 7f3c9e1a-...)
- Machine: laptop-a3b4c5  (slug: necall-a3b4c5)
- Remote: origin (git@github.com:litianyi/necall-wiki.git)
- Branch: main
- Result: success-with-driver
- Local commits ahead of base: 4
- Remote commits ahead of base: 7  (old origin sha: deadbee, new: cafef00)
- Commit produced: 1a2b3c4 [kata sync] merge origin/main at 2026-05-07T23:00:12Z
- Pushed: yes (1 retry due to push race)
- Stash: none
- Auto-configured drivers: no (already set, paths verified)

## Auto-merged

| File | Driver | Detail |
|------|--------|--------|
| log.md | akwiki-log | added 7 entries; deduped 2; kept 1 same-triple-different-body pair |
| entities/mosaic.md | git default | frontmatter `updated` advanced 2026-05-04 → 2026-05-06 |

## Files cleanly fast-forwarded

- dreaming/2026-05-04.md (remote-only)
- briefs/databricks-acquires-mosaic.md (remote-only)

## Identity check

- Local SCHEMA.md wiki_id: 7f3c9e1a-...
- Remote SCHEMA.md wiki_id: 7f3c9e1a-...   (matched)
```

### 9.3 冲突报告样本

```markdown
# Sync conflicts · 2026-05-07T23:15:44Z

- Wiki: ~/.llm-wiki/necall
- Machine: laptop-a3b4c5
- Result: conflicts (sync stopped, push not attempted)

## State of working tree

- .git/MERGE_HEAD: present  (do NOT manually pop stash until you resolve)
- Stash: commit `9f3a2b1c` ("[kata sync] auto-stash 2026-05-07T23:15:44Z")
  - Always reference by SHA, not stash@{n} — n drifts as user adds/removes stashes
- Unmerged paths:
  - SCHEMA.md
  - entities/foo.md
  - index.md   (akwiki-index driver exited non-zero — section rename detected)

## Conflicts detail

### SCHEMA.md
- Local:  dreaming.confidence_threshold: 0.55
- Remote: dreaming.confidence_threshold: 0.65
- Base:   dreaming.confidence_threshold: 0.6
- Suggested: this is a strategy disagreement; pick the value matching your
  current dogfood window or talk to the other machine's user

### entities/foo.md (line-level)
File has conflict markers `<<<<<<<` / `>>>>>>>` between local and remote.
Open the file to resolve.

### index.md (driver-detected schema change)
akwiki-index driver detected a section rename:
- base has `## Entities`
- ours has `## People` (you renamed)
- theirs modified bullets under `## Entities`

This is a category schema change, not a routine ingest conflict.
Decide whether to keep the rename and apply theirs' bullet changes
under `## People`, or revert the rename.

## Recovery commands

# Resolve conflicts in your editor, then:
git add SCHEMA.md entities/foo.md index.md
git commit                              # message will be the one sync prepared
git push

# Restore your stashed work after manual resolution (use SHA, not stash@{n}):
git stash apply 9f3a2b1c
# Then optionally drop it:
git stash list --format='%gd %H'        # find which stash@{n} matches 9f3a2b1c
git stash drop stash@{N}                # N from above lookup

# Abort everything (loses the merge attempt, keeps your stash by SHA):
git merge --abort
git stash apply 9f3a2b1c                # restore working tree from SHA

# Remote is wrong, you want to overwrite it:
git push --force-with-lease             # only after careful review
```

## 10. Per-machine 状态

新加 `.gitignore`(在 wiki repo 内,与 kata 仓库 .gitignore 不同):

```gitignore
# Per-machine state — should never be synced
.wiki-ingest-queue.json
.wiki-import-checkpoint.json
.wiki-import-lock
.wiki-plugins.yaml          # H4: per-machine; contains absolute paths / vars / secrets
.kata-stash-tag
```

**这一改可以独立先做掉**,不依赖 sync 实现。watcher 队列在多机本来就
不该共享(每台机看到的 raw/ 入队时机不同),import lock / plugins 配置同理。

`.wiki-import-lock` 内容(JSON,沿用 watcher PID 的设计):
```json
{
  "pid": 12340,
  "started_at": "2026-05-07T22:14:03Z",
  "source": "/home/me/notes",
  "format": "obsidian"
}
```

由 `wiki-import` 在 Phase 1 (Discovery) 之前创建,正常结束 / 错误退出
时删除。`is_pid_alive()` 复用 `wiki_watch.py:223` 的跨平台实现。

> **重要 (H3):** 即使有 import-lock,`wiki-import` 必须**修改成 phase 5
> 单次 commit + push**,而不是现在可能的 wave-by-wave 行为。否则 B 机
> 的 sync 仍可能从 origin 拉到 A 机 import 中途已 push 的半成品页。
> 这个改动是 v1.8 MVP 的依赖项,见 §13。

## 11. 安全栏(9 条不变量)

1. **try/finally cleanup** (H1) — lock 释放、stash 处理、报告写入都在
   `finally` 块,任何早退路径都不会跳过
2. **Local sync lock** (H2) — `~/.kata/sync-{slug}.lock` 是 **per-machine**
   重入保护,**不是跨机互斥**;跨机争用走 push rejection + bounded retry
3. **Force-push detect** (B2) — fetch 前后比对 `origin/<branch>` ref 的
   祖先关系;`old_origin` 不是 `new_origin` 祖先就退出 1
4. **Merge in progress** — `.git/MERGE_HEAD` / `REBASE_HEAD` / `CHERRY_PICK_HEAD` 任一存在就退出
5. **--dry-run 真 read-only** (M1) — 在 acquire lock / stash / register
   driver / modify log 之前分叉;只允许 fetch 到 `.git/refs/remotes/`
6. **--auto 退出非零的语义** — 任何冲突让退出码非零,确保 cron 链
   `wiki-sync && wiki-dream` 在冲突时**不会跑 dream**
7. **没配 remote 友好降级** — 报"sync 没配 remote,跳过",不报错
8. **Import-in-progress detect** — `.wiki-import-lock` alive → 友好退;
   pid 已死 → stale 自动清理。配合 §10 的 wiki-import 改造防跨机风险
9. **Wiki identity check** (H7) — fetch 后用 `git show
   origin/<branch>:SCHEMA.md` 提 remote 的 `wiki_id`,与本地比对;
   不一致直接 abort。防止误把不同 wiki 当作同一个

## 12. SCHEMA.md 新 block

```yaml
# 单调 UUID,wiki-init 生成,never auto-changed (H7)
wiki_id: 7f3c9e1a-b8c2-4d3e-9f5a-1234567890ab

sync:
  enabled: true                          # 默认 .git 存在则开;false 则 wiki-sync 直接 no-op
  remote: origin                         # 哪个 remote
  branch: main                           # 哪个 branch
  on_conflict: report-and-exit           # report-and-exit | force-resolve-ours | force-resolve-theirs
  auto_chain_dream: false                # cron 是否需要 sync && dream(脚本本身不串,这是 SKILL.md 的提示)
  auto_configure_drivers: true           # M2: false 时尊重用户 git config --unset,不自动加回
```

`schema_validate` 加这个 block 的 schema:
- `wiki_id` **格式校验** 形如 `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`
  (UUID v4);缺失 / 非法格式 → 报错。
  **不验 immutable** — 单文件 schema 校验只能看格式,无法证明字段在
  历史中没被改过 (M5 round 2)。Identity 是否真稳定靠 sync runtime
  在 fetch 后比对 local vs remote (§6.9 / §11.9)。
- `sync.enabled` bool
- `sync.remote` 形如 `^[a-z][a-z0-9_-]*$`
- `sync.branch` 形如 `^[a-z0-9._/-]+$`
- `sync.on_conflict` enum
- `sync.auto_chain_dream` bool
- `sync.auto_configure_drivers` bool

**Cross-field 规则:**
- `sync.enabled: true` 要求 `wiki_id` 必须存在 (跨机校验需要)
- `wiki-init` 升级时若旧 wiki 缺 `wiki_id` → 提示用户运行
  `wiki-init --refresh-id` 生成 (一次性,要求 commit history 干净或
  显式 `--force`)

## 13. 分期交付

### MVP (v1.8-mvp,目标 2-3 周)

**目的:** 最小可运行的双机同步循环,能接住 80% 日常 ingest divergence,
并且通过审查的所有 BLOCKING 修复都已落地。

依赖项 — `wiki-import` 改造 (H3 + M2 round 2 + M6 round 4 子任务):
- [ ] **import-lock**: `.wiki-import-lock` JSON (pid / started_at /
      source / format) 在 phase 1 创建,phase 5 成功 / 异常退出时删除
- [ ] **Dirty-tree policy**: import 启动时若 wiki tree 有 uncommitted
      改动 → 退出非零提示用户 commit 或 stash;不在脏树上叠 import
- [ ] **Phase 5 单次 commit + push**: 现行 wave-by-wave 写文件改成
      只在所有 wave 完成后**一次** `git add . && git commit -m
      "wiki-import: <source> (<N> pages)" && git push`
- [ ] **Phase 5 success cleanup (M6 round 5 修订)**: **`git commit` 成功
      就删 `.wiki-import-checkpoint.json`**,不等 push 结果。
      理由: commit 后本地状态已经是合法 git repo,即使 push 失败也是
      "同步问题"(由 wiki-sync 处理)而不是 "import 问题"。push 失败时
      wiki-import 打印明确提示:
      ```
      Import committed (local sha: <abbrev>). Push failed: <error>.
      To push later: run `wiki-sync` or `git push` manually.
      Checkpoint cleared — wiki-sync will not be blocked.
      ```
      v5 设计写"commit + push 全成功后才删"漏掉了 commit-OK / push-fail
      中间态,会让 sync 被持续 false-positive 阻塞。round-5 catch
- [ ] **失败 / abort 行为**: 中途失败 (任意 wave 抛异常 / Ctrl-C) →
      已写入 raw/ 的源文件**保留** (raw/ 是 immutable 层,不回滚);
      已写入但未 commit 的 wiki 页保留在 working tree 让用户人工审查;
      checkpoint 文件保留以便 --resume;import-lock 必删

依赖项 — `wiki_id` (H7):
- [ ] `wiki-init` 默认生成 UUID `wiki_id` 字段
- [ ] `wiki-init --refresh-id` 给老 wiki 一次性补 (要求空 commit history
      或 user 显式 `--force` 覆盖旧 id)
- [ ] schema_validate 增 UUID 格式校验 (注意: **不**强制 immutable,
      M5 round 2 — schema 单文件验证不能证明 immutable;identity 依赖
      sync runtime 比对)

可独立先合 (gitignore 部分):
- [ ] `.gitignore` per-machine 状态 (`.wiki-ingest-queue.json` /
      `.wiki-import-checkpoint.json` / `.wiki-import-lock` /
      `.wiki-plugins.yaml`),**这一改无 sync 依赖也独立有意义**

Sync 主体:
- [ ] `wiki_sync.py` 主脚本: try/finally 状态机 (H1) + fetch +
      compare + merge + push retry
- [ ] `wiki-sync/SKILL.md` (interactive + `--auto` + `--dry-run`)
- [ ] **`merge_log.py`** driver (B3 修正: 全 entry 哈希去重,body 不同
      保留多份)
- [ ] **driver 自动注册** + 路径 verify (Option A 三护栏,§8) +
      `sync.auto_configure_drivers` 开关 (M2)
- [ ] **import-lock** 检测 (alive/stale)
- [ ] **Force-push detect 修正** (B2): 比对 fetch 前后 origin ref
- [ ] **Wiki identity 校验** (H7): SCHEMA.md `wiki_id` 字段比对
- [ ] Sync 报告写到 `~/.kata/sync-reports/{slug}/` (B1) + 冲突报告
- [ ] Local sync lock + push retry (3 次, bounded backoff)
- [ ] SCHEMA.md `sync:` block + `wiki_id` field + schema_validate
- [ ] **--dry-run 真 read-only** (M1): 在副作用前分叉
- [ ] Smoke test: 1 共享 bare + 2 working tree fixture

### v1.8 完整版

- [ ] `merge_index.py` driver (H5 section rename detect / H6 prose 严格)
- [ ] frontmatter `updated` / `tier_override_set_at` take-max 辅助
- [ ] cron 串联示例进 wiki-init 输出
- [ ] dogfood-v1.8 文档

### v1.9+ backlog

- [ ] Submodule 模式 (用户每个 wiki 是大 monorepo 的子模块)
- [ ] 让 LLM 在 sync-conflicts 报告里给出推荐 resolution 文本
- [ ] 团队多人协作 (branch 策略 / PR review 集成)
- [ ] `--accept-force-push` 显式 flag
- [ ] `.wiki-plugins.shared.yaml` 共享部分 (剥离 secret/path 后)

## 14. Test plan

`tests/run_smoke.py` 加:

| Test | 场景 |
|------|------|
| T-sync-1 | 完全 up-to-date,sync 无 op,exit 0,**不写任何报告** (减少 noise) |
| T-sync-2 | local 单边领先,push 成功,exit 0 |
| T-sync-3 | remote 单边领先,fast-forward,exit 0 |
| T-sync-4 | log.md 双向各加 entries,akwiki-log driver auto-merge,push 成功 |
| T-sync-5 | (v1.8 完整版) index.md 双向各加 bullets,akwiki-index driver auto-merge |
| T-sync-6 | 同一 page body 双向修改 → conflict 报告,exit 非零,push 不发生,stash 保留 |
| T-sync-7 | **Force-push detect (B2 验证)**: A 机 push 后 B 机直接 `git push --force` 一个无关 commit;A 机 sync `old_origin != ancestor of new_origin` → 退出 1 |
| T-sync-8 | local sync lock:**同机** 第二个 sync 看到 alive lock,friendly exit。注意:这不模拟跨机 |
| T-sync-9 | --dry-run **真不写**:跑完后 `~/.kata/sync-{slug}.lock` 不存在、SCHEMA.md 路径下 `git config` 没新加 driver、`log.md` 内容字节级未变、工作树未变、origin 未变 (M1 验证) |
| T-sync-10 | --auto 退出码:任何冲突都退非零 (用 shell `&&` 链验证 dream 不会跑) |
| T-sync-11 | import-lock alive: `.wiki-import-lock` 含 alive pid → sync friendly 退出,工作树未动 |
| T-sync-12 | import-lock stale: `.wiki-import-lock` 含 dead pid → sync 清理 lock 后继续 |
| T-sync-13 | Driver 自动注册:首次跑后 `git config merge.akwiki-log.driver` 已设;路径指向的脚本被删后重跑 → 自动重设 |
| **T-sync-14** | **B3 验证**: A 机 ingest source.md, log.md 加 `## [date] ingest \| Foo` + `Files: a.md, b.md`;B 机同日同 source ingest, log.md 加 `## [date] ingest \| Foo` + `Files: a.md, b.md, c.md`。Sync 后 log.md 应**同时保留**两条 entry,不能丢一边 |
| **T-sync-15** | **B1 验证**: 跑两次 sync (中间无任何 wiki 改动)。第二次 sync 不应当看到第一次的报告作为 untracked 改动;`git status` 必须 clean (报告在 `~/.kata/`,不在 wiki repo 里) |
| **T-sync-16** | **跨机 push race (L3 round 5 — env var 约定)**: per-role ready 文件方案需要 role 和 barrier dir 显式传给 subprocess。**测试 harness 约定的环境变量**: `AKWIKI_SYNC_TEST_ROLE=A\|B` (subprocess 知道写哪个文件) + `AKWIKI_SYNC_BARRIER_DIR=tests/_sync/barrier-{ts}/` (绝对路径)。pre-push hook 里读这两个 env: 写 `${BARRIER_DIR}/${ROLE}.ready`,然后轮询直到对方 ready 文件存在;**hook 内 timeout 10s 退出非零** (push 失败,父进程感知);harness 父进程 `wait()` + `Popen.kill()` 兜底防 hang。第一个 push 赢, 第二个 reject → fetch + retry, bounded ≤ 3 次, 最终两机一致 |
| **T-sync-17a** | **Graceful interrupt (H1 round 2)**: sync 跑到 fetch 前用 SIGINT 中断;Python finally 块跑;期望: lock 已释放,stash 仍在 stash list 且报告里提到 SHA,不盲目 pop |
| **T-sync-17b** | **Hard kill (M4 round 2)**: sync 跑到 fetch 前用 SIGKILL (POSIX) / TerminateProcess (Windows) 强杀;**finally 不会跑**;期望: 下次 sync 启动检测到 stale lock (pid 已死) 自动清,stash 因为是 git ref 仍可见 (`git stash list`)。这是 H1 的"努力但不保证"边界 |
| **T-sync-18** | **Unrelated histories (H1a round 2 验证)**: 两台机各自 `wiki-init`,history 没共同祖先 (`git merge-base HEAD origin/<branch>` 返回空)。sync 应当被 §6.8 case (ii) 命中,**state.result = "unrelated-history"** 并 exit 1。**不**走 force-push detect 那条 (case v),因为 force-push detect 要求 old_origin_sha 存在;首次本机 fetch 时它不存在 |
| **T-sync-19** | **Identity mismatch (H7 验证)**: 两台机的 SCHEMA.md `wiki_id` 不同;sync fetch 后比对失败 → exit 1 with "remote is a different wiki" |
| **T-sync-20** | **Checkpoint cleanup 三态 (L4 round 6 hook lifecycle 修订)**: 三个子场景: <br>**(a) Full success** — phase 1-5 全 OK + push 成功 → checkpoint 已删 + sync 不被卡 <br>**(b) Commit success, push fail (round-6 修订)** — **测试 harness 主动管理 hook lifecycle**: <br>&nbsp;&nbsp;**Step 1**: 在 origin 装 pre-receive hook 拒收所有 push <br>&nbsp;&nbsp;**Step 2**: 跑 wiki-import → phase 5 commit OK,push 失败 → **assertion 1**: `.wiki-import-checkpoint.json` 已删 (commit 后立即) + 错误提示用户跑 wiki-sync <br>&nbsp;&nbsp;**Step 3**: harness 移除 pre-receive hook (one-shot 完成) <br>&nbsp;&nbsp;**Step 4**: 跑 wiki-sync → **assertion 2a**: preflight 不被 checkpoint 卡 (因为 step 2 已删) + **assertion 2b**: local-ahead-only 路径 push 成功 <br>&nbsp;&nbsp;两个 assertion 分别证明: "checkpoint cleanup 时机正确" (assertion 1+2a) 和 "wiki-sync 能接住 import 留下的未推 commit" (assertion 2b)。避免 conflate "未被卡" 与 "push 成功" <br>**(c) Phase failure** — 模拟 phase 3 mapping 阶段抛异常 → checkpoint **保留** (允许 --resume) + sync 被 preflight **卡** + 错误提示让用户 resume 或 clean |

每条测试用 `tests/_sync/` 下的 fixture:1 个共享 bare repo 充当 origin,
2 个独立 working tree 充当 A 机和 B 机。**T-sync-9** 必须做 byte-level
比对验证 dry-run 没动任何持久状态。

## 15. Open questions / known unknowns

仍未拍板的项:

- **远端 history rewrite 后用户主动想接受:** 当前无脑拒绝。是否需要
  `--accept-force-push` 显式 flag 留 v1.9 backlog。MVP 不做。
- **多 branch 策略:** 当前只 sync `sync.branch` 配置的 branch。如果用户
  在 wiki 里开 feature branch 测试,sync 不会动它 —— 这是有意的,但
  SKILL.md 需要文档化"sync 不是 git wrapper"。
- **dream 跨机 cron timing:** 当前推荐 "A dream → A sync → B sync → B
  dream",但 cron 是固定时间触发,无法保证顺序。MVP 不解决,SKILL.md
  写"建议 A 机和 B 机错开 cron 时段 (例如 A=23:00, B=23:30)"。

已在 v2 决定的项 (复审 follow-up):

- ~~**B1 sync 报告生命周期**~~ → 报告改写到 `~/.kata/sync-reports/`
  (§9.1),不进 wiki repo,不会自冲突
- ~~**B2 force-push 检测 tautology**~~ → 改为比对 fetch 前后的
  `origin/<branch>` ref 祖先关系 (§6.7-6.9)
- ~~**B3 akwiki-log body 数据丢失**~~ → 改为完整 entry 哈希去重,
  body 不同保留多份 (§8)
- ~~**H1 finally cleanup**~~ → §6.1/6.2 显式状态机
- ~~**H2 sync lock 命名**~~ → "local sync lock" + 跨机靠 push retry (§11.2)
- ~~**H3 wiki-import 半成品 push**~~ → import 必须 phase 5 单次 commit
  (§13 MVP 依赖项)
- ~~**H4 .wiki-plugins.yaml**~~ → per-machine gitignore (§7 / §10)
- ~~**H5 section rename**~~ / ~~**H6 prose 三方不一致**~~ → driver exit
  非零 (§8)
- ~~**H7 wiki identity**~~ → SCHEMA.md `wiki_id` UUID 字段 (§11.9 / §12)
- ~~**M1 dry-run side effects**~~ → 在副作用前分叉 (§6.4 / §11.5)
- ~~**M2 driver auto-config 与用户 unset 冲突**~~ →
  `sync.auto_configure_drivers` 开关 (§12)
- ~~**M3 矩阵 MVP vs full 混淆**~~ → §7 加两列
- ~~**M4 control files 策略**~~ → §7 加 `.gitattributes` /
  `.gitignore` / `templates/` 行
- ~~**Driver Option A vs setup**~~ (v1) → 维持 Option A 三护栏
- ~~**大文件 push 失败提示**~~ (v1) → 不在 MVP 范围

## 16. Roll-out & rollback

**Roll-out:**
- v1.8.0 SCHEMA.md 默认 `sync.enabled: true`(当 .git 存在时);
  老 wiki 升级后第一次运行 wiki-sync 才生效
- `wiki-init` 加 `--enable-sync` flag,新 wiki 默认开
- README 加 multi-machine 章节,引到本文档

**Rollback (基础):**
- `wiki-config --set sync.enabled false`  → wiki-sync 直接 no-op
- `wiki-config --set sync.auto_configure_drivers false` → 防止再次自动注册
- `git config --unset merge.akwiki-log.driver`
- `git config --unset merge.akwiki-index.driver`
- 删 wiki 内 `.gitattributes` 中的 driver 绑定行 (commit 这一改动)
- `wiki-sync` 看到 `enabled: false` 直接 no-op 退出

**Rollback (可选 cleanup, L1):**

下列文件 / 历史 commit 不会影响人工 `git pull/push`,可留作审计:

- `~/.kata/sync-reports/{slug}/` — 本地报告日志,可以
  `rm -r ~/.kata/sync-reports/{slug}/` 清空,纯审计无功能依赖
- `~/.kata/sync-{slug}.lock` — 自然过期,可以删
- 历史 sync commit (commit message 含 `[kata sync]`) — 不能 rewrite
  history,但人工继续用普通 git 时不影响
- log.md 里 `## [date] sync | configured merge drivers` 行 — 可以
  人工 `git revert` 或保留作为审计

回到不带 sync 的状态,wiki 仍是普通 git repo,用户可以手 `git pull/push`。
**这是设计上对回退的支持:sync 是 amplifier 不是 gatekeeper。**

## 17. 风险点

| 风险 | 触发条件 | 缓解 |
|------|----------|------|
| Driver 在某些 git 版本表现不一 | git < 2.20 不支持某些 attribute | MVP 在 README 写最小 git 版本 |
| Custom merge driver 失败但 git 看不出来 | driver exit 非零时 git 不会自动跑 default merge — 它把 driver 当时写到 %A 的内容当作 unmerged 文件保留 | §8 round 5 简化: driver **任何失败统一调 `write_semantic_marker(reason=…)` + exit 1**,不再有 textual fallback / `git merge-file` 路径;wiki-sync 脚本主动检查 `.git/MERGE_MSG` 和 unmerged 路径,确认每个 unmerged 文件都含可读 `AKWIKI-SEMANTIC-CONFLICT` marker |
| Marker block 嵌三方原文使大文件三倍膨胀 (round 5 新增) | semantic conflict 时 marker 块内嵌 ours/base/theirs 三份原文,500 行 index.md → 1500+ 行 marker。git diff 视图会很乱 | **接受** — 用户人工 resolve 时三方原文是最有用的上下文,优于让用户去 `git show :1:foo` / `:2:foo` / `:3:foo` 逐 stage 查看。文档化在 §9.3 recovery 提示用户用 editor (而非 `git diff`) 看冲突 |
| 用户在多台机有不同的 plugin_root | git config 里的 driver 路径绝对化后跨机失效 | §8 护栏 1: 每次 sync 启动 verify 路径,失效就自动重写 |
| Sync 时 watcher daemon 在写 queue.json | 队列文件已 gitignore,但 stash 时可能扫到 | stash 用 `--include-untracked=no`,只 stash 已 tracked 的 |
| SCHEMA.md 自动 merge 的双方都改了同一行 | 真策略冲突 | 这正是 §11.6 兜的:报告 + 退出非零;**identity (wiki_id) 不在 schema field 里手 set,所以这条规则不影响 identity 校验** |
| dream 跨机重复 promote 同一 page | 两台机各自 dream apply 同一候选 | M9 dedup 已处理 (后写覆盖前写);SKILL 推荐 cron 错开时段 (§15) |
| Import 中途 B 机 sync 拉到 A 机 push 的半成品页 | A 机 wave-by-wave commit 期间 B 机 sync | **修复要求 (H3 / §13 MVP 依赖项)**: wiki-import 必须改为 phase 5 单次 commit + push;import-lock 仅防同机重入 |
| Import-lock 进程被 kill 后留 stale lock | A 机 import SIGKILL,lock 文件不清 | sync 检测 dead pid 自动清理 + warn (T-sync-12) |
| **Wiki identity 漂移** | 用户手编 SCHEMA.md 改了 `wiki_id` | schema_validate 只能验 UUID 格式,**单文件无法证明 immutable** (M5 round 2)。真正的兜底是 sync runtime: fetch 后 §6.9 比对 local vs remote `wiki_id`,不一致 hard stop (T-sync-19)。如果两机用户都各自把 wiki_id 改成相同的非原值,这是 user error,设计不防 — 类似 git 用户用同一 SSH key 推到两个不同 repo |
| **跨机 push race 进入死循环** | A/B 持续高频 commit + sync,push retry 一直被对方挤掉 | bounded retry 3 次 (§6.12);超出报告"concurrent sync race",建议手动 stagger sync timing |
| **Sync 中 SIGTERM 后 lock / stash 残留** | Ctrl-C / OS reboot 在 sync 中 | §6.2 cleanup 在 finally 触发;若进程被强 kill, lock 含 pid,下次 sync 检测 stale 自清;stash 不会丢 (commit 在 stash 上,worst case 用户 `git stash list` 可见) |
| **Dry-run 误改动状态** | `--dry-run` 调用了 §6.5 / §6.6 中的副作用代码 | T-sync-9 byte-level 验证 dry-run 不动 lock / log / config / 工作树 / origin |

## 18. Appendix — sync 状态机

```
              ┌──────────────────────┐
              │   wiki-sync invoked  │
              └──────────┬───────────┘
                         ▼
            ┌──────────────────────────┐
            │ resolve wiki / read cfg  │
            │ identity check (local)   │
            └──────────┬───────────────┘
                       ▼
              ┌────────┴────────┐
              │  --dry-run ?    │── yes ──▶ fetch only / preview / exit
              └────────┬────────┘
                       │ no
                       ▼
            ┌──────────────────────────┐
            │ acquire local sync lock  │
            │ register driver if need  │
            │ STASH (if dirty tree)    │  ← stash 提前到这里 (H3 r2)
            │ record stash SHA         │  ← 用 SHA 不用 stash@{0} (H1b r2)
            └──────────┬───────────────┘
                       ▼
            ┌──────────────────────────┐
            │ fetch + ancestry classify│
            └──────────┬───────────────┘
                       ▼
       ┌────────┬──────┼──────┬──────────┬───────────┐
   equal  ahead  behind  unrelated   force-push   identity-mismatch
       │      │      │       │            │              │
       ▼      ▼      ▼       ▼            ▼              ▼
    no-op  push   ff-only  EXIT 1     EXIT 1         EXIT 1
       │      │      │  (case ii)   (case v)     (post-fetch)
       │      │      │       │            │              │
       │      │      │  (state.result   (state.result   (state.result
       │      │      │  = unrelated-    = force-push-   = identity-
       │      │      │   history)        detected)       mismatch)
       │      │      │
       └──────┴──────┘
                │
                ▼              ┌─── diverge case ───┐
                │              │                    │
                │              ▼                    │
                │   ┌─────────────────────┐         │
                │   │ git merge --no-ff   │         │
                │   │ drivers run         │         │
                │   │   - akwiki-log      │         │
                │   │   - akwiki-index    │         │
                │   │   - default 3-way   │         │
                │   └──────────┬──────────┘         │
                │              ▼                    │
                │      ┌───────┴────────┐           │
                │   no-conflict     conflict        │
                │      │                 │          │
                │      ▼                 ▼          │
                │  commit           keep MERGE_HEAD │
                │  push (retry)     EXIT (auto≠0)   │
                │      │                 │          │
                └──────┘                 │          │
                                         │          │
                ┌────────────────────────┴──────────┘
                │
                ▼  (any exit path lands here, including exceptions)
            ┌──────────────────────────────┐
            │ FINALLY cleanup(state):      │
            │   try: stash apply <SHA>     │  ← 失败不阻塞下一步
            │   try: write local report    │  ← ~/.kata/sync-reports/
            │   try: release lock          │  ← 必跑 (H2 r2)
            └──────────────────────────────┘
                       ▼
                     exit
```

(图比 v2 更精确: stash 提前到 fetch 之前; ancestry 分类有 6 个分支
而不是 v2 的 4 个;cleanup 三层各自有 try。报告路径修正为 local。)

---

## 给跨 LLM 复审的关注重点

如果这个设计要交叉复审,建议 reviewer 抓这几点:

1. **§7 冲突矩阵**有没有遗漏的文件类型?特别是 `_archive/`、watcher 队列、
   未来可能加的字段。
2. **§8 merge driver** 算法是否真的对 log.md / index.md 普遍成立?有没有
   反例(用户在 index.md 里加自由文字段是否会被破坏)?
3. **§11 安全栏**是否够?force-push detect 是否有 bypass(例如 origin 的
   ref 被改写但 reflog 看不见)?
4. **§12 SCHEMA `sync:` block** 配 schema_validate 是否有 cross-field 规则?
   例如 `enabled: true` 时 remote/branch 必填?
5. **§17 风险点**第 4 行(stash 与 watcher daemon 竞态)是否还能再细化?
6. v1.8-MVP 的范围是否合理?(我倾向先只做 log.md driver 是因为 80%
   收益在那里;index.md 可以靠 git 默认 merge 在 MVP 阶段维持)
