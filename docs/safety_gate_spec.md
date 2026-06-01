# Safety Gate Specification

The project is a paper-only research scaffold. Safety gates block live-readiness claims until the paper evidence is strong enough for a separate human security and market-risk review.

## Non-Negotiable Boundaries

- No live order placement.
- No wallet signing.
- No private-key, seed phrase, or credential loading.
- No asset movement.
- No investment-advice claim.

Any change that adds execution, signing, private-key handling, Web3 order-submission dependencies, or production Polymarket order paths is out of scope for the current repository state.

## Readiness Decision States

- `NO_LIVE_TRADING`: default state. One or more blocker checks failed, evidence is incomplete, or forward paper settlement is not proven.
- `PAPER_ONLY_REVIEW`: blocker checks passed for a paper sample. This is still not live-trading approval; it only means a larger external review can begin.

## Blocker Checks

The readiness gate blocks promotion unless all of these are true:

- Forward paper sample size is at least the configured minimum.
- Active model final equity beats a no-trade baseline.
- Mark-to-market P&L is non-negative.
- Open positions are zero after replay.
- At least one official closed forward resolution is loaded into replay.
- Closed non-oracle forward trade count meets the configured minimum.
- Event-level max drawdown is present and below the configured limit.

Missing numeric fields fail closed. Incomplete manifests must not be interpreted as passing.

## Survival Stop Condition

Paper replay must treat bankroll depletion as terminal for the scenario under test. If cash plus marked value reaches zero or below, the strategy is considered failed for that run and must not open new paper exposure.

This condition exists to test agent behavior under extreme loss assumptions. It is not a live kill switch because this repository does not connect to live execution.

## Evidence Requirements

Before changing the status beyond `NO_LIVE_TRADING`, maintainers must preserve:

- The exact input rows used for the benchmark.
- The forecast file and audit report.
- The survival report, event summary, and readiness report.
- The baseline comparison on the same rows and bankroll.
- The official-resolution replay evidence.

Reports are research artifacts only. They must not be presented as financial advice or production trading approval.
