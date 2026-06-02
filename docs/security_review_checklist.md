# Security Review Checklist

Use this checklist for pull requests that affect CI/CD, packaging, security policy, forecast import, benchmark reports, readiness gates, settlement replay, or financial data pipelines.

## Scope

- [ ] The change is paper-only.
- [ ] No live order placement or production order-submission path was added.
- [ ] No wallet signing, private-key loading, seed phrase handling, or asset movement was added.
- [ ] No dependency was added that enables signing or live execution without explicit review.

## Data And Secrets

- [ ] No API keys, bearer tokens, credentials, private keys, seed phrases, or account exports are committed.
- [ ] External AI review, if used, received only public/sanitized excerpts or diffs.
- [ ] Generated data files do not contain private financial or personally identifying records.

## Forecast And Benchmark Integrity

- [ ] Forecast rows are schema-validated before replay.
- [ ] Input hashes are checked where applicable.
- [ ] Missing official resolutions are not treated as performance evidence.
- [ ] Brier/calibration metrics are computed only on resolved rows.
- [ ] No oracle/lookahead artifact is included in predictive-performance claims.

## Readiness Gates

- [ ] Missing numeric fields fail closed.
- [ ] Open positions, negative mark P&L, missing official resolutions, and under-baseline performance remain blockers.
- [ ] Reports continue to state `NO_LIVE_TRADING` when evidence is incomplete.

## Verification

- [ ] `PYTHONPATH=src python -m pytest tests -q`
- [ ] `ruff check src tests`
- [ ] `python -m build`
- [ ] Generated docs/manifests affected by the change were refreshed or explicitly left unchanged with a reason.
