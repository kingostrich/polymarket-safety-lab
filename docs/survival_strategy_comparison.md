# Survival Strategy Comparison

Screening rank is a review heuristic: ALIVE before DEAD, scenarios with opened positions before no-trade baselines, higher ROI, then lower event MDD. It is not an investment recommendation.

| rank | scenario | run | state | ROI | event MDD | forecast calls | opened | open | entry skips | partial entries | exit skips | unfilled exit | slippage cost | risk flags |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | survival_synthetic | 20260527T144020Z | ALIVE | -5.84% | 6.37% | 0 | 10 | 10 | 0 | 0 | 0 | 0.00 | 0.0000 | legacy_mdd;open_positions;missing_fields |
| 2 | survival_synthetic_depth | 20260527T232040Z | ALIVE | -5.84% | 6.37% | 0 | 10 | 10 | 0 | 0 | 0 | 0.00 | 0.0000 | legacy_mdd;open_positions;missing_fields |
| 3 | standardized/synthetic_entry_depth | 20260530T025121Z | ALIVE | -7.57% | 7.57% | 154 | 10 | 10 | 0 | 0 | 0 | 0.00 | 0.0000 | open_positions |
| 4 | standardized/synthetic_no_depth | 20260530T025121Z | ALIVE | -7.57% | 7.57% | 154 | 10 | 10 | 0 | 0 | 0 | 0.00 | 0.0000 | open_positions |
| 5 | standardized/synthetic_exit_bid_depth | 20260530T025121Z | ALIVE | -7.87% | 7.87% | 154 | 11 | 10 | 0 | 0 | 10 | 18.04 | 0.0000 | open_positions;exit_liquidity;unfilled_exit |
| 6 | survival_synthetic_exit_bid_depth | 20260527T234802Z | ALIVE | -7.87% | 7.87% | 0 | 11 | 10 | 0 | 0 | 10 | 18.04 | 0.0000 | legacy_mdd;mixed_history;open_positions;exit_liquidity;unfilled_exit;missing_fields |
| 7 | survival_synthetic_partial_entry_exit_depth | 20260527T235559Z | ALIVE | -7.87% | 7.87% | 0 | 11 | 10 | 0 | 0 | 10 | 18.04 | 0.0000 | legacy_mdd;open_positions;exit_liquidity;unfilled_exit;missing_fields |
| 8 | standardized/synthetic_slippage_event | 20260530T025139Z | ALIVE | -7.90% | 7.90% | 154 | 11 | 10 | 0 | 0 | 10 | 18.03 | 0.0159 | open_positions;exit_liquidity;unfilled_exit;slippage_cost |
| 9 | survival_synthetic_last_valid_bid | 20260528T001651Z | ALIVE | -7.90% | 7.90% | 0 | 11 | 10 | 0 | 0 | 10 | 18.03 | 0.0159 | legacy_mdd;open_positions;exit_liquidity;unfilled_exit;slippage_cost;missing_fields |
| 10 | survival_synthetic_slippage | 20260528T000914Z | ALIVE | -7.90% | 7.90% | 0 | 11 | 10 | 0 | 0 | 10 | 18.03 | 0.0159 | legacy_mdd;open_positions;exit_liquidity;unfilled_exit;slippage_cost;missing_fields |
| 11 | standardized/synthetic_full_constraints_event | 20260530T025139Z | ALIVE | -9.96% | 9.96% | 104 | 11 | 10 | 0 | 0 | 10 | 18.00 | 0.0158 | open_positions;exit_liquidity;unfilled_exit;slippage_cost |
| 12 | standardized/synthetic_full_constraints_timestamp_close | 20260530T025139Z | ALIVE | -9.96% | 9.96% | 104 | 11 | 10 | 0 | 0 | 10 | 18.00 | 0.0158 | open_positions;exit_liquidity;unfilled_exit;slippage_cost |
| 13 | survival_synthetic_actionable_forecasts | 20260529T115920Z | ALIVE | -9.96% | 9.96% | 104 | 11 | 10 | 0 | 0 | 10 | 18.00 | 0.0158 | legacy_mdd;open_positions;exit_liquidity;unfilled_exit;slippage_cost;missing_fields |
| 14 | survival_synthetic_history_first | 20260529T120623Z | ALIVE | -9.96% | 9.96% | 104 | 11 | 10 | 0 | 0 | 10 | 18.00 | 0.0158 | legacy_mdd;open_positions;exit_liquidity;unfilled_exit;slippage_cost;missing_fields |
| 15 | survival_synthetic_position_first | 20260529T124651Z | ALIVE | -9.96% | 9.96% | 104 | 11 | 10 | 0 | 0 | 10 | 18.00 | 0.0158 | legacy_mdd;open_positions;exit_liquidity;unfilled_exit;slippage_cost;missing_fields |
| 16 | survival_synthetic_timestamp_close | 20260530T023618Z | ALIVE | -9.96% | 9.96% | 104 | 11 | 10 | 0 | 0 | 10 | 18.00 | 0.0158 | open_positions;exit_liquidity;unfilled_exit;slippage_cost |
| 17 | survival_synthetic_always_forecasts | 20260529T115603Z | ALIVE | -10.96% | 10.96% | 154 | 11 | 10 | 0 | 0 | 10 | 18.00 | 0.0158 | legacy_mdd;open_positions;exit_liquidity;unfilled_exit;slippage_cost;missing_fields |
| 18 | survival_synthetic_exit | 20260527T144805Z | ALIVE | -35.78% | 35.78% | 0 | 65 | 6 | 0 | 0 | 0 | 0.00 | 0.0000 | legacy_mdd;mixed_history;open_positions;missing_fields |
| 19 | standardized/rule_baseline | 20260530T025121Z | ALIVE | 0.00% | 0.00% | 154 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.0000 | no_trades |
| 20 | survival_rule_baseline | 20260527T233546Z | ALIVE | 0.00% | 0.00% | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.0000 | no_trades;legacy_mdd;missing_fields |
| 21 | survival_rule_baseline_depth | 20260527T232040Z | ALIVE | 0.00% | 0.00% | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.0000 | no_trades;legacy_mdd;missing_fields |
| 22 | survival | 20260527T233546Z | DEAD | -100.00% | 100.00% | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.0000 | dead;no_trades;legacy_mdd;mixed_history;missing_fields |
| 23 | survival_death_test | 20260527T144028Z | DEAD | -100.00% | 100.00% | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.0000 | dead;no_trades;legacy_mdd;missing_fields |

## Interpretation Notes

- `screening_rank` is for review triage only. It does not prove a deployable strategy.
- Prefer `event_max_drawdown` for conservative risk review; `timestamp_close_max_drawdown` can hide intra-timestamp stress.
- `legacy_mdd` and `missing_fields` rows are weaker evidence because older reports lack some modern risk fields.
- `open_positions`, `exit_liquidity`, `unfilled_exit`, `entry_liquidity`, `partial_entry`, `partial_exit`, and `slippage_cost` indicate execution-risk areas that require deeper event-level review.
- Current depth and slippage models are top-3 aggregate approximations, not full order-book market-impact simulations.
- Current forward logs are short samples; use this table to choose the next stress tests, not to infer live-trading performance.
