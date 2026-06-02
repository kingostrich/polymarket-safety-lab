# Security Policy

## Supported Scope

This repository currently supports a paper-only research scaffold. It does not support live trading, private-key handling, wallet signing, or asset movement.

## Reporting a Vulnerability

For sensitive security reports, use GitHub Private Vulnerability Reporting if it is available for this repository:

https://github.com/kingostrich/polymarket-safety-lab/security/advisories/new

Do not post exploit details, secrets, private account information, or vulnerability proof-of-concepts in public issues.

For non-sensitive hardening requests, documentation fixes, or safety-boundary questions, use a normal GitHub issue.

## Sensitive Data Rules

Never commit:

- API keys or bearer tokens.
- Wallet private keys, seed phrases, or signing material.
- Brokerage or exchange credentials.
- Account numbers, tax records, or private transaction exports.
- Full private model prompts that contain confidential data.

## Safety Expectations

- New functionality must preserve paper-only defaults.
- Code paths that could enable live execution must be isolated, disabled by default, and explicitly reviewed before being considered.
- Do not add Web3 signing libraries, private-key loaders, exchange/broker order execution, or production order-submission SDK paths without a separate security design review.
- Readiness reports are safety evidence, not investment advice or production approval.
- Model forecasts must be auditable and reproducible before being used in benchmark claims.

## Security Tooling

- GitHub Actions runs unit tests, lint, and package-build checks on protected branches.
- CodeQL is configured for Python static analysis.
- Dependabot is configured for Python package and GitHub Actions update checks.
- Pull requests that affect CI/CD, packaging, forecast import, benchmark reports, readiness gates, settlement replay, or policy should use `docs/security_review_checklist.md`.

## Current Live-Trading Status

`NO_LIVE_TRADING`

The current project state is suitable for research, paper logging, forecast auditing, and backtesting only.
