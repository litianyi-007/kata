---
name: wiki-query
description: "Answer a question using the wiki's compiled knowledge. Searches relevant pages, synthesizes with citations, reports explicit answer confidence, supports multiple output formats (markdown/table/slides/chart/canvas), files substantive answers back into the wiki, and optionally falls back to external plugins (e.g. deepwiki-cli for source code) when local wiki coverage is insufficient — with results funneled back through wiki-ingest so future queries hit local first."
user-invocable: true
argument-hint: "<question> [--file] [--format=markdown|table|slides|chart|canvas] [--tier=active|all|archived|frozen] [--external] [--no-external] [--auto-external]"
---

# wiki-query

Answer a question from compiled wiki knowledge. Unlike asking the same question
cold, the wiki has already synthesized and cross-referenced the relevant sources.

**Like ingestion, substantive query results compound back into the wiki.** When an
answer is worth keeping — a comparison, a synthesis, a connection you discovered —
it's filed as a new wiki page and joins the knowledge base. Your explorations
compound in the wiki just like your ingested sources do. That's the whole trick:
nothing valuable disappears into chat history.

## When to use

- User asks any question about the wiki's domain
- User wants a comparison, deep dive, or cross-cutting synthesis
- `--file` flag: force-file the answer as a new wiki page

## Pre-flight (orientation guard)

Before querying, read orientation files if not done this session:
```
read_file {wiki_path}/SCHEMA.md
read_file {wiki_path}/index.md
read_file {wiki_path}/log.md  # last 20 lines
```

## Steps

### ① Parse the question

Classify it — the strategy depends on type:
- **Factual**: "What is X?" → entity/concept lookup
- **Comparative**: "How does X differ from Y?" → check for existing comparison first
- **Synthesis**: "What do we know about X across sources?" → multi-page read
- **Gap**: "What don't we know about X?" → check open questions in pages, run `wiki-lint`

### ② Find relevant pages

Run `wiki-search` internally for key terms, inheriting the `--tier` default
(`active` when tiers are enabled, else `all`). For wikis with 100+ pages, also
filter by relevant tags from SCHEMA.md's taxonomy. **Karpathy's rule: read
`index.md` first, then drill into specific pages** — this is exactly what
`wiki-search` does.

**If local search returns very few relevant pages**, note that — step ⑤b
(external fallback plugins) may apply. Don't skip the local read; local context
still frames how the external results get synthesized.

### ③ Read the relevant pages

Use `read_file`. For large wikis, prioritize in order:
1. Existing comparison pages (if the question is comparative — may already answer it)
2. Concept pages (usually have the synthesis)
3. Entity pages (the specifics)
4. Query pages (previously filed answers that may contain the answer already)

### ④ Synthesize an answer

- Draw from compiled wiki knowledge, citing pages inline: "According to
  [[flash-attention]], the algorithm reduces memory from O(N²) to O(N)..."
- If the wiki has no coverage on part of the question, **say so explicitly**.
  Karpathy's "lint also finds content gaps" applies here — a gap in the answer
  is a signal for the next ingest.
- When pages contradict each other, present **both views with their sources**.
  Don't hide the contradiction.
- Match the structure to the question (prose / list / table / chart — see ⑤)

### ④b Assess answer confidence

Every answer must include an explicit confidence score and label. This is an
operational estimate of how well the wiki supports the answer with relevant,
current, citable, actionable, and verifiable pages. It is not a probability that
the answer is universally true.

| Confidence | Range | Meaning | Behavior |
|------------|-------|---------|----------|
| **High** | 0.80-1.00 | Directly relevant pages, clear citations, current context, and verification or decision evidence | Answer directly; cite sources; name the verification boundary |
| **Medium** | 0.50-0.79 | Useful coverage, but missing some branch/version/platform context, proof, or validation | Answer with caveats; name the missing evidence; suggest targeted ingest or checks |
| **Low** | 0.20-0.49 | Partial context or weakly related pages only | Treat as partial; avoid decisive claims; identify the smallest source batch needed |
| **No answer** | 0.00-0.19 | No relevant pages, keyword noise only, or stale/conflicting material with no resolution path | Say the wiki cannot answer yet; use fallback/search; ingest resulting evidence |

Use these factors when assigning the score:
- **Relevance** — matches the specific entity, API, platform, bug shape, or decision
- **Source strength** — backed by specs, final reports, reviewed fixes, code paths, or primary notes
- **Freshness** — matches current repo, branch, base/default branch, version,
  release context, or other time-sensitive truth state
- **Actionability** — supports a concrete next edit, investigation, review, or decision
- **Verifiability** — includes tests, manifests, logs, reproduction steps, review outcomes, or other checkable evidence

A page match is not automatically an answer. If retrieved pages only share a
keyword or nearby topic, mark it as a context hit and keep confidence Low or No
answer. A query counts as answered only when the retrieved pages support a
concrete next step and explain the relevant boundaries.

### ④c Detect truth-state changes

