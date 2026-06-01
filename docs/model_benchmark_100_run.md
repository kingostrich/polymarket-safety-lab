# 100-Row Blind Model Benchmark Run

Date: 2026-05-30

This run expands the delegated-model check from the 20-row smoke subset to 100 rows from the accumulated forward paper logs. It is still a small paper-trading benchmark and not investment advice.

## Inputs

- Source paper directory: `data/paper/model_bench_100`
- Source records selected: the first 100 time-sorted rows of 154 available forward-log rows
- Template: `data/forecasts/model_bench_100/template.jsonl`
- Blind prompt packet: `data/forecasts/model_bench_100/model_prompt_packet_blind.md`
- Model output: `data/forecasts/next_model_blind_100/model_minimal.jsonl`
- Raw `agy` output: `/tmp/agy_model_bench100_blind_raw.txt`

The blind packet intentionally includes only `logged_at`, `market_id`, `question`, and `input_hash` in each input row. It excludes bid/ask, price, liquidity, volume, and prior fair-value fields to reduce market-midpoint echo.

## Validation

- JSON rows extracted from raw model output: 100
- Extraction manifest: `data/forecasts/next_model_blind_100/model_minimal.jsonl.manifest.json`
- Ignored non-JSON raw lines: 28
- Required keys present: `logged_at`, `market_id`, `input_hash`, `fair_yes`, `cost`, `reasoning`
- Import/audit status: PASS
- Coverage: 100%
- Input hash mismatches: 0
- Invalid probabilities: 0
- Invalid costs: 0
- Forecast/model cost total: 0.0

The raw `agy` response included non-JSON commentary before the forecast rows, so the raw file was preserved and valid JSON object lines were extracted with `polymarket_backtest.model_output_extract` before import.

## Replay Result

- Summary: `docs/next_model_blind_100_summary.md`
- Baseline comparison summary: `docs/model_bench_100_performance_summary.md`
- Exit-policy probe: `docs/model_bench_100_exit_policy_run.md`
- Event exposure summary: `docs/next_model_blind_100_event_summary.md`
- Survival report: `data/paper/model_bench_100_survival_next_model_blind_100/latest_survival_report.json`
- State: ALIVE
- Initial bankroll: 50.00
- Mark equity: 46.07
- Mark P&L: -3.93
- Max drawdown: 9.43%
- Forecast calls: 100
- Actionable rows: 53
- Signals seen: 54
- Positions opened: 9
- Positions closed: 0
- Open positions: 9
- Diagnosis flags: none
- Risk flags: `open_positions;loss`

## Interpretation

The 100-row blind run's diagnostics show `market_echo_share_1bp` at 0.00% on this sample, while actionable rows increased to 53. That is useful for pipeline validation, but it is not enough to prove predictive quality. The replay result is not a profitable signal: the run ended below starting bankroll on mark-to-market equity and with all 9 opened positions still unresolved.

Treat the mark equity as provisional because the survival engine marks open positions at the effective bid price, using last valid bid behavior when configured. A larger full-history test should separate model quality from unresolved-position exposure by adding an explicit exit/expiry handling review and by comparing against the same sample with a no-trade, midpoint, and calibrated baseline.

## Baseline Comparison

The same 100-row sample was replayed with `rule_baseline_midpoint`.

- Quality summary: `docs/model_bench_100_summary.md`
- Performance summary: `docs/model_bench_100_performance_summary.md`
- Baseline audit status: PASS
- Baseline market echo share: 100.00%
- Baseline actionable rows: 0
- Baseline positions opened: 0
- Baseline mark equity: 50.00
- Baseline risk flags: `no_trades;market_echo;no_actionable_edges`

The performance view ranks the no-trade midpoint baseline above the blind model because the blind model opened exposure and ended with negative mark P&L. This does not mean midpoint is a predictive model; it means the blind model has not yet beaten a do-nothing plumbing baseline on this sample.

## Event Exposure

The blind model's no-exit event log contains 54 replay events:

- `OPEN_POSITION`: 9
- `SKIP_EXISTING_POSITION`: 45
- Position close or settlement events: 0
- Gross opened notional: 21.3503
- Gross opened notional / min event equity: 47.15%
- Mean open edge: 0.2809
- Min event equity: 45.2858

The event pattern shows that the run is dominated by positions opened early in a short observation window and then repeatedly skipped as already-open positions. It is therefore an exposure test, not a settled trade-performance test.

## Exit Probe

Two early-exit variants were checked on the same 100-row blind forecasts:

- `edge_below=0.08`: no positions closed; result matched the no-exit run.
- `edge_below=1.00`: forced-exit probe opened 29 positions, closed 25, left 4 open, realized P&L -2.18, and mark P&L -5.31.

The forced-exit probe proves that the benchmark wrapper can exercise the survival engine's exit accounting path. It does not improve the strategy; aggressive churn worsened the result on this sample. The higher opened count comes from re-entry after exits: 9 unique markets opened, 7 markets reopened, and 20 open events were repeats after prior opens.

## Limitations

- The 100 rows are a time-sorted prefix, not a randomized or stratified sample.
- `cost=0.0` is the model forecast cost field. It is not gas, exchange fees, or full real execution cost.
- `slippage_cost_total=0.0` in this replay means the configured depth model did not add entry/exit slippage in this sample; it does not prove live slippage would be zero.
- All 9 opened positions remained open at replay end, so P&L is mark-to-market and not final resolved market P&L.
- Blind forecasts deliberately exclude market state; this tests non-echo behavior, but it does not prove the model has enough evidence to forecast accurately.
