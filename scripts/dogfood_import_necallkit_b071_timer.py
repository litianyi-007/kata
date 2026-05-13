from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "necallkit-electron-duration-from-onconnect-2026-05-10"
TODAY = date.today().isoformat()

SOURCE_FILES: tuple[PurePosixPath, ...] = (
    PurePosixPath("docs/bugfix/B071-electron-duration-from-onconnect/analysis.md"),
    PurePosixPath("docs/bugfix/B071-electron-duration-from-onconnect/B071-electron-duration-from-onconnect-test.md"),
)

NEW_BUG_PATH = PurePosixPath("bugs/electron-duration-timer-from-onconnect-2026-05-10.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import NECallKit B071 duration timer from onCallConnected.")
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
        "Electron 通话页计时器需从 onCallConnected 起算（B071）",
        "bugs",
        ("electron", "callkit", "regression", "state-machine", "lifecycle", "testing"),
        raw_source_lines(),
    ) + """# Electron 通话页计时器需从 onCallConnected 起算（B071）

## Summary

- B071 修正 Electron runtime 通话页计时器起点：从被叫 `accept()` 返回 `callStatus=3` 改为收到 `onCallConnected` 通知后才开始。
- 关键判据从 `derivedCallStatus === 3` 改为 `state.connected && derivedCallStatus === 3`。
- `onCallConnected` 首次到达 `wasInActiveCall=false` → durationSeconds=0；refresh 时 `wasInActiveCall=true` → 保留当前 durationSeconds，避免短暂归零。
- 与 Web runtime 的 `state.connected && callStatus === 3` 起算语义对齐。

## 旧链路（错误）

```text
1. 被叫 accept()
2. sdk.accept() 返回 callStatus=3
3. syncState() 看到 derivedCallStatus===3 → 提前 startDurationTicker()
4. RTC/NIM 真实建连较慢，等几秒才收到 onCallConnected
5. onCallConnected 再次写 durationSeconds=0，但 ticker 已存在 → 直接 return
6. UI 按 accept 时刻起算，包含等待建连时间 → 双端不对齐
```

## 修复

```js
if (state.connected && derivedCallStatus === 3) {
  startDurationTicker();
} else {
  stopDurationTicker();
}
```

`accept()` 返回 `callStatus=3, connected=false` 时，UI 显示"连接中..."，计时不启动。`onCallConnected` 到达时：

```js
durationSeconds: wasInActiveCall ? state.durationSeconds : 0
```

## 影响范围

| 层级 | 文件 |
|------|------|
| Electron runtime | `packages/callkit-runtime-electron/src/runtime.ts` |
| Runtime contract test | `packages/callkit-runtime-electron/test/runtime-contract.test.ts` |

不涉及 `desktop/core` / `Electron/node-addon` / native bridge ABI / source bridge 产物。

## 与既有约束的关系

- L009（setInterval drift use Date.now）：保留——计时仍用 `Date.now() - durationBaseTimestamp`，setInterval 只驱动刷新。
- B071 不解决"接通慢"的底层耗时；仅修正通话页计时起点。

## 验证

| ID | 命令 | 结果 |
|----|------|------|
| TC-B071-001 | `node --test --test-name-pattern "starts duration only after onCallConnected" packages/callkit-runtime-electron/test/runtime-contract.test.ts` | 1/1 |

真机验证仍需 macOS 呼叫 Windows 视频通话双端实测对齐。

## Related

- 关联 lesson（项目内）：`docs/lessons/platform-issues/L009-setinterval-drift-use-date-now.md`
- 改动文件：`packages/callkit-runtime-electron/src/runtime.ts`
"""


def update_index(wiki_root: Path, created_bug: bool) -> None:
    index_path = wiki_root / "index.md"
    text = read_text(index_path)
    if created_bug:
        text = re.sub(r"Total pages: (\d+)", lambda m: f"Total pages: {int(m.group(1)) + 1}", text, count=1)
    bug_entry = f"- [Electron 通话页计时器需从 onCallConnected 起算（B071）]({NEW_BUG_PATH.as_posix()}) - 计时起点从 accept() 返回 callStatus=3 改为 connected=true && callStatus=3，对齐 Web runtime 语义。"
    if bug_entry not in text:
        text = text.replace("## Bugs\n\n", "## Bugs\n\n" + bug_entry + "\n", 1)
    write_text(index_path, text.rstrip() + "\n")


def append_log(wiki_root: Path, raw_created: int, raw_unchanged: int) -> None:
    log_path = wiki_root / "log.md"
    text = read_text(log_path).rstrip()
    marker = "import | <workspace>/project/NECallKit docs B071 duration timer from onCallConnected"
    if marker in text:
        return
    entry = f"""

## [{TODAY}] import | <workspace>/project/NECallKit docs B071 duration timer from onCallConnected (2 files)
- Format: curated folder batch
- Created: 1 wiki page
- Updated: 0
- Raw: raw/imported/{BUNDLE_NAME}/ ({raw_created} created, {raw_unchanged} unchanged)
- Source group: B071 通话页计时器起点从 accept 改到 onCallConnected；ticker 启动加 connected gate；onCallConnected refresh 不归零
- Filed: [[electron-duration-timer-from-onconnect-2026-05-10]]
- Decision: ingest immediately because no existing wiki page covered Electron timer start semantics; previously only Web runtime had this convention. New page locks in the connected-gate rule.
"""
    write_text(log_path, text + entry)


def execute(wiki_root: Path, project_root: Path) -> dict[str, object]:
    raw_counts = {"created": 0, "unchanged": 0}
    for source in SOURCE_FILES:
        raw_counts[safe_copy_raw(project_root, wiki_root, source)] += 1
    bug_full = wiki_root / Path(NEW_BUG_PATH.as_posix())
    created_bug = not bug_full.exists()
    write_text(bug_full, bug_page())
    update_index(wiki_root, created_bug)
    append_log(wiki_root, raw_counts["created"], raw_counts["unchanged"])
    return {"raw_created": raw_counts["created"], "raw_unchanged": raw_counts["unchanged"], "created": [str(NEW_BUG_PATH)], "updated": []}


def main() -> int:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    project_root = Path(args.project).resolve()
    checkpoint_script = Path(args.checkpoint_script).resolve()
    validate_sources(project_root)
    plan = {"bundle": BUNDLE_NAME, "sources": [s.as_posix() for s in SOURCE_FILES], "new_pages": [NEW_BUG_PATH.as_posix()], "updates": 0}
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
