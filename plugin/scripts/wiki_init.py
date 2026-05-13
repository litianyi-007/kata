#!/usr/bin/env python3
"""Non-interactive wiki bootstrap.

The wiki-init skill in interactive mode walks the user through domain,
categories, dimensions, etc. For CI / scripted setup that's not viable —
this script handles the same end state from CLI flags only, no LLM.

Usage:
    wiki_init.py [--path <wiki_path>] [--domain "AI research"]
        [--categories entities,concepts,comparisons,queries]
        [--set-tags concept,reference,question]
        [--set-active-days 365] [--set-archived-days 730]
        [--set-driving-field published_at]
        [--set-dimension 'name:type:required:refresh_on1+refresh_on2']
        [--template market_research]
        [--force]
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import uuid
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "templates"

# PRD-v1.8-sync §10: per-machine state files that must NEVER be synced.
# Written into the wiki repo's .gitignore by wiki-init / --refresh-id.
PER_MACHINE_GITIGNORE_LINES = (
    "# Per-machine state — never sync across machines (PRD-v1.8-sync §10)",
    ".wiki-ingest-queue.json",
    ".wiki-import-checkpoint.json",
    ".wiki-import-lock",
    ".wiki-plugins.yaml",
    ".kata-stash-tag",
)

# PRD-v1.8-sync §8: bind log.md to custom merge driver. The binding is
# committed (so every clone gets it); the driver COMMAND is per-clone
# git config (handled by wiki-sync auto-register Option A). Written by
# wiki-init / --refresh-id even when --enable-sync isn't passed, so
# adopting sync later requires no additional setup.
#
# v1.8 MVP: only log.md driver shipped (review-1 MEDIUM-4). The
# `index.md merge=akwiki-index` line is intentionally NOT written —
# the matching merge_index.py script is v1.8-full per PRD §13. Without
# the driver registered, an orphan `merge=akwiki-index` binding makes
# git fall back to the default merge silently, which works but creates
# a misleading "I have a custom index driver" claim. Add the line in
# v1.8-full alongside merge_index.py.
GITATTRIBUTES_LINES = (
    "# kata custom merge drivers (PRD-v1.8-sync §8)",
    "log.md   merge=akwiki-log",
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--path", default=None,
                   help="Wiki root. If omitted, use kata path resolution.")
    p.add_argument("--domain", default="general")
    p.add_argument("--categories",
                   default="entities,concepts,comparisons,queries")
    p.add_argument("--set-tags",
                   default="concept,reference,question")
    p.add_argument("--set-active-days", type=int, default=365)
    p.add_argument("--set-archived-days", type=int, default=730)
    p.add_argument("--set-driving-field", default="published_at",
                   choices=["published_at", "ingested_at", "created", "updated"])
    p.add_argument("--set-dimension", action="append", default=[],
                   help="name:type:required:refresh_on (repeatable)")
    p.add_argument("--template", default=None,
                   choices=["market_research"],
                   help="Use a domain template instead of building from flags")
    p.add_argument("--enable-dreaming", action="store_true",
                   dest="enable_dreaming",
                   help="Write a default dreaming: block into SCHEMA.md and "
                        "print the recommended `claude /schedule` line. "
                        "Implied by templates that ship dreaming on.")
    p.add_argument("--enable-sync", action="store_true",
                   dest="enable_sync",
                   help="Write a default sync: block into SCHEMA.md and "
                        "wire wiki_id (UUID) so wiki-sync can do "
                        "cross-machine identity check. PRD-v1.8-sync §12.")
    p.add_argument("--refresh-id", action="store_true",
                   dest="refresh_id",
                   help="Generate a fresh wiki_id UUID for an existing wiki. "
                        "Use this when adopting v1.8 sync on a wiki created "
                        "before wiki_id was a field. Requires --force if "
                        "an existing wiki_id is present (overwriting drops "
                        "cross-machine identity, all peers must re-init).")
    p.add_argument("--force", action="store_true",
                   help="Overwrite if path exists and is non-empty, or "
                        "overwrite an existing wiki_id with --refresh-id")
    args = p.parse_args()

    # --refresh-id is a single-shot operation on an existing wiki: don't
    # rebuild SCHEMA.md / category dirs, just rewrite the wiki_id field.
    if args.refresh_id:
        return refresh_wiki_id(args)

    if args.path:
        path = Path(args.path).expanduser().resolve()
    else:
        from wiki_lib import find_wiki_root
        path = find_wiki_root()

    # Standard layout guard: wikis must live under ~/.llm-wiki/<project>/.
    # Initializing inside a source repo (or any arbitrary path) is the
    # most common AI-agent mistake — it mixes wiki history with the
    # source-project history, defeats multi-machine sync conventions,
    # and breaks the cross-project `~/.llm-wiki/{project}` layout that
    # registry.yaml and skill defaults rely on. Refuse unless --force.
    home_wiki_root = (Path.home() / ".llm-wiki").resolve()
    try:
        path.relative_to(home_wiki_root)
        inside_standard_layout = True
    except ValueError:
        inside_standard_layout = False
    if not inside_standard_layout and not args.force:
        print(
            f"FAIL: target path is outside the standard `~/.llm-wiki/<project>/` layout.\n"
            f"  Target:   {path}\n"
            f"  Standard: {home_wiki_root}/<project>/\n"
            f"\n"
            f"  Initializing here is rejected because:\n"
            f"    - it mixes wiki history with the source project's git history\n"
            f"    - multi-machine sync (v1.8) assumes ~/.llm-wiki/<project>\n"
            f"    - skill path resolution + registry.yaml + cross-wiki vault\n"
            f"      federation all assume the standard layout\n"
            f"\n"
            f"  Recommended: re-run with --path ~/.llm-wiki/<project-slug>\n"
            f"  Or if you truly need this path, add --force.",
            file=sys.stderr,
        )
        return 2

    if path.exists() and any(path.iterdir()) and not args.force:
        print(f"FAIL: {path} exists and is non-empty (use --force to overwrite)",
              file=sys.stderr)
        return 2

    path.mkdir(parents=True, exist_ok=True)

    # Template path: copy the template SCHEMA.md verbatim, then inject
    # wiki_id and (if --enable-sync) sync block. Templates predate v1.8
    # so they don't include these fields by default; review-1 HIGH-2.
    if args.template:
        template_dir = TEMPLATES_DIR / args.template
        src = template_dir / "SCHEMA.md"
        if not src.exists():
            print(f"FAIL: template {args.template!r} not found at {src}",
                  file=sys.stderr)
            return 2
        template_text = src.read_text(encoding="utf-8")
        # Inject wiki_id if missing (idempotent — template upgrade adds it
        # automatically once, future re-runs won't duplicate)
        if not re.search(r"^\s*wiki_id\s*:\s*[0-9a-f-]{36}",
                         template_text, re.MULTILINE):
            new_wiki_id = str(uuid.uuid4())
            identity_block = (
                f"\n## Identity\n\n"
                f"```yaml\n"
                f"wiki_id: {new_wiki_id}\n"
                f"```\n\n"
                f"> Auto-injected by `wiki_init.py --template {args.template}`. "
                f"Do not edit; coordinate with peer machines if regenerated.\n"
            )
            m = re.search(r"^# .+?\n(?:>.*?\n)*\n?", template_text,
                          re.MULTILINE)
            if m:
                template_text = (template_text[:m.end()] + identity_block
                                 + template_text[m.end():])
            else:
                template_text = identity_block + template_text
        # Inject sync block if --enable-sync and template doesn't have one
        if args.enable_sync and not re.search(r"^sync\s*:",
                                              template_text, re.MULTILINE):
            sync_yaml = (
                "\n## Multi-machine sync\n\n"
                "```yaml\n"
                "sync:\n"
                "  enabled: true\n"
                "  remote: origin\n"
                "  branch: main\n"
                "  on_conflict: report-and-exit\n"
                "  auto_chain_dream: false\n"
                "  auto_configure_drivers: true\n"
                "```\n\n"
                "> Auto-injected by `wiki_init.py --enable-sync`. "
                "See `docs/PRD-v1.8-sync.md`.\n"
            )
            template_text = template_text.rstrip() + "\n" + sync_yaml
        (path / "SCHEMA.md").write_text(template_text, encoding="utf-8")
        index_template = template_dir / "index.md"
        if index_template.exists() and not (path / "index.md").exists():
            (path / "index.md").write_text(
                index_template.read_text(encoding="utf-8"),
                encoding="utf-8")
        # Read categories from template SCHEMA so we create the right dirs
        from wiki_lib import load_schema
        schema = load_schema(path)
        cats = []
        for c in schema.get("categories") or []:
            if isinstance(c, dict) and c.get("name"):
                cats.append(c["name"])
        if not cats:
            cats = ["entities", "concepts", "comparisons", "queries"]
    else:
        cats = [c.strip() for c in args.categories.split(",") if c.strip()]
        tags = [t.strip() for t in args.set_tags.split(",") if t.strip()]
        dimensions = [_parse_dim(d) for d in args.set_dimension]
        # PRD-v1.8 §12: every fresh init gets a wiki_id UUID for cross-machine
        # identity check by wiki-sync. Templates already include wiki_id in
        # their SCHEMA.md; the non-template path generates one here.
        new_wiki_id = str(uuid.uuid4())
        (path / "SCHEMA.md").write_text(_render_schema(
            domain=args.domain,
            categories=cats,
            tags=tags,
            active_days=args.set_active_days,
            archived_days=args.set_archived_days,
            driving_field=args.set_driving_field,
            dimensions=dimensions,
            enable_dreaming=args.enable_dreaming,
            enable_sync=args.enable_sync,
            wiki_id=new_wiki_id,
        ), encoding="utf-8")

    # Per-machine .gitignore (PRD-v1.8 §10): always written, idempotent.
    # Don't depend on --enable-sync — these state files should never sync
    # regardless of whether the wiki has remote sync configured.
    _write_gitignore(path)
    # .gitattributes for merge driver bindings (PRD-v1.8 §8): also always
    # written so adopting sync later via --enable-sync needs no extra setup.
    _write_gitattributes(path)

    # Directory layout
    for cat in cats:
        (path / cat).mkdir(exist_ok=True)
    (path / "raw" / "articles").mkdir(parents=True, exist_ok=True)
    (path / "raw" / "papers").mkdir(parents=True, exist_ok=True)
    (path / "raw" / "transcripts").mkdir(parents=True, exist_ok=True)
    (path / "raw" / "external").mkdir(parents=True, exist_ok=True)
    (path / "raw" / "imported").mkdir(parents=True, exist_ok=True)
    (path / "raw" / "assets").mkdir(parents=True, exist_ok=True)
    (path / "_archive").mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()

    # index.md
    if not (path / "index.md").exists():
        idx_lines = [
            "# Wiki Index",
            "",
            f"> Content catalog. Last updated: {today} | Total pages: 0",
            "",
        ]
        for cat in cats:
            idx_lines.append(f"## {cat.capitalize()}")
            idx_lines.append("")
        (path / "index.md").write_text("\n".join(idx_lines) + "\n",
                                       encoding="utf-8")

    # log.md
    if not (path / "log.md").exists():
        log = (
            "# Wiki Log\n\n"
            "> Append-only chronological action log.\n"
            "> Format: ## [YYYY-MM-DD] action | subject\n\n"
            f"## [{today}] init | Wiki initialized non-interactively\n"
            f"- Domain: {args.domain}\n"
            f"- Path: {path}\n"
            f"- Categories: {', '.join(cats)}\n"
            f"- Mode: scripted (wiki_init.py --non-interactive)\n"
        )
        (path / "log.md").write_text(log, encoding="utf-8")

    # Detect whether the resulting SCHEMA.md actually has dreaming enabled
    # (true for any template that ships dreaming on, or when --enable-dreaming
    # was passed). If so, surface the recommended schedule line so users can
    # start their dogfood window without hunting through docs/.
    schema_text = (path / "SCHEMA.md").read_text(encoding="utf-8")
    dreaming_on = bool(
        re.search(r"dreaming:\s*\n[^`]*?enabled:\s*true",
                  schema_text, re.DOTALL)
    )

    print(f"ok: wiki initialized at {path}")
    print(f"    categories: {cats}")
    print(f"    SCHEMA.md, index.md, log.md created")
    if dreaming_on:
        print(f"    dreaming: enabled (weekly co-occurrence strategy)")
        print(f"    schedule weekly run with:")
        print(f"        claude /schedule \"0 23 * * 0\" \"/kata:wiki-dream\"")
        print(f"        # candidates land in dreaming/{{date}}.md for review")
    print(f"    next: drop a source in raw/articles/ and run /wiki-ingest")
    return 0


def _write_gitignore(wiki_root: Path) -> None:
    """Idempotently merge per-machine state lines into wiki repo's .gitignore.

    PRD-v1.8 §10. Don't blow away an existing .gitignore — append our block
    only if it's not already there. Lookup is line-exact so adding a new
    pattern in PER_MACHINE_GITIGNORE_LINES will be re-merged on next run.
    """
    gi_path = wiki_root / ".gitignore"
    existing = ""
    if gi_path.exists():
        existing = gi_path.read_text(encoding="utf-8")
    existing_lines = set(existing.splitlines())
    to_add = [ln for ln in PER_MACHINE_GITIGNORE_LINES
              if ln not in existing_lines]
    if not to_add:
        return  # already up to date
    sep = "" if not existing or existing.endswith("\n") else "\n"
    gi_path.write_text(existing + sep + "\n".join(to_add) + "\n",
                       encoding="utf-8")


def _write_gitattributes(wiki_root: Path) -> None:
    """Idempotently merge merge-driver bindings into wiki repo's
    .gitattributes. PRD-v1.8 §8. Same idempotence rule as _write_gitignore.
    """
    ga_path = wiki_root / ".gitattributes"
    existing = ""
    if ga_path.exists():
        existing = ga_path.read_text(encoding="utf-8")
    existing_lines = set(existing.splitlines())
    to_add = [ln for ln in GITATTRIBUTES_LINES
              if ln not in existing_lines]
    if not to_add:
        return
    sep = "" if not existing or existing.endswith("\n") else "\n"
    ga_path.write_text(existing + sep + "\n".join(to_add) + "\n",
                       encoding="utf-8")


def refresh_wiki_id(args) -> int:
    """Generate a fresh wiki_id UUID for an existing wiki and write it
    into the Identity yaml block at the top of SCHEMA.md.

    Modes:
    - SCHEMA.md has no wiki_id → insert Identity block after the doc header
    - SCHEMA.md has wiki_id → require --force (overwriting drops cross-
      machine identity; all peers must re-init or this becomes
      "different wiki" per §11.9)
    """
    if args.path:
        path = Path(args.path).expanduser().resolve()
    else:
        from wiki_lib import find_wiki_root
        path = find_wiki_root()
    schema_md = path / "SCHEMA.md"
    if not schema_md.exists():
        print(f"FAIL: {schema_md} not found — run `wiki_init.py` first to "
              f"create a wiki", file=sys.stderr)
        return 2

    text = schema_md.read_text(encoding="utf-8")
    # Look for an existing wiki_id field inside any yaml block.
    existing_match = re.search(
        r"(^\s*wiki_id\s*:\s*)([^\n#]+)", text, re.MULTILINE)
    new_id = str(uuid.uuid4())

    if existing_match:
        if not args.force:
            old_id = existing_match.group(2).strip().strip('"\'')
            print(f"FAIL: wiki_id already set ({old_id}). Overwriting drops "
                  f"cross-machine identity — all peer machines must re-init "
                  f"after this change. Pass --force to confirm.",
                  file=sys.stderr)
            return 3
        # Replace existing scalar value in place
        new_text = (text[:existing_match.start(2)] + new_id
                    + text[existing_match.end(2):])
    else:
        # Insert a new Identity block after the doc preamble (after first
        # blockquote that follows the H1, or right after H1 if no quote).
        identity_block = (
            f"\n## Identity\n\n"
            f"```yaml\n"
            f"wiki_id: {new_id}\n"
            f"```\n\n"
            f"> Generated by `wiki-init --refresh-id` for v1.8 sync. "
            f"Do not edit; coordinate with peer machines if regenerated.\n"
        )
        # Insert after the first H1 + (optional blockquote) section
        m = re.search(r"^# .+?\n(?:>.*?\n)*\n?", text, re.MULTILINE)
        if m:
            new_text = text[:m.end()] + identity_block + text[m.end():]
        else:
            new_text = identity_block + text

    schema_md.write_text(new_text, encoding="utf-8")
    # Also write the per-machine gitignore + .gitattributes — old wikis
    # upgrading to v1.8 need both even if they never re-run wiki-init.
    _write_gitignore(path)
    _write_gitattributes(path)
    # Append a log entry for auditability.
    log_md = path / "log.md"
    if log_md.exists():
        with log_md.open("a", encoding="utf-8") as f:
            f.write(f"\n## [{date.today().isoformat()}] init | "
                    f"wiki_id refreshed\n"
                    f"- New wiki_id: {new_id}\n"
                    f"- Reason: --refresh-id flag\n"
                    f"- Note: peer machines must re-init or sync will fail "
                    f"identity check\n")

    print(f"ok: wiki_id refreshed at {path}")
    print(f"    new wiki_id: {new_id}")
    if existing_match:
        print(f"    PEERS MUST RE-INIT: this overwrites a previous wiki_id, "
              f"existing peer machines will see identity-mismatch on next sync")
    print(f"    .gitignore updated with per-machine state patterns")
    return 0


def _parse_dim(spec: str) -> dict:
    """Parse 'name:type:required:refresh_on1+refresh_on2' into a dict."""
    parts = spec.split(":")
    if len(parts) < 3:
        raise SystemExit(
            f"--set-dimension {spec!r}: expected 'name:type:required[:refresh_on]'"
        )
    name, type_, required = parts[0], parts[1], parts[2]
    refresh_on = ["ingest"]
    if len(parts) >= 4:
        refresh_on = [r for r in parts[3].split("+") if r]
    return {
        "name": name, "type": type_,
        "required": required.lower() in ("true", "yes", "1", "required"),
        "refresh_on": refresh_on,
        "description": f"{name} for {type_} pages",
    }


def _render_schema(domain: str, categories: list[str], tags: list[str],
                   active_days: int, archived_days: int, driving_field: str,
                   dimensions: list[dict],
                   enable_dreaming: bool = False,
                   enable_sync: bool = False,
                   wiki_id: str | None = None) -> str:
    cat_block = "\n".join(f"  - name: {c}\n    purpose: \"{c} content\""
                           for c in categories)
    tag_block = "\n".join(f"  - {t}" for t in tags)
    if dimensions:
        # Block form so each dimension's required keys land on their own line.
        dim_lines = []
        for d in dimensions:
            dim_lines.append(f"  - name: {d['name']}")
            dim_lines.append(f"    type: {d['type']}")
            dim_lines.append(f"    description: \"{d['description']}\"")
            dim_lines.append(f"    required: {str(d['required']).lower()}")
            dim_lines.append(f"    refresh_on: [{', '.join(d['refresh_on'])}]")
        dim_section = "custom_dimensions:\n" + "\n".join(dim_lines)
    else:
        # Empty list MUST be inline — `custom_dimensions:\n  []` is ambiguous
        # to the indent-aware parser and resolves to an empty dict, which
        # then fails schema_validate (expects array, got dict).
        dim_section = "custom_dimensions: []"

    sync_section = ""
    if enable_sync:
        sync_section = """
