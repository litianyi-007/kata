#!/usr/bin/env python3
"""Generate the market-research dreaming fixture.

The fixture is a synthetic AI-market wiki circa "today minus various ages",
designed so the dreamer's expected behavior (per expected.json) is:

- Re-promote `mosaic`, `mpt-7b`, `mpt-30b` because of the planted
  Databricks-acquires-Mosaic recent ingest.
- Re-promote `switch-transformer`, `glam`, `moe-foundational-paper`,
  `trends/moe-architecture` because of the planted DeepSeek-V3 recent
  ingest, which links MoE history.
- Re-promote `trends/multimodal` because three planted ingests carry
  tag #multimodal (resurgence signal) and link to the page.
- Stay frozen for the obvious legacy entries (BERT, GPT-2, attention paper,
  ChatGPT launch event, etc.) which are mentioned nowhere in fresh ingests
  and share no resurgent tags.

Real entity names are used because the ground truth is easier to reason
about. See tests/dreaming_fixtures/market_research/README.md for the
non-recommendation disclaimer.

Run: python tests/build_dreaming_fixture.py [--out tests/dreaming_fixtures/market_research]
"""
from __future__ import annotations

import argparse
import shutil
from datetime import date, timedelta
from pathlib import Path

# Today's date for the fixture's "now". Hardcoded so reruns are reproducible
# regardless of the wall clock.
FIXTURE_TODAY = date(2026, 4, 25)
WATERMARK = date(2026, 4, 21)  # 4 days before "today"

PAGE_TEMPLATE = """---
title: {title}
type: {type}
tags: [{tags}]
created: {created}
updated: {updated}
published_at: {published_at}
ingested_at: {ingested_at}
sources: 1
---

# {title}

{body}

{links_block}
"""


def page(category: str, title: str, type_: str, tags: list[str],
        links: list[str], days_old: int, body: str = "") -> tuple[str, str]:
    """Returns (relative_path, file_text)."""
    pub = FIXTURE_TODAY - timedelta(days=days_old)
    ingested = FIXTURE_TODAY - timedelta(days=max(days_old - 5, 1))
    body = body or f"Synthetic fixture page about {title} for the dreaming benchmark."
    links_block = ""
    if links:
        links_block = "## See also\n" + "\n".join(f"- [[{l}]]" for l in links)
    text = PAGE_TEMPLATE.format(
        title=title,
        type=type_,
        tags=", ".join(tags),
        created=pub.isoformat(),
        updated=(pub + timedelta(days=1)).isoformat(),
        published_at=pub.isoformat(),
        ingested_at=ingested.isoformat(),
        body=body,
        links_block=links_block,
    )
    return f"{category}/{title}.md", text


# ────────────────────── PAGES ──────────────────────────

COMPANIES = [
    # (title, tags, links, days_old)
    ("anthropic", ["vendor", "lab", "llm"], ["claude-3-opus", "claude-3-5-sonnet", "dario-amodei"], 60),
    ("openai", ["vendor", "lab", "llm"], ["gpt-4", "gpt-4o", "sam-altman"], 30),
    ("google-deepmind", ["lab", "llm"], ["gemini-1-5", "gemini-2", "demis-hassabis"], 90),
    ("meta-ai", ["lab", "llm"], ["llama-3", "llama-3-1", "yann-lecun"], 120),
    ("xai", ["startup", "llm"], [], 150),
    ("mistral", ["startup", "llm"], ["mistral-large", "mistral-7b"], 180),
    ("microsoft-ai", ["public-co"], ["microsoft-inflection-deal"], 150),
    ("databricks", ["public-co", "enterprise"], [], 240),
    ("deepseek", ["startup", "lab"], ["deepseek-v3"], 90),
    ("cohere", ["vendor", "enterprise"], [], 390),
    ("character-ai", ["startup", "consumer"], [], 360),
    ("inflection", ["startup", "acquired"], ["microsoft-inflection-deal"], 330),
    ("adept", ["startup", "acquired"], ["david-luan"], 420),
    ("mosaic", ["startup", "acquired"], ["mpt-7b", "mpt-30b", "mpt-paper"], 600),
    ("ada-company", ["startup", "consumer"], [], 840),  # frozen — irrelevant legacy
]

