from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path


TODAY = date.today().isoformat()
QUERY_SLUG = "necallkit-electron-web-bugfix-preflight-lessons-query"
QUERY_PATH = Path("queries") / f"{QUERY_SLUG}.md"
QUERY_TITLE = "Electron/Web bugfix 前历史 lessons 检查清单"
QUERY_SUMMARY = "Query filed 2026-05-08 / 将 lessons seed set 转成 Electron/Web bugfix 前置检查清单"


@dataclass(frozen=True)
class SourcePage:
    path: Path
    slug: str
    title: str
    reason: str


SOURCE_PAGES: tuple[SourcePage, ...] = (
    SourcePage(
        path=Path("lessons/l008-generation-counter-async-handler-的-await-边界竞态守卫模式.md"),
        slug="l008-generation-counter-async-handler-的-await-边界竞态守卫模式",
        title="Generation Counter — async handler 的 await 边界竞态守卫模式",
        reason="异步事件处理器在 await 后必须重新验证状态代次。",
    ),
    SourcePage(
        path=Path("lessons/l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离.md"),
        slug="l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离",
        title="Electron 音视频切换与摄像头开关必须跨 runtime、desktop core、source bridge 三层隔离",
        reason="Electron/Web 修复不能只看 JS 层；source bridge 和 native staging 也可能决定真实运行行为。",
    ),
    SourcePage(
        path=Path("lessons/l005-信令事件处理回调同样需要入口状态守卫-被动通知的-callstatus-前置检查.md"),
        slug="l005-信令事件处理回调同样需要入口状态守卫-被动通知的-callstatus-前置检查",
        title="信令事件处理回调同样需要入口状态守卫",
        reason="被动信令事件入口必须按 callStatus 做状态守卫，尤其是多端登录。",
    ),
    SourcePage(
        path=Path("lessons/l012-系统返回键退后台与直接退后台不是同一生命周期路径-只修单一路径会留下悬浮窗回归.md"),
        slug="l012-系统返回键退后台与直接退后台不是同一生命周期路径-只修单一路径会留下悬浮窗回归",
        title="系统返回键退后台与直接退后台不是同一生命周期路径",
        reason="生命周期修复必须枚举不同 OS/host 入口路径，不能只修一个入口。",
    ),
    SourcePage(
        path=Path("lessons/l003-signalcontroller-call-accept-状态边界处理不足-重复调用异常与错误码语义不清.md"),
        slug="l003-signalcontroller-call-accept-状态边界处理不足-重复调用异常与错误码语义不清",
        title="SignalController call()/accept() 状态边界处理不足",
        reason="状态机 API 要区分非法状态与已经处于目标状态的幂等重复调用。",
    ),
    SourcePage(
        path=Path("lessons/l010-nim-logger-对入参做-json-stringify-复杂对象传入导致循环引用崩溃.md"),
        slug="l010-nim-logger-对入参做-json-stringify-复杂对象传入导致循环引用崩溃",
        title="nim.logger 对入参做 JSON.stringify，复杂对象传入导致循环引用崩溃",
        reason="第三方 logger / SDK 边界需要 wrapper 层安全序列化复杂对象。",
    ),
    SourcePage(
        path=Path("queries/necallkit-electron-web-reuse-operating-boundary-query.md"),
        slug="necallkit-electron-web-reuse-operating-boundary-query",
        title="Electron/Web reuse 在 NECallKit 多平台仓库中的维护边界",
        reason="把 lessons 检查清单放回 Electron/Web reuse 的仓库级维护边界中。",
    ),
    SourcePage(
        path=Path("decisions/necallkit-agent-sdd-operating-contract.md"),
        slug="necallkit-agent-sdd-operating-contract",
        title="NECallKit Agent 与 SDD 操作规范",
        reason="agent 执行前应按任务类型读取具体 PRD、bugfix、lessons，而不是无差别预载全部文档。",
    ),
)
BACKLINK_SLUGS = {
    "l008-generation-counter-async-handler-的-await-边界竞态守卫模式",
    "l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离",
    "l005-信令事件处理回调同样需要入口状态守卫-被动通知的-callstatus-前置检查",
    "l012-系统返回键退后台与直接退后台不是同一生命周期路径-只修单一路径会留下悬浮窗回归",
    "l003-signalcontroller-call-accept-状态边界处理不足-重复调用异常与错误码语义不清",
    "l010-nim-logger-对入参做-json-stringify-复杂对象传入导致循环引用崩溃",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="File the NECallKit lessons preflight query.")
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
  - async
  - lifecycle
  - logger
  - state-machine
  - regression
  - testing
  - callkit
  - nim
created: {TODAY}
updated: {TODAY}
published_at: {TODAY}
ingested_at: {TODAY}
sources:
{source_wikilinks()}
---

# {QUERY_TITLE}

## Question

下一个 Electron/Web bugfix 开始前，agent 应该先检查哪些历史 lessons？

## Answer

先不要从代码修改开始。对 Electron/Web 相关 bugfix，agent 应先把任务放进 [[necallkit-electron-web-reuse-operating-boundary-query]] 的维护边界中：判断改动属于 shared 语义、runtime adapter、formal wrapper、example host，还是 Electron-only native/managed 能力；然后按 [[necallkit-agent-sdd-operating-contract]] 的分层加载模型读取对应 lessons。当前 seed set 给出的前置检查清单如下。

