# Settled P&L Smoke Run

Date: 2026-05-31

This run verifies that the historical resolved-market simulator can open positions and close them at market resolution. It is not a strategy-alpha result.

## Data

- Source: Polymarket public Gamma/CLOB APIs through `polymarket_backtest.collect_historical`
- Output directory: `data/normalized/polymarket_recent_binary_10_20260531`
- Markets requested: 10
- Markets with price history: 10
- Price points: 168
- Snapshot rows: 84
- Resolved outcomes: YES 6, NO 4

This is intentionally a small smoke dataset. It is only strong enough to verify file ingestion and settlement accounting paths, not model performance or market-regime coverage.

## Neutral Plumbing Run

- Snapshots: `data/normalized/polymarket_recent_binary_10_20260531/snapshots_neutral.csv`
- Report: `data/backtests/polymarket_recent_binary_10_20260531/neutral/metrics.json`
- Closed trades: 0
- Final equity: 100.00
- Return: 0.00%

This is expected because `fair_yes` equals the observed YES price, so the 8 percentage point edge rule does not trigger.

## Oracle Settlement Smoke

- Test-only snapshots: `data/normalized/polymarket_recent_binary_10_20260531/snapshots_oracle_smoke.csv`
- Report: `data/backtests/polymarket_recent_binary_10_20260531/oracle_smoke/metrics.json`
- Closed trades CSV: `data/backtests/polymarket_recent_binary_10_20260531/oracle_smoke/closed_trades.csv`
- Equity curve CSV: `data/backtests/polymarket_recent_binary_10_20260531/oracle_smoke/equity_curve.csv`
- Closed trades: 9
- Final equity: 143.62
- Return: 43.62%
- Max drawdown: 3.05%
- Win rate: 100.00%

The oracle smoke file uses resolved outcomes to move `fair_yes` toward the winning side before resolution. This deliberately uses lookahead and must not be used for predictive-performance claims. Its purpose is only to prove that entry, settlement, closed-trade accounting, P&L, win-rate, and equity-curve output work on resolved-market files.

One of the 10 resolved markets did not produce a trade because its pre-resolution NO price was already around 0.935-0.945. Even with oracle fair value, the NO edge did not cross the configured 0.08 threshold.

This simulator path does not model full Polymarket live execution. The run used `slippage_bps=0.0`, `fee_rate=0.00` from the generated snapshots, and no gas or orderbook-depth fill constraints. Use the survival engine's depth/slippage scenarios for execution-risk testing, and treat this smoke as settlement-accounting evidence only.

## Commands

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.collect_historical \
  --out-dir data/normalized/polymarket_recent_binary_10_20260531 \
  --markets 10 --interval 1d --fidelity 60 --max-pages 10

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.settlement_smoke \
  --input-snapshots data/normalized/polymarket_recent_binary_10_20260531/snapshots_neutral.csv \
  --out-csv data/normalized/polymarket_recent_binary_10_20260531/snapshots_oracle_smoke.csv \
  --edge 0.12

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.backtest_report \
  --snapshots data/normalized/polymarket_recent_binary_10_20260531/snapshots_oracle_smoke.csv \
  --out-dir data/backtests/polymarket_recent_binary_10_20260531/oracle_smoke \
  --bankroll 100 --edge-threshold 0.08 --max-fraction 0.06
```

## Next Step

The next useful step is a non-oracle historical benchmark: attach forecast rows that were generated before each historical timestamp, or use forward logs until enough markets resolve. Without timestamp-valid forecasts, historical LLM forecasts would leak future information.

After that, add settled tests for cancellation/refund, partial fill, and delayed-resolution cases before relying on aggregate ROI or win-rate metrics.
