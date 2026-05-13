from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "necallkit-switchcalltype-media-state-2026-05-09"
TODAY = date.today().isoformat()

SOURCE_FILES: tuple[PurePosixPath, ...] = (
    PurePosixPath("docs/bugfix/B059-electron-switch-video-stale-camera-closed/analysis.md"),
    PurePosixPath("docs/bugfix/B059-electron-switch-video-stale-camera-closed/B059-electron-switch-video-stale-camera-closed-test.md"),
    PurePosixPath("docs/bugfix/B060-electron-camera-closed-overlay-text/analysis.md"),
    PurePosixPath("docs/bugfix/B060-electron-camera-closed-overlay-text/B060-electron-camera-closed-overlay-text-test.md"),
    PurePosixPath("docs/bugfix/B061-electron-switch-video-default-microphone-on/analysis.md"),
    PurePosixPath("docs/bugfix/B061-electron-switch-video-default-microphone-on/B061-electron-switch-video-default-microphone-on-test.md"),
    PurePosixPath("docs/bugfix/B062-electron-switch-reject-remote-camera-closed/analysis.md"),
    PurePosixPath("docs/bugfix/B062-electron-switch-reject-remote-camera-closed/B062-electron-switch-reject-remote-camera-closed-test.md"),
    PurePosixPath("docs/bugfix/B063-electron-local-reject-switch-no-remote-reject-toast/analysis.md"),
    PurePosixPath("docs/bugfix/B063-electron-local-reject-switch-no-remote-reject-toast/B063-electron-local-reject-switch-no-remote-reject-toast-test.md"),
)

