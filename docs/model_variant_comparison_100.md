# Model Variant Comparison

Generated: 2026-06-01T18:41:10.081961+00:00

This report compares paper-only benchmark manifests. It is not a live-trading approval.

## Current Gate

- Strategy readiness decision: `NO_LIVE_TRADING`
- Blockers: `5`

## Variants

| rank | benchmark | rows | provider | mark equity | return | vs baseline | MDD | opened | closed | open | echo <=1bp | decision | risk flags |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | `rule_baseline_100` | 100 | rule_baseline | 50.0000 | 0.00% | 0.00% | 0.00% | 0 | 0 | 0 | 100.00% | `NO_LIVE_TRADING` | `no_trades;no_closed_trades;market_echo` |
| 2 | `next_model_blind_100` | 100 | agy | 46.0714 | -7.86% | -7.86% | 9.43% | 9 | 0 | 9 | 0.00% | `NO_LIVE_TRADING` | `loss_vs_initial;under_baseline;open_positions;no_closed_trades;no_official_resolutions` |
| 3 | `next_model_blind_100_exit_edge` | 100 | agy | 46.0714 | -7.86% | -7.86% | 9.43% | 9 | 0 | 9 | 0.00% | `NO_LIVE_TRADING` | `loss_vs_initial;under_baseline;open_positions;no_closed_trades;no_official_resolutions` |
| 4 | `next_model_blind_100_official_resolution_check` | 100 | agy | 46.0714 | -7.86% | -7.86% | 9.43% | 9 | 0 | 9 | 0.00% | `NO_LIVE_TRADING` | `loss_vs_initial;under_baseline;open_positions;no_closed_trades;no_official_resolutions` |
| 5 | `next_model_blind_100_forced_exit` | 100 | agy | 44.6905 | -10.62% | -10.62% | 12.23% | 29 | 25 | 4 | 0.00% | `NO_LIVE_TRADING` | `loss_vs_initial;under_baseline;open_positions;no_official_resolutions` |

## Interpretation

- A no-trade or market-echo baseline can rank above an active model if the active model loses money.
- `NO_LIVE_TRADING` on any row means that variant still fails one or more paper-safety conditions.
- Oracle settlement smoke is intentionally excluded from this model-variant table because it uses resolved outcomes.
