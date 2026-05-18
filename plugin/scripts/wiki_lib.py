"""Shared library for kata deterministic algorithms.

Used by graph_query.py, tier_compute.py, schema_validate.py, etc.
Pure stdlib — no third-party deps required.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

WIKILINK_RE = re.compile(r"\[\[([^\[\]|#]+)(?:#[^\[\]|]+)?(?:\|[^\[\]]+)?\]\]")
EMBED_RE = re.compile(r"!\[\[[^\[\]]+\]\]")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class YamlParseError(ValueError):
    """Raised when our subset YAML parser hits syntax it can't handle.

    The parser deliberately avoids pyyaml to stay stdlib-only, but that
    means literal block scalars (|, >), anchors (&), and aliases (*)
    are unsupported. Before this exception existed the parser silently
    returned a string '|' or skipped the indented continuation lines,
    leading to surprising downstream errors (e.g. schema_validate
    reporting `missing description` when the description was a multi-line
    block scalar). Raising explicitly makes the failure mode actionable.
    """


@dataclass
class Page:
    path: str  # relative to wiki root, posix-separated
    title: str
    frontmatter: dict = field(default_factory=dict)
    body: str = ""
    out_links: list[str] = field(default_factory=list)  # raw link text
    in_links: list[str] = field(default_factory=list)  # populated by build_graph


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML-ish frontmatter without pulling pyyaml.

    Supports the subset of YAML that SCHEMA.md actually uses:
    - scalars: string, number, bool, null, ISO date
    - inline lists: [a, b, c]
    - block-style lists: leading "- "
    - quoted strings (single or double)
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    body = text[m.end():]
    return _parse_yaml_block(raw), body


def _parse_scalar(s: str):
    s = s.strip()
    if not s:
        return None
    # Catch unsupported YAML syntax loudly rather than misparse silently.
    # `|` / `>` are block scalar indicators; `&name` declares an anchor;
    # `*name` references an alias. Quoted strings (`"|"`, `"&foo"`) are fine
    # and handled below.
    if not (s.startswith('"') or s.startswith("'")):
        if s == "|" or s == ">" or s.startswith("|\n") or s.startswith(">\n"):
            raise YamlParseError(
                f"block scalar indicator {s[:1]!r} is not supported by "
                "the stdlib parser; quote the value or use inline form"
            )
        if s.startswith("&"):
            raise YamlParseError(
                f"YAML anchor {s.split()[0]!r} is not supported"
            )
        if s.startswith("*"):
            raise YamlParseError(
                f"YAML alias {s.split()[0]!r} is not supported"
            )
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    if s.lower() in ("true", "yes"):
        return True
    if s.lower() in ("false", "no"):
        return False
    if s.lower() in ("null", "none", "~"):
        return None
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(p) for p in _split_top(inner, ",")]
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        pass
    # ISO date
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return date.fromisoformat(s)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.*", s):
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    return s


def _split_top(s: str, sep: str) -> list[str]:
    """Split on sep at depth 0 (respect [], {}, quotes)."""
    out, buf, depth = [], [], 0
    quote = None
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf).strip())
    return out


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _parse_yaml_block(raw: str) -> dict:
    """Indent-aware YAML subset parser.

    Supports: nested mappings, block lists (incl. lists of dicts with their
    own nested lists/maps), inline lists [a, b], scalars, comments. Tab
    indentation is treated as one space (don't mix tabs and spaces).
    """
    lines = []
    for ln in raw.splitlines():
        # strip trailing inline comments (but not '#' inside quotes — heuristic)
        stripped = ln.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        lines.append(stripped)
    parsed, _ = _parse_block(lines, 0, 0)
    return parsed if isinstance(parsed, dict) else {}


def _parse_block(lines, start: int, indent: int):
    """Parse a block at the given indent level. Return (value, next_index)."""
    if start >= len(lines):
        return None, start
    first = lines[start]
    first_indent = _indent(first)
    if first_indent < indent:
        return None, start
    if first.lstrip().startswith("- "):
        return _parse_list(lines, start, first_indent)
    return _parse_map(lines, start, first_indent)


def _parse_map(lines, start: int, indent: int):
    result: dict = {}
    i = start
    while i < len(lines):
        line = lines[i]
        if _indent(line) < indent:
            break
        if _indent(line) > indent:
            i += 1
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line.lstrip())
        if not m:
            i += 1
            continue
        key, value = m.group(1), m.group(2).strip()
        if value:
            result[key] = _parse_scalar(value)
            i += 1
        else:
            # nested block
            j = i + 1
            # find next non-empty line at deeper indent
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and _indent(lines[j]) > indent:
                child_indent = _indent(lines[j])
                child, next_i = _parse_block(lines, j, child_indent)
                result[key] = child
                i = next_i
            else:
                result[key] = None
                i += 1
    return result, i


def _parse_list(lines, start: int, indent: int):
    items = []
    i = start
    while i < len(lines):
        line = lines[i]
        if _indent(line) < indent:
            break
        if _indent(line) > indent:
            i += 1
            continue
        stripped = line.lstrip()
        if not stripped.startswith("- "):
            break
        rest = stripped[2:].strip()
        # peek next line indent for nested content
        j = i + 1
        if not rest:
            # nested block under "- "
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and _indent(lines[j]) > indent:
                child, next_i = _parse_block(lines, j, _indent(lines[j]))
                items.append(child)
                i = next_i
                continue
            items.append(None)
            i += 1
            continue
        # rest is a value or "key: value"
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", rest)
        if m:
            # dict item — start it, then absorb lines indented past the "-" by 2
            key, value = m.group(1), m.group(2).strip()
            # the dict item's own field indent is indent + 2 (after "- ")
            item_indent = indent + 2
            cur = {key: _parse_scalar(value) if value else None}
            if not value:
                # nested block under this key
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines) and _indent(lines[j]) > item_indent:
                    child, j = _parse_block(lines, j, _indent(lines[j]))
                    cur[key] = child
            # now consume more "key: value" lines at item_indent
            i = j
            while i < len(lines):
                ln = lines[i]
                if _indent(ln) < item_indent:
                    break
                if _indent(ln) > item_indent:
                    i += 1
                    continue
                if ln.lstrip().startswith("- "):
                    break
                mm = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", ln.lstrip())
                if not mm:
                    i += 1
                    continue
                k2, v2 = mm.group(1), mm.group(2).strip()
                if v2:
                    cur[k2] = _parse_scalar(v2)
                    i += 1
                else:
                    j2 = i + 1
                    while j2 < len(lines) and not lines[j2].strip():
                        j2 += 1
                    if j2 < len(lines) and _indent(lines[j2]) > item_indent:
                        child, j2 = _parse_block(lines, j2, _indent(lines[j2]))
                        cur[k2] = child
                        i = j2
                    else:
                        cur[k2] = None
                        i += 1
            items.append(cur)
        else:
            items.append(_parse_scalar(rest))
            i += 1
    return items, i


def extract_links(body: str) -> list[str]:
    """Return wikilink targets in order, deduped, embeds excluded."""
    body_no_embed = EMBED_RE.sub("", body)
    seen, out = set(), []
    for m in WIKILINK_RE.finditer(body_no_embed):
        target = m.group(1).strip()
        if target and target not in seen:
            seen.add(target)
            out.append(target)
    return out


def discover_pages(wiki_root: Path) -> list[Page]:
    """Walk wiki_root, skip raw/, _archive/, hidden dirs. Return Pages.

    Per-page parse errors (malformed YAML frontmatter, unsupported scalar
    styles, etc.) are caught and logged to stderr but **do not abort the
    walk**. A single bad page must not poison a wiki-search / wiki-query /
    spec_preflight / MCP-server scan of the rest of the wiki. The skipped
    page is reported once in the form `[discover_pages] skipped <path>:
    <error>` so the user/agent can fix or quarantine it.
    """
    pages: list[Page] = []
    skip_dirs = {"raw", "_archive", "node_modules"}
    for root, dirs, files in os.walk(wiki_root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in skip_dirs]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            full = Path(root) / fname
            rel = full.relative_to(wiki_root).as_posix()
            try:
                text = full.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            try:
                fm, body = parse_frontmatter(text)
            except Exception as exc:  # noqa: BLE001 — tolerate any frontmatter
                # malformation; one bad page must not kill the whole scan.
                sys.stderr.write(
                    f"[discover_pages] skipped {rel}: "
                    f"{type(exc).__name__}: {exc}\n"
                )
                continue
            title = fm.get("title") or full.stem
            pages.append(Page(
                path=rel,
                title=str(title),
                frontmatter=fm,
                body=body,
                out_links=extract_links(body),
            ))
    return pages


def build_graph(pages: list[Page]) -> tuple[dict[str, Page], dict[str, list[str]]]:
    """Return (id_to_page, dangling_targets_by_source).

    Page id is the relative path. Links are resolved to ids by:
    1. Frontmatter title match
    2. Filename stem match (case-insensitive)
    """
    id_map: dict[str, Page] = {p.path: p for p in pages}
    title_to_id: dict[str, str] = {}
    stem_to_id: dict[str, str] = {}
    for p in pages:
        if p.title:
            title_to_id.setdefault(p.title.lower(), p.path)
        stem = Path(p.path).stem.lower()
        stem_to_id.setdefault(stem, p.path)

    dangling: dict[str, list[str]] = {}
    in_edges: dict[str, list[str]] = {p.path: [] for p in pages}
    for p in pages:
        resolved = []
        for target in p.out_links:
            t = target.lower()
            tid = title_to_id.get(t) or stem_to_id.get(t) or stem_to_id.get(Path(t).stem)
            if tid:
                resolved.append(tid)
                in_edges[tid].append(p.path)
            else:
                dangling.setdefault(p.path, []).append(target)
        p.out_links = resolved
    for p in pages:
        p.in_links = in_edges.get(p.path, [])
    return id_map, dangling


def load_schema(wiki_root: Path) -> dict:
    """Read SCHEMA.md and extract YAML config blocks (memory_tiers,
    custom_dimensions, etc.). Returns {} if missing.

    Parse errors per block (YamlParseError + anything else the subset
    parser can't handle) are collected into ``_parse_errors`` so callers
    can surface them instead of mistaking a missing block for a missing
    field. schema_validate reads this list.
    """
    schema_path = wiki_root / "SCHEMA.md"
    if not schema_path.exists():
        return {}
    text = schema_path.read_text(encoding="utf-8")
    config: dict = {}
    parse_errors: list[str] = []
    for i, block in enumerate(re.finditer(r"```ya?ml\s*\n(.*?)\n```",
                                          text, re.DOTALL)):
        try:
            parsed = _parse_yaml_block(block.group(1))
        except YamlParseError as e:
            parse_errors.append(f"SCHEMA.md yaml block #{i + 1}: {e}")
            continue
        except Exception as e:  # noqa: BLE001 — defensive: don't crash on
            # malformed blocks, but DO surface them so the user learns
            # something is wrong instead of losing config silently.
            parse_errors.append(
                f"SCHEMA.md yaml block #{i + 1}: parser bug or malformed "
                f"input ({type(e).__name__}: {e})"
            )
            continue
        for k, v in parsed.items():
            if k not in config or config[k] in (None, [], {}):
                config[k] = v
    if parse_errors:
        config["_parse_errors"] = parse_errors
    return config


def compute_tier(page: Page, schema: dict, today: date | None = None) -> str:
    """Return 'active' | 'archived' | 'frozen' for a page based on SCHEMA.md tiers."""
    tiers = schema.get("memory_tiers") or {}
    if isinstance(tiers, dict) and tiers.get("enabled") is False:
        return "active"
    override = page.frontmatter.get("tier_override")
    if override in ("active", "archived", "frozen"):
        return override
    today = today or date.today()
    active_days = int(tiers.get("active_days", 365)) if isinstance(tiers, dict) else 365
    archived_days = int(tiers.get("archived_days", 730)) if isinstance(tiers, dict) else 730
    field_name = tiers.get("driving_field") if isinstance(tiers, dict) else None
    field_name = field_name or "published_at"
    raw = page.frontmatter.get(field_name) or page.frontmatter.get("ingested_at")
    if isinstance(raw, str):
        try:
            raw = date.fromisoformat(raw[:10])
        except ValueError:
            return "active"
    if isinstance(raw, datetime):
        raw = raw.date()
    if not isinstance(raw, date):
        return "active"
    age = (today - raw).days
    if age <= active_days:
        return "active"
    if age <= archived_days:
        return "archived"
    return "frozen"


def shortest_path(id_map: dict[str, Page], src: str, dst: str) -> list[str] | None:
    """BFS over the undirected wikilink graph. Return list of ids, or None."""
    if src not in id_map or dst not in id_map:
        return None
    if src == dst:
        return [src]
    visited = {src}
    queue: list[tuple[str, list[str]]] = [(src, [src])]
    while queue:
        cur, path = queue.pop(0)
        page = id_map[cur]
        for neighbor in set(page.out_links) | set(page.in_links):
            if neighbor in visited:
                continue
            new_path = path + [neighbor]
            if neighbor == dst:
                return new_path
            visited.add(neighbor)
            queue.append((neighbor, new_path))
    return None


def neighbors(id_map: dict[str, Page], seed: str, depth: int) -> dict[int, list[str]]:
    """BFS layers from seed (undirected). Depth capped at 4."""
    depth = min(max(depth, 1), 4)
    if seed not in id_map:
        return {}
    layers: dict[int, list[str]] = {0: [seed]}
    visited = {seed}
    frontier = [seed]
    for d in range(1, depth + 1):
        next_frontier: list[str] = []
        for cur in frontier:
            page = id_map[cur]
            for n in set(page.out_links) | set(page.in_links):
                if n not in visited:
                    visited.add(n)
                    next_frontier.append(n)
        if not next_frontier:
            break
        layers[d] = next_frontier
        frontier = next_frontier
    return layers


def hub_score(page: Page) -> float:
    return len(page.in_links) + 0.5 * len(page.out_links)


def find_wiki_root(start: Path | str | None = None) -> Path:
    """Resolve the wiki root for global, multi-project installs.

    Priority:
    1. Explicit path argument (`--wiki` / `--path`)
    2. `WIKI_PATH`
    3. Nearest ancestor that already looks like a wiki root (`SCHEMA.md`)
    4. `LLM_WIKI_PROJECT` under `LLM_WIKI_HOME` (default `~/.llm-wiki`)
    5. Project binding file: `.llm-wiki.yaml` / `.kata.yaml`
    6. `~/.llm-wiki/registry.yaml`
    7. Git root name as `~/.llm-wiki/{git-root-name}`
    8. Legacy `~/.kata/config.yaml`
    9. `~/.llm-wiki/common`
    """
    if start:
        return _expand_path(start)

    env = os.environ.get("WIKI_PATH")
    if env:
        return _expand_path(env)

    cwd = Path.cwd().resolve()
    ancestor = _find_ancestor_wiki_root(cwd)
    if ancestor:
        return ancestor

    project = os.environ.get("LLM_WIKI_PROJECT")
    if project:
        return _project_wiki_path(project)

    binding = _read_nearest_project_binding(cwd)
    if binding:
        if binding.get("wiki_path") or binding.get("path"):
            return _expand_path(binding.get("wiki_path") or binding.get("path"),
                                base=binding.get("_base"))
        if binding.get("project"):
            return _project_wiki_path(binding["project"])

    registered = _read_registry_for_cwd(cwd)
    if registered:
        return registered

    git_root = _find_git_root(cwd)
    if git_root:
        return _project_wiki_path(git_root.name)

    legacy = _read_legacy_config()
    if legacy:
        return legacy

    return _wiki_home() / "common"


def _wiki_home() -> Path:
    raw = os.environ.get("LLM_WIKI_HOME") or "~/.llm-wiki"
    return _expand_path(raw)


def _expand_path(raw: Path | str, base: Path | str | None = None) -> Path:
    text = os.path.expandvars(str(raw).strip().strip('"\''))
    path = Path(text).expanduser()
    if not path.is_absolute() and base:
        path = Path(base).expanduser() / path
    return path.resolve()


def _project_wiki_path(project: str, must_exist: bool = False) -> Path:
    slug = _clean_project_slug(project)
    path = (_wiki_home() / slug).resolve()
    if must_exist and not path.exists():
        return (_wiki_home() / "common").resolve()
    return path


def _clean_project_slug(project: str) -> str:
    slug = project.strip().strip('"\'')
    slug = slug.replace("\\", "/").split("/")[-1]
    if not slug:
        return "common"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", slug).strip("-") or "common"


def _find_ancestor_wiki_root(start: Path) -> Path | None:
    for cur in (start, *start.parents):
        if (cur / "SCHEMA.md").exists() and (cur / "log.md").exists():
            return cur.resolve()
    return None


def _read_nearest_project_binding(start: Path) -> dict | None:
    for cur in (start, *start.parents):
        for name in (".llm-wiki.yaml", ".kata.yaml"):
            path = cur / name
            if path.exists():
                data = _read_simple_yaml(path)
                data["_base"] = cur
                return data
    return None


def _read_simple_yaml(path: Path) -> dict:
    data: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return data
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"\'')
        if key in {"project", "wiki_path", "path"} and value:
            data[key] = value
    return data


def _read_registry_for_cwd(cwd: Path) -> Path | None:
    registry = _wiki_home() / "registry.yaml"
    if not registry.exists():
        return None
    in_projects = False
    try:
        lines = registry.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        raw = line.rstrip()
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^projects\s*:\s*$", stripped):
            in_projects = True
            continue
        if in_projects and not raw.startswith((" ", "\t")):
            in_projects = False
        if not in_projects or ":" not in stripped:
            continue
        m = re.match(r"^(.+):\s+(.+)$", stripped)
        if not m:
            continue
        key, value = m.group(1).strip().strip('"\''), m.group(2)
        repo = _expand_path(key, base=registry.parent)
        if _is_relative_to(cwd, repo):
            target = value.strip().strip('"\'')
            if _looks_like_path(target):
                return _expand_path(target, base=registry.parent)
            return _project_wiki_path(target)
    return None


def _looks_like_path(value: str) -> bool:
    return (
        value.startswith(("~", ".", "/", "\\"))
        or bool(re.match(r"^[A-Za-z]:", value))
        or "/" in value
        or "\\" in value
    )


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _find_git_root(start: Path) -> Path | None:
    ceilings = {
        Path(p).expanduser().resolve()
        for p in os.environ.get("GIT_CEILING_DIRECTORIES", "").split(os.pathsep)
        if p
    }
    for cur in (start, *start.parents):
        if (cur / ".git").exists():
            return cur.resolve()
        if cur.resolve() in ceilings:
            break
    return None


def _read_legacy_config() -> Path | None:
    cfg = Path.home() / ".kata" / "config.yaml"
    if not cfg.exists():
        return None
    for line in cfg.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*(?:wiki\.)?path:\s*(.+)$", line)
        if m:
            return _expand_path(m.group(1))
    return None


def emit(payload: dict) -> None:
    """Print payload as JSON on stdout. The wrapper skill summarizes."""
    print(json.dumps(payload, default=str, ensure_ascii=False, indent=2))


def wiki_slug(root: Path) -> str:
    """Stable filesystem-safe slug for a wiki root (per-machine namespace).

    Used by wiki-watch for PID/log files and by wiki-sync for
    sync-{slug}.lock + sync-reports/{slug}/. Format: {leaf-name}-{sha1[:8]}
    where leaf is sanitized and the hash distinguishes different paths
    that happen to share a leaf name.
    """
    import hashlib
    abs_path = str(root.resolve())
    leaf = re.sub(r"[^A-Za-z0-9._-]+", "-", root.name).strip("-") or "wiki"
    digest = hashlib.sha1(abs_path.encode("utf-8")).hexdigest()[:8]
    return f"{leaf}-{digest}"


def is_pid_alive(pid: int) -> bool:
    """Cross-platform liveness check. Used by watcher PID lock and by
    wiki-import lock (PRD-v1.8 §10/§11). pid <= 0 is treated as dead.

    POSIX: os.kill(pid, 0) raises OSError if no such process; raises
    PermissionError if process exists but owned by another user.
    Windows: os.kill(pid, 0) maps to OpenProcess + checks handle.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True  # process exists, just owned by another user
    except OSError:
        return False


# ----- log parsing & dreaming support (v1.6) -----

LOG_HEADER_RE = re.compile(r"^##\s+\[(\d{4}-\d{2}-\d{2})\]\s+([a-z]+)\s+\|\s+(.*)$")
WATERMARK_RE = re.compile(r"^\s*-\s*Watermark:\s*(\S+)\s*$", re.MULTILINE)


@dataclass
class LogEntry:
    date: date
    action: str  # init, ingest, query, dream, lint, etc.
    subject: str
    body_lines: list[str] = field(default_factory=list)
    referenced_files: list[str] = field(default_factory=list)
    referenced_links: list[str] = field(default_factory=list)


def parse_log(log_md: Path) -> list[LogEntry]:
    """Parse log.md into structured entries.

    Karpathy format:
        ## [YYYY-MM-DD] action | subject
        - Files: foo.md, bar.md
        - Notes: ...

    The parser is liberal — anything not matching the header format is
    appended to the previous entry's body_lines.
    """
    if not log_md.exists():
        return []
    entries: list[LogEntry] = []
    cur: LogEntry | None = None
    for line in log_md.read_text(encoding="utf-8").splitlines():
        m = LOG_HEADER_RE.match(line)
        if m:
            if cur:
                _enrich_log_entry(cur)
                entries.append(cur)
            try:
                d = date.fromisoformat(m.group(1))
            except ValueError:
                d = date.today()
            cur = LogEntry(date=d, action=m.group(2),
                           subject=m.group(3).strip())
        elif cur is not None:
            cur.body_lines.append(line)
    if cur:
        _enrich_log_entry(cur)
        entries.append(cur)
    return entries


def _enrich_log_entry(entry: LogEntry) -> None:
    """Extract Files: and Linked to: references from a log entry's body."""
    file_re = re.compile(r"\b([a-zA-Z0-9_-]+/[a-zA-Z0-9_./-]+\.md)\b")
    for line in entry.body_lines:
        # Files: foo.md, bar.md, baz.md
        m = re.match(r"^\s*-\s*Files?:\s*(.*)$", line)
        if m:
            for f in re.split(r"[,\s]+", m.group(1)):
                if f.endswith(".md"):
                    entry.referenced_files.append(f)
            continue
        # Linked to: [[a]], [[b]]
        m = re.match(r"^\s*-\s*Linked to:\s*(.*)$", line)
        if m:
            entry.referenced_links.extend(extract_links(m.group(1)))
            continue
        # Created/Updated: foo.md, bar.md  — also relevant
        m = re.match(r"^\s*-\s*(?:Created|Updated|Promoted):\s*(.*)$", line)
        if m:
            for path in file_re.findall(m.group(1)):
                entry.referenced_files.append(path)
            entry.referenced_links.extend(extract_links(m.group(1)))


def read_watermark(log_md: Path, action: str = "dream") -> date | None:
    """Find the most recent log entry of `action` with a Watermark: line and
    return its date. None if no such entry."""
    entries = parse_log(log_md)
    for e in reversed(entries):
        if e.action != action:
            continue
        for line in e.body_lines:
            m = re.match(r"^\s*-\s*Watermark:\s*(\d{4}-\d{2}-\d{2})", line)
            if m:
                try:
                    return date.fromisoformat(m.group(1))
                except ValueError:
                    pass
    return None


@dataclass
class Increment:
    """The 'what changed since watermark' bag the dreamer scores against."""
    since: date
    fresh_pages: list[Page] = field(default_factory=list)  # new or updated
    entities: set[str] = field(default_factory=set)        # lowercase ids
    tags: dict[str, int] = field(default_factory=dict)     # tag -> count this period
    inbound_links: dict[str, set[str]] = field(default_factory=dict)
    # inbound_links: target_id -> set of source_ids that linked to it from fresh pages


def compute_increment(pages: list[Page], log_md: Path, since: date,
                      id_map: dict[str, Page] | None = None) -> Increment:
    """What changed in the wiki since `since`.

    Pages are 'fresh' if any of:
    - Their `ingested_at` >= since
    - Their `updated` >= since
    - They are mentioned (as Files: or Linked to:) in a log entry whose
      date >= since
    """
    inc = Increment(since=since)

    fresh_paths: set[str] = set()
    # By log entries
    for entry in parse_log(log_md):
        if entry.date < since:
            continue
        for f in entry.referenced_files:
            fresh_paths.add(f)

    # By page metadata
    for p in pages:
        ingested = _as_date(p.frontmatter.get("ingested_at"))
        updated = _as_date(p.frontmatter.get("updated"))
        if (ingested and ingested >= since) or (updated and updated >= since):
            fresh_paths.add(p.path)

    by_path = id_map or {p.path: p for p in pages}
    for path in fresh_paths:
        if path in by_path:
            inc.fresh_pages.append(by_path[path])

    # Aggregate signals from fresh pages
    for p in inc.fresh_pages:
        inc.entities.add(p.title.lower())
        inc.entities.add(Path(p.path).stem.lower())
        for link in p.out_links:
            inc.entities.add(link.lower())
            inc.inbound_links.setdefault(link, set()).add(p.path)
        tags = p.frontmatter.get("tags") or []
        if isinstance(tags, list):
            for t in tags:
                key = str(t).lower()
                inc.tags[key] = inc.tags.get(key, 0) + 1

    return inc


def detect_resurgence(pages: list[Page], increment: Increment,
                      dormancy_days: int = 180,
                      min_count: int = 3) -> set[str]:
    """A tag is 'resurgent' if it appears `min_count`+ times in the increment
    AND was absent from the prior `dormancy_days` window."""
    if not increment.fresh_pages:
        return set()
    today = increment.since
    dormancy_start = today.replace(day=1) - _td(days=dormancy_days)

    resurgent = set()
    for tag, count_in_increment in increment.tags.items():
        if count_in_increment < min_count:
            continue
        # Was the tag dormant before `since`?
        prior_count = 0
        for p in pages:
            tags = p.frontmatter.get("tags") or []
            if not (isinstance(tags, list) and any(str(t).lower() == tag for t in tags)):
                continue
            pub = _as_date(p.frontmatter.get("published_at")) or \
                  _as_date(p.frontmatter.get("ingested_at"))
            if pub and dormancy_start <= pub < today:
                prior_count += 1
        if prior_count == 0:
            resurgent.add(tag)
    return resurgent


def _as_date(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


def _td(days: int):
    from datetime import timedelta
    return timedelta(days=days)