NEW_BUG_PATH = PurePosixPath("bugs/electron-switchcalltype-media-state-and-reject-semantics-2026-05-09.md")
NEW_QUERY_PATH = PurePosixPath("queries/electron-switchcalltype-reject-state-and-media-preflight-query.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import NECallKit B059-B063 switchCallType media-state dogfood batch.")
    parser.add_argument("--wiki", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--checkpoint-script",
        default=str(Path(__file__).resolve().parents[1] / "plugin" / "scripts" / "import_checkpoint.py"),
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    return parser.parse_args()


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
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
    completed = subprocess.run(
        [sys.executable, str(script), "--wiki", str(wiki_root), *args],
        text=True,
        capture_output=True,
        check=True,
    )
    if completed.stdout.strip():
        print(completed.stdout.strip())


def validate_sources(project_root: Path) -> None:
    missing = [source.as_posix() for source in SOURCE_FILES if not (project_root / Path(source.as_posix())).exists()]
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
        "Electron switchCallType 媒体状态与拒绝态修复集（B059-B063）",
        "bugs",
        ("electron", "desktop", "rtc", "signaling", "callkit", "bridge", "regression", "camera", "state-machine", "testing"),
        raw_source_lines(),
    ) + """# Electron switchCallType 媒体状态与拒绝态修复集（B059-B063）

## Summary

- B059-B063 是 B045/B057 之后继续收紧的 switchCallType 高风险区：它不推翻“switchCallType、摄像头开关、麦克风开关、RTC video availability 分离”的原则，而是在 resolved / rejected / pending 边界补齐缺口。
- B059 修复音频态视频 stop 造成的 remote camera closed 残留：非视频 -> 视频时清理音频切换遗留状态。
- B060 恢复明确关闭摄像头时的本端/远端文案，但等待远端首帧仍不能误报“对方关闭了摄像头”。
- B061 是新的产品规则变更：非视频 -> 视频默认打开麦克风，但只在音频态未被用户触碰时生效。
- B062 处理拒绝态补偿：pending 视频 -> 音频期间被抑制的 remote video stop，在拒绝后且通话仍为视频时，应转成 remote camera closed 来遮住最后一帧。
- B063 修正 `state=3` 方向：只有本端 outgoing switch 被对端拒绝时才提示“对方拒绝了您的请求”；本端拒绝 incoming 的 native 回声必须静默。

## Issue Matrix

| ID | Problem | Durable rule |
|----|---------|--------------|
| B059 | 切音频再切回视频后 remote camera closed 状态残留 | 非视频 -> 视频时清理音频切换遗留的 remote closed 状态 |
| B060 | 真实关闭摄像头只剩黑屏没有文案 | UI 只在明确 local/remote camera closed 时显示文案，等待首帧不显示 |
| B061 | 切回视频后麦克风仍保持视频态关闭状态 | 非视频 -> 视频且音频态未触碰时默认开麦；音频态触碰后尊重用户操作 |
| B062 | A 发起视频转音频，B 拒绝后 B 看到 A 最后一帧 | pending audio switch 中被抑制的 remote video stop，在 reject 后转换为 remote closed |
| B063 | 本端拒绝 incoming switch 后误弹“对方拒绝了您的请求” | `state=3` toast 需要匹配 outgoing switch marker；local reject echo 静默 |

## Reject State Direction Model

| Event | Local role | Expected behavior |
|---|---|---|
| `state=1` incoming switch and confirm enabled | Receiver | Set `pendingSwitchCallType`; do not apply callType yet |
| Local rejects incoming switch by sending `state=3` | Receiver | Clear pending request; do not show remote-reject toast |
| Native echoes local reject as `state=3` | Receiver | Consume local reject marker and ignore |
| Peer rejects our outgoing switch with `state=3` | Initiator | Clear outgoing marker and show “对方拒绝了您的请求” |
| `state=3` without matching outgoing/pending marker | Either | Do not show remote-reject toast |

## Media State Compensation Model

During video -> audio pending switch, remote RTC can emit `onVideoAvailable(false)` or `onVideoMuted(true)` before the switch is accepted or rejected. B059 originally protected against treating that as camera closed too early. B062 adds the missing reject branch:

- If the request is accepted and callType becomes audio, do not display remote camera closed.
- If the request is rejected and callType remains video, convert the suppressed video stop into `remoteVideoMuted=true` / remote closed overlay.
- If remote video later resumes, clear the temporary compensation state.

## Product Rule Exceptions

The current switchCallType protected matrix has two explicit non-video -> video product exceptions:

- B057: default open local camera when resolved switch moves from non-video to video. Duplicate video echoes must not reset user camera choice.
- B061: default open local microphone when resolved switch moves from non-video to video only if the user did not touch microphone in audio mode.

These exceptions do not allow `onVideoAvailable(false)` / `onVideoMuted(true)` to become callType signals, and do not allow camera/microphone buttons to change callType.

## Verification Evidence

- B059/B060/B061/B062/B063 source docs record runtime, shared UI, Electron wrapper, desktop switch guard, and source bridge checks where applicable.
- B061 touched `desktop/core`, so source bridge build and `bridgeStrategy=source` manifest verification remain required when that code is included in a final commit.
- B062/B063 were runtime-only in their session, but the active worktree later included native/bridge/core modifications; any commit including those files must rerun source bridge validation.

## Related wiki pages

- [[electron-camera-switch-microphone-state-regression-bugfix-set]]
- [[electron-switch-video-default-camera-on-product-rule-change]]
- [[electron-switchcalltype-regression-merge-guard-query]]
- [[electron-win-mac-camera-switch-microphone-state-query]]
- [[l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离]]
"""


