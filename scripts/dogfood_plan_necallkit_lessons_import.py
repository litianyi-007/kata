from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


BUNDLE_NAME = "necallkit-lessons"
PROJECT_RELATIVE_ROOT = PurePosixPath("docs/lessons")
KNOWN_CATEGORY_HEADINGS = {
    "platforms": "Platforms",
    "modules": "Modules",
    "features": "Features",
    "bugs": "Bugs",
    "decisions": "Decisions",
    "queries": "Queries",
    "lessons": "Lessons",
}

TAG_ALIASES = {
    "source-bridge": "bridge",
    "nim-control": "nim",
    "signalcontroller": "signaling",
    "signalController": "signaling",
    "await-guard": "async",
    "generation-counter": "async",
    "race-condition": "async",
    "switch-call-type": "callkit",
    "merge": "compatibility",
    "json.stringify": "logger",
    "JSON.stringify": "logger",
}

SEED_ID_PRIORITY = {
    # First dogfood import should prove cross-cutting preventive value, not
    # maximize lesson count. These IDs cover async, state-machine, lifecycle,
    # Electron bridge boundaries, and logger integration.
    "L008": 100,
    "L013": 95,
    "L005": 90,
    "L003": 85,
    "L012": 80,
    "L010": 75,
}
RECOMMENDED_SEED_LIMIT = 6


@dataclass(frozen=True)
class LessonPlan:
    source: str
    target: str
    lesson_id: str
    title: str
    source_category: str
    action: str
    normalized_tags: tuple[str, ...]
    proposed_tags: tuple[str, ...]
    related_lessons: tuple[str, ...]
    related_fixes: tuple[str, ...]
    summary: str
    admission_decision: str
    admission_score: int
    admission_reasons: tuple[str, ...]
    admission_missing: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run planner for importing NECallKit docs/lessons into the dogfood wiki."
    )
    parser.add_argument("--wiki", required=True, help="NECallKit wiki root")
    parser.add_argument("--project", required=True, help="NECallKit project root")
    parser.add_argument(
        "--seed-limit",
        type=int,
        default=RECOMMENDED_SEED_LIMIT,
        help=f"Maximum number of high-signal lessons to recommend for first import (default: {RECOMMENDED_SEED_LIMIT})",
    )
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Print only the recommended seed-set import plan instead of the full per-file dry run.",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_schema_categories(schema_text: str) -> set[str]:
    return set(re.findall(r"^\s+- name:\s*([a-zA-Z0-9_-]+)\s*$", schema_text, re.MULTILINE))


def parse_schema_tags(schema_text: str) -> set[str]:
    block_match = re.search(r"tag_taxonomy:\n(?P<body>(?:\s+- .+\n)+)", schema_text)
    if not block_match:
        return set()
    return {
        line.strip()[2:].strip()
        for line in block_match.group("body").splitlines()
        if line.strip().startswith("- ")
    }


def parse_frontmatter(content: str) -> dict[str, object]:
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    frontmatter = content[3:end].strip()
    data: dict[str, object] = {}
    for raw_line in frontmatter.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [item.strip().strip("\"'") for item in value[1:-1].split(",") if item.strip()]
            data[key] = items
        else:
            data[key] = value.strip("\"'")
    return data


def extract_title(content: str, metadata: dict[str, object], fallback: str) -> str:
    if isinstance(metadata.get("title"), str) and metadata["title"]:
        return str(metadata["title"])
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def slugify(value: str) -> str:
    slug = value.lower()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", slug)
    return re.sub(r"-{2,}", "-", slug).strip("-")


def first_meaningful_line(content: str, title: str) -> str:
    body = content
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            body = content[end + 4 :]
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("|") or stripped.startswith("```"):
            continue
        cleaned = re.sub(r"[*_>`]+", "", stripped)
        return cleaned[:120]
    return title


def has_section(content: str, name: str) -> bool:
    return bool(re.search(rf"^##\s+{re.escape(name)}\s*$", content, re.MULTILINE))


