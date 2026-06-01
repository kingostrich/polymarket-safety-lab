# Use Cases

This project is intentionally narrow: it helps developers evaluate prediction-market AI agents in a paper-only environment before any live-trading design is considered.

## AI Agent Developers

Developers can route model forecasts into a deterministic paper replay and inspect whether the model beats a no-trade baseline on identical rows. The repository avoids private keys, signing, and live orders so prompt and model experiments stay separated from execution risk.

## Prediction-Market Researchers

Researchers can compare forecast files, settlement assumptions, slippage settings, drawdown, win rate, and official-resolution replay evidence. The current scripts are designed for reproducible audit trails rather than production execution.

## Safety Reviewers

Reviewers can inspect explicit `NO_LIVE_TRADING` blockers before a strategy is promoted. The default result should remain conservative until enough closed forward paper trades and official resolutions exist.

## Out Of Scope

- Live order execution.
- Wallet signing.
- Private-key handling.
- Asset movement.
- Investment advice or automated portfolio recommendations.
