# HN 提交手册 — 首次发布操作指南

> 第一次在 Hacker News 上发布 essay 的全流程。覆盖：注册 → 登录 → profile 配置 →
> 提交 → 提交后第一小时 → 评论应对。
>
> 平台说明：HN 是 Y Combinator 运营的技术社区，全英文，UI 非常 minimalist —
> 没有图片、没有动画、没有 emoji（社区规范不接受），唯一的样式是 #ff6600 橙
> 顶 bar。**功能上 = Reddit 的最早形态 +技术内容过滤**。读者画像：硅谷工程
> 师、startup founder、HFT/PE/学术人员混合，对营销话术零容忍。
>
> 适用于：Essay #1（2026-05-15 提交）+ Essay #2 + 之后所有 HN 提交。

---

## 第 1 步 — 注册账号

### 准备

- 用户名：**强烈建议用 `surebeli`**（与 github 一致，IP 收敛）
  - 用户名一旦确定**不能改**
  - 区分大小写
  - 用户名公开可见
- 密码：HN 没有强密码要求，但建议至少 16 位。**HN 不强制要求 email**，
  所以密码忘了 = 账号丢
- 浏览器：任意（HN UI 极简，所有现代浏览器都行）

### 操作

1. 打开 https://news.ycombinator.com/
2. 右上角点 `login`
3. 进入登录页面，**滚动到下方**，会看到 `Create Account` 区块（不需要点别的按钮，登录页面同时是注册页面）
4. 填入 `username` 和 `password`
5. 点 `create account`

### ⚠️ Email 字段 (Profile 里的 email)

HN 注册时**不要求 email**。但**注册后建议立即去 profile 里加上 email**——
否则忘记密码就找回不了，账号永久丢失。

```
注册完毕后访问：https://news.ycombinator.com/user?id=surebeli
点击 `email` 字段右边的 `change` 链接
填入 email，保存
```

**这是 HN 上最容易踩的坑** — 90% 的"我账号丢了"故事都是因为没有填 email。

---

## 第 2 步 — Profile 配置（可选但推荐，~5 min）

第一次登录后，profile 页面只有 `username`、`created`、`karma`（=0）和几个空字段。

### 推荐填写

访问 https://news.ycombinator.com/user?id=surebeli

- **email**：填上（见第 1 步警告）。
- **about**：短 bio + 链接到 GitHub。例：

  ```
  AI-paired engineer · builder of kata (a self-evolving wiki for AI workflows)
  https://github.com/surebeli/kata
  ```

  说明：约 200 字符以内，不写"AI enthusiast"/"passionate about X" 这类
  marketing 语，HN 风格是直接 + 具体身份 + 一个链接。

- **showdead / noprocrast** 等技术字段：保持默认（你不需要碰）。

保存方式：每个字段右边有 `change` 链接，改完单击 `update`。

---

## 第 3 步 — 提交前的"账号 warmup"（30 min 总投入，**强烈建议**）

**为什么需要 warmup**：HN 对新账号有反垃圾机制。**全新账号（karma=0）的
首次提交，初始可见度可能被压低**，而且某些情况下会被静默标记为 dead
（你看得到但别人看不到）。

防御性做法：在提交 essay 之前，先在 HN 上**积累 5-10 点 karma**。流程：

1. 在 https://news.ycombinator.com/ 浏览 front page（按 score 排序）+
   `new` 页面（最新提交，按时间排序）
2. 在 2-3 篇你**真的有意见**的文章下评论。规则：
   - 至少 50 字以上的实质性内容（不要 "This is great" / "Agree" 这种）
   - 引用文章里具体的某句话或某个数据
   - 提供你自己的反例 / 经验 / 数据点
   - 避免任何 emoji（emoji = 立刻被 downvote）
   - 不要在评论里塞自己的 link（self-promotion 会被 downvote）
3. 评论被 upvote = 你有 karma