MODELS = [
    ("gpt-4", ["llm", "closed-weights", "shipping"], ["gpt-4-paper", "openai"], 420),
    ("gpt-4o", ["llm", "multimodal", "closed-weights", "shipping"], ["openai"], 240),
    ("claude-3-opus", ["llm", "closed-weights", "shipping"], ["anthropic"], 300),
    ("claude-3-5-sonnet", ["llm", "closed-weights", "shipping"], ["anthropic"], 150),
    ("gemini-1-5", ["llm", "multimodal", "closed-weights", "shipping"], ["google-deepmind"], 360),
    ("gemini-2", ["llm", "multimodal", "closed-weights", "shipping"], ["google-deepmind"], 150),
    ("llama-3", ["llm", "open-weights", "shipping"], ["meta-ai", "llama-paper"], 330),
    ("llama-3-1", ["llm", "open-weights", "shipping"], ["meta-ai"], 240),
    ("mistral-large", ["llm", "shipping"], ["mistral"], 180),
    ("mistral-7b", ["llm", "open-weights"], ["mistral"], 540),
    # MPT family — should re-promote when Databricks-Mosaic ingest lands
    ("mpt-7b", ["llm", "open-weights"], ["mosaic", "mpt-paper"], 600),
    ("mpt-30b", ["llm", "open-weights"], ["mosaic", "mpt-paper"], 600),
    # MoE history — should re-promote when DeepSeek-V3 ingest lands
    ("switch-transformer", ["moe", "research"], ["moe-foundational-paper"], 1050),
    ("glam", ["moe", "research"], ["moe-foundational-paper"], 1050),
    # Genuine legacy — should stay frozen
    ("bloom", ["llm", "open-weights"], [], 780),
    ("gpt-3-5", ["llm", "closed-weights", "deprecated"], ["openai", "gpt-3-paper"], 900),
    ("gpt-2", ["llm", "open-weights", "deprecated"], ["openai"], 1500),
    ("bert", ["llm", "open-weights", "deprecated"], [], 1650),
    ("t5", ["llm", "open-weights", "deprecated"], [], 1500),
    ("universal-transformer-model", ["research", "deprecated"], [], 900),
]

PAPERS = [
    ("attention-is-all-you-need", ["transformer", "research"], [], 1800),
    ("gpt-3-paper", ["llm", "research"], ["openai"], 1500),
    ("chinchilla-paper", ["llm", "pretraining"], [], 540),
    ("transformers-tutorial", ["transformer"], [], 1050),
    # MoE foundational paper — should re-promote
    ("moe-foundational-paper", ["moe", "research"], ["switch-transformer", "glam"], 1080),
    ("mtp-paper", ["research"], [], 720),
    ("direct-preference-optimization", ["dpo", "rlhf"], [], 300),
    ("chain-of-thought", ["reasoning"], [], 330),
    ("rlhf-paper", ["rlhf"], [], 420),
    ("llama-paper", ["llm", "open-weights"], ["meta-ai", "llama-3"], 390),
    ("llama-2-paper", ["llm", "open-weights"], ["meta-ai"], 300),
    # MPT paper — should re-promote (acquired-context)
    ("mpt-paper", ["llm"], ["mpt-7b", "mosaic"], 600),
    ("gpt-4-paper", ["llm"], ["openai", "gpt-4"], 420),
    ("claude-paper", ["llm"], ["anthropic"], 210),
    ("universal-transformer-paper", ["research"], [], 900),
]

TRENDS = [
    # Multimodal — frozen but should re-promote on tag resurgence
    ("multimodal", ["multimodal", "vision", "voice"], ["gpt-4o", "gemini-1-5"], 480),
    # MoE architecture page — frozen, should re-promote on DeepSeek scenario
    ("moe-architecture", ["moe", "research"], ["switch-transformer", "moe-foundational-paper"], 720),
    ("moe-revival", ["moe"], ["deepseek-v3"], 120),  # active, recent trend
    ("agents", ["agents"], [], 180),
    ("voice-ai", ["voice"], [], 150),
    ("open-source-models", ["open-weights"], ["llama-3-1", "mistral-7b"], 240),
    ("consolidation", ["acquired"], ["microsoft-inflection-deal"], 180),
    ("enterprise-ai", ["enterprise"], [], 210),
    ("model-distillation", ["pretraining"], [], 540),
    ("vector-databases", ["enterprise"], [], 420),
]

PEOPLE = [
    ("dario-amodei", ["lab"], ["anthropic"], 120),
    ("sam-altman", ["vendor"], ["openai"], 90),
    ("yann-lecun", ["lab"], ["meta-ai"], 180),
    ("ilya-sutskever", ["lab"], [], 210),
    ("jensen-huang", ["public-co"], [], 180),
    ("demis-hassabis", ["lab"], ["google-deepmind"], 240),
    ("emad-mostaque", ["startup"], [], 420),
    ("noam-shazeer", ["lab"], [], 330),
    ("david-luan", ["startup", "acquired"], ["adept"], 360),
    ("mira-murati", ["lab"], ["openai"], 270),
]

