# Model Benchmark Plan

The model benchmark flow exists to compare forecast quality, calibration, and risk behavior across identical paper-trading rows. It is not a live-trading workflow.

## Minimum Flow

1. Create a fixed paper snapshot subset.
2. Generate a forecast template with stable `logged_at`, `market_id`, and `input_hash` fields.
3. Ask each model provider to fill only `fair_yes`, `cost`, and `reasoning`.
4. Import and audit the model output before replay.
5. Compute forecast diagnostics, including market-echo checks and Brier/calibration metrics when resolved outcomes are available.
6. Replay the same rows, bankroll, slippage assumptions, and safety gates for every provider.
7. Compare returns, drawdown, open exposure, closed-trade count, market-echo behavior, calibration, and baseline performance.

## API Credit Use

API credits would be used for reproducible OSS evaluation tasks:

- Running model forecasts on identical paper rows.
- Summarizing benchmark results and risk reports.
- Auditing PRs that alter benchmark, readiness, or forecast-import logic.
- Improving maintainer docs and issue triage.

Credits must not be used for live order execution, signing, private-key workflows, asset movement, or investment advice.

## Acceptance Criteria

- A benchmark report must identify the provider, model label, source row count, bankroll, forecast cost, and scenario prefix.
- The report must compare against a no-trade or rule baseline on the same rows.
- Resolved-market reports must include Brier score, resolved forecast count, excluded unresolved count, and calibration bins.
- Any model with open positions, missing official resolution replay, negative mark P&L, or worse-than-baseline final equity must remain blocked by the readiness gate.