def score_admission(
    content: str,
    metadata: dict[str, object],
    related_lessons: tuple[str, ...],
    related_fixes: tuple[str, ...],
    inbound_related_count: int,
) -> tuple[str, int, tuple[str, ...], tuple[str, ...]]:
    """Score whether a source deserves durable lesson status.

    The goal is to keep lessons scarce: a lesson must change future review or
    implementation behavior, not merely document that a bug happened.
    """
    text = content.lower()
    severity = str(metadata.get("severity") or "").lower()
    reasons: list[str] = []
    missing: list[str] = []
    score = 0

    has_root_cause = has_section(content, "根因") or "root cause" in text
    if has_root_cause:
        score += 2
        reasons.append("root-cause analysis")
    else:
        missing.append("explicit root cause")

    has_prevention = (
        has_section(content, "预防策略")
        or "code review" in text
        or "代码审查" in content
        or "检查项" in content
    )
    if has_prevention:
        score += 2
        reasons.append("future prevention checklist")
    else:
        missing.append("future prevention checklist")

    has_scope = has_section(content, "影响范围") or "平台" in content or "module" in metadata
    if has_scope:
        score += 1
        reasons.append("impact scope")
    else:
        missing.append("impact scope")

    transferable = bool(
        re.search(
            r"凡|适用场景|通用模式|同类|再次|回归|不要只|边界|guard|pattern|"
            r"code review|代码审查|检查清单",
            content,
            re.IGNORECASE,
        )
        or related_lessons
    )
    if transferable:
        score += 2
        reasons.append("transferable future trigger")
    else:
        missing.append("transferable future trigger")

    if severity == "high":
        score += 2
        reasons.append("high severity")
    elif severity == "medium":
        score += 1
        reasons.append("medium severity")

    if related_fixes:
        score += 1
        reasons.append("linked fix evidence")
    else:
        missing.append("linked fix evidence")

    recurring_or_linked = bool(related_lessons or inbound_related_count)
    if recurring_or_linked:
        score += 1
        reasons.append("linked or recurring lesson")

    category = str(metadata.get("category") or "")
    broad_boundary = bool(
        re.search(
            r"跨|多端|多平台|三层|边界|bridge|runtime|desktop core|source bridge|"
            r"state-machine|状态机|lifecycle|生命周期|async|await|logger|eventemitter|"
            r"setinterval|resource|资源|camera|摄像头",
            content,
            re.IGNORECASE,
        )
    )
    if broad_boundary:
        score += 1
        reasons.append("cross-boundary or cross-platform impact")

    durable_pattern = bool(
        category == "patterns"
        or re.search(
            r"通用模式|适用场景|pattern|凡|不要只|代码审查卡点|code review|review checkpoint|检查清单",
            content,
            re.IGNORECASE,
        )
    )
    if durable_pattern:
        score += 1
        reasons.append("durable review pattern")

    one_off_risk = category in {"config-issues", "platform-issues"} and not (
        severity == "high" or recurring_or_linked or durable_pattern
    )
    if one_off_risk:
        missing.append("not obviously durable beyond a one-off environment/platform finding")

    runbook_like = category == "config-issues" and not (severity == "high" or recurring_or_linked)
    if runbook_like:
        missing.append("looks like runbook/workflow guidance rather than scarce lesson memory")

    hard_gate_passed = has_root_cause and has_prevention and transferable
    lesson_worthy = severity == "high" or recurring_or_linked or broad_boundary or durable_pattern
    if not hard_gate_passed:
        decision = "reject"
    elif not lesson_worthy or one_off_risk or runbook_like:
        decision = "defer"
    elif score >= 9:
        decision = "admit"
    elif score >= 7:
        decision = "defer"
    else:
        decision = "reject"

    return decision, score, tuple(reasons), tuple(missing)


def seed_priority(plan: LessonPlan) -> int:
    if plan.admission_decision != "admit":
        return -1
    score = SEED_ID_PRIORITY.get(plan.lesson_id, 0)
    topic_tags = set(plan.normalized_tags) | set(plan.proposed_tags)
    for tag in ("async", "state-machine", "lifecycle", "logger", "camera"):
        if tag in topic_tags:
            score += 2
    if "electron" in topic_tags or "desktop" in topic_tags:
        score += 4
    if plan.related_lessons:
        score += 3
    if plan.related_fixes:
        score += 1
    if plan.source_category == "patterns":
        score += 4
    return score


