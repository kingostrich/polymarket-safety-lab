# Quickstart Walkthrough

This walkthrough proves the repository can be cloned and exercised without private keys, signing, live orders, or external data access.

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Validate The Included Sample

```bash
PYTHONPATH=src python -m polymarket_backtest.sample_validate \
  --snapshots data/mock/snapshots.csv
```

Expected result:

```text
status=PASS
rows=8
markets=3
resolved_rows=3
unresolved_rows=5
```

This check only validates the tiny public fixture. It is not evidence of alpha, profitability, or live readiness.

## 3. Run The Paper Backtest

```bash
PYTHONPATH=src python -m polymarket_backtest.cli \
  --snapshots data/mock/snapshots.csv \
  --bankroll 100
```

The command prints bankroll, final equity, return, max drawdown, win rate, and closed-trade count. It uses deterministic local fixture rows and does not call any trading API.

## 4. Run The Readiness Gate

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.paper_gate_cycle
```

The expected project state is still `NO_LIVE_TRADING`. Passing unit tests or running the mock dataset does not authorize live trading.