**warmup 不是必须的**（很多人裸账号也成功过），但**首次提交想最大化曝光率，
warmup 给你一个明显优势**。

### 评论触发 karma 的语言风格示例

不要写：
> "Great article, I totally agree. Thanks for sharing!"

要写：
> "Footnote on your section about retrieval latency: we hit the same wall
> with our internal dashboard (50ms p99 budget). What got us under was
> not faster Redis but moving the join into the application layer and
> caching the prepared response object — we cut 35ms by eliminating a
> single SQL roundtrip per request. Your point about 'cache at the
> compute boundary' matches that experience."

差异：具体数字 + 具体技术决策 + 不重复对方的论点。

---

## 第 4 步 — 正式提交 Essay #1

时间窗口：**2026-05-15 PT 08:00-11:00 = Beijing 23:00 周五 → 02:00 周六**

### 提交流程

1. 顶部 bar 点 `submit`
2. 进入 https://news.ycombinator.com/submit
3. 表单只有 3 个字段：
   - **title**（必填，≤ 80 字符）：
     ```
     Code quality is solved. Business thresholds aren't.
     ```
     **不要加 `Show HN:` 前缀** — `Show HN` 是项目发布前缀，你这篇是 essay，
     不是项目。直接用 title。
   - **url**（必填，与 text 二选一）：
     ```
     https://github.com/surebeli/kata/blob/main/docs/essay-drafts/2026-05-13-essay1-code-quality-vs-business-DRAFT.md
     ```
     **注意**：HN 把 github blob URL 渲染为可点击链接，浏览器跳转到 github
     markdown 预览页面。Github 的 markdown 渲染对 HN 读者来说**够用**——他们
     看惯了这种格式。**不需要额外转 HTML 或部署到独立站**。
   - **text**（与 url 二选一，**留空**）：保持空。你已经填了 url。

4. 点 `submit`

5. **提交成功后**：
   - 浏览器跳转到 `https://news.ycombinator.com/item?id=<你的提交 ID>`
   - **立即复制这个 URL，保存到任意地方**（之后要写回 STATUS.md）
   - 该提交立即出现在 https://news.ycombinator.com/newest 顶部

### ⚠️ 提交后**不要做**的事

- ❌ **不要立刻删除重发** — HN 检测到重发会把第二次提交标 `[dead]`，账号也会被打小记号
- ❌ **不要修改 URL** — 修改提交的 URL 会触发反垃圾，文章可能被踢出 front page 候选池
- ❌ **不要"求转发求点赞"** — vote ring 是 HN 上**最快被永久 ban 的操作**。任何形式的"叫朋友来 upvote"都禁止
- ❌ **不要同步发到 Reddit / Twitter 然后 link 回 HN 求流量** — HN 对外部刷流量极敏感

---

## 第 5 步 — 提交后的第一小时（**最关键**）

HN 上 essay 能否上 front page，**99% 取决于提交后的 60-120 分钟**。
机制：

1. **提交时点**：你的文章出现在 `/newest`，**0 votes, 0 comments**
2. **0-30 min**：路过 `/newest` 的读者投票。如果**有 3-5 个 upvote 且没有 flag**，
   就有机会进入 `front page`（前 30 名）。
3. **30-60 min**：进入 front page 后会有流量爆发，30 min 内 vote 累积速度决定能爬到多高
4. **60-120 min**：top 10 / front page 排位稳定
5. **6-12h**：自然衰减，从 top 慢慢往下走

### 第一小时你应该做的事

#### A. 留**第一条评论**（提交后 5 分钟内）

第一条评论是给读者上下文用的，让他们点开 essay 之前就知道你的视角。

**模板**（直接复制，根据你自己语气微调）：

