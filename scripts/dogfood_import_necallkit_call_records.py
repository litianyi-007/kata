from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "necallkit-call-records"
TODAY = date.today().isoformat()

CATEGORY_HEADINGS = {
    "platforms": "Platforms",
    "modules": "Modules",
    "features": "Features",
    "bugs": "Bugs",
    "decisions": "Decisions",
    "lessons": "Lessons",
    "queries": "Queries",
}

NEW_PAGES = {
    PurePosixPath("features/electron-default-im-call-record-sync.md"): (
        "Electron 默认 IM 话单同步展示",
        "F013 默认 IM call message/history 话单同步、node-nim V2 example owner、多端同步与 provider 边界。",
    ),
    PurePosixPath("bugs/electron-call-record-provider-and-list-semantics.md"): (
        "Electron 自定义话单 provider 与列表语义",
        "B047/B048 记录 setCallRecordProvider、onRecordSend、source runtime、append-only 列表和紧凑展示边界。",
    ),
    PurePosixPath("bugs/desktop-call-record-status-and-durations-compatibility.md"): (
        "Desktop 话单状态值与 durations 兼容性",
        "B018/B027 记录 desktop record raw status 必须对齐 iOS/NIM 1..5，默认 NIM call message durations 必须非空。",
    ),
    PurePosixPath("queries/necallkit-call-record-bugfix-preflight-query.md"): (
        "NECallKit 话单 bugfix 前置检查清单",
        "Query filed 2026-05-09 / 话单 bugfix 前区分默认 IM、provider-local、history sync、raw status 和 durations。",
    ),
}

SOURCE_FILES: tuple[PurePosixPath, ...] = (
    PurePosixPath("docs/prd/F013-electron-default-call-record-sync/F013-electron-default-call-record-sync.md"),
    PurePosixPath("docs/prd/F013-electron-default-call-record-sync/F013-electron-default-call-record-sync-test.md"),
    PurePosixPath("docs/prd/F013-electron-default-call-record-sync/F013-electron-default-call-record-sync-tasks.md"),
    PurePosixPath("docs/bugfix/B047-electron-record-provider-runtime-debug/analysis.md"),
    PurePosixPath("docs/bugfix/B047-electron-record-provider-runtime-debug/B047-electron-record-provider-runtime-debug-test.md"),
    PurePosixPath("docs/bugfix/B048-electron-call-record-list-append-compact/analysis.md"),
    PurePosixPath("docs/bugfix/B048-electron-call-record-list-append-compact/B048-electron-call-record-list-append-compact-test.md"),
    PurePosixPath("docs/bugfix/B018-desktop-record-state-ios-alignment/analysis.md"),
    PurePosixPath("docs/bugfix/B018-desktop-record-state-ios-alignment/B018-desktop-record-state-ios-alignment-test.md"),
    PurePosixPath("docs/bugfix/B027-desktop-record-durations-null/analysis.md"),
)


@dataclass(frozen=True)
class PageSpec:
    target: PurePosixPath
    title: str
    page_type: str
    tags: tuple[str, ...]
    published_at: str
    sources: tuple[PurePosixPath, ...]
    body: str

    @property
    def slug(self) -> str:
        return self.target.stem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import the NECallKit call-record curated dogfood batch.")
    parser.add_argument("--wiki", required=True, help="NECallKit wiki root")
    parser.add_argument("--project", required=True, help="NECallKit project root")
    parser.add_argument(
        "--checkpoint-script",
        default=str(Path(__file__).resolve().parents[1] / "plugin" / "scripts" / "import_checkpoint.py"),
        help="Path to kata import_checkpoint.py",
    )
    parser.add_argument("--execute", action="store_true", help="Write changes. Default is dry-run only.")
    parser.add_argument("--commit", action="store_true", help="Commit after a successful execute.")
    parser.add_argument("--push", action="store_true", help="Push after commit. Implies --commit.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow execute when wiki git tree is dirty.")
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


def yaml_quote(value: str) -> str:
    return '"' + value.replace('"', "'") + '"'


def raw_path(source: PurePosixPath) -> PurePosixPath:
    return PurePosixPath("raw") / "imported" / BUNDLE_NAME / source