def query_page() -> str:
    sources = [
        f"  - {NEW_BUG_PATH.as_posix()}",
        "  - bugs/electron-camera-switch-microphone-state-regression-bugfix-set.md",
        "  - bugs/electron-switch-video-default-camera-on-product-rule-change.md",
        "  - queries/electron-switchcalltype-regression-merge-guard-query.md",
        "  - queries/electron-win-mac-camera-switch-microphone-state-query.md",
    ]
    return frontmatter(
        "Electron switchCallType 拒绝态与媒体状态排查",
        "queries",
        ("electron", "desktop", "rtc", "signaling", "callkit", "bridge", "regression", "camera", "state-machine", "testing"),
        sources,
    ) + """# Electron switchCallType 拒绝态与媒体状态排查

## Question

处理 Electron switchCallType 的拒绝态、最后一帧、摄像头/麦克风默认状态问题时，应该先用哪些边界和验证矩阵？

## Answer Confidence

High, 0.88.

This answer is backed by B045/B057/B059/B060/B061/B062/B063 curated bugfix records and the prior switchCallType remediation query. It is high confidence for Electron runtime/shared UI/desktop-core guardrails, but still requires current-branch source verification before code changes.

## First Classification

| Symptom | First branch |
|---|---|
| 切音频/视频像开关摄像头 | Check B045 semantic separation first |
| 音频 -> 视频后本端摄像头仍关 | Check B057 non-video -> video camera exception |
| 音频 -> 视频后本端麦克风仍关 | Check B061 audio-mode touched rule |
| 切音频再切回视频后 remote closed 残留 | Check B059 stale remote closed cleanup |
| 真实关闭摄像头黑屏无文案 | Check B060 overlay text and first-frame guard |
| 拒绝视频 -> 音频后最后一帧残留 | Check B062 pending video stop compensation |
| 本端拒绝 incoming 却弹“对方拒绝” | Check B063 `state=3` direction model |

## State=3 Direction Checklist

1. Does `state=3` match a local `outgoingSwitchRequestCallType`? If yes, show “对方拒绝了您的请求”.
2. Does it match a local rejected incoming request marker? If yes, consume and ignore.
3. Was there a pending incoming request? Clear it without applying callType.
4. If none of the above match, do not show remote-reject toast.
5. Never treat `state=3` as permission to apply the target callType.

## Pending Video Stop Checklist

1. If current callType is video and pending target is audio, suppress immediate remote camera closed for incoming `onVideoAvailable(false)` / `onVideoMuted(true)`.
2. Record that remote video stopped while the audio switch was pending.
3. If the switch is accepted and callType becomes audio, do not show closed camera.
4. If the switch is rejected and callType remains video, convert the suppressed stop into remote camera closed to hide stale frame.
5. Clear temporary compensation state on video resume, resolved switch, setup/logout/destroy, and call end.

## Non-video -> Video Exceptions

| Resource | Rule | Guard |
|---|---|---|
| Camera | B057: default open when resolved switch moves non-video -> video | Do not apply on duplicate `callType=2` echo |
| Microphone | B061: default open when non-video -> video and audio mode was not touched | If user touched mic in audio mode, preserve user choice |

## Verification Matrix

Run at least:

```text
node --test packages/callkit-runtime-electron/test/runtime-contract.test.ts
node --test packages/callkit-runtime-electron/test/video-switch-regression.test.ts
node --test packages/callkit-react-core/test/call-view.test.js
node --test packages/callkit-vue3-core/test/call-view.test.js
node --test Electron/react-uikit/test/call-view.test.js Electron/vue3-uikit/test/call-view.test.js
```

If any commit includes `desktop/core`, `desktop/bridge`, `Electron/node-addon`, or native staging, also run source bridge build and inspect `Electron/out/native/*/manifest.json` for `bridgeStrategy=source`.

## Ingest Guidance

When a future fix changes any row in this state matrix, ingest it quickly. Old switchCallType pages are high-signal enough to mislead future agents when a product rule or state-direction exception changes.

## Sources Used

- [[electron-switchcalltype-media-state-and-reject-semantics-2026-05-09]]
- [[electron-camera-switch-microphone-state-regression-bugfix-set]]
- [[electron-switch-video-default-camera-on-product-rule-change]]
- [[electron-switchcalltype-regression-merge-guard-query]]
- [[electron-win-mac-camera-switch-microphone-state-query]]
"""


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
    related = "\n## Related"
    if related in text:
        return text.replace(related, block + related, 1)
    return text.rstrip() + block + "\n"


