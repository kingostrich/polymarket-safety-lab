# Quickstart Walkthrough

This walkthrough proves the repository can be cloned and exercised without private keys, signing, live orders, or external data access.

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 2. Run The Included Sample

```bash
pmlab-backtest --snapshots data/mock/snapshots.csv --bankroll 100
```

The command prints bankroll, final equity, return, max drawdown, win rate, and closed-trade count. It uses deterministic local fixture rows and does not call any trading API.

## 3. Run Forecast Diagnostics

```bash
PYTHONPATH=src python -m polymarket_backtest.forecast_diagnostics \
  --forecasts-file data/forecasts/agy_smoke/imported/latest_forecasts.jsonl \
  --out-json /tmp/pmlab_latest_diagnostics.json \
  --edge-threshold 0.08
```

The diagnostics report includes market-echo checks and Brier/calibration fields. If no official resolved outcomes are present, Brier is reported as not yet measurable rather than as model performance evidence.

## 4. Run The Local Checks

```bash
PYTHONPATH=src python -m pytest tests -q
ruff check src tests
python -m build
```

These checks validate the code, style, and package build. They do not imply live-readiness or investment performance.

## 5. Run The Readiness Gate Locally

```bash
pmlab-paper-gate
```

The expected project state is still `NO_LIVE_TRADING`. Passing unit tests or running the mock dataset does not authorize live trading.
