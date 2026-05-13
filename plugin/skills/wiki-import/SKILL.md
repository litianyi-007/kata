---
name: wiki-import
description: "Import an existing document system (folder tree, Obsidian vault, Notion/Confluence export, etc.) into the wiki. Scans source structure, maps to wiki types, deduplicates against existing content, prompts once per batch for any custom frontmatter dimensions declared in SCHEMA.md, and processes in priority order with checkpoint support."
user-invocable: true
argument-hint: "<source-path> [--format=folder|obsidian|notion|confluence|markdown] [--map=<mapping-file>] [--dry-run] [--resume] [--priority=recency|links|manual] [--set=key=value,...] [--per-file-prompt]"
---

# wiki-import

Bulk-import an existing document system into the wiki. Unlike `wiki-ingest` (which
handles one source at a time), `wiki-import` scans an entire directory tree, infers
structure, deduplicates against existing content, and processes files in waves with
checkpoint support for large imports.

## When to use

- User has an existing folder of notes, an Obsidian vault, a Notion export, a
  Confluence export, or any collection of markdown/text files
- User says "import my existing docs", "migrate my notes", "bring in my whole vault"
- Bootstrapping a wiki from an existing knowledge store

## Implementation

Checkpoint persistence + import-lock IO — the parts that absolutely must
not depend on agent self-discipline — live in
`plugin/scripts/import_checkpoint.py`. **The script is the source of
truth; the prose below explains its behavior.** The skill still does the
LLM-heavy work (mapping inference, dedup judgment, page writing); the
script owns durable state so a crash mid-import is recoverable AND
wiki-sync can detect "import in progress" before reading a half-imported
working tree.

```bash
# Phase 1 — also acquire import lock (PRD-v1.8 §10/§11.8)
python {plugin_root}/scripts/import_checkpoint.py --wiki {wiki_path} \
    lock --source /path/to/notes --format obsidian
python {plugin_root}/scripts/import_checkpoint.py --wiki {wiki_path} \
    init --source /path/to/notes --format obsidian --total 342

# Update progress after each wave of 20 files
python {plugin_root}/scripts/import_checkpoint.py --wiki {wiki_path} \
    update --processed 40 --last-file concepts/transformers.md

# Record skips and errors
python {plugin_root}/scripts/import_checkpoint.py --wiki {wiki_path} \
    skip --file foo.md --reason "duplicate"
python {plugin_root}/scripts/import_checkpoint.py --wiki {wiki_path} \
    error --file bad.md --message "could not parse frontmatter"

# Read on resume
python {plugin_root}/scripts/import_checkpoint.py --wiki {wiki_path} read

# Phase 5 success: clear checkpoint AFTER `git commit` succeeds (NOT after
# push — see "Phase 5: single commit + cleanup" below). Always unlock.
python {plugin_root}/scripts/import_checkpoint.py --wiki {wiki_path} clear
python {plugin_root}/scripts/import_checkpoint.py --wiki {wiki_path} unlock

# Phase failure: keep checkpoint (allows --resume), unlock anyway
python {plugin_root}/scripts/import_checkpoint.py --wiki {wiki_path} unlock
```

The state lives at:
- `{wiki_path}/.wiki-import-checkpoint.json` — durable progress
- `{wiki_path}/.wiki-import-lock` — per-machine in-progress signal

Both are gitignored by `wiki-init`. The script emits JSON on each call so
the skill can reason about state without re-reading files.

`{plugin_root}` resolves to the directory containing `.claude-plugin/`.

## Pre-flight

① Resolve wiki path (standard path resolution from CLAUDE.md)
② If wiki does not exist yet at the path, run `wiki-init` first — ask the user for
   the domain or infer it from the source documents
③ Read orientation files (SCHEMA.md, index.md, log.md) if wiki already exists
④ **Dirty-tree policy (PRD-v1.8 §13)**: refuse to start a fresh import
   when wiki working tree has uncommitted changes (`git status --porcelain`
   shows entries). Tell the user to `git commit` or `git stash` first.
   Reason: import writes ~10–15 pages per source; mixing those into an
   already-dirty tree makes review and rollback messy. Exception:
   `--resume` allows existing checkpoint state in the tree.
