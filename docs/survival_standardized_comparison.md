# Survival Strategy Comparison

Screening rank is a review heuristic: ALIVE before DEAD, scenarios with opened positions before no-trade baselines, higher ROI, then lower event MDD. It is not an investment recommendation.

| rank | scenario | run | state | ROI | event MDD | forecast calls | opened | open | entry skips | partial entries | exit skips | unfilled exit | slippage cost | risk flags |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | standardized/synthetic_entry_depth | 20260530T025121Z | ALIVE | -7.57% | 7.57% | 154 | 10 | 10 | 0 | 0 | 0 | 0.00 | 0.0000 | open_positions |
| 2 | standardized/synthetic_no_depth | 20260530T025121Z | ALIVE | -7.57% | 7.57% | 154 | 10 | 10 | 0 | 0 | 0 | 0.00 | 0.0000 | open_positions |
| 3 | standardized/synthetic_exit_bid_depth | 20260530T025121Z | ALIVE | -7.87% | 7.87% | 154 | 11 | 10 | 0 | 0 | 10 | 18.04 | 0.0000 | open_positions;exit_liquidity;unfilled_exit |
| 4 | standardized/synthetic_slippage_event | 20260530T025139Z | ALIVE | -7.90% | 7.90% | 154 | 11 | 10 | 0 | 0 | 10 | 18.03 | 0.0159 | open_positions;exit_liquidity;unfilled_exit;slippage_cost |
| 5 | standardized/synthetic_full_constraints_event | 20260530T025139Z | ALIVE | -9.96% | 9.96% | 104 | 11 | 10 | 0 | 0 | 10 | 18.00 | 0.0158 | open_positions;exit_liquidity;unfilled_exit;slippage_cost |
| 6 | standardized/synthetic_full_constraints_timestamp_close | 20260530T025139Z | ALIVE | -9.96% | 9.96% | 104 | 11 | 10 | 0 | 0 | 10 | 18.00 | 0.0158 | open_positions;exit_liquidity;unfilled_exit;slippage_cost |
| 7 | standardized/external_import_smoke_rule_baseline | 20260530T030814Z | ALIVE | 0.00% | 0.00% | 154 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.0000 | no_trades |
| 8 | standardized/rule_baseline | 20260530T025121Z | ALIVE | 0.00% | 0.00% | 154 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.0000 | no_trades |
| 9 | standardized/rule_baseline_forecast_file | 20260530T025951Z | ALIVE | 0.00% | 0.00% | 154 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.0000 | no_trades |

## Interpretation Notes

- `screening_rank` is for active-strategy review triage only. It does not prove a deployable strategy.
- Use `--rank-mode performance` when you want no-trade baselines and lower-loss runs to appear according to financial outcome rather than active-strategy debugging priority.
- Prefer `event_max_drawdown` for conservative risk review; `timestamp_close_max_drawdown` can hide intra-timestamp stress.
- `legacy_mdd` and `missing_fields` rows are weaker evidence because older reports lack some modern risk fields.
- `open_positions`, `exit_liquidity`, `unfilled_exit`, `entry_liquidity`, `partial_entry`, `partial_exit`, and `slippage_cost` indicate execution-risk areas that require deeper event-level review.
- Current depth and slippage models are top-3 aggregate approximations, not full order-book market-impact simulations.
- Current forward logs are short samples; use this table to choose the next stress tests, not to infer live-trading performance.
