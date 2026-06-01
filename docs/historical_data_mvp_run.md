# Historical Data MVP Run

Run timestamp: 2026-05-27 KST

## What Was Executed

Implemented and ran the first real-data ingestion MVP:

- `polymarket_backtest.collect_historical`
  - Gamma API closed/resolved market discovery.
  - Filters to binary `["Yes", "No"]` markets.
  - Excludes `negRisk=true` for the first MVP.
  - Pulls YES/NO CLOB `prices-history`.
  - Builds `snapshots_neutral.csv` for backtest plumbing.
- `polymarket_backtest.export_dataset`
  - Exports CSV inputs to Parquet.
  - Builds a DuckDB database.
  - Uses explicit DuckDB schemas so `YES`/`NO` outcomes remain strings while numeric fields stay numeric.

## Commands

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.collect_historical \
  --out-dir data/normalized/polymarket_recent_binary \
  --markets 30 --interval 1d --fidelity 60 --max-pages 20

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.cli \
  --snapshots data/normalized/polymarket_recent_binary/snapshots_neutral.csv \
  --bankroll 100

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.export_dataset \
  --input-dir data/normalized/polymarket_recent_binary \
  --output-dir data/normalized/polymarket_recent_binary/export
```

## Results

Collector manifest:

```text
markets_requested=30
markets_collected=30
markets_with_history=30
price_points=584
snapshots=292
interval=1d
fidelity=60
fair_value_mode=neutral_market_price
```

Backtest result on `snapshots_neutral.csv`:

```text
initial_bankroll=100.00
final_equity=100.00
total_return=0.00%
max_drawdown=0.00%
win_rate=0.00%
closed_trades=0
```

This zero-trade result is expected. `fair_yes` equals the observed YES price in the neutral dataset, so the 8 percentage point edge rule does not trigger. This run verifies ingestion, settlement labeling, file generation, and engine compatibility. It does not estimate strategy alpha.

DuckDB verification:

```text
markets_closed_binary 30
token_price_history 584
snapshots_neutral 292
resolved [('NO', 9), ('YES', 21)]
```

Generated files:

```text
data/normalized/polymarket_recent_binary/manifest.json
data/normalized/polymarket_recent_binary/markets_closed_binary.csv
data/normalized/polymarket_recent_binary/token_price_history.csv
data/normalized/polymarket_recent_binary/snapshots_neutral.csv
data/normalized/polymarket_recent_binary/export/markets_closed_binary.parquet
data/normalized/polymarket_recent_binary/export/token_price_history.parquet
data/normalized/polymarket_recent_binary/export/snapshots_neutral.parquet
data/normalized/polymarket_recent_binary/export/polymarket_recent_binary.duckdb
```

## Current Limitations

- Historical LLM fair-value replay is not implemented yet.
- `snapshots_neutral.csv` is a plumbing dataset, not a predictive dataset.
- `prices-history` gives token price series, not full executable depth. Orderbook-depth slippage comes next.
- Non-YES/NO binary markets, `negRisk=true` markets, and multi-outcome markets are excluded in this MVP.
- Public API reads now use a verified CA bundle through `certifi` when available. The earlier macOS Python CA failure is documented because it was encountered during the first run.
- DuckDB export uses explicit table schemas so `YES`/`NO` outcomes remain strings while numeric columns stay numeric.
- A simulator regression test now forces a YES signal and verifies open-position settlement, so the engine path is not only tested through the zero-trade neutral dataset.

## Next Engineering Step

Build a forward paper-trading logger that records, every 10 minutes:

- active market metadata,
- best bid/ask and orderbook depth,
- model or placeholder forecast,
- source context timestamps,
- generated signal and skipped-trade reason.

That produces non-lookahead forecast data suitable for the first honest strategy evaluation.