## Multi-machine sync

```yaml
sync:
  enabled: true
  remote: origin
  branch: main
  on_conflict: report-and-exit
  auto_chain_dream: false
  auto_configure_drivers: true
```

> See `docs/PRD-v1.8-sync.md` for design.
> Run interactively: `wiki-sync`. From cron: `wiki-sync --auto`.
"""

    dreaming_section = ""
    if enable_dreaming:
        dreaming_section = """
## Auto-dreaming

```yaml
dreaming:
  enabled: true
  strategy: co-occurrence
  cadence: weekly
  max_repromote_per_run: 10
  confidence_threshold: 0.6
  weights:
    entity: 0.5
    tag: 0.2
    citation: 0.4
  resurgence:
    dormancy_window_days: 180
    min_count: 3
```

> Tune via `wiki-config --set dreaming.<key> <value>`.
> Run weekly via `claude /schedule "0 23 * * 0" "/kata:wiki-dream"`.
"""

    # PRD-v1.8 §12: wiki_id is the FIRST yaml block — sync identity check
    # parses it before any other config. It's a single-line scalar at top
    # level (not a block) so the simple parser picks it up without nesting.
    wiki_id_block = ""
    if wiki_id:
        wiki_id_block = f"""
## Identity

```yaml
wiki_id: {wiki_id}
```

