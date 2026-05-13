# LLM Application Innovation Wiki

This wiki tracks the practical frontier of LLM applications: what teams
are building, which product and architecture patterns are spreading, and
what should be revisited when old ideas become relevant again.

## Working Views

- [[briefs/application-innovation-map]] — rolling synthesis of the field
- [[trends/agent-revival]] — recurring agent patterns and adoption signals
- [[trends/mcp-adoption]] — MCP ecosystem signals and product uptake
- [[patterns/rag]] — retrieval-augmented generation patterns
- [[patterns/code-assistant]] — coding assistant workflows and products
- [[comparisons/framework-landscape]] — LangChain / LlamaIndex / AutoGen / MCP
- [[discussions/open-questions]] — research questions and follow-up threads

## Weekly Loop

1. Drop new sources into `raw/articles/`, `raw/papers/`, `raw/transcripts/`,
   or `raw/external/`.
2. Run `/kata:wiki-watch --status` and `/kata:wiki-watch --drain`
   if watcher is enabled.
3. File important session outputs back into `briefs/` or `discussions/`
   so discussion can affect future retrieval and dreaming.
4. Run `/kata:wiki-dream` weekly and review `dreaming/{date}.md`.

## Dogfood Notes

During the v1.6 dogfood window, do not tune the dreaming block mid-run.
Record every accepted, rejected, and surprising candidate in
`docs/dogfood-v1.6.md`; tune only after four weekly runs.