def update_existing_pages(wiki_root: Path) -> None:
    source_lines = raw_source_lines()

    camera_page = wiki_root / "bugs" / "electron-camera-switch-microphone-state-regression-bugfix-set.md"
    text = update_frontmatter(read_text(camera_page), source_lines)
    text = upsert_section(
        text,
        "2026-05-09 B059-B063 媒体状态与拒绝态补充",
        """B059-B063 把原来的 B045/B020/B028/B051/B057 保护矩阵继续细化：

| ID | Rule |
|----|------|
| B059 | 非视频 -> 视频时清理音频切换导致的 remote closed 残留。 |
| B060 | 真实关闭摄像头恢复本端/远端文案，但等待首帧不显示 closed 文案。 |
| B061 | 非视频 -> 视频默认开麦仅在音频态未触碰时生效；音频态触碰后尊重用户操作。 |
| B062 | pending 视频 -> 音频期间被抑制的 remote video stop，在拒绝后且仍为视频通话时转为 remote closed。 |
| B063 | `state=3` 必须绑定方向：本端 outgoing 被拒才提示“对方拒绝了您的请求”；本端拒绝 incoming 的回声静默。 |

新增排查入口：[[electron-switchcalltype-media-state-and-reject-semantics-2026-05-09]] 与 [[electron-switchcalltype-reject-state-and-media-preflight-query]]。""",
    )
    write_text(camera_page, text)

    b057_page = wiki_root / "bugs" / "electron-switch-video-default-camera-on-product-rule-change.md"
    text = update_frontmatter(read_text(b057_page), source_lines[4:6])
    text = text.replace(
        "- 麦克风静音状态不随 B057 重置，仍按 B020 的边界保留真实本地音频状态。",
        "- 2026-05-09 后麦克风按 B061 窄例外处理：非视频 -> 视频且音频态未触碰时默认开麦；音频态触碰后仍保留用户选择。",
    )
    text = text.replace(
        "| 麦克风 | 保持切换前真实音频状态 | 顺手 `muteLocalAudio(false)` 或重置用户静音 |",
        "| 麦克风 | B061 后：非视频 -> 视频且音频态未触碰时默认开麦；音频态触碰后保留用户选择 | 把开麦扩展到视频 -> 音频、重复视频 echo 或音频态用户已触碰场景 |",
    )
    text = upsert_section(
        text,
        "2026-05-09 B061 麦克风规则补充",
        """B057 只定义摄像头默认打开。B061 后，麦克风也有一个独立的非视频 -> 视频产品例外，但它比摄像头更窄：只有音频态未发生用户麦克风操作时才自动开麦。不要把 B061 理解成“所有 switchCallType 都重置麦克风”。""",
    )
    write_text(b057_page, text)

    switch_query = wiki_root / "queries" / "electron-switchcalltype-regression-merge-guard-query.md"
    text = update_frontmatter(read_text(switch_query), [f"  - {NEW_BUG_PATH.as_posix()}", f"  - {NEW_QUERY_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-09 Reject / Media State Addendum",
        """B059-B063 扩展了 switchCallType 修复前必须读取的矩阵：

- B061: 非视频 -> 视频默认开麦，但只有音频态未触碰时生效。
- B062: pending 视频 -> 音频期间被抑制的 remote video stop，在 reject 后如果仍是视频通话，应转成 remote camera closed。
- B063: `state=3` 不是无条件“对方拒绝了我”；只有 matching outgoing switch request 才显示该 toast。

处理新的 switchCallType 问题时，先读 [[electron-switchcalltype-reject-state-and-media-preflight-query]]。""",
    )
    write_text(switch_query, text)

    win_mac_query = wiki_root / "queries" / "electron-win-mac-camera-switch-microphone-state-query.md"
    text = update_frontmatter(read_text(win_mac_query), [f"  - {NEW_BUG_PATH.as_posix()}", f"  - {NEW_QUERY_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-09 SwitchCallType 补充矩阵",
        """后续 win/mac callType、摄像头、麦克风问题要额外区分：

- B061 麦克风默认开规则：非视频 -> 视频且音频态未触碰才自动开麦。
- B062 拒绝视频 -> 音频后最后一帧：pending 中抑制的 remote video stop 在 reject 后需要变成 remote closed。
- B063 本端拒绝 incoming：不显示“对方拒绝了您的请求”，该提示只属于 outgoing switch 被对端拒绝。""",
    )
    write_text(win_mac_query, text)

    lesson = wiki_root / "lessons" / "l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离.md"
    text = update_frontmatter(read_text(lesson), [f"  - {NEW_BUG_PATH.as_posix()}"])
    text = upsert_section(
        text,
        "2026-05-09 Addendum",
        """B061-B063 不改变本 lesson 的核心结论，但把保护矩阵扩展到新的方向：

- 非视频 -> 视频可以有产品例外，但必须用窄条件表达。
- `state=3` 需要结合 outgoing/incoming marker 判断，不是无条件拒绝提示。
- pending switch 期间的 RTC video stop 可以临时抑制，但 reject 后需要按当前 callType 补偿 UI 状态。""",
    )
    write_text(lesson, text)


def update_index(wiki_root: Path, created_bug: bool, created_query: bool) -> None:
    index_path = wiki_root / "index.md"
    text = read_text(index_path)
    increment = int(created_bug) + int(created_query)
    if increment:
        text = re.sub(r"Total pages: (\d+)", lambda m: f"Total pages: {int(m.group(1)) + increment}", text, count=1)
    bug_entry = f"- [Electron switchCallType 媒体状态与拒绝态修复集（B059-B063）]({NEW_BUG_PATH.as_posix()}) - B059-B063 汇总非视频->视频摄像头/麦克风例外、拒绝态 state=3 方向和 pending video stop 补偿。"
    query_entry = f"- [Electron switchCallType 拒绝态与媒体状态排查]({NEW_QUERY_PATH.as_posix()}) - Query filed 2026-05-09 / 后续 callType 拒绝态、最后一帧、默认开麦/开摄像头问题的高置信度排查矩阵。"
    if bug_entry not in text:
        text = text.replace("## Bugs\n\n", "## Bugs\n\n" + bug_entry + "\n", 1)
    if query_entry not in text:
        text = text.replace("## Queries\n\n", "## Queries\n\n" + query_entry + "\n", 1)
    write_text(index_path, text.rstrip() + "\n")


def append_log(wiki_root: Path, raw_created: int, raw_unchanged: int) -> None:
    log_path = wiki_root / "log.md"
    text = read_text(log_path).rstrip()
    marker = "import | <workspace>/project/NECallKit docs B059-B063 switchCallType media-state cluster"
    if marker in text:
        return
    entry = f"""

## [{TODAY}] import | <workspace>/project/NECallKit docs B059-B063 switchCallType media-state cluster (10 files)
- Format: curated folder batch
- Created: 2 wiki pages
- Updated: 5 existing pages
- Raw: raw/imported/{BUNDLE_NAME}/ ({raw_created} created, {raw_unchanged} unchanged)
- Source groups: B059 stale remote camera closed; B060 camera closed text; B061 default microphone rule; B062 reject remote last frame; B063 local reject toast direction
- Filed: [[electron-switchcalltype-media-state-and-reject-semantics-2026-05-09]], [[electron-switchcalltype-reject-state-and-media-preflight-query]]
- Updated: [[electron-camera-switch-microphone-state-regression-bugfix-set]], [[electron-switch-video-default-camera-on-product-rule-change]], [[electron-switchcalltype-regression-merge-guard-query]], [[electron-win-mac-camera-switch-microphone-state-query]], [[l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离]]
- Decision: ingest immediately because user needs fresh wiki guidance for follow-up callType issues and older B020/B057 query results are now incomplete for B061-B063.
"""
    write_text(log_path, text + entry)


def execute(wiki_root: Path, project_root: Path) -> dict[str, object]:
    raw_counts = {"created": 0, "unchanged": 0}
    for source in SOURCE_FILES:
        raw_counts[safe_copy_raw(project_root, wiki_root, source)] += 1

    bug_full = wiki_root / Path(NEW_BUG_PATH.as_posix())
    query_full = wiki_root / Path(NEW_QUERY_PATH.as_posix())
    created_bug = not bug_full.exists()
    created_query = not query_full.exists()
    write_text(bug_full, bug_page())
    write_text(query_full, query_page())
    update_existing_pages(wiki_root)
    update_index(wiki_root, created_bug, created_query)
    append_log(wiki_root, raw_counts["created"], raw_counts["unchanged"])
    return {
        "raw_created": raw_counts["created"],
        "raw_unchanged": raw_counts["unchanged"],
        "created": [str(NEW_BUG_PATH), str(NEW_QUERY_PATH)],
        "updated": [
            "bugs/electron-camera-switch-microphone-state-regression-bugfix-set.md",
            "bugs/electron-switch-video-default-camera-on-product-rule-change.md",
            "queries/electron-switchcalltype-regression-merge-guard-query.md",
            "queries/electron-win-mac-camera-switch-microphone-state-query.md",
            "lessons/l013-electron-音视频切换与摄像头开关必须跨-runtime-desktop-core-source-bridge-三层隔离.md",
        ],
    }


def main() -> int:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    project_root = Path(args.project).resolve()
    checkpoint_script = Path(args.checkpoint_script).resolve()
    validate_sources(project_root)
    plan = {
        "bundle": BUNDLE_NAME,
        "sources": [source.as_posix() for source in SOURCE_FILES],
        "new_pages": [NEW_BUG_PATH.as_posix(), NEW_QUERY_PATH.as_posix()],
        "updates": 5,
    }
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