def source_list(sources: tuple[PurePosixPath, ...]) -> str:
    return "\n".join(f"  - {source_entry(source)}" for source in sources)


def source_entry(source: PurePosixPath) -> str:
    if source.parts and source.parts[0] in CATEGORY_HEADINGS:
        return source.as_posix()
    return raw_path(source).as_posix()


def tags_list(tags: tuple[str, ...]) -> str:
    return "\n".join(f"  - {tag}" for tag in tags)


def run_git(wiki_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(wiki_root), *args], text=True, capture_output=True, check=check)


def git_status_porcelain(wiki_root: Path) -> str:
    return run_git(wiki_root, "status", "--porcelain", check=True).stdout.strip()


def checkpoint(script: Path, wiki_root: Path, *args: str) -> None:
    command = [sys.executable, str(script), "--wiki", str(wiki_root), *args]
    completed = subprocess.run(command, text=True, capture_output=True, check=True)
    if completed.stdout.strip():
        print(completed.stdout.strip())


def safe_copy_raw(project_root: Path, wiki_root: Path, source: PurePosixPath) -> str:
    source_path = project_root / Path(source.as_posix())
    destination = wiki_root / Path(raw_path(source).as_posix())
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if source_path.read_bytes() == destination.read_bytes():
            return "unchanged"
        raise RuntimeError(f"Raw file differs and will not be overwritten: {destination}")
    shutil.copy2(source_path, destination)
    return "created"


def page_frontmatter(spec: PageSpec) -> str:
    return f"""---
title: {yaml_quote(spec.title)}
type: {spec.page_type}
tags:
{tags_list(spec.tags)}
created: {TODAY}
updated: {TODAY}
published_at: {spec.published_at}
ingested_at: {TODAY}
sources:
{source_list(spec.sources)}
---

"""


def page_content(spec: PageSpec) -> str:
    return page_frontmatter(spec) + spec.body.strip() + "\n"


