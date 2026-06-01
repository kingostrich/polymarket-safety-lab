# Codex for Open Source Application Notes

This document keeps the project positioning consistent for the Codex for Open Source application.

## Repository

https://github.com/kingostrich/polymarket-ai-trading-agent

## Role

Primary maintainer

## Interest Areas

- API credits
- Codex Security

## Project Fit Draft

This repository is an open-source, paper-only prediction-market research scaffold for Polymarket. It provides reproducible market-data ingestion, forecast auditing, survival/backtest accounting, official-resolution replay, and explicit NO_LIVE_TRADING safety gates. It helps developers evaluate model-based forecasts without private keys, signing, or live orders. The project is early but targets an under-served OSS niche: transparent safety infrastructure for prediction-market AI agents.

The repository name reflects the original research direction around prediction-market agents. The implementation has intentionally been narrowed into a safety lab and backtesting simulator with no live order execution, signing, private-key loading, or asset movement.

## API Credits Usage Draft

Credits will be used to benchmark model-generated Polymarket forecasts across identical paper-trading rows and prompt templates, then audit bias, calibration, and risk-report quality through the simulator. They will also support maintainer automation: PR review, issue triage, release notes, benchmark summaries, and documentation. No credits will be used for live order execution, signing, private-key workflows, or investment advice.

## Weaknesses To Address Before Applying

- The repository is new and has no external stars or downloads yet.
- The project needs public issues, an alpha release, and clearer contributor onboarding.
- Financial-risk perception must be managed by emphasizing paper-only safety infrastructure.

## Submission Timing

Default recommendation: apply after 7 to 14 days of public maintenance, at least one alpha release, and several clean issues.

Faster path: apply after README, license, security policy, contribution guide, public issues, and an alpha release are all visible on GitHub.
