# Forward Paper Resolution Status

Date: 2026-05-31

This check looks up the 100-row forward paper benchmark markets on Polymarket Gamma and writes a conservative `resolutions.csv` for survival replay. It does not place orders, sign messages, or move assets.

## Inputs

- Forward paper sample: `data/paper/model_bench_100`
- Unique markets checked: 15
- Status CSV: `data/paper/resolution_status/model_bench_100/market_resolution_status.csv`
- Conservative resolution CSV: `data/paper/resolution_status/model_bench_100/resolutions.csv`
- Manifest: `data/paper/resolution_status/model_bench_100/resolution_manifest.json`

## Result

- Official `closed=true` markets: 0
- Resolution-eligible rows written: 0
- Near-binary but still open markets: 3
- Near-binary, still-open, and disputed markets: 1

Near-binary but still-open markets are not used for settlement replay:

| market_id | conservative outcome from prices | reason |
|---|---|---|
| 1707932 | NO | `market_not_closed` |
| 1808970 | NO | `market_not_closed` |
| 2308197 | YES | `market_not_closed`; Gamma status also showed `umaResolutionStatus=disputed` |

The conservative rule is intentional: a market is written to `resolutions.csv` only when Gamma reports `closed=true`, the binary outcome is unambiguous from outcome prices, and a resolution timestamp is available.

The conservative binary threshold is inherited from the collector: YES is accepted only when YES price is at least 0.999 and NO price is at most 0.001; NO is accepted only under the symmetric condition. Gamma reads use the project `fetch_json` helper, which uses `certifi` CA support when available and retries transient fetch failures.

Policy details:

- Markets with `closed=false` are never written to `resolutions.csv`, even if prices are near 0/1.
- Disputed markets are never forced into settlement while `closed=false`.
- Missing Gamma market rows are retained in the status CSV with `missing_gamma_market` and are not eligible.
- Multi-outcome or non-binary markets are not accepted by the conservative binary outcome check.
- If Gamma API schema or fetch behavior changes, the cycle should be treated as failed rather than silently fabricating a resolution.

## Replay Check

The 100-row blind model was replayed with the generated `resolutions.csv`:

- Benchmark: `next_model_blind_100_official_resolution_check`
- Resolutions loaded: 0
- Positions opened: 9
- Positions closed: 0
- Open positions: 9
- Realized P&L: 0.00
- Mark equity: 46.07

Because no market is officially `closed=true` yet, this replay matches the prior no-resolution exposure result. The next resolution check should be rerun after Polymarket officially closes the near-binary markets.

This live forward check does not prove realized P&L settlement on the forward sample because `resolutions_loaded=0`. The settlement path itself is covered by unit tests with a non-empty `resolutions.csv` and by the resolved-market oracle smoke in `docs/settled_pnl_smoke_20260531.md`.

The first production E2E settlement evidence for this forward sample will only exist after at least one checked market becomes `closed=true` and the cycle runs with `replay_ran=true`.

## Repeatable Cycle

A repeatable resolution replay cycle is available:

- Cycle manifest: `data/paper/resolution_status/model_bench_100/latest_resolution_replay_cycle.json`
- Latest cycle result: `replay_ran=false`
- Skip reason: `no_closed_resolution_eligible_markets`

The cycle first refreshes Gamma resolution status, writes conservative `resolutions.csv`, and runs model replay only if at least one officially closed resolution is eligible. This keeps recurring checks from producing duplicate no-op replay folders while markets are still open.

## Commands

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
