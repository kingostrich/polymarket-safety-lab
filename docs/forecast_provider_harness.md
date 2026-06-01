# Forecast Provider Harness

## Purpose

This layer separates forecast generation from survival/backtest accounting.

The pipeline is now:

```text
paper_logger -> forecast_runner -> survival
```

No live orders are placed. No wallet, private key, signing, or asset movement is used.

## Providers

Implemented providers:

- `recorded`: reuses the paper logger's placeholder `fair_yes`.
- `rule_baseline`: zero-cost deterministic baseline using YES best bid/ask midpoint. It falls back to recorded `fair_yes` if the YES book is incomplete.
- `synthetic_edge`: test-only provider used to stress accounting behavior.

`rule_baseline` is not expected to create alpha. It exists to freeze the forecast file schema before paid LLM or external model calls are added.

## Generate Forecast Records

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.forecast_runner \
  --input-dir data/paper/live_snapshots \
  --out-dir data/forecasts/rule_baseline \
  --provider rule_baseline
```

Outputs:

- `forecasts_<timestamp>.csv`
- `forecasts_<timestamp>.jsonl`
- `latest_forecasts.csv`
- `latest_forecasts.jsonl`
- `latest_manifest.json`

Each forecast row includes:

- source key: `logged_at`, `market_id`
- forecast: `provider`, `model`, `fair_yes`, `cost`, `reasoning`
- audit: `input_hash`
- market context: best bid/ask, liquidity, 24h volume

## Replay Forecasts In Survival

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.survival \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/survival_rule_baseline \
  --bankroll 50 \
  --forecasts-file data/forecasts/rule_baseline/latest_forecasts.jsonl
```

By default, missing forecasts are an error. For exploratory runs only:

```bash
--allow-missing-forecasts
```

This falls back to the logged `fair_yes` for missing rows.

## Audit Forecast Files

Before replaying any paid LLM or external model forecasts, verify coverage and replay safety against the paper logger rows:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.forecast_audit \
  --input-dir data/paper/live_snapshots \
  --forecasts-file data/forecasts/rule_baseline/latest_forecasts.jsonl \
  --out-json data/forecasts/rule_baseline/latest_audit.json
```

The audit checks:

- every paper row has exactly one forecast key
- no extra forecast keys are present
- malformed rows with missing `logged_at` or `market_id` fail as `schema_errors`
- `input_hash` still matches the source row
- `input_hash` is present for every matched forecast
- `fair_yes` is within `[0, 1]`
- `fair_yes` and `cost` are finite parseable numbers, and forecast cost is non-negative
- reasoning/model/provider coverage is visible; blank model/provider values fail the audit

Treat `status=FAIL` as a replay blocker unless the run is explicitly exploratory.

## Import External Model Forecasts

External models should not write the canonical replay file directly. For paid or delegated model tests, first cut a small paper subset so the model only needs to cover the benchmark rows:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.paper_subset \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/model_bench_20 \
  --limit 20
```

`paper_subset` replaces prior `paper_signals_subset_*` files in the output directory to avoid mixing benchmark runs. Treat subset survival results as provider plumbing and cost smoke tests, not full-period ROI evidence, because a 20-row slice starts with a fresh bankroll and no prior positions.

Then create a prompt/input template from that subset:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.forecast_import template \
  --input-dir data/paper/model_bench_20 \
  --out-jsonl data/forecasts/model_bench_20/template.jsonl \
  --limit 20
```

The model should return JSONL or CSV rows with only these fields:

- `logged_at`
- `market_id`
- `input_hash`
- `fair_yes`
- `cost`
- `reasoning`

Then import the minimal model output into the canonical forecast schema:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.forecast_import import \
  --input-dir data/paper/model_bench_20 \
  --model-forecasts-file data/forecasts/my_model/model_minimal.jsonl \
  --out-dir data/forecasts/my_model/imported \
  --provider my_provider \
  --model my_model_label \
  --default-cost 0
```

The importer joins model rows back to the local paper rows, verifies the model returned the same `input_hash` that appeared in the prompt template, adds market context and provider/model labels, and writes canonical CSV/JSONL outputs. Run `forecast_audit` on the imported `latest_forecasts.jsonl` before replaying it in survival against the same subset input directory.

## Latest Baseline Run

```text
provider=rule_baseline
records=154
total_cost=0.0
state=ALIVE
final_equity=50.0
signals_seen=0
positions_opened=0
positions_closed=0
max_drawdown=0.0
```

This is expected: midpoint fair value is too close to executable ask prices to cross the PDF's 8 percentage point edge threshold.

## Review Notes

Antigravity reviewed the forecast recording/replay layer as a limited external reviewer. Codex accepted and fixed these material issues:

- resolved positions could remain locked if the resolved market stopped appearing in active logger rows
- empty quote fields could crash survival accounting
- naive and aware timestamps could fail comparison
- unknown resolution outcomes needed an explicit placeholder behavior
- forecast costs should not create negative cash

Remaining limitation: the engine still assumes full fill at best ask/bid and does not consume order-book depth level by level.

Follow-up broad review fixes:

- Forecast file loading now treats `.jsonl` suffixes case-insensitively.
- Forecast file replay keys now normalize timestamp strings to UTC before matching, so equivalent forms such as `2026-01-01T00:00:00Z` and `2026-01-01T09:00:00+09:00` map to the same replay key.
- Survival max-drawdown accounting now includes the initial bankroll point, preventing instant-death runs from reporting zero drawdown.

## Next Model Slot

The next provider should implement the same output contract:

```python
Forecast(fair_yes=float, model=str, cost=float, reasoning=str)
```

For LLM providers, add:

- strict pre-screening before paid calls
- per-call input hash and prompt version
- model label and cost estimate
- timeout and retry budget
- no secrets or private wallet data in prompts

Only after forecasts are recorded to file should survival/backtest consume them.
