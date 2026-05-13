# NECallKit Query Acceptance Worksheet

> Maintainer review worksheet for the four filed NECallKit dogfood queries.

## Where To Review

Open the wiki vault:

```text
~\.llm-wiki\NECallKit
```

Recommended review path: open that folder in Obsidian, then inspect:

```text
queries/
```

## Queries To Review

1. `queries/002-electron-callkit-electron-web-reuse-upgrade-positioning-query.md`
   - Title: Electron/Web reuse 对外升级口径与迁移代码判定
2. `queries/002-electron-callkit-example-contract-boundary-query.md`
   - Title: Electron/Web example 验证边界与平台差异口径
3. `queries/necallkit-electron-web-reuse-operating-boundary-query.md`
   - Title: Electron/Web reuse 在 NECallKit 多平台仓库中的维护边界
4. `queries/necallkit-electron-web-bugfix-preflight-lessons-query.md`
   - Title: Electron/Web bugfix 前历史 lessons 检查清单

## Review Rubric

Score each dimension from 1 to 5.

- Correctness: Does it match NECallKit reality?
- Usefulness: Would it save maintainer or future-agent time?
- Retention: Should this remain durable wiki memory?

## Suggested Review Steps

1. Read `Answer` first and mark anything factually wrong.
2. Check `Sources used` and decide whether the cited pages are the right evidence.
3. Follow 1-2 backlinks if a conclusion feels too strong.
4. Rate correctness, usefulness, and retention.
5. Add one short maintainer note: keep, revise, merge, or delete.

## Ratings

### 1. Upgrade Positioning Query

- Correctness: 5
- Usefulness: 4
- Retention: 5
- Maintainer note: note

### 2. Example Boundary Query

- Correctness: 5
- Usefulness: 4
- Retention: 5
- Maintainer note: note

### 3. Operating Boundary Query

- Correctness: 5
- Usefulness: 5
- Retention: 5
- Maintainer note: note

### 4. Lessons Preflight Query

- Correctness: 5
- Usefulness: 5
- Retention: 5
- Maintainer note: note

## Acceptance Summary

- Correctness: 4/4 queries rated 5.
- Usefulness: 2 queries rated 4, 2 queries rated 5.
- Retention: 4/4 queries rated 5.
- Strongest maintainer signal: the later operating-boundary and lessons
  preflight queries both received 5/5 on correctness, usefulness, and retention.

## Copy/Paste Reply Format

```text
1: 正确性_ 实用性_ 保留_ — note
2: 正确性_ 实用性_ 保留_ — note
3: 正确性_ 实用性_ 保留_ — note
4: 正确性_ 实用性_ 保留_ — note
```