⑤ **Acquire lock**: call `import_checkpoint.py lock --source ...
   --format ...`. If a fresh lock exists (another import in progress),
   exit with friendly error. If a stale lock (>24h) exists, the script
   warns and overwrites — log it for the user. After this, wiki-sync's
   preflight will see the lock and refuse to operate until phase 5
   completes (or the user manually unlocks).

---

## Steps

### Phase 1 — Discovery

① **Scan source directory:**
   Walk the source tree and build a manifest of all files:
   ```
   for each file in source-path (recursive):
       record: path, size, extension, modified-date, frontmatter (if any)
   ```
   Supported extensions: `.md`, `.txt`, `.html`, `.pdf` (text-extracted)
   Skip: binary files, hidden directories (`.git/`, `.obsidian/`), `node_modules/`

② **Infer source format** (if not specified via `--format`):
   - **Obsidian**: presence of `.obsidian/` config folder → use `[[wikilinks]]` and
     YAML frontmatter as-is
   - **Notion**: HTML or markdown with Notion-style UUIDs in filenames → strip UUIDs,
     map Notion databases to entity/concept types
   - **Confluence**: HTML export with `confluence-page.xml` or `site/` structure
   - **Plain folder**: generic markdown/text files with directory hierarchy as implicit
     category

③ **Analyze source structure:**
   - Map top-level directories to wiki types (see Mapping section below)
   - Extract all existing tags/categories across all files
   - Identify files that already have YAML frontmatter (migrate metadata directly)
   - Count files per directory to prioritize high-density clusters first

### Phase 2 — Mapping

④ **Map source categories to wiki types:**

   Default mapping (override with `--map=<yaml-file>`):
   ```yaml
   # Default directory-to-type mapping
   # Override: --map=my-mapping.yaml
   
   # Folder name patterns → wiki type
   people|person|team|org|company|product|model: entity
   concept|idea|topic|theory|technique|method: concept
   compare|comparison|vs|analysis|review: comparison
   note|notes|inbox|capture|scratch: concept  # treat as concept, review later
   
   # Fallback: any folder with mostly short files (<50 lines avg) → entity
   # Fallback: any folder with mostly long files (>100 lines avg) → concept
   ```

   For each source file, determine:
   - Target wiki type (entity/concept/comparison/query)
   - Target wiki subdirectory (entities/, concepts/, etc.)
   - Derived wiki filename (lowercase-hyphens.md, strip UUIDs and special chars)

⑤ **Show mapping preview** — print a summary and ask for confirmation before
   processing (unless `--dry-run` is used, which prints the full plan and exits):
   ```
   Import plan: 342 files from ~/notes
   
   entities/    →  87 files  (from: people/, models/, tools/)
   concepts/    → 193 files  (from: topics/, ideas/, inbox/)
   comparisons/ →  12 files  (from: comparisons/, vs/)
   queries/     →  50 files  (from: journal/, questions/)
   SKIP         →  47 files  (binary, too small <3 lines, or duplicates)
   
   Proceed? [y/n/edit-mapping]
   ```

### Phase 2b — Custom dimensions (batch-level prompt)

Read SCHEMA.md's `custom_dimensions:` block. For each dimension where
`refresh_on` includes `import`:

1. If `--set name=value` was passed, use it without prompting
2. Otherwise, ask **once for the whole batch**:
   > "Custom dimension `{name}` applies to imported pages. {description}
   > Use one value for all {total_files} files, or skip and set per-file?"
   - Accept a single value → applies to every page in the batch
   - Accept "skip" → dimension omitted (fails if `required: true`)
   - Accept "per-file" → fall back to per-file prompting (same as `--per-file-prompt`)
3. Required dimensions without a value block the import and emit a clear error

