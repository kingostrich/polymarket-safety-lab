# Exit Threshold Sweep

`scripts/optimize_exit_threshold.py` runs repeated paper-only survival replays across `edge_below` exit thresholds and writes CSV, Markdown, and manifest outputs.

It does not place orders, sign messages, move assets, or authorize live trading.

## Example

```bash
PYTHONPATH=src .venv/bin/python scripts/optimize_exit_threshold.py \
  --input-dir data/paper/model_bench_100 \
  --forecasts-file data/forecasts/next_model_blind_100/imported/latest_forecasts.jsonl \
  --out-dir data/paper/exit_threshold_sweep_next_model_blind_100 \
  --threshold-start 0.01 \
  --threshold-stop 0.20 \
  --threshold-step 0.01 \
  --bankroll 50 \
  --edge-threshold 0.08 \
  --max-fraction 0.06 \
  --max-positions 10 \
  --missing-quote-policy zero
```

Outputs:

- `exit_threshold_sweep.csv`
- `exit_threshold_sweep.md`
- `exit_threshold_sweep_manifest.json`

## Metrics

- `roi`: ending marked equity minus initial bankroll, divided by initial bankroll.
- `event_sharpe_smoke`: event-equity return Sharpe-style smoke metric from the replay event log. The event stream is irregular, so this is not a production portfolio statistic.
- `max_drawdown`: replay drawdown under the configured drawdown policy.
- `total_cost_paid`: `forecast_cost_total + slippage_cost_total`; it is not gas, exchange fees, or live execution cost.
- `realized_pnl`: closed or settled position P&L only.
- `open_positions`: unresolved exposure remaining at replay end.

## Interpretation

Use the sweep to compare mechanics on identical paper rows. The manifest sets `production_safe=false` and `readiness_decision=NO_LIVE_TRADING`. Do not treat the top-ranked threshold as a production optimum unless it also survives official-resolution replay, larger forward samples, baseline comparison, liquidity checks, and the readiness gate.