def build_pages() -> tuple[PageSpec, ...]:
    f013_sources = SOURCE_FILES[0:3]
    provider_sources = SOURCE_FILES[3:7]
    compat_sources = SOURCE_FILES[7:10]
    query_sources = (
        PurePosixPath("features/electron-default-im-call-record-sync.md"),
        PurePosixPath("bugs/electron-call-record-provider-and-list-semantics.md"),
        PurePosixPath("bugs/desktop-call-record-status-and-durations-compatibility.md"),
    )

    return (
        PageSpec(
            target=PurePosixPath("features/electron-default-im-call-record-sync.md"),
            title="Electron 默认 IM 话单同步展示",
            page_type="features",
            tags=("electron", "desktop", "web", "nim", "callkit", "call-record", "compatibility", "testing"),
            published_at="2026-04-28",
            sources=f013_sources,
            body="""# Electron 默认 IM 话单同步展示

## Summary

- F013 固定了 Electron React/Vue3 example 的默认话单来源：默认模式只展示 IM call message/history 形成的话单，不展示 provider-local `onRecordSend`。
- `setCallRecordProvider(true)` 表示 host 接管自定义话单，SDK 会截断默认 NIM 话单发送；因此 `onRecordSend` 不能被当成默认话单接收事件。
- 多端同步依赖 IM call message 与历史消息。相同账号多设备登录时，其他设备只能通过 IM 消息流/历史消息看到另一设备接听或结束形成的话单。
- F013 首发路径让 React/Vue3 example 使用 `node-nim` V2 `messageService` 读取默认 IM 话单，并在 setup 后主动调用 `setCallRecordProvider(false)`，避免历史自定义接管状态截断默认话单。
- F013 不把 renderer 直接持有 `node-nim` 提升为正式 public SDK contract；它只是 example 默认话单同步 owner。host-first 默认同步要等 node-addon V2-only message listener/query API 正式化。

## Source split

| Source | Trigger | Multi-device sync | UI meaning |
| --- | --- | --- | --- |
| `im-call-message` | 默认模式 SDK 内部发送，或其他端同步到 IM 消息 | Yes | 默认同步话单 |
| `im-history` | 登录后查询历史消息 | Yes | 初始化补齐 |
| `im-send` | 本端发送 call message 成功回调 | Yes | 本端即时写入 |
| provider-local `onRecordSend` | `setCallRecordProvider(true)` 后 native 请求 host 接管 | No by itself | 自定义接管调试/业务接管，不进入 F013 默认列表 |

## Implementation facts

- `CallRecordEntry.source` 需要保留 `im-call-message`、`im-history`、`im-send`，避免把默认同步和 provider-local 事件混成一个列表来源。
- 去重优先使用 `messageServerId` 或 `messageClientId`，再退到 `conversationId + timestamp + peer`，不能按 peer 聚合。
- 默认列表只保留 10 条，按消息时间倒序展示；缓存和展示都按账号隔离。
- Adapter 异常不能影响呼叫主流程，只能写 diagnostics/debug log。
- E2E summary 应保留 `callRecordSourceCounts`、`lastCallRecordMessageId`、`callRecordAdapterReady` / `callRecordAdapterError` 与 `runtimeDiagnostics.resolvedLibraryPath`。

## Verification evidence

- `node --test Electron/scripts/test/call-records.test.js`
- `node --test Electron/scripts/test/call-record-cache.test.js`
- `node --test Electron/scripts/test/call-record-message-adapter.test.js`
- `node --test Electron/scripts/test/example-external-nim-session.test.js`
- `node --test Electron/scripts/test/example-e2e-output-root.test.js`
- `node --test Electron/example-react/test/ui-shell.test.js`
- `node --test Electron/example-vue3/test/ui-shell.test.js`
- `cd Electron && npm run test:electron-release-artifact-contract`
- Manual acceptance recorded for `lty03` / `p01`: React/Vue3 default mutual calls, custom provider boundary, and same-account multi-device sync.

## Boundaries for future work

- Do not add V1 login, V1 message API, or V1 fallback for Electron/desktop call records.
- Do not make `onRecordSend` a default IM call-record receiver.
- Do not silently dual-send default IM records when provider mode is enabled.
- Do not claim renderer-owned `node-nim` as a formal SDK contract without a separate API decision.
- If a bug report says "话单不同步", first ask which source is involved: default IM message/history, local provider callback, local cache, or UI rendering.

## Related wiki pages

- [[electron-call-record-provider-and-list-semantics]]
- [[desktop-call-record-status-and-durations-compatibility]]
- [[necallkit-call-record-bugfix-preflight-query]]
- [[necallkit-electron-web-reuse-operating-boundary-query]]
- [[002-electron-callkit-contracts-electron-node-nim-boundary]]
""",
        ),
        PageSpec(
            target=PurePosixPath("bugs/electron-call-record-provider-and-list-semantics.md"),
            title="Electron 自定义话单 provider 与列表语义",
            page_type="bugs",
            tags=("electron", "desktop", "bridge", "callkit", "call-record", "regression", "testing"),
            published_at=TODAY,
            sources=provider_sources,
            body="""# Electron 自定义话单 provider 与列表语义

## Summary

- B047 证明 provider-local 话单问题可能同时来自 native runtime 版本、Electron source bridge、Vue3 automation 表单状态与 `setCallRecordProvider` 同步缺口。
- B048 证明 provider-local 列表语义是 append-only：每次 `onRecordSend` 都应新增一条记录，不应按 `callId`、peer 或对象聚合覆盖。
- 对 provider 模式的成功判断必须看本地 `recordSend` 是否触发、summary 是否记录 completed record、runtime 是否加载 source-built bridge，而不是看默认 IM 同步列表。

## B047 root cause pattern

Two independent risks were confirmed:

- Default `Electron/out/native/win32-debug` had previously loaded an old runtime, so manual example runs could miss desktop core's completed-record fix.
- Vue3 automation `patchForm({ callRecordProviderEnabled: true })` changed form state without immediately calling `sdk.setCallRecordProvider(true)`, so the script thought provider was enabled while native was still in default mode.

The fix rebuilt the source runtime, synchronized Vue3 provider / timeout / callConfig changes after initialization and automation patches, added `--call-record-provider` to E2E, and exposed logs in React/Vue3 summary for `setCallRecordProvider` and `onRecordSend`.

## Provider-local checklist

| Check | Why it matters |
| --- | --- |
| `setCallRecordProvider(true)` actually reached native | Form state alone is not a runtime contract |
| `runtimeDiagnostics.resolvedLibraryPath` points to intended source/native output | Old DLL/framework can make JS fixes look ineffective |
| Electron source bridge manifest uses source strategy when testing desktop core fixes | Packaged Flutter bridge may not include current desktop fixes |
| Summary/logs include `onRecordSend` and completed record evidence | Provider mode is local callback evidence, not IM sync evidence |
| React and Vue3 automation paths both sync provider state | Vue3 once drifted after `patchForm` |

## B048 list semantics

- Replace `upsertCallRecord()` with append semantics for provider-local records.
- Generate a unique row ID per `onRecordSend`, even when `callId` and `accId` repeat.
- Keep the recent list bounded. B048 kept the latest 20 provider records.
- Use a compact one-line row with truncation/title for small Electron example width.

Provider-local append semantics do not contradict F013 default IM list semantics. F013 deduplicates IM messages by message ID because IM receive/send/history can surface the same durable message more than once. B048 appends provider-local callback events because each native `onRecordSend` invocation is itself the record being displayed.

## Verification evidence

- `node Electron/scripts/test/desktop-record-trigger-matrix.test.js`
- `node --test Electron/example-react/test/ui-shell.test.js`
- `node --test Electron/example-vue3/test/ui-shell.test.js`
- `node Electron/sdk/test/event-alignment.test.js`
- `node Electron/sdk/test/ne-call.test.js`
- `node --test Electron/scripts/test/build-plan.test.js`
- `node --test Electron/scripts/test/build.test.js`
- Real account summaries: React/Vue3 local/remote hangup under `Electron/out/e2e-record-debug/.../summary.json`, all with `callerCompletedRecord=true`.

## Related wiki pages

- [[electron-default-im-call-record-sync]]
- [[desktop-call-record-status-and-durations-compatibility]]
- [[necallkit-call-record-bugfix-preflight-query]]
- [[electron-switchcalltype-regression-merge-guard-query]]
- [[necallkit-docs-guides-electron-flutter-merge-review-checklist]]
""",
        ),
        PageSpec(
            target=PurePosixPath("bugs/desktop-call-record-status-and-durations-compatibility.md"),
            title="Desktop 话单状态值与 durations 兼容性",
            page_type="bugs",
            tags=("desktop", "flutter", "ios", "android", "nim", "callkit", "call-record", "compatibility", "testing"),
            published_at="2026-04-15",
            sources=compat_sources,
            body="""# Desktop 话单状态值与 durations 兼容性

## Summary

- B018 fixed a raw protocol split: desktop provider payload had been exposing local `0..4` `CallRecordState` values while iOS `NIMRtcCallStatus` and default NIM call messages use `1..5`.
- B027 fixed a cross-platform crash: desktop default NIM call messages had empty `durations`, while Android Flutter parsing treated `getDurations()` as a non-null list.
- These fixes sit below Electron UI. Any话单 bug that crosses desktop, Flutter, Android, iOS, or NIM message history must check raw status values and `durations` before blaming the renderer.

## Raw status value contract

| Call status | Required raw value |
| --- | --- |
| completed / complete | `1` |
| cancelled / canceled | `2` |
| rejected | `3` |
| timeout | `4` |
| busy | `5` |

Desktop core, desktop bridge comments, Flutter desktop mapper, default NIM call message, iOS `NIMRtcCallStatus`, and provider payload must converge on this `1..5` raw value space. Flutter public `NIMCallStatus` enum semantics do not need to change; the bridge raw value mapping does.

## Durations contract

- `NECallKitHangupParam.duration` must be cached for the current desktop session and reset at session boundaries.
- Default NIM call message construction must pass a non-empty `durations` collection.
- The durations list should include at least the local account, and also the peer account when possible, so local and peer message histories both have a usable duration entry.
- Missing duration should fall back to `0`, not null/empty.
- This fix applies to default NIM call messages. It does not change Flutter record-provider payload semantics.

## Regression checks

- Provider completed raw `record_send.call_state = 1`.
- Provider rejected raw `record_send.call_state = 3`.
- Provider busy raw `record_send.call_state = 5`.
- Default NIM sending and custom provider use the same raw status space.
- Flutter desktop `onRecordSend` still maps to `completed / rejected / busy` public states.
- Flutter Desktop calling Flutter Android and hanging up before answer must not crash Android Flutter call attachment parsing.
- Desktop local and remote message history should contain a call attachment whose `durations` includes at least the local account item.

## Related wiki pages

- [[electron-default-im-call-record-sync]]
- [[electron-call-record-provider-and-list-semantics]]
- [[necallkit-call-record-bugfix-preflight-query]]
- [[necallkit-architecture-overview]]
- [[necallkit-docs-guides-electron-flutter-merge-review-checklist]]
""",
        ),
        PageSpec(
            target=PurePosixPath("queries/necallkit-call-record-bugfix-preflight-query.md"),
            title="NECallKit 话单 bugfix 前置检查清单",
            page_type="queries",
            tags=("electron", "desktop", "flutter", "ios", "android", "nim", "callkit", "call-record", "regression", "testing", "compatibility"),
            published_at=TODAY,
            sources=query_sources,
            body="""# NECallKit 话单 bugfix 前置检查清单

## Question

处理 NECallKit 话单相关 bug 或需求前，wiki 已沉淀哪些边界、风险和验证清单？

## Answer Confidence

High, 0.86.

The wiki now has directly relevant curated pages for F013, B047, B048, B018, and B027, with design, tests, and manual acceptance evidence. The boundary is still the current checked-out repo/branch: if the user reports a new requirement or a fact change, confirm the changed truth state and ingest the new fix/development record after resolution.

## First classification

| User symptom | First branch |
| --- | --- |
| "默认话单不同步" | Check IM call message/history, `node-nim` V2 adapter, message ID dedup, multi-device IM sync |
| "开启自定义话单后没回调" | Check `setCallRecordProvider(true)`, source runtime/bridge, local `onRecordSend` logs |
| "话单列表被覆盖/少一条" | Determine whether it is provider-local append-only or IM message dedup |
| "跨端解析崩溃" | Check default NIM call message attachment, especially non-null `durations` |
| "状态值不对" | Check raw status value space: desktop/iOS/NIM/provider should use `1..5` |
| "同账号另一个设备看不到" | Check IM message/history path, not provider-local events |

## Non-negotiable boundaries

1. Default IM call records and provider-local `onRecordSend` are distinct sources.
2. `setCallRecordProvider(true)` means host takes over and default NIM call record sending is cut off.
3. Do not use `onRecordSend` as the default call-record receiver.
4. Multi-device sync depends on IM call messages/history, not provider-local callbacks.
5. F013 `node-nim` V2 renderer/example owner is not a formal public SDK contract.
6. Desktop raw call status values must be `1..5`, aligned with iOS/NIM, not local `0..4`.
7. Default NIM call message `durations` must be non-null and should include local and peer account entries.

## Source-specific checks

### Default IM call-record sync

Use [[electron-default-im-call-record-sync]] when the issue involves default records, IM history, same-account multi-device sync, or React/Vue3 default list display.

- Verify `setCallRecordProvider(false)` is called during example setup.
- Verify `node-nim` V2 `messageService` is available when using the F013 example path.
- Check receive/send/modified/history counters and message IDs.
- Deduplicate by message ID, not by peer or call object.
- Preserve `callRecordSourceCounts`, adapter state, and last message ID in summary output.

### Provider-local records

Use [[electron-call-record-provider-and-list-semantics]] when the issue involves `setCallRecordProvider(true)`, `onRecordSend`, local custom provider, source runtime, or provider list rows.

- Confirm the UI or automation path actually called native `setCallRecordProvider(true)`.
- Confirm `runtimeDiagnostics.resolvedLibraryPath` points to the intended rebuilt native output.
- For desktop/core fixes, verify Electron source bridge/manifest uses the source strategy, not stale packaged bridge output.
- Provider-local list semantics are append-only. Do not collapse repeated `callId` rows.

### Cross-platform compatibility

Use [[desktop-call-record-status-and-durations-compatibility]] when the issue touches desktop bridge raw payloads, Flutter desktop, Android Flutter, iOS raw status, NIM message attachment, or call history parsing.

- Raw provider `call_state`: completed `1`, cancelled `2`, rejected `3`, timeout `4`, busy `5`.
- Default NIM call message and provider payload must not diverge into two status value spaces.
- Default NIM call message must provide non-empty `durations`; empty/null can break Android Flutter parsing.

## Requirement/fact-change guard

If the user explicitly says the call-record rule has changed, do not answer from old F013/B047/B048/B018/B027 guidance as if it is still current. State the old wiki-backed rule, the newly declared rule, and the evidence needed to make the new rule durable.

If the user does not say the rule changed but the requested behavior contradicts the wiki, ask a confirmation question before making a decisive fix. Examples:

- "Should provider mode now also send default IM call records, or is this still forbidden to avoid double-send?"
- "Should the default list now include provider-local rows, or should provider and default IM records remain separate?"
- "Has the public SDK contract changed to expose renderer/host message-service ownership, or is F013 still example-only?"
- "Did raw status values change away from iOS/NIM `1..5`, or is this a regression?"

## Evidence to preserve for ingest

When a new call-record bug or feature is solved outside the wiki, ask the current agent/LLM to save a short fix/development note with:

- Problem statement and user-visible symptom.
- Which source path was affected: default IM message/history, provider-local callback, cache/list UI, raw bridge payload, NIM call attachment, or adapter ownership.
- Root cause and changed files.
- Old wiki rule versus new confirmed rule, if any.
- Runtime/source bridge evidence, including `resolvedLibraryPath` and manifest/bridge strategy when desktop/core is involved.
- Tests and manual accounts/devices used.
- Generated artifacts checked.
- Remaining risks or deferred API decisions.

Timely ingest is required when a new fix changes any of the seven non-negotiable boundaries above. Otherwise future queries may return confident but stale guidance.

## Reusable prompt for future agents

Before editing call-record code, read [[electron-default-im-call-record-sync]], [[electron-call-record-provider-and-list-semantics]], and [[desktop-call-record-status-and-durations-compatibility]]. Classify the symptom by source, verify whether provider mode is enabled, confirm runtime/source bridge freshness, and do not merge default IM sync with provider-local `onRecordSend` unless the user confirms a requirement change and preserves evidence for ingest.
""",
        ),
    )


