# Polymarket Safety Lab

Paper-only Polymarket prediction-market backtesting, forecast auditing, and strategy-readiness safety gates.

[![CI](https://github.com/kingostrich/polymarket-safety-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/kingostrich/polymarket-safety-lab/actions/workflows/ci.yml)
![Paper only](https://img.shields.io/badge/paper--only-no%20live%20trading-blue)
![No signing](https://img.shields.io/badge/no%20signing-no%20private%20keys-green)
![Tests](https://img.shields.io/badge/tests-pytest-informational)
![Status](https://img.shields.io/badge/current%20gate-NO__LIVE__TRADING-red)

This project is an open-source research scaffold for evaluating prediction-market strategies without placing live orders. It focuses on reproducible data collection, paper accounting, model forecast auditing, official-resolution replay, and explicit safety gates for AI-agent experiments.

It is not investment advice. It does not place orders, sign messages, move assets, use private keys, or provide a production trading system.

**Name note:** this repository was renamed from its original trading-agent research name to make the current scope explicit. The implementation is a safety lab and backtesting simulator. Live trading, wallet signing, and private-key workflows are not implemented.

## Core Capabilities

- Historical collection for resolved binary Polymarket markets.
- Forward paper logger for market snapshots and orderbook summaries.
- Forecast audit/import tools for rule-based and external model outputs.
- Survival replay for bankroll, open-position, MDD, and settlement accounting.
- Readiness gates that keep the project in `NO_LIVE_TRADING` until evidence is strong enough for a separate safety review.

## Current Status

The current internal strategy-readiness decision is `NO_LIVE_TRADING`.

These are paper-simulation safety blockers, not build failures:

- Active model benchmark underperforms the no-trade baseline.
- Mark-to-market P&L is negative on the current 100-row paper sample.
- Open positions remain unsettled.
- No official closed forward resolutions are loaded yet.
- Closed non-oracle forward trade count is below the readiness threshold.

Use this repository as a research and safety-validation environment, not as a live trading bot.

## Reviewer Snapshot

- Latest release: [`v0.1.3`](https://github.com/kingostrich/polymarket-safety-lab/releases/tag/v0.1.3)
- CI coverage: Python 3.11 tests, Python 3.12 tests, Ruff lint, and package build.
- Local test suite: `pytest` suite across backtesting, forecast audit, calibration, survival replay, and readiness gates.
- Core install: intentionally has no default runtime dependencies; `duckdb` is optional for export workflows.
- Safety posture: paper-only by default, with no live execution, signing, private-key loading, or asset movement.
- Current gate: `NO_LIVE_TRADING`, documented in `docs/strategy_readiness_gate.md`.

## Hard Safety Boundaries

- Do not add live order placement, exchange/broker execution, wallet signing, or asset movement.
- Do not add private-key loaders, seed phrase handling, or transaction-signing flows.
- Do not add Web3 signing dependencies such as `web3.py`, `eth-account`, or production Polymarket order-submission SDK paths without a separate security design review.
- Treat all model forecasts as offline files that must pass audit before replay.
- Treat reports as research evidence, not investment advice.

The simulator includes paper accounting and configurable slippage/liquidity checks, but it cannot fully reproduce real market impact, fee changes, queue position, or liquidity exhaustion. Do not use results as the sole basis for investment decisions.

## Quickstart

Start with:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pmlab-backtest --snapshots data/mock/snapshots.csv --bankroll 100
```

The clone-to-result walkthrough is in `docs/quickstart_walkthrough.md`.

Collect a small recent resolved binary-market sample and run a neutral plumbing backtest:

```bash
PYTHONPATH=src python -m polymarket_backtest.collect_historical \
  --out-dir data/normalized/polymarket_recent_binary_smoke \
  --markets 5 --interval 1d --fidelity 60 --max-pages 5

PYTHONPATH=src python -m polymarket_backtest.cli \
  --snapshots data/normalized/polymarket_recent_binary_smoke/snapshots_neutral.csv \
  --bankroll 100

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.export_dataset \
  --input-dir data/normalized/polymarket_recent_binary_smoke \
  --output-dir data/normalized/polymarket_recent_binary_smoke/export
```

The collected `manifest.json` records the Gamma/CLOB collection path, conservative resolved-outcome validation, generated file names, and separate dataset modes for `neutral_plumbing` versus test-only `oracle_settlement_smoke`. Collection stops before writing the manifest if generated rows fail validation. The collected `snapshots_neutral.csv` sets `fair_yes` equal to the observed YES price. It verifies ingestion and settlement plumbing, not predictive alpha. Generated `data/normalized/*` datasets are ignored by git by default.

Log one forward paper-trading snapshot without placing orders:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.paper_logger \
  --out-dir data/paper/live_snapshots \
  --limit 20
```

Automation notes are in `docs/automation_runbook.md`.

Run paper survival accounting:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.survival \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/survival \
  --bankroll 50 \
  --forecast-mode recorded
```

Generate and replay zero-cost baseline forecasts:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.forecast_runner \
  --input-dir data/paper/live_snapshots \
  --out-dir data/forecasts/rule_baseline \
  --provider rule_baseline

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.survival \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/survival_rule_baseline \
  --bankroll 50 \
  --forecasts-file data/forecasts/rule_baseline/latest_forecasts.jsonl
```

Audit a forecast file before replaying it:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.forecast_audit \
  --input-dir data/paper/live_snapshots \
  --forecasts-file data/forecasts/rule_baseline/latest_forecasts.jsonl \
  --out-json data/forecasts/rule_baseline/latest_audit.json
```

Prepare and import minimal external model forecasts:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.paper_subset \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/model_bench_20 \
  --limit 20

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.forecast_import template \
  --input-dir data/paper/model_bench_20 \
  --out-jsonl data/forecasts/model_bench_20/template.jsonl \
  --limit 20

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.model_prompt_packet \
  --template-jsonl data/forecasts/model_bench_20/template.jsonl \
  --out-md data/forecasts/model_bench_20/model_prompt_packet.md \
  --benchmark-name my_model \
  --model-label my_model_label \
  --input-dir-for-harness data/paper/model_bench_20 \
  --context-mode market \
  --scenario-prefix model_bench_20_survival_

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.model_prompt_packet \
  --template-jsonl data/forecasts/model_bench_20/template.jsonl \
  --out-md data/forecasts/model_bench_20/model_prompt_packet_blind.md \
  --benchmark-name my_model_blind \
  --model-label my_model_label \
  --input-dir-for-harness data/paper/model_bench_20 \
  --context-mode blind \
  --scenario-prefix model_bench_20_survival_

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.forecast_import import \
  --input-dir data/paper/model_bench_20 \
  --model-forecasts-file data/forecasts/my_model/model_minimal.jsonl \
  --out-dir data/forecasts/my_model/imported \
  --provider my_provider \
  --model my_model_label \
  --default-cost 0
```

External model rows must echo `logged_at`, `market_id`, and `input_hash` from the template, then provide `fair_yes`, `cost`, and `reasoning`. If an external model returns commentary around the JSON rows, extract and validate the JSONL before import:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.model_output_extract \
  --raw-file /tmp/model_raw_output.txt \
  --out-jsonl data/forecasts/my_model/model_minimal.jsonl \
  --expected-records 20
```

The 20-row subset is for provider plumbing, schema, and cost smoke tests; use the full snapshot history for ROI or drawdown conclusions. Generated prompt packets include benchmark-specific summary paths so larger experiments do not overwrite the default 20-row smoke summary.

The latest delegated-model smoke result is summarized in `docs/model_benchmark_smoke.md`.
The latest 100-row blind delegated-model run is summarized in `docs/next_model_blind_100_summary.md`.
The latest 100-row baseline/performance comparison is summarized in `docs/model_bench_100_performance_summary.md`, with event exposure details in `docs/next_model_blind_100_event_summary.md`.
The latest 100-row exit-policy probe is summarized in `docs/model_bench_100_exit_policy_run.md`.
The latest resolved-market settlement smoke is summarized in `docs/settled_pnl_smoke_20260531.md`.
The latest forward paper resolution check is summarized in `docs/forward_resolution_status_20260531.md`.
The latest no-live-trading readiness gate is summarized in `docs/strategy_readiness_gate.md`.
The readiness rules are specified in `docs/safety_gate_spec.md`.
The latest 100-row model-variant comparison is summarized in `docs/model_variant_comparison_100.md`.

Prepare a larger 100-row blind benchmark packet from the accumulated forward logs:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.paper_subset \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/model_bench_100 \
  --limit 100

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.forecast_import template \
  --input-dir data/paper/model_bench_100 \
  --out-jsonl data/forecasts/model_bench_100/template.jsonl \
  --limit 100

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.model_prompt_packet \
  --template-jsonl data/forecasts/model_bench_100/template.jsonl \
  --out-md data/forecasts/model_bench_100/model_prompt_packet_blind.md \
  --benchmark-name next_model_blind_100 \
  --model-label "Gemini 3.5 Flash High via agy blind" \
  --input-dir-for-harness data/paper/model_bench_100 \
  --context-mode blind \
  --scenario-prefix model_bench_100_survival_
```

Summarize model audit/replay outputs:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.model_benchmark_summary \
  --forecast-root data/forecasts \
  --survival-root data/paper \
  --scenario-prefix model_bench_20_survival_ \
  --source-rows 20 \
  --rank-mode quality \
  --output-csv data/forecasts/model_benchmark_summary.csv \
  --output-md docs/model_benchmark_summary.md
```

For provider-to-provider comparisons, only compare benchmark manifests with the same `source_rows_fingerprint`. That fingerprint proves the providers were imported, audited, and replayed on identical paper rows; differing fingerprints mean the ROI, MDD, open-position, and calibration columns are not directly comparable.

Summarize a survival event log to inspect open-position exposure:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.survival_event_summary \
  --events-csv data/paper/model_bench_100_survival_next_model_blind_100/latest_survival_events.csv \
  --out-json data/paper/model_bench_100_survival_next_model_blind_100/event_summary.json \
  --out-csv data/paper/model_bench_100_survival_next_model_blind_100/open_positions.csv \
  --out-md docs/next_model_blind_100_event_summary.md
```

Run one model benchmark end to end from a minimal forecast file:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.model_benchmark_run \
  --input-dir data/paper/model_bench_20 \
  --model-forecasts-file data/forecasts/agy_smoke/model_minimal.jsonl \
  --benchmark-name agy_smoke \
  --provider agy \
  --model "Gemini 3.5 Flash High via agy" \
  --scenario-prefix model_bench_20_survival_ \
  --source-rows 20 \
  --summary-csv data/forecasts/agy_smoke/model_benchmark_summary.csv \
  --summary-md docs/agy_smoke_summary.md \
  --rank-mode quality
```

Run an early-exit probe through the same benchmark wrapper:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.model_benchmark_run \
  --input-dir data/paper/model_bench_100 \
  --model-forecasts-file data/forecasts/next_model_blind_100/model_minimal.jsonl \
  --benchmark-name next_model_blind_100_exit_edge \
  --provider agy \
  --model "Gemini 3.5 Flash High via agy blind exit_edge_0.08" \
  --scenario-prefix model_bench_100_survival_ \
  --source-rows 100 \
  --summary-csv data/forecasts/model_bench_100/model_benchmark_exit_summary.csv \
  --summary-md docs/model_bench_100_exit_summary.md \
  --exit-policy edge_below \
  --exit-edge-threshold 0.08 \
  --rank-mode quality
```

Check official Gamma resolution status for forward paper markets and replay with conservative resolutions:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.paper_resolution_status \
  --input-dir data/paper/model_bench_100 \
  --out-dir data/paper/resolution_status/model_bench_100

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.model_benchmark_run \
  --input-dir data/paper/model_bench_100 \
  --model-forecasts-file data/forecasts/next_model_blind_100/model_minimal.jsonl \
  --benchmark-name next_model_blind_100_official_resolution_check \
  --provider agy \
  --model "Gemini 3.5 Flash High via agy blind official_resolution_check" \
  --scenario-prefix model_bench_100_survival_ \
  --source-rows 100 \
  --resolutions-csv data/paper/resolution_status/model_bench_100/resolutions.csv \
  --summary-csv data/forecasts/model_bench_100/model_benchmark_resolution_summary.csv \
  --summary-md docs/model_bench_100_resolution_summary.md \
  --rank-mode quality
```

For recurring checks, use the conditional cycle command. It refreshes resolution status and only runs replay when at least one official closed resolution is eligible:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.resolution_replay_cycle \
  --input-dir data/paper/model_bench_100 \
  --status-out-dir data/paper/resolution_status/model_bench_100 \
  --model-forecasts-file data/forecasts/next_model_blind_100/model_minimal.jsonl \
  --benchmark-name next_model_blind_100_resolution_cycle \
  --provider agy \
  --model "Gemini 3.5 Flash High via agy blind resolution_cycle" \
  --cycle-manifest data/paper/resolution_status/model_bench_100/latest_resolution_replay_cycle.json \
  --scenario-prefix model_bench_100_survival_ \
  --source-rows 100 \
  --summary-csv data/forecasts/model_bench_100/model_benchmark_resolution_summary.csv \
  --summary-md docs/model_bench_100_resolution_summary.md \
  --rank-mode quality
```

Diagnose whether a forecast file is only echoing market midpoint:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.forecast_diagnostics \
  --forecasts-file data/forecasts/agy_smoke/imported/latest_forecasts.jsonl \
  --out-json data/forecasts/agy_smoke/imported/latest_diagnostics.json \
  --edge-threshold 0.08
```

Create a test-only oracle settlement smoke from resolved historical snapshots:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.settlement_smoke \
  --input-snapshots data/normalized/polymarket_recent_binary_10_20260531/snapshots_neutral.csv \
  --out-csv data/normalized/polymarket_recent_binary_10_20260531/snapshots_oracle_smoke.csv \
  --edge 0.12

PYTHONPATH=src .venv/bin/python -m polymarket_backtest.backtest_report \
  --snapshots data/normalized/polymarket_recent_binary_10_20260531/snapshots_oracle_smoke.csv \
  --out-dir data/backtests/polymarket_recent_binary_10_20260531/oracle_smoke \
  --bankroll 100 --edge-threshold 0.08 --max-fraction 0.06
```

The oracle smoke uses resolved outcomes and is only for settlement-accounting verification. Do not use it for alpha or model-quality claims.

Build a conservative strategy readiness gate from the current paper artifacts:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.strategy_readiness \
  --model-manifest data/forecasts/next_model_blind_100/latest_benchmark_manifest.json \
  --baseline-manifest data/forecasts/rule_baseline_100/latest_benchmark_manifest.json \
  --resolution-manifest data/paper/resolution_status/model_bench_100/resolution_manifest.json \
  --resolution-cycle-manifest data/paper/resolution_status/model_bench_100/latest_resolution_replay_cycle.json \
  --oracle-metrics data/backtests/polymarket_recent_binary_10_20260531/oracle_smoke/metrics.json \
  --out-json data/readiness/latest_strategy_readiness.json \
  --out-md docs/strategy_readiness_gate.md
```

The readiness gate is intentionally conservative. `NO_LIVE_TRADING` means the current evidence is not sufficient for live order placement, signing, or asset movement.

Compare current 100-row model variants against the same no-trade baseline:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.model_variant_compare \
  --source-rows 100 \
  --output-csv data/forecasts/model_variant_comparison_100.csv \
  --output-json data/forecasts/model_variant_comparison_100.json \
  --output-md docs/model_variant_comparison_100.md
```

The variant comparison consumes paper benchmark manifests and survival reports only. It excludes oracle settlement smoke and does not approve live trading.

Run the full paper gate cycle in one command. This refreshes official resolution status, conditionally replays resolved markets, rebuilds the readiness gate, and regenerates the 100-row model-variant comparison:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.paper_gate_cycle
```

The cycle manifest is written to `data/paper/paper_gate_cycle/latest_paper_gate_cycle.json`. If no new official closed resolutions exist, the manifest keeps `readiness_decision=NO_LIVE_TRADING`, sets `paper_collection_decision=CONTINUE_PAPER_LOGGING`, and explains that reports were rebuilt from existing benchmark artifacts. The default `--oracle-metrics latest` auto-selects the newest `data/backtests/*/oracle_smoke/metrics.json`.

Add a conservative top-3 ask depth guard when testing larger position sizes:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.survival \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/survival_synthetic_depth \
  --bankroll 50 \
  --forecast-mode synthetic_edge \
  --synthetic-edge 0.12 \
  --liquidity-model top3_ask \
  --max-depth-fraction 0.25
```

Allow partial entries when only part of the requested entry fits inside the ask-depth guard:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.survival \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/survival_synthetic_partial_entry_exit_depth \
  --bankroll 50 \
  --forecast-mode synthetic_edge \
  --synthetic-edge 0.12 \
  --liquidity-model top3_ask \
  --max-depth-fraction 0.25 \
  --entry-fill-policy partial
```

Add a conservative top-3 bid depth guard for early-exit tests:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.survival \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/survival_synthetic_exit_bid_depth \
  --bankroll 50 \
  --forecast-mode synthetic_edge \
  --synthetic-edge 0.12 \
  --exit-policy edge_below \
  --exit-edge-threshold 0.20 \
  --exit-liquidity-model top3_bid \
  --max-exit-depth-fraction 0.25
```

Stress entry and exit fills with a depth-utilization slippage penalty:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.survival \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/survival_synthetic_slippage \
  --bankroll 50 \
  --forecast-mode synthetic_edge \
  --synthetic-edge 0.12 \
  --liquidity-model top3_ask \
  --max-depth-fraction 0.25 \
  --entry-fill-policy partial \
  --exit-policy edge_below \
  --exit-edge-threshold 0.20 \
  --exit-liquidity-model top3_bid \
  --max-exit-depth-fraction 0.25 \
  --slippage-model depth_utilization \
  --max-slippage-bps 50
```

Avoid marking an open position to zero when a paper snapshot has a temporarily missing bid:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.survival \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/survival_synthetic_last_valid_bid \
  --bankroll 50 \
  --forecast-mode synthetic_edge \
  --synthetic-edge 0.12 \
  --missing-quote-policy last_valid_bid
```

Skip paid forecasts for rows that cannot trigger a new entry or exit:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.survival \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/survival_synthetic_actionable_forecasts \
  --bankroll 50 \
  --forecast-mode synthetic_edge \
  --synthetic-edge 0.12 \
  --forecast-cost 0.01 \
  --forecast-call-policy actionable
```

Reduce same-timestamp path dependence from `market_id` ordering:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.survival \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/survival_synthetic_position_first \
  --bankroll 50 \
  --forecast-mode synthetic_edge \
  --synthetic-edge 0.12 \
  --timestamp-order-policy position_first
```

Use timestamp-close MDD accounting to avoid treating same-timestamp internal event order as a separate drawdown path:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.survival \
  --input-dir data/paper/live_snapshots \
  --out-dir data/paper/survival_synthetic_timestamp_close \
  --bankroll 50 \
  --forecast-mode synthetic_edge \
  --synthetic-edge 0.12 \
  --timestamp-order-policy position_first \
  --drawdown-policy timestamp_close
```

Survival reports always include both `event_max_drawdown` and `timestamp_close_max_drawdown`; keep the event value as the conservative risk check.

Summarize all survival reports, including legacy reports created before the split MDD fields existed:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.report_summary \
  --input-dir data/paper \
  --output-csv data/paper/survival_report_summary.csv
```

The summary CSV includes `run_timestamp`, `return_on_investment`, liquidity/partial-fill fields, and `missing_fields` for legacy-report caveats.

Build a latest-run strategy comparison table from the summary:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.strategy_compare \
  --summary-csv data/paper/survival_report_summary.csv \
  --output-csv data/paper/survival_strategy_comparison.csv \
  --output-md docs/survival_strategy_comparison.md
```

The comparison rank is a screening heuristic, not an investment recommendation.

Build a comparison table for only the standardized reruns:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.strategy_compare \
  --summary-csv data/paper/survival_report_summary.csv \
  --scenario-prefix standardized/ \
  --rank-mode triage \
  --output-csv data/paper/survival_standardized_comparison.csv \
  --output-md docs/survival_standardized_comparison.md
```

Use `--rank-mode performance` for a finance-outcome view where no-trade baselines can rank above active loss-making runs.

Resolution and early-exit details are in `docs/survival_harness.md`.
Forecast recording details are in `docs/forecast_provider_harness.md`.

Live trading and asset movement are intentionally out of scope for this scaffold.
