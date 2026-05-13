# Market Research dreaming fixture

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