> Stable UUIDv4 generated by wiki-init. wiki-sync uses this for
> cross-machine identity check (PRD-v1.8 §11.9). **Do not edit by hand**
> — overwriting drops cross-machine identity, all peers must re-init.
> Use `wiki-init --refresh-id` if you need to reset (and coordinate with
> all peer machines).
"""

    return f"""# SCHEMA — {domain} wiki

> Initialized via `wiki_init.py --non-interactive`. User-editable; co-evolves
> with the wiki. All kata skills read this file rather than hardcoding rules.
{wiki_id_block}
## Domain

{domain}

## Categories

```yaml
categories:
{cat_block}
```

## Frontmatter

```yaml
frontmatter_fields:
  - title
  - type
  - tags
  - created
  - updated
  - published_at
  - ingested_at
  - sources
```

## Tag taxonomy

```yaml
tag_taxonomy:
{tag_block}
```

## Memory tiers

```yaml
memory_tiers:
  enabled: true
  active_days: {active_days}
  archived_days: {archived_days}
  driving_field: {driving_field}
```

## Custom dimensions

```yaml
{dim_section}
```
{dreaming_section}{sync_section}
## Page creation policy

A page is created when its subject is central to a source OR mentioned in
2+ sources. Passing mentions don't get their own page.

## Cross-reference policy

Link wherever there's a genuine connection. No minimum count.

## Page size limit

No hard limit.

## Log rotation

No rotation.
"""


if __name__ == "__main__":
    sys.exit(main())
