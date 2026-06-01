# Forward Paper Logger

Run timestamp: 2026-05-27 KST

## Purpose

The historical dataset cannot honestly replay LLM forecasts without lookahead risk. The next stage is a forward logger that records what the system can see now, then evaluates later after resolution.

This logger does not place orders, sign messages, move assets, or require private keys.

## What It Records

For each active binary `["Yes", "No"]` market:

- Gamma market metadata.
- YES and NO token ids.
- CLOB orderbook summary for both tokens.
- executable ask/bid fields for YES and NO.
- Gamma and CLOB fetch timestamps plus CLOB request latency.
- placeholder `fair_yes` using market-implied probability.
- PDF strategy edge calculation.
- generated paper signal or skipped-trade reason.

Default filters:

- `active=true`
- `closed=false`
- `enableOrderBook=true`
- `acceptingOrders=true`
- outcomes exactly `["Yes", "No"]`
- excludes `negRisk=true`

## Command

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.paper_logger \
  --out-dir data/paper/live_snapshots \
  --limit 20
```

The logger paces CLOB `/book` calls with `--book-sleep-seconds` and writes CSV/JSONL/manifest files atomically via temporary files and replace.

## Latest Run

```text
logged_at=2026-05-27T12:55:08.977387+00:00
records=13
signals=0
skips=13
csv_path=data/paper/live_snapshots/paper_signals_20260527T125508Z.csv
jsonl_path=data/paper/live_snapshots/paper_signals_20260527T125508Z.jsonl
forecast_mode=neutral_market_implied
```

All 13 rows skipped with `edge_below_threshold`, which is expected because the current forecast is market-implied and neutral.

## Output Files

```text
data/paper/live_snapshots/latest_manifest.json
data/paper/live_snapshots/latest_paper_signals.csv
data/paper/live_snapshots/latest_paper_signals.jsonl
data/paper/live_snapshots/paper_signals_<timestamp>.csv
data/paper/live_snapshots/paper_signals_<timestamp>.jsonl
```

## Important Limitation

`fair_yes` is currently `neutral_market_implied`, not an LLM forecast. The logger verifies forward data capture and signal plumbing. The first meaningful alpha test requires replacing the placeholder with a timestamped forecast provider and then waiting for market outcomes.
