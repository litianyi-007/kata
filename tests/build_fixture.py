#!/usr/bin/env python3
"""Generate a 50-page synthetic wiki fixture for smoke tests.

Categories: entities (15), concepts (15), comparisons (10), queries (10).
Wikilinks form a sparse graph with known hubs (claude-3, gpt-4, attention),
some orphans, and a planted shortest-path scenario.

Run: python tests/build_fixture.py [--out tests/fixture]
"""
from __future__ import annotations

import argparse
import shutil
from datetime import date, timedelta
from pathlib import Path

WIKI_FRONTMATTER = """---
title: {title}
type: {type}
tags: [{tags}]
created: {created}
updated: {updated}
published_at: {published_at}
ingested_at: {ingested_at}
sources: {sources}
---
"""


def page(title, type_, tags, links, body, days_old=30):
    today = date.today()
    pub = today - timedelta(days=days_old)
    fm = WIKI_FRONTMATTER.format(
        title=title,
        type=type_,
        tags=", ".join(tags),
        created=pub.isoformat(),
        updated=(pub + timedelta(days=1)).isoformat(),
        published_at=pub.isoformat(),
        ingested_at=today.isoformat(),
        sources=1,
    )
    body_with_links = body + "\n\nSee also: " + ", ".join(f"[[{l}]]" for l in links)
    return fm + "\n# " + title + "\n\n" + body_with_links + "\n"


ENTITIES = [
    # (title, tags, links, days_old)
    ("claude-3", ["model", "anthropic"], ["anthropic", "rlhf", "constitutional-ai", "transformer"], 60),
    ("gpt-4", ["model", "openai"], ["openai", "rlhf", "instruct-gpt", "transformer"], 90),
    ("llama-3", ["model", "meta"], ["meta", "transformer", "rlhf"], 120),
    ("anthropic", ["org"], ["claude-3", "constitutional-ai", "dario-amodei"], 200),
    ("openai", ["org"], ["gpt-4", "instruct-gpt"], 200),
    ("meta", ["org"], ["llama-3"], 250),
    ("dario-amodei", ["person"], ["anthropic"], 300),
    ("instruct-gpt", ["model"], ["openai", "rlhf"], 400),
    ("constitutional-ai", ["concept", "anthropic"], ["claude-3", "alignment"], 180),
    ("flash-attention", ["concept", "performance"], ["attention", "transformer"], 100),
    ("standard-attention", ["concept"], ["attention", "transformer"], 700),  # archived
    ("multi-head-attention", ["concept"], ["attention", "transformer"], 800),  # frozen
    ("rope", ["concept"], ["attention", "transformer"], 500),
    ("alibi", ["concept"], ["attention"], 600),
    ("orphan-page", ["misc"], [], 50),  # true orphan — no links in or out
]

CONCEPTS = [
    ("attention", ["mechanism", "core"], ["transformer", "flash-attention", "standard-attention", "multi-head-attention", "rope", "alibi"], 50),
    ("transformer", ["architecture"], ["attention", "claude-3", "gpt-4", "llama-3"], 70),
    ("rlhf", ["training"], ["alignment", "instruct-gpt", "claude-3", "gpt-4"], 110),
    ("alignment", ["safety"], ["rlhf", "constitutional-ai"], 130),
    ("tokenization", ["preprocessing"], ["transformer"], 150),
    ("scaling-laws", ["theory"], ["transformer"], 220),
    ("mixture-of-experts", ["architecture"], ["transformer"], 180),
    ("prompt-engineering", ["technique"], ["chain-of-thought"], 90),
    ("chain-of-thought", ["technique"], ["prompt-engineering"], 95),
    ("retrieval-augmented-generation", ["technique"], ["embedding"], 80),
    ("embedding", ["representation"], ["retrieval-augmented-generation"], 85),
    ("fine-tuning", ["training"], ["rlhf", "transfer-learning"], 200),
    ("transfer-learning", ["training"], ["fine-tuning"], 250),
    ("self-supervised", ["training"], ["transformer"], 350),
    ("isolated-concept", ["misc"], [], 45),  # leaf — no out, but maybe in
]