def normalize_tags(raw_tags: list[str], content: str, allowed_tags: set[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    candidates: list[str] = ["callkit", "testing"]
    text = content.lower()
    for platform_tag in (
        "android",
        "ios",
        "flutter",
        "electron",
        "desktop",
        "web",
        "miniprogram",
        "harmonyos",
        "uniapp",
        "nim",
        "rtc",
        "signaling",
        "bridge",
        "regression",
        "compatibility",
    ):
        if platform_tag in text:
            candidates.append(platform_tag)

    proposed: list[str] = []
    for raw_tag in raw_tags:
        alias = TAG_ALIASES.get(raw_tag, raw_tag)
        alias_lower = alias.lower()
        if alias_lower in allowed_tags:
            candidates.append(alias_lower)
        elif alias_lower in {"async", "state-machine", "lifecycle", "logger", "camera", "performance"}:
            proposed.append(alias_lower)
        elif alias_lower in {"circular-reference"}:
            proposed.append("logger")
        elif alias_lower in {"race-condition", "await-guard", "generation-counter"}:
            proposed.append("async")
        elif alias_lower in {"source-bridge"}:
            candidates.append("bridge")

    if "状态" in content or "state" in text or "callstatus" in text:
        proposed.append("state-machine")
    if "生命周期" in content or "lifecycle" in text or "后台" in content:
        proposed.append("lifecycle")
    if "logger" in text or "日志" in content:
        proposed.append("logger")
    if "摄像头" in content or "camera" in text:
        proposed.append("camera")
    if "资源" in content or "性能" in content or "leak" in text:
        proposed.append("performance")

    normalized_unique = tuple(dict.fromkeys(tag for tag in candidates if tag in allowed_tags))
    proposed_unique = tuple(sorted(set(tag for tag in proposed if tag not in allowed_tags)))
    return normalized_unique, proposed_unique


def as_list(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    if isinstance(value, str) and value:
        return tuple(item.strip() for item in value.split(",") if item.strip())
    return ()


def build_plan(project_root: Path, wiki_root: Path, seed_limit: int = RECOMMENDED_SEED_LIMIT) -> dict[str, object]:
    schema_text = read_text(wiki_root / "SCHEMA.md")
    existing_categories = parse_schema_categories(schema_text)
    allowed_tags = parse_schema_tags(schema_text)
    lesson_root = project_root / Path(PROJECT_RELATIVE_ROOT.as_posix())
    lesson_files = sorted(lesson_root.rglob("*.md"))
    plans: list[LessonPlan] = []
    all_proposed_tags: set[str] = set()
    source_category_counts: dict[str, int] = {}
    inbound_lesson_refs: dict[str, int] = {}
    file_records: list[tuple[Path, PurePosixPath, str, dict[str, object], str, str, list[str]]] = []

    for path in lesson_files:
        relative = PurePosixPath(path.relative_to(project_root).as_posix())
        content = read_text(path)
        metadata = parse_frontmatter(content)
        title = extract_title(content, metadata, path.stem)
        lesson_id = str(metadata.get("id") or re.match(r"(L\d+)", path.stem, re.IGNORECASE).group(1))
        for ref in as_list(metadata.get("related_lesson")):
            inbound_lesson_refs[ref] = inbound_lesson_refs.get(ref, 0) + 1
        source_category = str(metadata.get("category") or relative.parts[-2])
        raw_tags = [str(tag) for tag in as_list(metadata.get("tags"))]
        file_records.append((path, relative, content, metadata, title, lesson_id, raw_tags))

    for _path, relative, content, metadata, title, lesson_id, raw_tags in file_records:
        source_category = str(metadata.get("category") or relative.parts[-2])
        normalized_tags, proposed_tags = normalize_tags(raw_tags, content, allowed_tags)
        related_lessons = as_list(metadata.get("related_lesson"))
        related_fixes = as_list(metadata.get("related_fix") or metadata.get("related_features"))
        admission_decision, admission_score, admission_reasons, admission_missing = score_admission(
            content,
            metadata,
            related_lessons,
            related_fixes,
            inbound_lesson_refs.get(lesson_id, 0),
        )
        all_proposed_tags.update(proposed_tags)
        source_category_counts[source_category] = source_category_counts.get(source_category, 0) + 1

        target = PurePosixPath("lessons") / f"{lesson_id.lower()}-{slugify(title)}.md"
        target_path = wiki_root / Path(target.as_posix())
        plans.append(
            LessonPlan(
                source=relative.as_posix(),
                target=target.as_posix(),
                lesson_id=lesson_id,
                title=title,
                source_category=source_category,
                action="update" if target_path.exists() else "create",
                normalized_tags=normalized_tags,
                proposed_tags=proposed_tags,
                related_lessons=related_lessons,
                related_fixes=related_fixes,
                summary=first_meaningful_line(content, title),
                admission_decision=admission_decision,
                admission_score=admission_score,
                admission_reasons=admission_reasons,
                admission_missing=admission_missing,
            )
        )

    target_counts: dict[str, int] = {}
    admission_counts: dict[str, int] = {}
    for plan in plans:
        target_counts[plan.action] = target_counts.get(plan.action, 0) + 1
        admission_counts[plan.admission_decision] = admission_counts.get(plan.admission_decision, 0) + 1
    recommended_seed = sorted(
        (plan for plan in plans if plan.admission_decision == "admit"),
        key=lambda plan: (-seed_priority(plan), plan.lesson_id),
    )[:seed_limit]

    return {
        "bundle": BUNDLE_NAME,
        "mode": "dry-run",
        "source_root": PROJECT_RELATIVE_ROOT.as_posix(),
        "total_files": len(plans),
        "target_category": "lessons",
        "schema_changes_required": {
            "add_category_lessons": "lessons" not in existing_categories,
            "proposed_category": {
                "name": "lessons",
                "purpose": "Lessons learned, prevention strategies, and reusable debugging/review patterns.",
            },
            "proposed_tags": sorted(all_proposed_tags),
        },
        "summary": {
            "actions": target_counts,
            "admission": dict(sorted(admission_counts.items())),
            "source_categories": dict(sorted(source_category_counts.items())),
            "would_update_files_minimum": admission_counts.get("admit", 0) + 3,
            "mass_update_confirmation_required": admission_counts.get("admit", 0) + 3 >= 10,
        },
        "admission_policy": {
            "hard_gate": [
                "explicit root cause",
                "future prevention checklist",
                "transferable future trigger",
            ],
            "lesson_worthiness_gate": [
                "high severity, or",
                "linked/recurring lesson evidence, or",
                "cross-boundary or cross-platform impact, or",
                "durable review pattern that changes future code review behavior",
            ],
            "score_thresholds": {
                "admit": ">= 9, hard gate passed, and lesson-worthiness gate passed",
                "defer": "7-8 or one-off risk; keep raw or merge into an existing page until it recurs",
                "reject": "< 7 or hard gate failed; do not create a lesson page",
            },
            "principle": "Lessons are scarce operating knowledge: they must change future behavior, not merely record that a small bug happened.",
        },
        "cross_links": {
            "recommended_backlinks_from": [
                "decisions/necallkit-agent-sdd-operating-contract.md",
                "modules/necallkit-docs-index.md",
                "queries/necallkit-electron-web-reuse-operating-boundary-query.md",
            ],
            "recommended_followup_query": "下一个 Electron/Web bugfix 开始前，agent 应该先检查哪些历史 lessons？",
        },
        "recommended_seed_set": {
            "limit": seed_limit,
            "principle": "First import should prove preventive value with a small high-signal seed set, not maximize lesson count.",
            "ids": [plan.lesson_id for plan in recommended_seed],
            "sources": [plan.source for plan in recommended_seed],
            "would_update_files_minimum": len(recommended_seed) + 3,
            "mass_update_confirmation_required": len(recommended_seed) + 3 >= 10,
        },
        "plan": [
            {
                "source": plan.source,
                "target": plan.target,
                "id": plan.lesson_id,
                "title": plan.title,
                "source_category": plan.source_category,
                "action": plan.action,
                "tags": list(plan.normalized_tags),
                "proposed_tags": list(plan.proposed_tags),
                "related_lessons": list(plan.related_lessons),
                "related_fixes": list(plan.related_fixes),
                "summary": plan.summary,
                "admission": {
                    "decision": plan.admission_decision,
                    "score": plan.admission_score,
                    "reasons": list(plan.admission_reasons),
                    "missing": list(plan.admission_missing),
                },
            }
            for plan in plans
        ],
    }


def main() -> None:
    args = parse_args()
    wiki_root = Path(args.wiki).resolve()
    project_root = Path(args.project).resolve()
    plan = build_plan(project_root, wiki_root, max(args.seed_limit, 0))
    if args.seed_only:
        plan = {
            "bundle": plan["bundle"],
            "mode": plan["mode"],
            "source_root": plan["source_root"],
            "schema_changes_required": plan["schema_changes_required"],
            "recommended_seed_set": plan["recommended_seed_set"],
            "admission_policy": plan["admission_policy"],
        }
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
