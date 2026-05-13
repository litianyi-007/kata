from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "necallkit-electron-switch-calltype-media-default-2026-05-10"
TODAY = date.today().isoformat()

SOURCE_FILES: tuple[PurePosixPath, ...] = (
    PurePosixPath("docs/bugfix/B072-electron-switch-calltype-reset-local-media-default/analysis.md"),
    PurePosixPath("docs/bugfix/B072-electron-switch-calltype-reset-local-media-default/B072-electron-switch-calltype-reset-local-media-default-test.md"),
)

NEW_BUG_PATH = PurePosixPath("bugs/electron-switch-calltype-reset-local-media-default-2026-05-10.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import NECallKit B072 switchCallType local media default reset.")
    parser.add_argument("--wiki", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--checkpoint-script", default=str(Path(__file__).resolve().parents[1] / "plugin" / "scripts" / "import_checkpoint.py"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    return parser.parse_args()


def read_text(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def raw_path(source: PurePosixPath) -> PurePosixPath:
    return PurePosixPath("raw") / "imported" / BUNDLE_NAME / source


def yaml_quote(value: str) -> str:
    return '"' + value.replace('"', "'") + '"'


def raw_source_lines() -> list[str]:
    return [f"  - {raw_path(source).as_posix()}" for source in SOURCE_FILES]


def run_git(wiki_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(wiki_root), *args], text=True, capture_output=True, check=check)


def git_status_porcelain(wiki_root: Path) -> str:
    return run_git(wiki_root, "status", "--porcelain", check=True).stdout.strip()


def checkpoint(script: Path, wiki_root: Path, *args: str) -> None:
    completed = subprocess.run([sys.executable, str(script), "--wiki", str(wiki_root), *args], text=True, capture_output=True, check=True)
    if completed.stdout.strip():
        print(completed.stdout.strip())


def validate_sources(project_root: Path) -> None:
    missing = [s.as_posix() for s in SOURCE_FILES if not (project_root / Path(s.as_posix())).exists()]
    if missing:
        raise FileNotFoundError("Missing source files:\n" + "\n".join(missing))


def safe_copy_raw(project_root: Path, wiki_root: Path, source: PurePosixPath) -> str:
    src = project_root / Path(source.as_posix())
    dst = wiki_root / Path(raw_path(source).as_posix())
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if src.read_bytes() == dst.read_bytes():
            return "unchanged"
        raise RuntimeError(f"Raw file differs and will not be overwritten: {dst}")
    shutil.copy2(src, dst)
    return "created"


def frontmatter(title: str, page_type: str, tags: tuple[str, ...], sources: list[str]) -> str:
    return f"""---
title: {yaml_quote(title)}
type: {page_type}
tags:
{chr(10).join(f"  - {tag}" for tag in tags)}
created: {TODAY}
updated: {TODAY}
published_at: {TODAY}
ingested_at: {TODAY}
sources:
{chr(10).join(sources)}
---

"""


def bug_page() -> str:
    return frontmatter(
        "Electron switchCallType 后本地媒体默认打开规则升级（B072）",
        "bugs",
        ("electron", "desktop", "rtc", "callkit", "bridge", "regression", "camera", "state-machine", "testing"),
        raw_source_lines(),
    ) + """# Electron switchCallType 后本地媒体默认打开规则升级（B072）

## Summary

- B072 是 B057/B061 媒体默认规则的产品扩张：每次真实发生 callType 切换后，**麦克风**和（切到视频时）**摄像头**都恢复默认打开，不再保留 B061 的"音频态触碰麦克风后切回视频不开麦"窄例外。
- 移除 `audioModeLocalAudioTouched`（runtime）/ `audio_mode_local_audio_touched_`（desktop core）状态变量。
- 关键判据：`didSwitchCallType` 为 true 时恢复麦克风；`previousCallType !== 2 && nextCallType === 2` 时恢复摄像头。**重复同类型 echo 不算 switch**，不重置媒体（保护视频通话中用户正在做的设备调整）。

## 与 B061 的差异

| 维度 | B061（旧） | B072（新） |
|------|-----------|----------|
| 麦克风默认开启 | 仅在"非视频→视频且音频态未触碰麦克风"时 | 任何真实 switchCallType 后都恢复 |
| 摄像头默认开启 | B057：非视频→视频时恢复（不变） | B057：非视频→视频时恢复（保留） |
| 用户音频态触碰麦克风后切回视频 | 保留关闭 | 恢复打开（这是产品扩张点） |
| 状态变量 | `audioModeLocalAudioTouched` | 移除 |
| 重复同类型 echo | 同左 | 同左：仍不触发重置 |

## Issue Matrix

| ID | Problem | Durable rule |
|----|---------|--------------|
| B072 | 切换 callType 后本地媒体设备不恢复默认打开 | `didSwitchCallType=true` 恢复麦克风；`prev!==2 && next===2` 恢复摄像头；重复同类型 echo 不重置 |

## 状态机判据

```text
runtime: didSwitchCallType
desktop core: did_switch_call_type
```

均仅在 resolved callType 真实改变时为 true。重复 `state=2` echo / 重复同类型 resolved 不命中。

设备恢复路径：

| 切换 | 麦克风 | 摄像头 |
|------|--------|--------|
| 视频 → 音频 | 恢复打开（取消静音） | 不恢复（callType 仍 gate 视频） |
| 音频 → 视频 | 恢复打开 | 恢复打开（B057 保留） |
| 视频 → 视频 echo | 不动 | 不动（保护用户当前设备状态） |
| 音频 → 音频 echo | 不动 | 不动 |

## 影响范围

| 层级 | 文件 | 影响 |
|------|------|------|
| Electron runtime | `packages/callkit-runtime-electron/src/runtime.ts` | 移除 `audioModeLocalAudioTouched`；resolved callType 变化时 unmute 麦克风；切到视频时恢复摄像头采集 |
| desktop core | `desktop/core/src/call_controller.cpp` | 移除 `audio_mode_local_audio_touched_`；resolved callType 变化时恢复 `local_audio_muted_=false`；视频切换时恢复 `local_video_capture_enabled_=true` |
| Runtime tests | `packages/callkit-runtime-electron/test/runtime-contract.test.ts` | 替换 B061 期望，补充重复 echo 不重置媒体的回归 |
| Source guard | `Electron/scripts/test/switch-call-type-control-source.test.js` | 锁定 C++ `did_switch_call_type` 条件，避免回归 |

## 与历史规则的兼容性

- **B045 三层隔离原则保留**：switchCallType / 摄像头按钮 / 麦克风按钮仍是独立入口；`onVideoAvailable(false)` / `onVideoMuted(true)` 仍**不**作为 callType 信号。
- **B057 摄像头规则保留**：非视频→视频时默认开摄像头。
- **B061 麦克风窄例外被替换**：原"音频态触碰后保留关闭"行为被产品口径推翻，B072 完全恢复打开。
- **B065 outgoing pending 保护保留**：`switchCallType(state=1)` 仍只 mark `outgoingSwitchCallType`，不提前 apply；只有 `state=2` resolved 时才走 B072 媒体恢复路径。
- **B066 IPC normalize cleared 信号保留**。
- **B069 stale window guard 保留**：切到视频后 2 秒 window 内 negative 信号仍被 skip。

## 验证

| ID | 命令 | 结果 |
|----|------|------|
| TC-B072-001 | `node --test packages/callkit-runtime-electron/test/runtime-contract.test.ts packages/callkit-runtime-electron/test/video-switch-regression.test.ts` | 31/31 |
| TC-B072-002 | `node --test Electron/scripts/test/switch-call-type-control-source.test.js` | 6/6 |
| TC-B072-003 | `cd Electron && npm run build:native:source` | 通过 |
| TC-B072-004 | 读取 `Electron/out/native/win32-debug/manifest.json` | `bridgeStrategy=source`，bridgeSource 指向 `desktop/build-electron/win32-debug/bin/Debug/ne_callkit.dll` |

`desktop/core` 改动必须使用 source bridge 构建验证；packaged bridge 不能用于本次代码验收。

## Related wiki pages

- [[electron-switch-video-default-camera-on-product-rule-change]]
- [[electron-camera-switch-microphone-state-regression-bugfix-set]]
- [[electron-switchcalltype-media-state-and-reject-semantics-2026-05-09]]
- [[electron-switch-wait-peer-and-stale-video-2026-05-09]]
- [[electron-switchcalltype-reject-state-and-media-preflight-query]]
- [[l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离]]
"""


def update_existing_pages(wiki_root: Path) -> None:
    source_lines = raw_source_lines()

    b057_page = wiki_root / "bugs" / "electron-switch-video-default-camera-on-product-rule-change.md"
    text = update_frontmatter(read_text(b057_page), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-10 B072 麦克风规则扩张（替换 B061 窄例外）",
        f"""B072 把 B061 的"音频态触碰后保留麦克风关闭"窄例外**直接推翻**。新产品口径：

- 任何 resolved switchCallType 都恢复麦克风默认打开（包括音频态用户已触碰麦克风后切回视频）。
- 摄像头继续走 B057：仅非视频→视频时恢复采集。
- 重复同类型 echo 不触发重置（保护视频通话中用户正在做的设备操作）。
- runtime `audioModeLocalAudioTouched` / desktop core `audio_mode_local_audio_touched_` **已移除**——以后再看到这个变量就是 stale 代码。

详见 [[{NEW_BUG_PATH.stem}]]。""",
    )
    write_text(b057_page, text)

    media_bug = wiki_root / "bugs" / "electron-switchcalltype-media-state-and-reject-semantics-2026-05-09.md"
    text = update_frontmatter(read_text(media_bug), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-10 B072 媒体默认规则升级",
        f"""B061 的麦克风窄例外被 B072 推翻——任何真实 switchCallType 都恢复麦克风默认打开。Issue Matrix 里 B061 行的"非视频→视频且音频态未触碰时默认开麦"已 stale，应读 [[{NEW_BUG_PATH.stem}]] 获取最新规则。""",
    )
    write_text(media_bug, text)

    cluster_bug = wiki_root / "bugs" / "electron-switch-wait-peer-and-stale-video-2026-05-09.md"
    text = update_frontmatter(read_text(cluster_bug), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-10 B072 媒体默认规则升级",
        f"""B065 outgoing pending 保护、B069 stale window 全保留。但 resolved `state=2` 走完后，runtime / desktop core 现在统一恢复本地媒体默认打开（B072）。
{chr(10)}详见 [[{NEW_BUG_PATH.stem}]]。""",
    )
    write_text(cluster_bug, text)

    reject_query = wiki_root / "queries" / "electron-switchcalltype-reject-state-and-media-preflight-query.md"
    text = update_frontmatter(read_text(reject_query), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-10 后续 B072 媒体默认规则升级",
        f"""排查矩阵新增一行：

| Symptom | First branch |
|---|---|
| 切回视频后麦克风仍保持音频态关闭 | Check B072 `didSwitchCallType` resolved-only path（**B061 窄例外已废弃**） |
| 切到音频后麦克风仍是静音 | Check B072 `didSwitchCallType` 路径 |
| 重复同类型 echo 把用户刚关的摄像头打开 | Check B072 同类型 echo 不重置规则；若被打开则有回归 |

旧文里 B061 麦克风窄例外的描述（"音频态未触碰才自动开麦"）应视为 stale。runtime 中的 `audioModeLocalAudioTouched` 已移除。详见 [[{NEW_BUG_PATH.stem}]]。""",
    )
    write_text(reject_query, text)

    lesson = wiki_root / "lessons" / "l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离.md"
    text = update_frontmatter(read_text(lesson), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-10 B072 Addendum",
        f"""B072 不推翻三层隔离原则，但收紧"产品例外"的写法：

- 媒体默认状态例外**不能**绑定到中间态变量（如旧 `audioModeLocalAudioTouched`）。
- 例外条件**只**用 resolved callType 真实变化（`didSwitchCallType`）+ 方向（`prev !== 2 && next === 2`）。
- 任何"用户中途操作"的状态都应在 resolved switch 时被产品规则重置，不应反过来抑制规则。
- 重复同类型 echo **必须**不触发重置——这是保护用户在视频通话中正在做的设备操作。

详见 [[{NEW_BUG_PATH.stem}]]。""",
    )
    write_text(lesson, text)


def update_frontmatter(text: str, extra_sources: list[str]) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    fm = text[: end + 4]
    body = text[end + 4 :]
    fm = re.sub(r"updated:\s*\d{4}-\d{2}-\d{2}", f"updated: {TODAY}", fm, count=1)
    fm = re.sub(r"ingested_at:\s*\d{4}-\d{2}-\d{2}", f"ingested_at: {TODAY}", fm, count=1)
    for source in extra_sources:
        if source not in fm:
            fm = fm.replace("\n---", f"\n{source}\n---", 1)
    return fm + body


def upsert_section(text: str, heading: str, section: str) -> str:
    pattern = re.compile(rf"\n## {re.escape(heading)}\n.*?(?=\n## |\Z)", re.S)
    block = f"\n## {heading}\n\n{section.strip()}\n"
    if pattern.search(text):
        return pattern.sub(block, text)
    related = "\n## Related wiki pages"
    if related in text:
        return text.replace(related, block + related, 1)
    related2 = "\n## Related"
    if related2 in text:
        return text.replace(related2, block + related2, 1)
    return text.rstrip() + block + "\n"


def update_index(wiki_root: Path, created_bug: bool) -> None:
    index_path = wiki_root / "index.md"
    text = read_text(index_path)
    if created_bug:
        text = re.sub(r"Total pages: (\d+)", lambda m: f"Total pages: {int(m.group(1)) + 1}", text, count=1)
    bug_entry = f"- [Electron switchCallType 后本地媒体默认打开规则升级（B072）]({NEW_BUG_PATH.as_posix()}) - 任何真实 callType 切换后恢复麦克风/摄像头默认打开；移除 audioModeLocalAudioTouched；推翻 B061 窄例外。"
    if bug_entry not in text:
        text = text.replace("## Bugs\n\n", "## Bugs\n\n" + bug_entry + "\n", 1)
    write_text(index_path, text.rstrip() + "\n")


def append_log(wiki_root: Path, raw_created: int, raw_unchanged: int) -> None:
    log_path = wiki_root / "log.md"
    text = read_text(log_path).rstrip()
    marker = "import | <workspace>/project/NECallKit docs B072 switchCallType local media default reset"
    if marker in text:
        return
    entry = f"""

## [{TODAY}] import | <workspace>/project/NECallKit docs B072 switchCallType local media default reset (2 files)
- Format: curated folder batch
- Created: 1 wiki page
- Updated: 5 existing pages
- Raw: raw/imported/{BUNDLE_NAME}/ ({raw_created} created, {raw_unchanged} unchanged)
- Source group: B072 product rule change — switchCallType resolved 后麦克风/摄像头都恢复默认打开；移除 audioModeLocalAudioTouched；重复同类型 echo 不重置
- Filed: [[electron-switch-calltype-reset-local-media-default-2026-05-10]]
- Updated: [[electron-switch-video-default-camera-on-product-rule-change]], [[electron-switchcalltype-media-state-and-reject-semantics-2026-05-09]], [[electron-switch-wait-peer-and-stale-video-2026-05-09]], [[electron-switchcalltype-reject-state-and-media-preflight-query]], [[l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离]]
- Decision: ingest immediately because B072 推翻 B061 窄例外，旧 wiki page 在产品规则上误导。
"""
    write_text(log_path, text + entry)


def execute(wiki_root: Path, project_root: Path) -> dict[str, object]:
    raw_counts = {"created": 0, "unchanged": 0}
    for source in SOURCE_FILES:
        raw_counts[safe_copy_raw(project_root, wiki_root, source)] += 1
    bug_full = wiki_root / Path(NEW_BUG_PATH.as_posix())
    created_bug = not bug_full.exists()
    write_text(bug_full, bug_page())
    update_existing_pages(wiki_root)
    update_index(wiki_root, created_bug)
    append_log(wiki_root, raw_counts["created"], raw_counts["unchanged"])
    return {
        "raw_created": raw_counts["created"],
        "raw_unchanged": raw_counts["unchanged"],
        "created": [str(NEW_BUG_PATH)],
        "updated": [
            "bugs/electron-switch-video-default-camera-on-product-rule-change.md",
            "bugs/electron-switchcalltype-media-state-and-reject-semantics-2026-05-09.md",
            "bugs/electron-switch-wait-peer-and-stale-video-2026-05-09.md",
            "queries/electron-switchcalltype-reject-state-and-media-preflight-query.md",
            "lessons/l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离.md",
        ],
    }


def main() -> int:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    project_root = Path(args.project).resolve()
    checkpoint_script = Path(args.checkpoint_script).resolve()
    validate_sources(project_root)
    plan = {"bundle": BUNDLE_NAME, "sources": [s.as_posix() for s in SOURCE_FILES], "new_pages": [NEW_BUG_PATH.as_posix()], "updates": 5}
    if not args.execute:
        print(plan)
        return 0
    if not args.allow_dirty:
        status = git_status_porcelain(wiki_root)
        if status:
            raise RuntimeError(f"Wiki git tree is dirty; commit/stash before import:\n{status}")
    checkpoint(checkpoint_script, wiki_root, "lock", "--source", str(project_root / "docs"), "--format", "markdown")
    try:
        checkpoint(checkpoint_script, wiki_root, "init", "--source", str(project_root / "docs"), "--format", "markdown", "--total", str(len(SOURCE_FILES)))
        result = execute(wiki_root, project_root)
        checkpoint(checkpoint_script, wiki_root, "update", "--processed", str(len(SOURCE_FILES)), "--last-file", SOURCE_FILES[-1].as_posix())
        print(result)
        return 0
    finally:
        checkpoint(checkpoint_script, wiki_root, "unlock")


if __name__ == "__main__":
    raise SystemExit(main())