def insert_schema_tag(wiki_root: Path, tag: str) -> bool:
    schema_path = wiki_root / "SCHEMA.md"
    text = read_text(schema_path)
    if re.search(rf"^\s*-\s+{re.escape(tag)}\s*$", text, re.MULTILINE):
        return False
    lines = text.splitlines()
    insert_at = None
    in_taxonomy = False
    in_fence = False
    for index, line in enumerate(lines):
        if line.strip() == "## Tag taxonomy":
            in_taxonomy = True
            continue
        if in_taxonomy and line.strip() == "```yaml":
            in_fence = True
            continue
        if in_taxonomy and in_fence and line.strip() == "- state-machine":
            insert_at = index + 1
            break
        if in_taxonomy and in_fence and line.strip() == "```":
            insert_at = index
            break
    if insert_at is None:
        raise RuntimeError("Could not find tag_taxonomy block in SCHEMA.md")
    lines.insert(insert_at, f"  - {tag}")
    write_text(schema_path, "\n".join(lines).rstrip() + "\n")
    return True


def update_index(wiki_root: Path, created_pages: set[PurePosixPath]) -> None:
    index_path = wiki_root / "index.md"
    text = read_text(index_path)
    if created_pages:
        text = re.sub(
            r"Total pages: (\d+)",
            lambda match: f"Total pages: {int(match.group(1)) + len(created_pages)}",
            text,
            count=1,
        )
    for target, (title, summary) in NEW_PAGES.items():
        page_type = target.parts[0]
        heading = CATEGORY_HEADINGS[page_type]
        entry = f"- [{title}]({target.as_posix()}) - {summary}"
        if entry in text:
            continue
        heading_marker = f"## {heading}\n\n"
        if heading_marker not in text:
            raise RuntimeError(f"Could not find index section: {heading}")
        before, after = text.split(heading_marker, 1)
        next_heading = re.search(r"\n## [^\n]+\n", after)
        if next_heading:
            section = after[: next_heading.start()]
            rest = after[next_heading.start() :]
        else:
            section = after
            rest = ""
        lines = [line for line in section.splitlines() if line.strip()]
        lines.append(entry)
        lines = sorted(lines, key=lambda line: re.sub(r"^- \[(.*?)\].*$", r"\1", line).lower())
        text = before + heading_marker + "\n".join(lines) + "\n\n" + rest.lstrip("\n")
    write_text(index_path, text.rstrip() + "\n")


