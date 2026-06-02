# Strategy Readiness Gate

Generated: 2026-06-02T06:28:48.616206+00:00

Decision: `NO_LIVE_TRADING`

This gate is a paper-trading safety check. It does not place orders, sign messages, or move assets.

## Summary

- `model_final_equity`: 46.07135674680741
- `baseline_final_equity`: 50.0
- `model_mark_pnl`: -3.9286432531925897
- `model_open_positions`: 9
- `model_positions_closed`: 0
- `official_resolution_eligible`: 0
- `oracle_closed_trades`: 9
- `event_max_drawdown`: 0.09428409946385187

## Checks

| Check | Status | Severity | Observed | Required |
|---|---:|---:|---|---|
| `sample_size` | `PASS` | `blocker` | 100 | >= 100 forward paper rows |
| `beats_no_trade_baseline` | `FAIL` | `blocker` | model=46.0714, baseline=50.0000 | model final equity > no-trade baseline final equity |
| `non_negative_mark_pnl` | `FAIL` | `blocker` | mark_pnl=-3.9286 | mark P&L >= 0 on forward paper benchmark |
| `no_open_positions` | `FAIL` | `blocker` | 9 | 0 open positions after replay |
| `official_forward_resolutions` | `FAIL` | `blocker` | resolutions_loaded=0, resolution_eligible=0, replay_ran=False | at least one official closed forward resolution loaded into replay |
| `closed_trade_count` | `FAIL` | `blocker` | model_closed=0, cycle_closed=0 | >= 30 closed non-oracle forward trades |
| `max_drawdown_under_limit` | `PASS` | `blocker` | 0.0943 | event max drawdown <= 25.00% |
| `portfolio_joint_exposure` | `FAIL` | `blocker` | status=NOT_PROVIDED, violations=0, validation_errors=0 | portfolio risk manifest status PASS with no joint exposure violations |
| `not_market_echo` | `PASS` | `warning` | market_echo_share_1bp=0.0000, actionable_rows=53 | market echo share < 0.5 and actionable_rows > 0 |
| `oracle_smoke_is_accounting_only` | `PASS` | `warning` | oracle_closed_trades=9 | oracle smoke exists and model identity does not contain oracle |

## Blocker Details

- `beats_no_trade_baseline`: A losing active model should not advance toward live trading while a no-trade baseline preserves capital better.
- `non_negative_mark_pnl`: Survival state alone is insufficient; the mark-to-market path must not be loss-making.
- `no_open_positions`: Unsettled open exposure prevents treating the run as a completed performance sample.
- `official_forward_resolutions`: Forward paper settlement must be proven with official closed markets, not only near-binary open markets.
- `closed_trade_count`: A live gate needs enough timestamp-valid closed trades to estimate realized P&L, win rate, and drawdown.
- `portfolio_joint_exposure`: Hedged, correlated, or omitted portfolio-risk evidence prevents readiness from advancing.

## Next Actions

- Continue paper logging and official resolution replay until closed forward trades exist.
- Do not route private keys, signing, live order placement, or asset movement through this scaffold.
- Only compare model variants after each produces timestamp-valid forecasts on the same forward rows.
