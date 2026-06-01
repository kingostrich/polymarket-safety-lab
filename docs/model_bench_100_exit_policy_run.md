# 100-Row Exit Policy Probe

Date: 2026-05-31

This probe tests whether the survival engine can exercise early-exit accounting for the same 100-row blind model benchmark. It is an execution-mechanics check, not investment advice.

## Scenarios

| scenario | exit policy | exit threshold | mark equity | mark P&L | realized P&L | opened | closed | open | note |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| no exit | none | n/a | 46.07 | -3.93 | 0.00 | 9 | 0 | 9 | exposure-only baseline |
| edge exit | edge_below | 0.08 | 46.07 | -3.93 | 0.00 | 9 | 0 | 9 | no hold edge fell below threshold |
| forced exit probe | edge_below | 1.00 | 44.69 | -5.31 | -2.18 | 29 | 25 | 4 | validates exit accounting path |

## Evidence

- Exit summary: `docs/model_bench_100_exit_performance_summary.md`
- No-exit event summary: `docs/next_model_blind_100_event_summary.md`
- Forced-exit event summary: `docs/next_model_blind_100_forced_exit_event_summary.md`
- Forced-exit survival report: `data/paper/model_bench_100_survival_next_model_blind_100_forced_exit/latest_survival_report.json`
- Forced-exit event log: `data/paper/model_bench_100_survival_next_model_blind_100_forced_exit/latest_survival_events.csv`

## Interpretation

The standard `edge_below=0.08` exit rule did not close any positions on this sample. That means the existing model forecasts did not create an exit signal under the configured hold-edge threshold during the short observation window.

The forced-exit probe with `edge_below=1.00` did exercise the exit path: it opened 29 positions, closed 25, left 4 open, and produced realized P&L of -2.18 with mark P&L of -5.31. This confirms that exit accounting can run through the benchmark wrapper, but it also shows that aggressive churn worsened the result on this sample.

The larger `opened` count in the forced-exit scenario is expected from capital recycling, not a separate entry-filter change: the event summary shows 9 unique opened markets, 7 markets reopened after prior exits, and 20 repeated open events after prior opens. In the no-exit run, the same 9 unique markets opened once and then produced 45 existing-position skips.

`mark P&L` is ending mark-to-market equity minus initial bankroll and therefore includes both realized cash changes and remaining open-position marks. `realized P&L` includes only closed/settled positions. The forced-exit scenario still has 4 open positions, so its mark P&L remains partly unrealized.

The correct next data step is not to tune the exit threshold on this tiny sample. It is to collect or import enough post-entry observations and resolved outcomes so `hold_to_resolution`, realistic early exit, and forced liquidation can be compared on settled P&L.