EVENTS = [
    ("openai-saga-2023", ["consumer"], ["openai", "sam-altman", "ilya-sutskever"], 510),
    ("microsoft-inflection-deal", ["acquired", "enterprise"], ["microsoft-ai", "inflection"], 300),
    ("bing-ai-launch", ["consumer"], ["microsoft-ai"], 780),
    ("gpt-4-announcement", ["llm", "shipping"], ["openai", "gpt-4"], 420),
    ("llama-leak", ["open-weights"], ["meta-ai"], 750),
    ("chatgpt-launch", ["consumer"], ["openai"], 900),
    ("google-bard-launch", ["consumer", "deprecated"], ["google-deepmind"], 750),
    ("ai-act-passed", ["enterprise"], [], 420),
    ("nvidia-blackwell-launch", ["enterprise"], ["jensen-huang"], 150),
    ("stability-bankruptcy", ["acquired"], [], 420),
]

QUERIES: list = []  # empty for fixture; queries get filed by wiki-query


# ────────────────────── PLANTED RECENT INGESTS ──────────────────────────
# These land in raw/articles/_recent/ and via log.md become the increment
# the dreamer evaluates against the frozen pool.

RECENT = [
    # Days-ago, slug, tags, body, links
    (3, "databricks-acquires-mosaic",
     ["acquired", "enterprise", "open-weights"],
     "Databricks announced it will acquire MosaicML for $1.3 billion. "
     "The deal includes the MPT-7B and MPT-30B model family and the LLM Foundry "
     "training stack. Mosaic's research team will join Databricks' AI division.",
     ["databricks", "mosaic", "mpt-7b", "mpt-30b", "mpt-paper"]),

    (2, "deepseek-v3-paper-released",
     ["llm", "moe", "research", "open-weights"],
     "DeepSeek-V3 introduces a 671B-parameter mixture-of-experts model with "
     "37B active parameters per token. The architecture builds explicitly on "
     "prior MoE work — Switch Transformer and GLaM are cited as direct "
     "ancestors. The paper revives interest in the moe-architecture lineage.",
     ["deepseek", "deepseek-v3", "switch-transformer", "glam",
      "moe-foundational-paper", "moe-architecture", "moe-revival"]),

    (2, "anthropic-claude-3-7-released",
     ["shipping", "llm", "closed-weights"],
     "Anthropic shipped Claude 3.7 Sonnet today. Improved reasoning and "
     "tool use. Claude 3.5 Sonnet remains available.",
     ["anthropic", "claude-3-5-sonnet"]),

    (1, "multimodal-roundup-april",
     ["trend", "multimodal"],
     "Three major multimodal launches this month. The trend toward unified "
     "text+vision+voice is accelerating. See [[multimodal]] for the longer arc.",
     ["multimodal", "gpt-4o", "claude-3-5-sonnet", "gemini-2"]),

    (1, "voice-vision-converging",
     ["trend", "multimodal", "voice"],
     "Voice AI and vision models are converging into multimodal systems. "
     "GPT-4o and Gemini 2 both lead with native multimodal architectures.",
     ["multimodal", "voice-ai", "gpt-4o", "gemini-2"]),

    (0, "multimodal-research-summary",
     ["trend", "multimodal", "research"],
     "Recent papers focusing on multimodal reasoning and chain-of-thought "
     "with images. Multimodal capability is now table stakes.",
     ["multimodal", "chain-of-thought"]),

    (3, "mistral-large-2-released",
     ["model", "llm", "shipping"],
     "Mistral released Mistral Large 2 today. Better function calling.",
     ["mistral", "mistral-large"]),

    (0, "blackwell-deployment-scale",
     ["enterprise"],
     "Nvidia Blackwell GPUs reaching scale deployment at hyperscalers.",
     ["jensen-huang", "nvidia-blackwell-launch"]),
]


# ────────────────────── BUILD ──────────────────────────

