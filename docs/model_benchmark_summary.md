# Model Benchmark Summary

This table compares forecast-file audit results and matching survival replay results. It is a pipeline and model-output quality screen, not investment advice.

Rows are ranked by audit pass, survival state, source coverage, lower forecast cost, then path. This is a quality screen, not a return ranking.

| rank | benchmark | provider | model | audit | coverage | echo <=1bp | actionable | brier | resolved | excluded | cost | survival | initial | mark equity | mark P&L | calls | opened | open | risk flags |
|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | agy_smoke/imported | agy | Gemini 3.5 Flash High via agy | PASS | 100.00% | 100.00% | 0 | n/a | 0 | 20 | 0.0000 | ALIVE | 50.00 | 50.00 | 0.00 | 20 | 0 | 0 | no_trades;market_echo;no_actionable_edges |
| 2 | model_bench_20/rule_baseline | rule_baseline | rule_baseline_midpoint | PASS | 100.00% | 100.00% | 0 | n/a | 0 | 20 | 0.0000 | ALIVE | 50.00 | 50.00 | 0.00 | 20 | 0 | 0 | no_trades;market_echo;no_actionable_edges |
| 3 | next_model_blind_smoke/imported | agy | Gemini 3.5 Flash High via agy blind | PASS | 100.00% | 0.00% | 11 | n/a | 0 | 20 | 0.0000 | ALIVE | 50.00 | 48.76 | -1.24 | 20 | 7 | 7 | open_positions;loss |

## Notes

- `audit_status=PASS` means the forecast file has full source-row coverage, valid probabilities/costs, and matching input hashes.
- `missing_survival` means a forecast file exists but no matching replay report was found for its model label.
- `survival_row_mismatch` means a same-label survival report exists, but its row count or forecast-call count does not match the audit file.
- `multi_provider_counts` and `multi_model_counts` require explicit manifest labels before model-to-survival matching can be trusted.
- `market_echo` means most forecasts are effectively the YES bid/ask midpoint; that is useful for plumbing but weak evidence of independent predictive signal.
- `actionable` counts forecasts whose YES or NO edge crosses the configured strategy threshold before liquidity and portfolio constraints.
- `brier` is the mean squared error between `fair_yes` and resolved YES/NO outcomes when official outcomes are present; `resolved=0` is rendered as `n/a` because calibration is not yet measurable.
- `excluded` counts unresolved or invalid rows omitted from Brier/calibration scoring. Calibration bins are written to each benchmark's `latest_diagnostics.json`.
- `cost` is forecast/model cost from the imported forecast file; it is not gas, exchange fees, or order-execution slippage.
- `calls` is the number of forecast lookups consumed by the replay; `opened` and `open` are opened positions and positions still unresolved at replay end.
- `mark equity` is cash plus open-position mark value at the replay engine's effective bid price, using the last valid bid when configured. Treat it as provisional when `open > 0` because unresolved exposure can still move before market resolution.
- `mark P&L` is `mark equity - initial`; `loss` and `open_positions` indicate the replay ended below starting bankroll or with unresolved exposure.
- `no_trades` is not automatically bad in a smoke test; it means the imported fair values did not cross the strategy's edge threshold.
- Use full-history runs, not 20-row smoke subsets, for ROI and drawdown claims.