## Pre-work checklist

| Check | Ask before editing | Lesson source | Why it matters |
| --- | --- | --- | --- |
| Async race | 这个 handler 是否有 `await`，await 期间是否可能被 `resetState()` / `clear()` / `dispose()` 改变状态？ | [[l008-generation-counter-async-handler-的-await-边界竞态守卫模式]] | 入口 guard 不覆盖 await 之后的竞态窗口；需要 generation counter 或等价校验。 |
| State-machine boundary | 这个 API / handler 是否区分了非法状态、重复调用、已经处于目标状态三类情况？ | [[l003-signalcontroller-call-accept-状态边界处理不足-重复调用异常与错误码语义不清]] | 重复 `accept()` 这类幂等场景不应被误报成信令异常；错误码语义要与状态对应。 |
| Passive signal guard | 被动收到的 NIM / RTC / signaling 事件是否也检查了当前 `callStatus`？ | [[l005-信令事件处理回调同样需要入口状态守卫-被动通知的-callstatus-前置检查]] | 多端登录时，idle 客户端可能收到与自身状态不匹配的事件；不能只保护主动 API。 |
| Lifecycle split | 这个修复是否覆盖了所有生命周期入口，而不是只覆盖一个可复现路径？ | [[l012-系统返回键退后台与直接退后台不是同一生命周期路径-只修单一路径会留下悬浮窗回归]] | 系统返回键、直接退后台、锁屏/解锁、小窗路径可能走不同链路；只修一个入口会留下回归。 |
| Electron bridge boundary | 如果现象出现在 Electron，当前运行时是否真的加载了 source bridge / freshly staged native artifact？ | [[l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离]] | JS/runtime 层看似修好并不代表 Electron demo/package 使用了修复后的 desktop core。 |
| Logger / SDK boundary | 有没有把复杂对象直接传给第三方 SDK logger 或 vendor API？ | [[l010-nim-logger-对入参做-json-stringify-复杂对象传入导致循环引用崩溃]] | `console.log` 能处理的对象不代表 vendor logger 能处理；wrapper 层要做 safe serialization。 |

## Decision path

1. 如果任务涉及 async event handler，先套用 [[l008-generation-counter-async-handler-的-await-边界竞态守卫模式]]，检查每个 await 后是否仍会写状态或 emit 事件。
2. 如果任务涉及 `callStatus`、call/accept/hangup/switch 等状态迁移，先读 [[l003-signalcontroller-call-accept-状态边界处理不足-重复调用异常与错误码语义不清]] 和 [[l005-信令事件处理回调同样需要入口状态守卫-被动通知的-callstatus-前置检查]]，把主动 API 与被动事件入口都列出来。
3. 如果任务涉及 Electron 音视频切换、camera、desktop core、native package、demo/package 运行结果，先读 [[l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离]]，确认 bridge strategy、staged manifest、source build 都进入验收前置。
4. 如果任务涉及后台、悬浮窗、小窗、OS 返回键、应用生命周期，先读 [[l012-系统返回键退后台与直接退后台不是同一生命周期路径-只修单一路径会留下悬浮窗回归]]，列全入口路径再改。
5. 如果任务涉及日志、diagnostics、SDK wrapper 或上报，先读 [[l010-nim-logger-对入参做-json-stringify-复杂对象传入导致循环引用崩溃]]，避免把复杂对象穿透给 vendor code。

## What this changes in the agent workflow

这不是普通搜索结果。导入 lessons 前，agent 只能从 [[necallkit-docs-index]] 知道存在 `docs/lessons/`，但不能把具体历史经验转成执行前检查。导入 seed lessons 后，wiki 能把 6 条历史经验合成一个 bugfix preflight：先判断任务触发哪类历史 failure mode，再决定要读哪条 lesson、补哪个 guard、跑哪类验收。

这证明的产品点是：query 不只是回答“有哪些 lesson”，而是把 lesson 变成下一次工作的入口条件。

## Scope limits

- 这只是 seed set，不代表 `docs/lessons/` 的完整覆盖。L001、L004、L007、L009、L011 等 admitted lessons 还未导入。
- L002 和 L006 已被 admission gate 拒绝进入首批 lessons；它们更接近 runbook / platform fact，不应稀释 `lessons/`。
- 这个 checklist 适合 bugfix 前置检查，不替代具体 PRD、bugfix 文档或代码级验证。

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
        f"- [[{QUERY_SLUG}]] — turns the lessons seed set into a pre-work checklist for Electron/Web bugfixes.\n"
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
        f"\n\n## [{TODAY}] query | Electron/Web bugfix lessons preflight\n"
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
    backlinks = [
        source.path.as_posix()
        for source in SOURCE_PAGES
        if source.slug in BACKLINK_SLUGS and add_backlink_if_missing(wiki_root, source)
    ]
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
        + [source.path.as_posix() for source in SOURCE_PAGES if source.slug in BACKLINK_SLUGS],
    }
    missing = [source.path.as_posix() for source in SOURCE_PAGES if not (wiki_root / source.path).exists()]
    if missing:
        print(json.dumps({"ok": False, "missing_sources": missing, **result}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
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
        run_git(wiki_root, "commit", "-m", "wiki-query: file electron web bugfix lessons preflight")
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
