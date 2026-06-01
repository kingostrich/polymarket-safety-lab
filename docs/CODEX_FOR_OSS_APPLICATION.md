# Codex for Open Source Application Notes

This document keeps the project positioning consistent for the Codex for Open Source application.

## Repository

https://github.com/kingostrich/polymarket-safety-lab

## Role

Primary maintainer

## Interest Areas

- API credits
- Codex Security

## Project Fit Draft

This repository is an open-source, paper-only prediction-market research scaffold for Polymarket. It provides reproducible market-data ingestion, forecast auditing, survival/backtest accounting, official-resolution replay, and explicit NO_LIVE_TRADING safety gates. It helps developers evaluate model-based forecasts without private keys, signing, or live orders. The project is early but targets an under-served OSS niche: transparent safety infrastructure for prediction-market AI agents.

The repository was renamed from its original trading-agent research name to make the current scope explicit. The implementation is a safety lab and backtesting simulator with no live order execution, signing, private-key loading, or asset movement.

## API Credits Usage Draft

Credits will be used to benchmark model-generated Polymarket forecasts across identical paper-trading rows and prompt templates, then audit bias, calibration, and risk-report quality through the simulator. They will also support maintainer automation: PR review, issue triage, release notes, benchmark summaries, and documentation. No credits will be used for live order execution, signing, private-key workflows, or investment advice.

## Weaknesses To Address Before Applying

- The repository is new and has no external stars or downloads yet.
- The project currently has low public adoption signals, so the application should not imply broad usage.
- The project needs at least one follow-up alpha release and at least one closed issue that demonstrates real maintenance after publication.
- Financial-risk perception must be managed by emphasizing paper-only safety infrastructure.
- The repository was renamed to reduce live-trading confusion, but the application should still clarify that the project is paper-only safety and backtesting infrastructure.

## Submission Timing

Default recommendation: apply after 14 days of public maintenance, at least two alpha releases, and at least one clean issue closed by code or documentation work.

Faster path: apply after README, license, security policy, contribution guide, public issues, and an alpha release are all visible on GitHub.

Recommended application date if there is no deadline pressure: 2026-06-15 or later.

## Pre-Submission Evidence Checklist

- README includes a clone-to-result quickstart.
- `docs/quickstart_walkthrough.md` validates the included sample dataset and runs the local paper backtest.
- `docs/safety_gate_spec.md` defines the `NO_LIVE_TRADING` blockers and paper bankroll-depletion stop condition.
- At least one public issue is closed after visible implementation work.
- A follow-up alpha release documents the paper-only status and recent hardening work.
- Local verification passes:
  - `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests`
  - `PYTHONPATH=src .venv/bin/python -m compileall src tests`
  - `PYTHONPATH=src .venv/bin/python -m polymarket_backtest.paper_gate_cycle`

## Application Evidence Links To Include

- Repository: https://github.com/kingostrich/polymarket-safety-lab
- Latest alpha release: update this after the follow-up release.
- Quickstart walkthrough: `docs/quickstart_walkthrough.md`
- Safety gate spec: `docs/safety_gate_spec.md`
- Readiness gate report: `docs/strategy_readiness_gate.md`
- Model benchmark evidence: `docs/model_variant_comparison_100.md`