**Rationale**: prompting per file during a 300-file import is a UX disaster. The
common case is that an import represents _one_ version of _one_ source system, so
one answer per batch is usually correct. `--per-file-prompt` is available as an
escape hatch for mixed-batch imports.

**Source dates** during import:
- `published_at` — if the source file's frontmatter already has a date field
  (Obsidian `date:`, Notion `Created time`, etc.) use it. Otherwise fall back to
  the file's mtime from Phase 1 discovery.
- `ingested_at` — set to today for every imported page

### Phase 3 — Deduplication

⑥ **Check against existing wiki content** (if wiki is non-empty):

   For each source file, check for existing wiki pages that cover the same topic:
   - Exact title match → merge (append new information, update `updated` date)
   - High title similarity (>80%) → flag for user review before merging
   - Keyword overlap with existing page content → link, don't duplicate

   Deduplication is skipped for `raw/` (source files are always saved to `raw/`
   regardless — dedup applies only to the wiki page layer).

### Phase 4 — Processing (wave-based)

⑦ **Process in priority order:**

   **Priority: recency** (default) — process files modified most recently first.
   Most recently updated files are likely most relevant.

   **Priority: links** — process most-linked files first (Obsidian backlinks, or
   files referenced by other files). Hub documents become wiki anchors.

   **Priority: manual** — user provides an ordered list or processes interactively.

⑧ **Save raw files:**
   Copy all source files to `raw/imported/{source-dirname}/` preserving relative paths.
   These are immutable originals — never modified after import.

⑨ **Create wiki pages in waves of 20:**
   For each file in priority order:
   - Extract title (frontmatter > H1 heading > filename)
   - Preserve existing frontmatter fields; add missing required fields
   - Map existing tags to SCHEMA.md taxonomy (see Tag Normalization below)
   - Write a summary section at the top (for files > 100 lines, summarize in 3–5 bullets)
   - Convert source links (Obsidian `[[links]]` → validate; Notion UUIDs → resolve)
   - Save to target wiki directory

   Every 20 files: write checkpoint to `.wiki-import-checkpoint.json` (see Resume below)

⑩ **Tag normalization:**
   Collect all source tags. For each source tag not in SCHEMA.md taxonomy:
   - Try fuzzy match to existing taxonomy tag (e.g., "llm" → "language-model")
   - If no match: propose adding to SCHEMA.md taxonomy or grouping under existing tag
   - Ask once per batch of unmapped tags (not once per file)

### Phase 5 — Navigation update + single commit + cleanup

⑪ **Update index.md** — add all new pages in one pass (not incrementally per file).
   Group by type, sort alphabetically within each section.

⑫ **Update SCHEMA.md** — if new tags were approved during tag normalization, add
   them to the taxonomy section.

⑬ **Write log entry:**
   ```
   ## [YYYY-MM-DD] import | {source-path} ({N} files)
   - Format: {format}
   - Created: {N} wiki pages
   - Skipped: {N} files (duplicates: M, too small: K)
   - Updated: {N} existing pages (merged)
   - Raw: raw/imported/{dirname}/
   - Tag additions to SCHEMA.md: {list or none}
   ```