```
Author here. Quick context for what you're about to read:

This is one essay from a 4-week dogfood — I was building a wiki tool for
AI agents (kata, link in the essay), and three bugs in a row showed me
the same shape: code-correct against the generic spec the LLM had,
wrong against the local project spec only my team carried. The essay
names the failure mode and argues it's the part of "code quality" that
AI doesn't kill the same way.

Happy to dig into specific bugs (B066/B070/B074 from the essay), the
wiki design (kata at github/surebeli/kata), or the methodology (line-
cited dogfood log linked at the end).

The cold-baseline experiment is the obvious next missing piece — flagged
in the closing. Not pretending I have that data yet.
```

**风格说明**：
- 第一人称、不卖弄、直接指出你的"open gap"（提前承认 cold-baseline 还没跑），
  HN 读者吃这种"engineering honest"风
- 不重复 essay 内容，只给上下文
- 邀请 3 个具体方向的提问（bug 细节 / 工具设计 / 方法论）→ 引导评论
- 长度 ~100-150 字，不超过这个量级

#### B. 监控 (~每 10 分钟 refresh 一次)

打开两个 tab：
1. `https://news.ycombinator.com/item?id=<你的ID>` — 看自己文章
2. `https://news.ycombinator.com/newest` — 看自己在 /newest 上的位置

观察：
- vote 数（>3 = 健康；>10 in 30min = 大概率上 front page）
- 评论数 + 评论质量
- 是否有 [flagged] 或 [dead] 标记（绝大多数情况下不会有）

#### C. 实时回复评论（**最关键的行为**）

提交后 1-2 小时内，**每一条评论都要在 30 分钟内回复**。

- 评论同意你 → 加一条延伸的事实/数据/例子
- 评论质疑你 → **不要 defensive**。引用对方的具体词，承认对方对的部分，
  指出双方的真正分歧，给一个可以验证的事实点
- 评论说你写得不好 → 不回，留给别人。**绝不删除负面评论**
- 评论提技术问题 → 直接答，引用 essay 里的具体 line 或 commit SHA

**HN 读者特别看重 "author 是否真的在场"**。Author 在场快速回答 = 文章质量高
的强信号 = 更多人愿意点开看。

#### D. 不要做的事

- ❌ 不要在评论区放第二个 link 到你的 github / blog / 别的 essay
- ❌ 不要 emoji
- ❌ 不要"thanks for the kind words"这种空内容回复
- ❌ 不要在第一小时内自己 upvote 自己（HN 系统会忽略 self-upvote 但留痕）

---

## 第 6 步 — 提交后 24-72 小时

### 数据收集（按 STATUS.md 模板）

提交后回到 `docs/essay-drafts/STATUS.md`，填入：

1. **HN submission URL** — `https://news.ycombinator.com/item?id=<ID>`
2. **Front-page peak rank** — 上到的最高名次（如 "Rank 8 at 2026-05-15
   18:42 UTC"）
3. **Top 5 substantive comments** — 引用对方原文 + 你的回复（如有）
4. **Reception-driven calibration for Essay #2** — 这次的 tone / topic /
   visual 哪些 work、哪些不 work

### 自然衰减期处理

文章 6-12 小时后会自然下沉到 front page 末尾再退出。**这是正常的，
不需要做任何事**。

- 不要 24h 后重发（违规）
- 不要找人在评论里"顶"
- 不要 24h 内同时投另一个相关 link

---

## 进阶：HN 特定的潜规则

### 1. "Show HN" vs 普通提交

- **Show HN: <项目名> — <一句描述>** = 项目发布。规则更严格（必须能用，必须
  open source 或可注册）。
- **普通提交**（你这次用的）= essay / blog / news article / opinion piece。
  没有"必须能用"要求。

Essay #1 走普通提交。Essay #2 也走普通提交。如果未来某天发布 kata v3.0
重大版本，可以考虑 Show HN。

### 2. Title 风格

