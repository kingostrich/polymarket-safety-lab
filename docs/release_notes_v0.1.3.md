# v0.1.3 - paper-only dataset and benchmark evidence hardening

Paper-only release. No live trading, no signing, no private keys, and no asset movement.

## Highlights

- Adds conservative validation for collected resolved binary historical datasets before writing generated CSVs/manifests.
- Extends historical manifests to distinguish neutral plumbing data from test-only oracle settlement smoke evidence.
- Adds same-row `source_rows_fingerprint` evidence to model benchmark manifests and docs so provider comparisons are only made on identical paper rows.
- Refreshes tracked benchmark manifests with fingerprints for current 20-row and 100-row evidence runs.
- Adds PR template, threat model, security review checklist, Dependabot, and CodeQL evidence for OSS safety posture.
- Updates GitHub Actions dependencies after green CI and CodeQL checks.

## Validation

- PR #16, PR #21, and Dependabot PRs #17-#20 passed GitHub Actions and CodeQL.
- Local checks for PR #21 passed: 154 tests, ruff, compileall, package build, twine check, and secret scan.
- Antigravity external review found initial must-fix issues in the dataset/benchmark diff; Codex fixed them, and the re-review found no remaining blocking issues for Issue #2/#3 acceptance.

This remains a research scaffold for paper-trading, backtesting, forecast auditing, and safety gates. It is not investment advice and does not authorize live trading.