⑭ **Single commit + push (PRD-v1.8 §13 / H3)**: stage + commit + push
   the **entire** import as ONE atomic commit, not wave-by-wave. This
   prevents wiki-sync on another machine from pulling a half-imported
   tree (the import-lock prevents same-machine concurrent sync, but
   not cross-machine peer pulling A's mid-import push).

   ```bash
   cd {wiki_path}
   git add .
   git commit -m "wiki-import: {source-name} ({N} pages)"
   git push  # may fail if remote diverged or unreachable; that's OK
   ```

⑮ **Phase 5 success cleanup (round-5 fix M6)**:
   - **`git commit` 成功就 delete checkpoint**, regardless of `git push`
     outcome:
     ```bash
     python {plugin_root}/scripts/import_checkpoint.py \
         --wiki {wiki_path} clear
     python {plugin_root}/scripts/import_checkpoint.py \
         --wiki {wiki_path} unlock
     ```
   - If `git push` failed (network down / remote rejected), surface a
     clear message:
     > "Import committed (sha: {abbrev}). Push failed: {reason}.
     > To push later, run `wiki-sync` or `git push` manually.
     > Checkpoint cleared — wiki-sync preflight will not be blocked."

   The reasoning: after commit, the wiki repo is in a logically-complete
   state. Push failure is a *sync* problem, not an *import* problem.
   wiki-sync's normal "local-ahead-only" path handles the unpushed
   commit on next run. Keeping the checkpoint here would persistently
   block wiki-sync via §6.3.6 preflight (round-5 catch).

⑯ **Phase failure cleanup**: any phase 1-4 exception (parse failure,
   IO error, user Ctrl-C in the LLM session) → checkpoint **kept** for
   `--resume`, lock **unlocked** to free the next attempt:
   ```bash
   python {plugin_root}/scripts/import_checkpoint.py \
       --wiki {wiki_path} unlock
   # Do NOT call clear here.
   ```

---

## Resume support (`--resume`)

If a previous import was interrupted, resume from the checkpoint:
```json
// .wiki-import-checkpoint.json (in wiki root)
{
  "source_path": "/path/to/notes",
  "format": "obsidian",
  "total_files": 342,
  "processed": 140,
  "last_file": "concepts/transformers.md",
  "timestamp": "2026-04-12T14:30:00Z",
  "skipped": ["file-a.md", "file-b.md"],
  "errors": []
}
```
`wiki-import --resume` reads this file and continues from `processed + 1`.
The checkpoint is deleted when import completes successfully.

---

## Dry run (`--dry-run`)

Print the full import plan without writing any files:
- Complete file manifest with proposed target paths
- Mapping decisions with reasoning
- Deduplication hits (existing pages that would be merged)
- Tag normalization proposals
- Estimated number of wiki pages that would be created/updated

---

## Source format details

### Obsidian (`--format=obsidian`)
- `[[wikilinks]]` are preserved and validated against import manifest
- YAML frontmatter `tags:` migrated directly (with normalization)
- `![[image.png]]` attachments copied to `raw/assets/`
- Obsidian aliases (`aliases:` frontmatter) become redirects in index.md

### Notion (`--format=notion`)
- Strip UUID suffixes from filenames (`My Page a1b2c3d4.md` → `my-page.md`)
- Notion database tables → entity pages (one row = one entity stub)
- Notion `Properties` → YAML frontmatter fields
- Callout blocks → preserved as blockquotes

### Confluence (`--format=confluence`)
- HTML exports: convert to markdown (strip nav/header/footer)
- Page hierarchy → directory hierarchy → type mapping
- Confluence labels → tags (with normalization)
- Attachments → `raw/assets/`

### Plain folder (`--format=folder`)
- Directory name → type mapping (configurable)
- Files without frontmatter → infer title from H1 or filename
- Existing `# Tags:` comment lines → extract as tags

---

## Output

```
[Operation] wiki-import | {source-path}

[Discovery]
Scanned: {N} files | Mapped: {M} to import | Skipped: {K}
Format detected: {format}

[Mapping]
entities/  → {N} files
concepts/  → {M} files
comparisons/ → {K} files

[Processing]
Wave 1/18 (files 1–20): {status}
...
Wave 18/18 (files 341–342): {status}
Checkpoint cleared.

[Changes]
- Raw: raw/imported/{dirname}/ ({N} files)
- Created: {N} new wiki pages
- Updated: {M} existing pages (merged)
- Skipped: {K} (duplicates: X, too small: Y)
- index.md: {N} entries added
- SCHEMA.md: {N} tags added to taxonomy

[Summary]
Imported {N} files from {source-path} into the wiki. {M} entities, {K} concepts,
{J} comparisons. {Notable observation about the imported content.}

[Suggested next]
→ kata:wiki-digest  (to see the full picture of your knowledge base)
→ kata:wiki-lint    (to find any structural issues from the import)
```