HN 读者扫 title 比 Reddit 快 10 倍。规则：
- ✓ Specific claim that's debatable: "Code quality is solved. Business thresholds aren't."
- ✓ Counter-intuitive observation: "Our database is the bottleneck, but indexing won't help"
- ✗ Click-bait: "You won't believe what happened next..."
- ✗ Self-promotion in title: "How my new tool fixes X"
- ✗ Marketing language: "Powerful new approach to X"

### 3. URL 注意事项

- HN 显示 URL 域名：你提交 `github.com/...` 会显示 `(github.com)`
- 不同人对 github.com 反应不同，有人觉得 "ok markdown 渲染没问题"，有人觉得 "嗯能不能放个独立站"
- 如果未来要给 essay 独立 host：用 GitHub Pages / Cloudflare Pages /
  Vercel 都行。但**对 Essay #1，github 链接足够**。

### 4. 别人 flagging 你的文章

如果文章被 `[flagged]`：
- 通常因为：title 太 click-bait / 内容明显是 marketing / 重发了已有内容
- 极少数因为：内容惹了某个特定圈子
- **不要在评论里"求解禁"**。如果文章质量真的好，可以发邮件给 `hn@ycombinator.com`
  说明，他们看心情处理

Essay #1 的 title + 内容都符合 HN 规范，几乎不会被 flagged。

### 5. Karma 的真实价值

- karma 在 HN 上**没有实际功能效益**（不解锁任何东西，只是个数字）
- 唯一的隐性作用：高 karma 评论的可见度略好；新账号评论容易被 collapsed
- 不要为 karma 而 karma，会让你写不出真东西

---

## Essay #1 提交日 checklist（拍照式 / 顺序执行）

```
T-12h (Beijing 11:00 周五):
  [ ] 注册 HN 账号 (surebeli)
  [ ] Profile 填 email + about + github link
  [ ] (可选) warmup 评论 2-3 篇

T-1h (Beijing 22:00 周五):
  [ ] 重读一遍 docs/essay-drafts/2026-05-13-essay1-code-quality-vs-business-DRAFT.md
  [ ] 确认 github URL 可访问（用无痕窗口测一下）
  [ ] 准备好"第一条评论"文本（直接复制本指南第 5 步 A 节模板）

T = Submit (Beijing 23:00 周五):
  [ ] 访问 https://news.ycombinator.com/submit
  [ ] 填 title + URL，text 留空
  [ ] 点 submit
  [ ] 复制 item URL 保存

T+5 min:
  [ ] 在自己文章下贴第一条评论

T+10 min .. T+2h:
  [ ] 每 10 分钟刷新一次 /item?id=<...> 和 /newest
  [ ] 评论及时回复（30 min 内）

T+24h:
  [ ] 数据填回 STATUS.md
  [ ] 整理 top 5 评论 + 反馈
  [ ] 开始 Essay #2 drafting（如果反馈 OK）
```

---

## 故障排查

| 症状 | 可能原因 | 处理 |
|---|---|---|
| 提交后看不到自己文章在 /newest | 新账号被静默 hold，或 caching delay | 等 5-10 min 再刷新；如果 1h 后仍然看不到，删除提交并联系 hn@ycombinator.com |
| 文章在 /newest 但 vote 数始终是 0 | 新账号曝光被压；或文章质量不被认可 | 等 30 min 看自然 vote；不要 self-upvote |
| 提交时报错 "you can't submit so quickly" | 同一 IP / 账号 24h 内提交太多 | 等 24h 再试 |
| Title 太长被截断 | 超过 80 字符 | 修改 title（提交前必须 ≤ 80） |
| URL 不被接受 | github blob 链接有时会被 normalize | 用 raw URL: `https://raw.githubusercontent.com/...`；或先把链接放 `text` 字段 |

---

## 相关文档

- `docs/essay-drafts/STATUS.md` — Essay #1 提交日期 + 提交后 closeout 模板
- `docs/essay-style-guide.md` v1.2 — HN 风格规范
- `docs/dogfood-necallkit-hn-essay.md` — Essay #1 完整证据链
