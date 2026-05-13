# Wiki External Plugins — Interface Specification

External plugins extend `wiki-query` with fallback data sources: code search,
web search, private knowledge bases, or any tool that takes a text query and
returns useful text. When the local wiki can't answer, registered plugins step
in — their output is funneled through `wiki-ingest` so the wiki grows and
future queries don't need the fallback.

> **v1.4 breaking change.** The `command_template` (string-substitute-then-shell)
> field is **removed** because it allowed prompt-injected queries to land
> in `/bin/sh`. Plugins now declare an `argv:` array; the runner calls
> `execve` directly with no shell. See migration at the bottom of this file.

## Config location

```
{wiki_path}/.wiki-plugins.yaml
```

Per-wiki, user-editable, not version-controlled by default. Add to `.gitignore`
or commit it — your choice.

## How execution works

```
.wiki-plugins.yaml
        │
        ▼
schema_validate.py --validate-plugins-yaml         (1) validate format
        │
        ▼
external_plugin_run.py --plugin X --query Q        (2) substitute + check
        │
        ├── render argv tokens with {query}, {wiki_path}, {date}, vars.*
        ├── reject any token containing ; | & ` $( etc.
        ├── show argv to user (if auto_run=false and no --auto)
        ▼
subprocess.run(argv, shell=False, timeout=N, env=safe_env)   (3) execve
        │
        ▼
sanitize stdout (strip <system> / <|im_start|> / "ignore previous"  …)
truncate to max_output_bytes
        │
        ▼
raw/external/{plugin}/{date}-{slug}.md  + security header  (4) capture
        │
        ▼
wiki-ingest treats it as a normal raw source                (5) integrate
```

## Manifest format

```yaml
# .wiki-plugins.yaml — registered external plugins for wiki-query fallback

plugins:
  - name: deepwiki-cli
    description: "Search target codebase for implementation details"
    enabled: true
    priority: 1                   # lower = tried first
    auto_run: false               # true = skip user confirmation
    trigger: on_empty             # on_empty | on_low_confidence | on_request
    min_local_hits: 2             # only used when trigger = on_low_confidence

    # argv: literal token list. Each element is one argument passed to execve.
    # Tokens may contain {query}, {wiki_path}, {date}, or any key from vars.
    # Substitution is per-token: there is no shell, no globbing, no $IFS,
    # no command substitution. A query containing "; rm -rf /" lands in
    # ARGV[3], not in /bin/sh. The runner additionally rejects any token
    # that contains shell metacharacters after substitution.
    argv:
      - deepwiki-cli
      - search
      - "--repo={repo_path}"
      - "--query={query}"
      - "--format=markdown"

    # Static variables substituted into argv tokens.
    vars:
      repo_path: "/path/to/target/repo"

    output_dir: "raw/external/deepwiki-cli"     # default: raw/external/{name}
    auto_tags: ["source:deepwiki", "external"]

    # Resource caps. Output beyond max_output_bytes is truncated (and the
    # truncation is recorded in the saved file's frontmatter).
    timeout_seconds: 60
    max_output_bytes: 1048576

  - name: web-search
    description: "Search the public web"
    enabled: true
    priority: 2
    auto_run: false
    trigger: on_request
    argv:
      - curl
      - "-sS"
      - "--max-time"
      - "30"
      - "--data-urlencode"
      - "q={query}"
      - "--data-urlencode"
      - "format=markdown"
      - "https://api.search-engine.example/search"
    output_dir: "raw/external/web-search"
    auto_tags: ["source:web", "external"]
```

Validate before use:

```bash
python plugin/scripts/schema_validate.py --validate-plugins-yaml ~/wiki/.wiki-plugins.yaml
```

## Field reference

| Field             | Type   | Required | Description                                                                  |
| ----------------- | ------ | -------- | ---------------------------------------------------------------------------- |
| `name`            | string | yes      | Unique identifier, lowercase-hyphen                                          |
| `description`     | string | yes      | One-line purpose shown in confirmation prompt                                |
| `enabled`         | bool   | no       | Default `true`                                                               |
| `priority`        | int    | no       | Lower = tried first. Default 10                                              |
| `auto_run`        | bool   | no       | Default `false`. `true` skips user confirmation                              |
| `trigger`         | enum   | no       | `on_empty` (default) / `on_low_confidence` / `on_request`                    |
| `min_local_hits`  | int    | no       | Threshold for `on_low_confidence`. Default 2                                 |
| `argv`            | list   | yes      | Argv tokens. NO shell. Each element is one execve argument.                  |
| `vars`            | map    | no       | Static key→value substitutions for argv                                      |
| `output_dir`      | string | no       | Default `raw/external/{name}`                                                |
| `auto_tags`       | list   | no       | Tags auto-applied to pages created from output                               |
| `timeout_seconds` | int    | no       | Default 60. Plugin killed if it runs longer                                  |
| `max_output_bytes`| int    | no       | Default 1 MiB. Output truncated with a marker if larger                      |

## Security model

1. **No shell.** `subprocess.run(argv, shell=False)`. Tokens are literal.
2. **Argv-only substitution.** `{query}` lands in one argv element; pipes,
   redirects, and command substitution in the query are inert because nothing
   ever interprets them.
3. **Defense-in-depth metachar block.** After substitution, the runner refuses
   any argv token containing `;`, `|`, `&`, `&&`, `||`, `` ` ``, `$(`, `<`,
   `>`, or newlines. This catches plugins that try to be clever (e.g.
   `argv: [bash, -c, "tool {query}"]`) — that whole pattern is forbidden.
4. **Confirmation default.** `auto_run: false` means the runner prints argv
   and exits. The skill must surface it to the user before re-running with
   `--auto`. CLI flag `--auto-external` to wiki-query implies `--auto` for
   one call.
5. **Output sanitization.** Stdout is scanned for prompt-injection markers
   before being saved:
   - `<system>`, `</system>`, `<|im_start|>`, `<|im_end|>`
   - Lines beginning with "Ignore previous" / "Ignore above" / "You are now"
   - `[[INST]]` / `[[/INST]]` markers
   Each match is replaced with `[[REDACTED-INJECTION-MARKER]]` and the count
   is recorded in the saved file's frontmatter.
6. **Output sized.** Truncated to `max_output_bytes` (default 1 MiB). The
   truncation is recorded; nothing is silently dropped.
7. **Minimal env.** Only `PATH`, `HOME`, `TMPDIR`/`TEMP`, `USER`/`USERPROFILE`,
   `SystemRoot`, and `ComSpec` are passed to the child. Secrets in env vars
   stay with the parent.
8. **Treated as untrusted.** The saved file lives under `raw/external/`,
   carries `source: external` and a header warning the agent not to copy
   verbatim. wiki-ingest reads and processes it like any other raw source —
   meaning the agent summarizes and cross-references; raw text never lands
   directly in a wiki page.

## Migration from v1.3 `command_template`

v1.3 plugins looked like:

```yaml
# v1.3 — REMOVED. external_plugin_run.py refuses to execute these.
plugins:
  - name: web-search
    command_template: >
      curl -s "https://api/search?q={query}&format=markdown"
```

The string was substituted, then handed to `/bin/sh -c`. A query like
`x" && rm -rf ~ "y` would substitute, escape the quotes, and run.

v1.4 equivalent:

```yaml
plugins:
  - name: web-search
    argv:
      - curl
      - "-sS"
      - "--max-time"
      - "30"
      - "--data-urlencode"
      - "q={query}"
      - "https://api/search"
```

If you genuinely need shell features (pipes, redirects, sub-commands), put
them in a script you control:

```yaml
plugins:
  - name: my-pipeline
    argv:
      - bash
      - "{wiki_path}/.wiki-scripts/search.sh"
      - "{query}"
```

Now `search.sh` is the trust boundary; you write it once, audit it, and the
plugin runner can't be tricked into running anything else.

## Lifecycle

```
wiki-query "How does the auth middleware work?"
    │
    ├── wiki-search → 0 hits (trigger: on_empty fires)
    │
    ├── read .wiki-plugins.yaml  +  schema_validate.py
    │   └── plugin: deepwiki-cli (priority 1, trigger met)
    │       ├── external_plugin_run.py --plugin deepwiki-cli --query "..."
    │       ├── (auto_run=false) preview argv → user confirms
    │       ├── re-run with --auto → execve → capture stdout
    │       ├── sanitize + truncate
    │       └── save → raw/external/deepwiki-cli/2026-04-25-auth-middleware.md
    │
    ├── wiki-ingest raw/external/deepwiki-cli/2026-04-25-auth-middleware.md
    │   ├── creates: concepts/auth-middleware.md, entities/jwt-handler.md, ...
    │   └── updates: index.md, log.md
    │
    ├── wiki-search (re-run) → 3 hits now
    ├── read pages
    ├── synthesize answer with [[citations]]
    └── file back → queries/auth-middleware-explained.md
```

The key insight: **external plugin output becomes a new raw source**. It
enters the same wiki-ingest pipeline. The plugin just needs to produce useful
text on stdout — the wiki machinery handles the rest, and the security model
guarantees that "useful text" cannot become "useful command".

## Writing a new plugin

A plugin is any command-line tool that:

1. Accepts a query as argv (NOT stdin — the argv path is the audited one)
2. Writes useful text (preferably markdown) to stdout
3. Exits 0 on success

That's the whole interface. The wiki handles everything else.

### Example: deepwiki-cli

```bash
pip install deepwiki-cli
deepwiki-cli index /path/to/repo
```

Register with the manifest above and `wiki-query` will use it on local misses.

### Example: custom wrapper script

```bash
#!/bin/bash
# my-search.sh — thin wrapper around an internal API
# IMPORTANT: this script is the trust boundary. It receives "$1" as the
# query verbatim — quote it everywhere, NEVER eval, NEVER pass it to a shell.
set -euo pipefail
curl -sS --max-time 30 --data-urlencode "q=$1" https://internal-kb.corp/api/search \
    | jq -r '.results[].content'
```

```yaml
plugins:
  - name: internal-kb
    description: "Search the internal knowledge base"
    argv:
      - bash
      - "{wiki_path}/.wiki-scripts/my-search.sh"
      - "{query}"
    trigger: on_low_confidence
    min_local_hits: 3
```

`{query}` is one argv token; `my-search.sh` receives it as `$1`, never
reinterpreted by a shell.
