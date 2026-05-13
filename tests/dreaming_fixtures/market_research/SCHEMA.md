# SCHEMA — LLM application innovation

> User-editable. Co-evolves with the wiki. `wiki_init.py --template market_research`
> writes this starter. All kata skills read and enforce SCHEMA.md rather
> than hardcoding opinions.
>
> **Scope.** Tracking innovation in LLM applications — frameworks, patterns,
> tooling, products, builders, deployment architectures. NOT tracking core
> model research (better suited to a paper-heavy schema), NOT tracking
> general tech market. Rename categories/tags if your slice differs.

## Domain

**LLM application innovation** — what's being built on top of LLMs, how
people are deploying them, which patterns are spreading, which fade. The
field moves fast (weekly product launches, monthly architectural shifts)
so the wiki is the user's working memory of "what was the state of X
practice 6 months ago and where is it now."

The "frozen → resurgent" pattern fires often:
- An old framework gets revived because a new product picks it up
  (LangChain → MCP, AutoGen → multi-agent renaissance)
- A pattern goes dormant then reappears under a new name (chain-of-thought → reasoning)
- An acquired company's tech matters again (Mosaic → Databricks)

## Categories

```yaml
categories:
  - name: products
    purpose: "Shipping LLM-based products (Claude, Cursor, Perplexity, v0)."
  - name: frameworks
    purpose: "Libraries and runtimes for building (LangChain, LlamaIndex, AutoGen, MCP)."
  - name: patterns
    purpose: "Recurring application patterns (RAG, agents, code-gen, voice agents)."
  - name: companies
    purpose: "Vendors, labs, startups, builders. Status flag tracks acquired/dead/active."
  - name: models
    purpose: "Specific model releases when they materially shape app innovation (Claude 3.5 Sonnet, GPT-4o, DeepSeek-V3)."
  - name: launches
    purpose: "Discrete events — product launches, fundings, acquisitions, deprecations. Time-stamped, narrow."
  - name: trends
    purpose: "Patterns spanning many sources (multimodal-as-default, agent revival, MCP adoption)."
  - name: comparisons
    purpose: "Side-by-side analyses of products / frameworks / approaches."
  - name: benchmarks
    purpose: "Eval methods, leaderboards, real-world test patterns."
  - name: briefs
    purpose: "Synthesized research notes: market maps, application scans, source digests."
  - name: discussions
    purpose: "Filed-back discussions, hypotheses, decisions, and follow-up questions from research sessions."
  - name: people
    purpose: "Founders, builders, researchers — when a person matters to a story."
  - name: queries
    purpose: "Filed-back wiki-query results that compound into knowledge."
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
  # Application patterns
  - rag
  - agents
  - multi-agent
  - voice
  - code-assistant
  - workflow
  - orchestration
  - mcp
  - function-calling
  - retrieval
  - embedding
  - prompt-engineering
  - chain-of-thought
  - reasoning
  - reflexion
  - plan-and-execute
  # Research workflow
  - research-question
  - market-map
  - source-digest
  - discussion
  - hypothesis
  - follow-up
  - use-case
  # Capability area
  - llm
  - vision
  - multimodal
  - audio
  # Engineering concerns
  - latency
  - cost
  - eval
  - deployment
  - observability
  - safety
  - hallucination
  # Org tags
  - vendor
  - lab
  - startup
  - acquired
  - public-co
  # Lifecycle / market position
  - shipping
  - preview
  - research
  - deprecated
  - open-weights
  - closed-weights
  - enterprise
  - consumer
```

## Custom dimensions

```yaml
custom_dimensions:
  - name: launch_date
    type: date
    description: "When this product/framework/company first became public."
    required: false
    refresh_on: [ingest]
    applies_to: [products, frameworks, companies]

  - name: company_status
    type: enum
    enum_values: [active, acquired, dead, stealth, ipo]
    description: "Current operational status. Update on each related ingest."
    required: false
    refresh_on: [ingest, digest]
    applies_to: [companies]

  - name: maturity
    type: enum
    enum_values: [research, preview, ga, deprecated]
    description: "Lifecycle stage of a product, model, or framework."
    required: false
    refresh_on: [ingest]
    applies_to: [products, models, frameworks]

  - name: mainstream
    type: enum
    enum_values: [experimental, emerging, standard, legacy]
    description: "Where this pattern / framework sits on the adoption curve right now. Re-prompted on digest because it shifts faster than launch_date."
    required: false
    refresh_on: [ingest, digest]
    applies_to: [patterns, frameworks]

  - name: cost_class
    type: enum
    enum_values: [free, cheap, pro, enterprise]
    description: "Pricing tier of a product (rough — refine in the page body)."
    required: false
    refresh_on: [ingest]
    applies_to: [products]

  - name: signal_type
    type: enum
    enum_values: [announcement, demo, benchmark, case-study, analysis, discussion]
    description: "What kind of signal created this page. Used during dogfood to separate source ingestion from higher-level discussion."
    required: false
    refresh_on: [ingest, import, manual]
    applies_to: [launches, trends, comparisons, briefs, discussions]

  - name: evidence_level
    type: enum
    enum_values: [source-backed, inferred, speculative]
    description: "Confidence level for synthesized claims. Discussion notes can be speculative; product and launch pages should usually be source-backed."
    required: false
    refresh_on: [manual, digest]
    applies_to: [briefs, discussions, trends, comparisons]
```

## Memory tiers

```yaml
memory_tiers:
  enabled: true
  active_days: 365
  archived_days: 730
  driving_field: published_at
```

> **Tuning hypothesis (validate during dogfood retrospective):** in a
> fast-moving app-innovation domain, 365/730 may be too long. Try
> 180/540 if the dogfood log shows "active tier feels stale" or
> "archived pages dominate searches I expected to be quick."
> **Don't tune mid-window** — let one set of thresholds run for the
> full 4 weeks so the data is comparable.

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
    dormancy_window_days: 90
    min_count: 2
```

> **Resurgence tuned for fast-moving domain.** Dormancy 90d (vs default
> 180d) and min_count 2 (vs 3) reflect that LLM app patterns cycle in
> months, not half-years. This is a domain-specific tuning that's
> baked in the template; the weights and threshold remain at safe
> defaults for the dogfood window.
>
> **Dogfood baseline.** For the first 4-week dogfood window, do not
> change `confidence_threshold`, weights, `dormancy_window_days`, or
> `min_count`. Record false positives/false negatives in
> `docs/dogfood-v1.6.md` and tune only in the retrospective.

Tune via `/wiki-config --set dreaming.confidence_threshold 0.55` etc.
Run weekly via `claude /schedule "0 23 * * 0" "/kata:wiki-dream"`.

## Page creation policy

A wiki page is created when an entity, framework, pattern, product,
research brief, or discussion:
- Is **central** to a source (the source is fundamentally about it), OR
- Is **mentioned in 2+ sources** (cross-referenced enough to deserve its own node)

For app innovation specifically: be eager to create `patterns/` and
`frameworks/` pages even on first mention — they accumulate cross-refs
fast. Create `briefs/` for synthesized research outputs and
`discussions/` when a conversation produces reusable hypotheses,
decisions, or follow-up questions. Be conservative on `people/` — only
when a person's role is load-bearing.

## Cross-reference policy

Link wherever there is a genuine connection. No minimum count. In this
domain, products often cite frameworks which cite patterns — the
chain-of-references is the point.

## Page size limit

No hard limit. `wiki-lint` flags pages > 500 lines for review (likely should
be split into a hub + sub-pages — common when a framework or pattern
matures and needs its own sub-graph).

## Log rotation

No rotation.
