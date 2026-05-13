# kata tests

Fast, deterministic smoke tests for the algorithmic scripts under
`plugin/scripts/`. They build a 50-page synthetic wiki, then exercise the
graph, tier, schema, and external-plugin modules and assert structural
properties.

## Run

```bash
python tests/run_smoke.py
```

Exit code 0 on success, 1 on any failed assertion. Requires Python 3.10+
(uses PEP 604 type hints internally) and stdlib only — no third-party deps.

## What it tests

| Test | Script | Covers |
|------|--------|--------|
| 1 | graph_query.py | Page discovery, edge count, tier distribution buckets |
| 2 | graph_query.py | BFS shortest-path resolution and hop count |
| 3 | graph_query.py | Hub ranking surfaces the planted hubs (attention, transformer) |
| 4 | graph_query.py | Orphan detection finds the planted `orphan-page` |
| 5 | tier_compute.py | Active/archived/frozen distribution sums to total |
| 6 | tier_compute.py | Preview mode reports a delta when thresholds change |
| 7 | schema_validate.py | A well-formed SCHEMA.md validates clean |
| 8 | schema_validate.py | Plugin argv with shell metachars is rejected |
| 9 | external_plugin_run.py | Query with `; rm -rf /` is refused before execve |
| 10 | external_plugin_run.py | `auto_run: false` defaults to preview, never runs |
| 11 | import_checkpoint.py | Init / update lifecycle round-trips through JSON |

## Regenerating the fixture

```bash
python tests/build_fixture.py --out tests/fixture
```

The fixture is auto-generated and gitignored. Scenarios planted in
`build_fixture.py`:

- `attention` and `transformer` are linked from many pages → hubs
- `orphan-page` has no in-edges and no out-edges → true orphan
- `isolated-concept` has no out-edges (a leaf, not a true orphan)
- Two pages with `days_old > 730` land in `frozen`; a few in `archived`
- A planted shortest-path through `attention → transformer → claude-3`