COMPARISONS = [
    ("claude-vs-gpt", ["comparison"], ["claude-3", "gpt-4"], 30),
    ("flash-vs-standard-attention", ["comparison"], ["flash-attention", "standard-attention"], 40),
    ("rope-vs-alibi", ["comparison"], ["rope", "alibi"], 60),
    ("transformer-vs-rnn", ["comparison"], ["transformer"], 200),
    ("rlhf-vs-cai", ["comparison"], ["rlhf", "constitutional-ai"], 100),
    ("openai-vs-anthropic", ["comparison"], ["openai", "anthropic"], 80),
    ("llama-vs-mistral", ["comparison"], ["llama-3"], 70),
    ("dpo-vs-rlhf", ["comparison"], ["rlhf"], 110),
    ("moe-vs-dense", ["comparison"], ["mixture-of-experts", "transformer"], 150),
    ("gpt-3-vs-gpt-4", ["comparison"], ["gpt-4"], 250),
]

QUERIES = [
    ("how-does-attention-scale", ["query"], ["attention", "scaling-laws"], 20),
    ("why-rlhf-works", ["query"], ["rlhf", "alignment"], 25),
    ("flash-attention-tradeoffs", ["query"], ["flash-attention"], 35),
    ("constitutional-ai-explained", ["query"], ["constitutional-ai", "alignment"], 40),
    ("rope-vs-alibi-tradeoffs", ["query"], ["rope", "alibi", "rope-vs-alibi"], 45),
    ("scaling-laws-history", ["query"], ["scaling-laws"], 800),  # frozen
    ("transformer-genealogy", ["query"], ["transformer", "self-supervised"], 600),  # archived
    ("emergent-abilities", ["query"], ["scaling-laws"], 90),
    ("safety-tradeoffs", ["query"], ["alignment", "rlhf", "constitutional-ai"], 50),
    ("retrieval-trends", ["query"], ["retrieval-augmented-generation", "embedding"], 65),
]


def write_fixture(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    (out / "entities").mkdir(parents=True)
    (out / "concepts").mkdir(parents=True)
    (out / "comparisons").mkdir(parents=True)
    (out / "queries").mkdir(parents=True)
    (out / "raw" / "papers").mkdir(parents=True)

    for cat, items in [
        ("entities", ENTITIES),
        ("concepts", CONCEPTS),
        ("comparisons", COMPARISONS),
        ("queries", QUERIES),
    ]:
        type_ = cat.rstrip("s") if cat != "comparisons" else "comparison"
        for title, tags, links, days_old in items:
            text = page(title, type_, tags, links,
                        f"Synthetic fixture page about {title}.",
                        days_old=days_old)
            (out / cat / f"{title}.md").write_text(text, encoding="utf-8")

    # SCHEMA.md with embedded YAML config blocks
    schema_md = """# SCHEMA — fixture wiki

This file is user-editable and authoritative. Skills read it, never override.

## Memory tiers

```yaml
memory_tiers:
  enabled: true
  active_days: 365
  archived_days: 730
  driving_field: published_at
```

## Custom dimensions

```yaml
custom_dimensions: []
```

## Tag taxonomy

```yaml
tag_taxonomy:
  - model
  - org
  - person
  - concept
  - mechanism
  - architecture
  - training
  - safety
  - comparison
  - query
  - misc
  - core
  - performance
  - theory
  - technique
  - representation
  - preprocessing
  - anthropic
  - openai
  - meta
```
"""
    (out / "SCHEMA.md").write_text(schema_md, encoding="utf-8")

    # index.md (minimal)
    (out / "index.md").write_text(
        "# Index\n\nSee directory listing — fixture is auto-generated.\n",
        encoding="utf-8")
    (out / "log.md").write_text(
        "# Log\n\n## [2026-04-25] init | Fixture wiki\n",
        encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="tests/fixture")
    args = p.parse_args()
    out = Path(args.out).resolve()
    write_fixture(out)
    print(f"Wrote fixture to {out} ({sum(1 for _ in out.rglob('*.md'))} markdown files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
