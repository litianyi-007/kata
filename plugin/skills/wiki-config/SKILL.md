---
name: wiki-config
description: "Unified read/write for SCHEMA.md config — show all settings in one place, get/set scalar values by dotted path with schema validation, explain what each key does. Domain-specific skills (wiki-tier, wiki-init) still own their UX shortcuts; wiki-config is the generic interface."
user-invocable: true
argument-hint: "[--show] [--get <path>] [--set <path> <value>] [--explain <path>] [--validate]"
---

# wiki-config

A single place to inspect and tune SCHEMA.md without hand-editing YAML.
Skill-specific commands (`wiki-tier --set-active=540d`, `wiki-init`) are
better UX for their domain; `wiki-config` is the **generic path-based**
interface — equally valid, more systematic, used when the user knows the
exact key they want or when there is no domain-specific shortcut for the
config they need (e.g. dreaming weights).

## Implementation

The IO layer is `plugin/scripts/config_io.py`. **The script is the source
of truth; the prose below explains its behavior.** Edits are line-level
surgical replacements that preserve comments, blank lines, and ordering;
schema validation runs after every write and the script reverts on failure.

```bash
# Show all config blocks at a glance
python {plugin_root}/scripts/config_io.py --wiki {wiki_path} show

# Read one value
python {plugin_root}/scripts/config_io.py --wiki {wiki_path} \
    get --path memory_tiers.active_days

# Set one value (validated; reverts on failure)
python {plugin_root}/scripts/config_io.py --wiki {wiki_path} \
    set --path dreaming.confidence_threshold --value 0.55

# Read the docstring for a key
python {plugin_root}/scripts/config_io.py --wiki {wiki_path} \
    explain --path dreaming.weights.entity

# Run the full schema_validate pipeline
python {plugin_root}/scripts/config_io.py --wiki {wiki_path} validate
```

## When to use

- "Show me everything that's tunable in this wiki"
- "What does dreaming.weights.tag mean?"
- "Set my dreaming threshold to 0.55"
- "Validate my SCHEMA.md after I edited it by hand"

## When NOT to use this — use the domain-specific skill instead

- Adjusting tier thresholds with delta preview → `wiki-tier --set-active=...`
  (it shows you "31 pages would move archived → active" before applying)
- Initial wiki bootstrap → `wiki-init` (interactive, multi-field at once)
- Pinning a single page → `wiki-tier --pin=<page>:<tier>` (writes
  page-level frontmatter, not SCHEMA.md)

`wiki-config` is for the long-tail of fine-tuning where the domain skill
doesn't have a shortcut.

## Limitations (v1.6)

- **Edits existing scalars only.** Cannot add new keys or new YAML blocks.
  For introducing a `dreaming:` block to a wiki initialized before v1.6,
  edit SCHEMA.md by hand or re-run `wiki-init` with the dreaming flag.
- **No list-index editing.** `custom_dimensions[0].required` is not
  reachable; edit SCHEMA.md by hand.
- **No multi-key transactions.** Each `--set` is one key, validated
  independently. To change two related keys, run twice.

These restrictions are deliberate for v1.6 — the script's surgical-edit
approach trades expressiveness for safety (every edit preserves user
formatting and is auto-reverted on validation failure).

## Output

```
[Operation] wiki-config | {mode}

[Result]
{JSON or formatted summary}

[Suggested next]
→ {follow-up skill if applicable}
```

## Notes for the agent

- Always show the user the BEFORE and AFTER values when running `--set`.
  The script returns both; surface them.
- If validation fails after a write, the script reverts and reports the
  errors. Pass these errors verbatim to the user; they're the actionable
  signal for why the change was rejected.
- Append-to-log on every successful set happens automatically (the
  script writes to `log.md`). The skill should not duplicate.
