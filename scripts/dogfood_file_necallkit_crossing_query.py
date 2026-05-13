from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path


TODAY = date.today().isoformat()
QUERY_SLUG = "necallkit-electron-web-reuse-operating-boundary-query"
QUERY_PATH = Path("queries") / f"{QUERY_SLUG}.md"
QUERY_TITLE = "Electron/Web reuse 在 NECallKit 多平台仓库中的维护边界"
QUERY_SUMMARY = "Query filed 2026-05-08 / 连接 Electron/Web reuse、仓库架构、发布入口与 agent SDD 工作流"


@dataclass(frozen=True)
class SourcePage:
    path: Path
    slug: str
    title: str
    reason: str


SOURCE_PAGES: tuple[SourcePage, ...] = (
    SourcePage(
        path=Path("modules/necallkit-architecture-overview.md"),
        slug="necallkit-architecture-overview",
        title="NECallKit 多平台架构与 Web/Electron 稳定边界",
        reason="仓库长期架构、shared 真相源、formal package 与 example 边界。",
    ),
    SourcePage(
        path=Path("platforms/necallkit-platform-matrix-release-entry.md"),
        slug="necallkit-platform-matrix-release-entry",
        title="NECallKit 平台矩阵与发布入口",
        reason="多平台目录、分发形态、统一出包入口和平台发布定位。",
    ),
    SourcePage(
        path=Path("decisions/necallkit-agent-sdd-operating-contract.md"),
        slug="necallkit-agent-sdd-operating-contract",
        title="NECallKit Agent 与 SDD 操作规范",
        reason="agent 分层加载、SDD、验收和经验沉淀流程。",
    ),
    SourcePage(
        path=Path("features/002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20.md"),
        slug="002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20",
        title="Web / Electron Reuse 开发工作手册",
        reason="reuse 开发落点、shared 真相源、平台差异和 example 职责。",
    ),
    SourcePage(
        path=Path("queries/002-electron-callkit-electron-web-reuse-upgrade-positioning-query.md"),
        slug="002-electron-callkit-electron-web-reuse-upgrade-positioning-query",
        title="Electron/Web reuse 对外升级口径与迁移代码判定",
        reason="对外口径、低成本升级边界、必须迁移代码客户类型。",
    ),
    SourcePage(
        path=Path("queries/002-electron-callkit-example-contract-boundary-query.md"),
        slug="002-electron-callkit-example-contract-boundary-query",
        title="Electron/Web example 验证边界与平台差异口径",
        reason="formal package、example host、平台差异和验证链分层。",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="File the NECallKit dogfood crossing query.")
    parser.add_argument("--wiki", required=True, help="NECallKit wiki root")
    parser.add_argument("--execute", action="store_true", help="Write changes. Default is dry-run.")
    parser.add_argument("--commit", action="store_true", help="Commit after writing.")
    parser.add_argument("--push", action="store_true", help="Push after commit. Implies --commit.")
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_git(wiki_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=wiki_root, text=True, capture_output=True, check=check)


def source_wikilinks() -> str:
    return "\n".join(f"  - {source.path.as_posix()}" for source in SOURCE_PAGES)


def sources_used_list() -> str:
    return "\n".join(f"- [[{source.slug}]] — {source.reason}" for source in SOURCE_PAGES)


def query_content() -> str:
    return f"""---
title: "{QUERY_TITLE}"
type: queries
tags:
  - electron
  - web
  - desktop
  - bridge
  - architecture
  - compatibility
  - testing
  - callkit
  - nim
  - rtc
created: {TODAY}
updated: {TODAY}
published_at: {TODAY}
ingested_at: {TODAY}
sources:
{source_wikilinks()}
---

# {QUERY_TITLE}

## Question

Electron/Web reuse 的维护边界如何落到 NECallKit 多平台仓库架构、发布入口和 agent 工作流？

## Answer

Electron/Web reuse 在 NECallKit 中不应该被理解成一个独立的 Electron feature，也不应该被理解成把 Web 和 Electron 表层行为强行做成完全一致。更稳妥的维护边界是：仓库长期架构把 `packages/` 定义为 Web/Electron shared 真相源，Web 与 Electron 继续保留正式平台包和各自 example 宿主，agent 工作流则负责在变更前判断落点、在验收时区分 formal package contract、example host contract 和平台差异证据。这个口径同时来自 [[necallkit-architecture-overview]]、[[002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20]] 和 [[002-electron-callkit-example-contract-boundary-query]]。

## Operating boundary

| Layer | Maintain here | Do not turn into |
| --- | --- | --- |
| Shared semantics | `packages/callkit-domain`、shared runtime contract、React/Vue3 shared core | Web/Electron 两端各自复制的一套状态机或 UI 行为 |
| Formal package wrappers | `Web/call-kit`、Web React/Vue3 UIKit、`Electron/sdk`、Electron React/Vue3 UIKit | 直接暴露 `packages/*` 作为客户接入入口 |
| Platform adapters | `packages/callkit-runtime-web` 与 `packages/callkit-runtime-electron` 的薄适配 | 把 Electron managed/native 生命周期外推成 Web contract |
| Example hosts | Web basic examples 与 Electron examples 的 consumer 模板、验证平台、发布样板 | 私有 bypass demo 或 shared 功能真相源 |
| Release / delivery | NECallKit 统一出包入口 + Electron 下的 Web/Electron 组装入口 | 零散脚本、个人环境或一次性 feature 说明 |
| Agent workflow | AGENTS 的分层加载、SDD、验收与 compound 经验沉淀 | 每次从零读全仓库或把 chat answer 当长期记忆 |

## What must be true before changing code

1. 先判断改动属于 shared 语义、runtime adapter、formal wrapper、example host，还是 Electron-only native/managed 能力。[[002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20]] 明确说“一次编码”不是所有需求只改一个文件，而是公共语义只保留一份真相源。
2. 如果改动影响 Web/Electron 交集能力，优先落在 `packages/`，再由两端薄 wrapper 消费。[[necallkit-architecture-overview]] 把 `packages/` 定义为 shared 真相源，但正式交付仍保持平台包形态。
3. 如果改动涉及 Electron `node-addon`、managed/external、main/preload、host helper 或 native bridge，不要伪装成 Web shared 能力。[[002-electron-callkit-example-contract-boundary-query]] 已经把 formal package、example host 和平台差异拆开。
4. 如果改动用于对外升级或 release note，不要使用“零代码改动”或“无感升级”的 blanket claim。[[002-electron-callkit-electron-web-reuse-upgrade-positioning-query]] 只支持对最小 contract 客户使用低成本升级口径。
5. 如果是 agent 执行，应按 [[necallkit-agent-sdd-operating-contract]] 的分层加载模型读取 `ARCHITECTURE.md`、`TASKS.md` / `TRACKER.md`、具体 PRD/bugfix/lessons，而不是无差别预载所有文档。

## How this lands in release and validation

对外发布层面，[[necallkit-platform-matrix-release-entry]] 说明 NECallKit 是多平台 SDK 仓库，统一出包平台是发布与联调入口。对 Web/Electron reuse 来说，这意味着 release evidence 要同时回答三件事：

- 平台包是否仍按 Web / Electron 的正式分发形态交付。
- Shared 语义是否通过正式 wrapper 和 clean-consumer example 被验证。
- 平台差异是否已明确记录，而不是被误判为 regression。

这和 [[002-electron-callkit-example-contract-boundary-query]] 的结论一致：Electron/Web example 审核不能再按“表层行为完全一致”判定；应区分 formal package contract、example purity contract、example host contract 与验证链。

## Agent playbook

当后续 agent 处理 Electron/Web reuse 相关任务时，应按这个顺序工作：

1. 读 [[necallkit-agent-sdd-operating-contract]]，确认当前任务属于功能、bug、发布、验收还是经验沉淀。
2. 读 [[necallkit-architecture-overview]]，确认变更是否碰到 shared 真相源、formal package wrapper 或平台 adapter。
3. 读 [[002-electron-callkit-electron-web-reuse-development-handbook-2026-04-20]]，做落点判断。
4. 如果涉及客户升级承诺，读 [[002-electron-callkit-electron-web-reuse-upgrade-positioning-query]]，避免过度承诺。
5. 如果涉及 example 或平台差异，读 [[002-electron-callkit-example-contract-boundary-query]]，避免把允许差异误判成 blocker。
6. 实现后把验证证据回填到对应 PRD、test、tracker 或 wiki query，而不是只留在聊天上下文。

## Maintainer shorthand

可以用这一句话作为维护口径：

> Web/Electron reuse 的目标不是让两个平台失去边界，而是让 shared 语义只有一份真相源；正式平台包、example 宿主、发布入口和 agent SDD 流程共同保证这份真相源能被正确消费、验证和对外解释。

## Coverage gaps

- 当前 wiki 尚未导入完整 `docs/lessons/`，所以这条 playbook 还没有系统利用历史 bug / lessons 来做预防性提示。
- `TASKS.md` 和 `TRACKER.md` 已导入，但本 query 没有把每条未完成任务展开为状态视图；后续可单独 filed 一个“当前 Electron 风险 lane”查询。

## Sources used

{sources_used_list()}
"""


def add_backlink_if_missing(wiki_root: Path, source: SourcePage) -> bool:
    path = wiki_root / source.path
    text = read_text(path)
    if f"[[{QUERY_SLUG}]]" in text:
        return False
    addition = (
        "\n\n## Filed follow-up queries\n\n"
        f"- [[{QUERY_SLUG}]] — connects this source to the project-level architecture, "
        "release entry, and agent SDD workflow for Electron/Web reuse.\n"
    )
    write_text(path, text.rstrip() + addition)
    return True


def update_index(wiki_root: Path) -> None:
    index_path = wiki_root / "index.md"
    text = read_text(index_path)
    text = re.sub(
        r"Total pages: (\d+)",
        lambda match: f"Total pages: {int(match.group(1)) + (0 if QUERY_PATH.as_posix() in text else 1)}",
        text,
        count=1,
    )
    entry = f"- [{QUERY_TITLE}]({QUERY_PATH.as_posix()}) - {QUERY_SUMMARY}"
    if entry not in text:
        marker = "## Queries\n\n"
        if marker not in text:
            raise RuntimeError("Could not find Queries section in index.md")
        before, after = text.split(marker, 1)
        lines = [line for line in after.splitlines() if line.strip()]
        query_lines: list[str] = []
        rest_start = len(lines)
        for index, line in enumerate(lines):
            if line.startswith("## "):
                rest_start = index
                break
            if line.startswith("- "):
                query_lines.append(line)
        rest = lines[rest_start:]
        query_lines.append(entry)
        query_lines = sorted(query_lines, key=lambda line: re.sub(r"^- \[(.*?)\].*$", r"\1", line).lower())
        rebuilt = marker + "\n".join(query_lines) + "\n"
        if rest:
            rebuilt += "\n" + "\n".join(rest) + "\n"
        text = before + rebuilt
    write_text(index_path, text.rstrip() + "\n")


def append_log(wiki_root: Path) -> None:
    log_path = wiki_root / "log.md"
    text = read_text(log_path).rstrip()
    source_links = ", ".join(f"[[{source.slug}]]" for source in SOURCE_PAGES)
    entry = (
        f"\n\n## [{TODAY}] query | Electron/Web reuse project operating boundary\n"
        f"- Pages used: {source_links}\n"
        "- Format: markdown\n"
        f"- Filed: {QUERY_PATH.as_posix()}\n"
        f"- Created: [[{QUERY_SLUG}]]\n"
        f"- Linked to: {source_links}\n"
    )
    if f"Created: [[{QUERY_SLUG}]]" not in text:
        write_text(log_path, text + entry)


def execute(wiki_root: Path) -> dict[str, object]:
    query_full_path = wiki_root / QUERY_PATH
    existed = query_full_path.exists()
    write_text(query_full_path, query_content())
    backlinks = [source.path.as_posix() for source in SOURCE_PAGES if add_backlink_if_missing(wiki_root, source)]
    update_index(wiki_root)
    append_log(wiki_root)
    return {
        "query": QUERY_PATH.as_posix(),
        "created": not existed,
        "backlinks_updated": backlinks,
        "sources": [source.path.as_posix() for source in SOURCE_PAGES],
    }


def main() -> None:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    result = {
        "query": QUERY_PATH.as_posix(),
        "title": QUERY_TITLE,
        "sources": [source.path.as_posix() for source in SOURCE_PAGES],
        "would_update_files": [QUERY_PATH.as_posix(), "index.md", "log.md"]
        + [source.path.as_posix() for source in SOURCE_PAGES],
    }
    if not args.execute:
        print(json.dumps({"ok": True, "mode": "dry-run", **result}, ensure_ascii=False, indent=2))
        return

    if run_git(wiki_root, "status", "--porcelain").stdout.strip():
        raise RuntimeError("Wiki working tree is dirty; refusing to file query")

    exec_result = execute(wiki_root)
    commit_sha = None
    push_attempted = False
    if args.push:
        args.commit = True
    if args.commit:
        run_git(wiki_root, "add", ".")
        run_git(wiki_root, "commit", "-m", "wiki-query: file electron web operating boundary")
        commit_sha = run_git(wiki_root, "rev-parse", "--short", "HEAD").stdout.strip()
        if args.push:
            push_attempted = True
            run_git(wiki_root, "push")
    print(
        json.dumps(
            {
                "ok": True,
                "mode": "execute",
                **exec_result,
                "commit": commit_sha,
                "push_attempted": push_attempted,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