Some queries are not asking for missing knowledge; they are asking whether old
knowledge is still true. This is common in code wikis as requirement or product
rule changes, but the general case includes any fact, policy, price, API,
version, organization, schedule, conclusion, or world-state change.

Treat this as a special confidence case:

- **Declared change:** if the user explicitly says the requirement, rule, fact,
  policy, API, or state changed, do not answer as if the older wiki page is
  current. State the old wiki-backed position, the newly declared position, the
  affected boundary, and the evidence needed to make the new position durable.
- **Inferred change:** if the user does not say anything changed, but the query
  implies behavior or facts that contradict a retrieved wiki rule, invariant,
  lesson, or prior answer, ask the user to confirm the possible change before
  giving a decisive answer. Use `askuserquestion` when available; otherwise ask
  a concise direct question.
- **Confidence impact:** a strong hit on an old rule is not High confidence when
  the question may be changing that rule. Mark the answer Medium at best until
  the change is confirmed with current evidence, and Low/No answer if the wiki
  only contains the obsolete side of the conflict.
- **Ingest impact:** once the change is confirmed or solved, recommend timely
  ingest. Stale wiki guidance can mislead future queries, so preserve both the
  new evidence and the old page whose judgment changed.

When filing a query about a truth-state change, include: old wiki position, new
or suspected position, contradiction, confirmed scope, evidence used, remaining
unknowns, and the ingest plan. For software work, also include repo, branch,
base/default branch, changed files, tests, generated artifacts, and whether old
regression guards still apply outside the narrowed exception.

If confidence is below High and the user will solve the issue outside the wiki,
tell them what durable record to ask their current agent/LLM to save for later
ingest. For software work, prefer a short fix/development note containing:
problem statement, root cause, changed files, decision boundaries, tests run,
generated artifacts checked, and remaining risks. The user does not need to
write wiki pages; they only need to preserve ingestible evidence.

### ⑤ Apply output format

**`--format=markdown`** (default)

Prose with headers and `[[wikilink]]` citations throughout. The answer is a
mini-article.

**`--format=table`**

Structured comparison table. Each row = option/entity, columns = dimensions:
```markdown
| Dimension    | [[claude-3]] | [[gpt-4]]   | [[gemini]]  |
|--------------|--------------|-------------|-------------|
| Context      | 200k         | 128k        | 1M          |
| Multimodal   | yes          | yes         | yes         |
| Open weights | no           | no          | no          |
| Sources      | [[page-a]]   | [[page-b]]  | [[page-c]]  |
```

**`--format=slides`** (Marp)

Marp-compatible markdown slide deck. Obsidian has a Marp plugin; the Marp CLI
also renders to PDF/HTML/PPTX.

```markdown
---
marp: true
theme: default
paginate: true
---

# {Question}

> {one-line thesis}

---

## Finding 1 — {short title}

- bullet from [[page-a]]
- bullet from [[page-b]]

---

## Finding 2 — {short title}

![width:500px](../raw/assets/diagram.png)

- bullet

---

## Synthesis

{1-2 sentence takeaway}

Sources: [[page-a]], [[page-b]], [[page-c]]
```

Save as `queries/{name}.md` when filing back.

**`--format=chart`** (matplotlib via code execution)

For quantitative questions. Gather data from wiki pages, then use the code
execution tool:
```python
import matplotlib.pyplot as plt
# data extracted from wiki pages — cite the source pages in comments
data = {...}
plt.figure(figsize=(10, 6))
# ... plot ...
plt.savefig("queries/{name}-chart.png", dpi=150, bbox_inches="tight")
```
The filed query page then references the chart:
```markdown
![{Chart title}](./{name}-chart.png)

Data sources: [[page-a]], [[page-b]]
```

**`--format=canvas`** (Obsidian canvas)

For relational / spatial questions where a 2D layout helps. Output an Obsidian
`.canvas` JSON file — nodes are wiki pages, edges are derived connections:
```json
{
  "nodes": [
    {"id": "n1", "type": "file", "file": "entities/claude-3.md", "x": 0, "y": 0, "width": 300, "height": 200},
    {"id": "n2", "type": "file", "file": "entities/gpt-4.md", "x": 400, "y": 0, "width": 300, "height": 200},
    {"id": "n3", "type": "text", "text": "Both use RLHF", "x": 200, "y": 300, "width": 200, "height": 60}
  ],
  "edges": [
    {"id": "e1", "fromNode": "n1", "toNode": "n3"},
    {"id": "e2", "fromNode": "n2", "toNode": "n3"}
  ]
}
```
Save to `queries/{name}.canvas` — Obsidian will render it as a 2D canvas. Useful
for "how are X, Y, Z related?" questions.

### ⑤b External fallback plugins (F3)

If the local wiki doesn't have enough coverage, `wiki-query` can delegate to
**external plugins** registered in `{wiki_path}/.wiki-plugins.yaml`. Examples:

- `deepwiki-cli` — searches a target codebase
- A web-search shim — searches the public web
- A private knowledge-base shim — queries an internal system