def append_log(wiki_root: Path, raw_created: int, raw_unchanged: int, schema_tag_added: bool) -> None:
    log_path = wiki_root / "log.md"
    text = read_text(log_path).rstrip()
    marker = "import | <workspace>/project/NECallKit docs call-record cluster"
    if marker in text:
        return
    entry = f"""

## [{TODAY}] import | <workspace>/project/NECallKit docs call-record cluster (10 files)
- Format: curated folder batch
- Created: 4 wiki pages
- Updated: 0 existing pages
- Raw: raw/imported/{BUNDLE_NAME}/ ({raw_created} created, {raw_unchanged} unchanged)
- Source groups: F013 default IM call-record sync; B047 provider runtime debug; B048 provider list append semantics; B018 raw status alignment; B027 durations compatibility
- Filed: [[electron-default-im-call-record-sync]], [[electron-call-record-provider-and-list-semantics]], [[desktop-call-record-status-and-durations-compatibility]], [[necallkit-call-record-bugfix-preflight-query]]
- Tag additions to SCHEMA.md: {"call-record" if schema_tag_added else "none"}
- Decision: ingest before话单 bug work because existing wiki hits were thin/noisy and Chinese-only `话单` search had no usable terms.
"""
    write_text(log_path, text + entry)


def validate_sources(project_root: Path) -> None:
    missing = [source.as_posix() for source in SOURCE_FILES if not (project_root / Path(source.as_posix())).exists()]
    if missing:
        raise FileNotFoundError("Missing source files:\n" + "\n".join(missing))


