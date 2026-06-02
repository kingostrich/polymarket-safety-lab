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
- The project now has follow-up release evidence after packaging, CI hardening, sample validation, calibration diagnostics, resolved-market dataset validation, and same-row model benchmark evidence.
- Financial-risk perception must be managed by emphasizing paper-only safety infrastructure.
- Community discussions are enabled but need more real feedback threads before applying.
- The strongest remaining gap is public adoption evidence, not core code volume.

## Submission Timing

Default recommendation: apply after 14 days of public maintenance, at least two clean releases, and at least one issue closed by visible code or documentation work.

Faster path: apply after README, license, security policy, contribution guide, public issues, and an alpha release are all visible on GitHub.

Recommended application date if there is no deadline pressure: 2026-06-15 or later.

## Pre-Submission Evidence Checklist

- README includes a clone-to-result quickstart and live CI badge.
- GitHub branch protection requires the current CI checks.
- CI validates unit tests, lint, and Python package build.
- `docs/quickstart_walkthrough.md` documents the local sample run.
- `docs/safety_gate_spec.md` defines the `NO_LIVE_TRADING` blockers and paper bankroll-depletion stop condition.
- Public issues #2 and #3 are closed after visible implementation work.
- A follow-up release documents the paper-only status, sample validation, forecast calibration diagnostics, resolved-market dataset validation, and same-row benchmark evidence.
- Security hardening evidence includes CodeQL, Dependabot, a PR template, and a threat model.
- Benchmark docs include same-row fingerprint evidence for current provider comparisons.

## Application Evidence Links To Include

- Repository: https://github.com/kingostrich/polymarket-safety-lab
- Latest release: https://github.com/kingostrich/polymarket-safety-lab/releases/tag/v0.1.3
- Quickstart walkthrough: `docs/quickstart_walkthrough.md`
- Safety gate spec: `docs/safety_gate_spec.md`
- Readiness gate report: `docs/strategy_readiness_gate.md`
- Model benchmark evidence: `docs/model_variant_comparison_100.md`
- Threat model: `docs/threat_model.md`
- Security review checklist: `docs/security_review_checklist.md`

## Go/No-Go Recommendation

Do not submit immediately unless there is a deadline. The preferred application window is still after at least two weeks of visible maintenance and at least one external feedback or contributor interaction. If applying early, be explicit that the project is early and frame the value as an under-served safety infrastructure niche rather than established ecosystem adoption.
