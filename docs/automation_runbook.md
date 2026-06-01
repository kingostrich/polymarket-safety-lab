# Forward Logger Automation Runbook

## Purpose

Run the forward paper logger every 10 minutes so future evaluations have non-lookahead market snapshots.

The automation must not place orders, sign messages, move assets, or use private keys.

## Manual Command

```bash
cd "/Users/gangtaesu/Documents/금융 에이전트"
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.paper_logger \
  --out-dir data/paper/live_snapshots \
  --limit 20 \
  --book-sleep-seconds 0.05
```

## Check Latest Run

```bash
cat data/paper/live_snapshots/latest_manifest.json
wc -l data/paper/live_snapshots/latest_paper_signals.csv
ls -lh data/paper/live_snapshots | tail
```

## Expected Output

- Timestamped CSV/JSONL pair for each run.
- Updated `latest_manifest.json`.
- Updated `latest_paper_signals.csv`.
- Updated `latest_paper_signals.jsonl`.

## Current Forecast Mode

`neutral_market_implied`.

This mode records forward market data and verifies signal plumbing. It is not an alpha model. The next model step is adding a timestamped forecast provider.