def execute(wiki_root: Path, project_root: Path) -> dict[str, object]:
    raw_counts = {"created": 0, "unchanged": 0}
    for source in SOURCE_FILES:
        result = safe_copy_raw(project_root, wiki_root, source)
        raw_counts[result] += 1

    created_pages: set[PurePosixPath] = set()
    pages = build_pages()
    for spec in pages:
        target = wiki_root / Path(spec.target.as_posix())
        if not target.exists():
            created_pages.add(spec.target)
        write_text(target, page_content(spec))

    schema_tag_added = insert_schema_tag(wiki_root, "call-record")
    update_index(wiki_root, created_pages)
    append_log(wiki_root, raw_counts["created"], raw_counts["unchanged"], schema_tag_added)

    return {
        "raw_created": raw_counts["created"],
        "raw_unchanged": raw_counts["unchanged"],
        "created_pages": [page.as_posix() for page in sorted(created_pages)],
        "schema_tag_added": schema_tag_added,
    }


def main() -> int:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    project_root = Path(args.project).resolve()
    checkpoint_script = Path(args.checkpoint_script).resolve()
    validate_sources(project_root)
    pages = build_pages()
    plan = {
        "bundle": BUNDLE_NAME,
        "sources": [source.as_posix() for source in SOURCE_FILES],
        "pages": [spec.target.as_posix() for spec in pages],
        "schema_tag": "call-record",
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

        if args.commit or args.push:
            run_git(wiki_root, "add", "SCHEMA.md", "index.md", "log.md", "features/electron-default-im-call-record-sync.md", "bugs/electron-call-record-provider-and-list-semantics.md", "bugs/desktop-call-record-status-and-durations-compatibility.md", "queries/necallkit-call-record-bugfix-preflight-query.md", f"raw/imported/{BUNDLE_NAME}")
            run_git(wiki_root, "commit", "-m", "wiki-import: call record sync and provider cluster")
            checkpoint(checkpoint_script, wiki_root, "clear")
            if args.push:
                run_git(wiki_root, "push", "origin", "master")
        return 0
    finally:
        checkpoint(checkpoint_script, wiki_root, "unlock")


if __name__ == "__main__":
    raise SystemExit(main())