**Trigger logic** (per plugin `trigger:` setting):
- `on_empty` — fire when step ② returned 0 relevant pages (default)
- `on_low_confidence` — fire when local confidence is below the plugin's
  configured threshold (or when fewer than `min_local_hits` pages were usable,
  for legacy plugin configs)
- `on_request` — only fire if the user passed `--external`

**Execution**:

1. Read `.wiki-plugins.yaml` to get the plugin list ordered by `priority:`
2. For each plugin whose trigger condition is met, **delegate to the runner
   script** — never substitute and shell out yourself:

   ```bash
   python {plugin_root}/scripts/external_plugin_run.py \
       --wiki {wiki_path} --plugin <name> --query "<question>"
   ```

   The script: validates the plugin entry against `plugin/schema/wiki-schema.json`,
   renders argv tokens with `{query}` / `{wiki_path}` / `{date}` / `vars.*`,
   refuses any token containing shell metachars after substitution, and (by
   default) returns a `mode: "preview"` payload with the rendered argv for
   user confirmation.

   a. **Show the rendered argv to the user and ask for confirmation** unless
      `auto_run: true` (or `--auto-external` was passed). Re-run with
      `--auto` to actually execute.
   b. On execution, the script writes
      `raw/external/{plugin-name}/{YYYY-MM-DD}-{slug}.md` with a security
      header (plugin, query, argv, executed_at, injection_markers_redacted,
      truncated, auto_tags) — pre-sanitized for prompt-injection markers and
      truncated at `max_output_bytes`.
3. **Pipe the saved file through `wiki-ingest`** so the plugin's answer
   becomes new wiki pages — properly categorized, tagged, cross-referenced,
   and tier-stamped. External output → raw layer → ingest → wiki pages →
   future queries hit local first.
4. Re-run step ② (local search) against the now-expanded wiki and proceed to
   step ③ with the fresh pages included.

> **v1.4 breaking change:** the pre-v1.4 `command_template:` (string-concat
> into `/bin/sh`) is removed. Plugins that still use it are refused with
> exit code 3. Migrate to `argv:` (see PLUGINS.md). Never re-implement the
> render-then-shell flow inside the skill.

**Flags**:
- `--external` — force-try all `on_request` plugins even when local hits exist
- `--no-external` — skip fallback entirely (useful when offline)
- `--auto-external` — don't ask for confirmation before running plugin commands

**Safety**:
- Fallback plugins are arbitrary shell commands the user registered. The
  default is `auto_run: false` — agent **must** show the command and wait for
  confirmation before execution. Never bypass this without explicit user flag.
- If a plugin fails (non-zero exit or stderr), report the failure and
  continue to the next plugin. Don't block the query.
- Output is captured as-is; it gets cleaned up during the wiki-ingest pipe.

**Log entry** (per plugin invocation):
```
## [YYYY-MM-DD] external | {plugin-name}: {question}
- Command: {rendered-command}
- Saved: raw/external/{plugin-name}/{file}.md
- Ingest: {list of wiki pages created}
```

### ⑥ Decide whether to file back

File the answer to `queries/{name}.md` when **any** of these hold:
- The answer required reading 4+ pages (the synthesis is the value)
- It's a comparison that didn't exist yet in `comparisons/`
- It reveals an emergent insight not captured anywhere
- User passed `--file` explicitly

When filing:
- Write full frontmatter (`type: query`, tags, sources = list of pages used)
- Include `confidence:` and `confidence_label:` in frontmatter when the schema
  allows custom fields; otherwise include them near the top of the page body
- Add to `index.md` under the appropriate section
- Update `log.md`
- **Cross-reference both ways** — link from the sources back to the query

This is how queries compound. A filed query is indistinguishable from an ingested
source in terms of future retrievability.

### ⑦ Update log

```
## [YYYY-MM-DD] query | {Question}
- Pages used: {list}
- Format: {markdown|table|slides|chart|canvas}
- Confidence: {0.00-1.00} ({High|Medium|Low|No answer})
- Filed: {queries/name.md | no}
```

## Output

```
[Operation] wiki-query | "{question}"

[Answer]

Confidence: {0.00-1.00} ({High|Medium|Low|No answer})

{Synthesized answer with [[wikilink]] citations throughout}

Sources used:
- [[{page1}]] — {why this page was relevant}
- [[{page2}]] — {why this page was relevant}

Coverage gaps:  (if any)
- The wiki has no pages on {X}. Consider ingesting {source type}.
- Confidence is below High because {missing branch/version/evidence/validation/etc.}.
- If you solve this now with another agent/LLM, ask it to save an ingestible
  fix/development record: problem, root cause, changed files, decision
  boundaries, tests run, generated artifacts checked, and remaining risks.

[Filed]
→ queries/{name}.md   (or "Not filed — simple lookup")

[Suggested next]
→ kata:wiki-ingest <source>   (to fill identified gaps)
→ kata:wiki-lint              (if gaps keep appearing — schema may need evolution)
```
