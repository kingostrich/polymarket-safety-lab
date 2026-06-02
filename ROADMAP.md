# Roadmap

This roadmap is focused on open-source research infrastructure, not live trading.

## Near Term: v0.1.3

- Keep generated benchmark/readiness docs synchronized with the current code.
- Add security hardening evidence through CodeQL and Dependabot.
- Add a reproducible demo that runs from clone to paper-only readiness output.
- Expand threat-model documentation for external model forecasts and market-data handling.

## Mid Term: v0.2.0

- Complete a reproducible resolved-market dataset adapter.
- Improve model benchmark reports across identical rows and baselines.
- Add calibration report exports that summarize Brier score, resolved-row counts, excluded rows, and calibration bins.
- Add lightweight visualization or CSV exports for benchmark diagnostics.

## Later

- Support richer prediction-market structures only after the binary-market scaffold is stable.
- Add multi-leg or hedged portfolio simulation behind explicit paper-only gates.
- Add exit-policy parameter sweeps for paper replay.

## Explicitly Out Of Scope

- Live order submission.
- Wallet signing.
- Private-key, seed phrase, or credential loading.
- Asset movement.
- Investment advice or production trading approval.