def build(out: Path) -> None:
    preserved: dict[str, str] = {}
    if out.exists():
        for keeper in ("expected.json", "README.md"):
            kp = out / keeper
            if kp.exists():
                preserved[keeper] = kp.read_text(encoding="utf-8")
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for cat in ("companies", "models", "papers", "trends", "people",
                "events", "queries"):
        (out / cat).mkdir()
    (out / "raw" / "articles").mkdir(parents=True)
    (out / "raw" / "articles" / "_recent").mkdir(parents=True)

    # Write category pages
    for cat, items in [
        ("companies", COMPANIES),
        ("models", MODELS),
        ("papers", PAPERS),
        ("trends", TRENDS),
        ("people", PEOPLE),
        ("events", EVENTS),
    ]:
        type_ = cat.rstrip("s") if cat != "people" else "person"
        for title, tags, links, days_old in items:
            rel, text = page(cat, title, type_, tags, links, days_old)
            (out / rel).write_text(text, encoding="utf-8")

    # Write planted recent ingests as wiki pages too (they ARE the fresh
    # pages that drive the increment). Type = "ingest" — they're stub
    # records that the wiki-ingest pipeline would normally produce.
    for days_ago, slug, tags, body, links in RECENT:
        date_str = (FIXTURE_TODAY - timedelta(days=days_ago)).isoformat()
        rel, text = page("queries", slug, "ingest", tags, links, days_ago,
                         body=body)
        (out / rel).write_text(text, encoding="utf-8")

    # SCHEMA.md — copy from template
    template = Path(__file__).resolve().parent.parent / "templates" / \
               "market_research" / "SCHEMA.md"
    (out / "SCHEMA.md").write_text(template.read_text(encoding="utf-8"),
                                   encoding="utf-8")

    # log.md — base entries + recent ingest entries
    log_lines = ["# Log\n"]
    log_lines.append(f"## [{(FIXTURE_TODAY - timedelta(days=400)).isoformat()}] init | "
                     "Market research wiki")
    log_lines.append("- Domain: AI market research")
    log_lines.append("- Path: tests/dreaming_fixtures/market_research/")
    log_lines.append("")
    # Watermark — last dream run was 4 days ago, before all RECENT ingests
    log_lines.append(f"## [{WATERMARK.isoformat()}] dream | weekly run")
    log_lines.append(f"- Window: prior week")
    log_lines.append(f"- Watermark: {WATERMARK.isoformat()}")
    log_lines.append("")
    # Now the planted recent ingests, dated after the watermark
    for days_ago, slug, tags, body, links in RECENT:
        d = (FIXTURE_TODAY - timedelta(days=days_ago)).isoformat()
        log_lines.append(f"## [{d}] ingest | {slug}")
        log_lines.append(f"- Files: queries/{slug}.md")
        log_lines.append("- Linked to: " + ", ".join(f"[[{l}]]" for l in links))
        log_lines.append("")
    (out / "log.md").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    # index.md (minimal)
    (out / "index.md").write_text(
        "# Index\n\n(Auto-generated fixture; see directory structure.)\n",
        encoding="utf-8")

    # README — disclaimer + ground-truth pointer (restore preserved if any)
    (out / "README.md").write_text(
        preserved.get("README.md", README_TEXT), encoding="utf-8")
    if "expected.json" in preserved:
        (out / "expected.json").write_text(preserved["expected.json"],
                                           encoding="utf-8")
    # Clean up any stale .bak from earlier runs
    for keeper in ("expected.json", "README.md"):
        bak = out.parent / f"_{keeper}.bak"
        if bak.exists():
            bak.unlink()


README_TEXT = """# Market Research dreaming fixture

Synthetic test fixture for the wiki-dream algorithm. **Entity names match real
companies/products/papers as of 2026-04 for ground-truth realism, but this file
is NOT a market recommendation, NOT a current source of news, and NOT updated
to reflect real events.**

## Structure

- `companies/`, `models/`, `papers/`, `trends/`, `people/`, `events/`,
  `queries/` — the ~80 wiki pages composing the synthetic AI-market wiki.
- `raw/articles/_recent/` — would-be raw sources; in this fixture the
  ingest-stubs live under `queries/` instead so they're discovered as wiki
  pages.
- `log.md` — base entries plus the eight planted recent ingests dated
  after the watermark `2026-04-21`.
- `SCHEMA.md` — copied verbatim from `templates/market_research/SCHEMA.md`.
- `expected.json` — ground truth: which pages **should** be re-promoted by
  these recent ingests, and which **should stay frozen**. Used by
  `tests/run_dreaming_eval.py` for precision/recall measurement.

## Regenerating

```
python tests/build_dreaming_fixture.py --out tests/dreaming_fixtures/market_research
```

The script preserves `expected.json` and `README.md` across regenerations so
you don't lose hand-curated ground truth when adjusting page specs.
"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="tests/dreaming_fixtures/market_research")
    args = p.parse_args()
    out = Path(args.out).resolve()
    build(out)
    md_count = sum(1 for _ in out.rglob("*.md"))
    print(f"Wrote market-research dreaming fixture to {out}")
    print(f"  {md_count} markdown files")
    print(f"  watermark: {WATERMARK.isoformat()}")
    print(f"  fixture today: {FIXTURE_TODAY.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
