# Changelog

## Unreleased

## v0.1.3 - 2026-06-02

- Added resolved-market collection manifest fields that distinguish neutral plumbing data from test-only oracle smoke data.
- Added collected historical dataset validation for conservative binary outcomes and neutral `fair_yes` rows.
- Added same-row benchmark fingerprint evidence to model benchmark manifests.
- Added PR template with explicit paper-only safety boundary checks.
- Added Dependabot and CodeQL configuration.
- Updated GitHub Actions dependencies to current major versions after green CI and CodeQL checks.
- Added threat model and security review checklist.
- Removed static unit-test count from README badges to reduce stale metadata.

## v0.1.2 - 2026-06-01

- Added sample snapshot dataset validation.
- Added Brier score and calibration-bin diagnostics for resolved forecast rows.
- Updated benchmark summaries to render unresolved-only Brier scores as `n/a`.
- Added diagnostics quickstart guidance.

## v0.1.1 - 2026-06-01

- Hardened OSS positioning and package metadata.
- Removed live-trading/provider dependencies from default package requirements.
- Added paper-only quickstart, safety-gate, model-benchmark, and use-case docs.

## v0.1.0 - 2026-06-01

- Added GitHub Actions CI for tests, lint, and package build.
- Added PyPI-oriented project metadata.
- Added issue templates and first stable GitHub release notes.

## v0.1.0-alpha - 2026-06-01

- Prepared the repository as a paper-only prediction-market safety and backtesting scaffold.
- Added baseline OSS documents and initial public release evidence.
