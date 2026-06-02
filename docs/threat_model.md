# Threat Model

This repository is a paper-only prediction-market research scaffold. The primary risk is that research artifacts could be mistaken for live-trading approval or investment advice.

## Assets To Protect

- Private keys, seed phrases, wallet credentials, and brokerage credentials.
- Private financial records and personally identifying transaction data.
- Integrity of benchmark inputs, forecast files, manifests, and readiness reports.
- Safety-boundary clarity: no live trading, no signing, no asset movement.

## Non-Negotiable Boundaries

- No live order placement.
- No wallet signing.
- No private-key or seed phrase loading.
- No asset movement.
- No investment-advice claims.

## Main Threats

### Live Execution Drift

Risk: a future change adds production order submission, signing dependencies, or private-key loaders under the appearance of a normal backtesting feature.

Controls:
- `SECURITY.md`, `CONTRIBUTING.md`, README, and PR template require explicit safety-boundary checks.
- Default dependencies exclude Web3 signing and production order-submission SDKs.
- Any execution/signing path requires a separate security design review before consideration.

### Forecast Overclaiming

Risk: model forecasts are presented as predictive alpha before official resolutions, calibration, or baseline comparisons exist.

Controls:
- Forecast import requires stable keys and input hashes.
- Readiness gates fail closed when evidence is missing.
- Benchmark summaries mark unresolved Brier scores as `n/a`.
- Reports state that they are not investment advice.

### Lookahead Bias

Risk: resolved outcomes or oracle smoke fixtures leak into predictive benchmark claims.

Controls:
- Oracle settlement smoke is labeled as accounting-only.
- Model-variant comparisons exclude oracle smoke from live-readiness claims.
- Official-resolution replay is separated from forecast generation.

### Market-Data Integrity

Risk: stale, malformed, or inconsistent paper rows produce misleading replay results.

Controls:
- Sample snapshot validation checks required columns, timestamps, market IDs, probabilities, resolved outcomes, and fee rates.
- Forecast audit checks source-row coverage, duplicate keys, input-hash mismatches, invalid probabilities, invalid costs, and provider/model labels.

### External Model Output Risk

Risk: an external model emits malformed rows, hidden commentary, or probabilities that simply echo market midpoint without useful signal.

Controls:
- Model outputs are imported through explicit schemas.
- Diagnostics flag market echo and missing resolved outcomes.
- Calibration metrics are computed only for resolved rows.

## Residual Risks

- Paper replay cannot fully model live liquidity, queue priority, order-book changes, fees, geographic restrictions, or market impact.
- Community users may still misunderstand financial reports unless docs remain conservative.
- Early OSS adoption is low, so external validation is still limited.

## Review Triggers

Request additional security review for changes touching:

- CI/CD, packaging, dependency manifests, or GitHub security settings.
- Forecast import, benchmark reports, readiness gates, or settlement replay.
- Any authentication, signing, wallet, exchange, broker, or live-market integration.
