# Multi-Leg Portfolio Risk Schema

This project remains paper-only. The portfolio schema validator checks grouped prediction-market exposure before a strategy-readiness report can advance. It does not place orders, sign messages, touch wallets, or move assets.

Use this when a forecast strategy opens related YES/NO legs across overlapping markets, hedges a primary thesis with another contract, or evaluates a portfolio instead of isolated single-market positions.

## JSON Shape

```json
{
  "portfolio_id": "candidate_hedge_v1",
  "groups": [
    {
      "group_id": "overlapping_election_markets",
      "description": "Paper-only example for related prediction-market legs.",
      "max_joint_notional": 25,
      "max_correlation": 0.9,
      "legs": [
        {
          "market_id": "market-candidate-a-wins",
          "side": "YES",
          "max_notional": 10,
          "hedge_role": "primary",
          "correlation": 0.8
        },
        {
          "market_id": "market-candidate-b-wins",
          "side": "NO",
          "max_notional": 12,
          "hedge_role": "hedge",
          "correlation": -0.7
        }
      ]
    }
  ]
}
```

Required rules:

- `portfolio_id` must be present.
- `groups` must contain at least one group.
- Each group must contain at least two legs.
- `max_joint_notional` must be positive.
- Each leg must have a unique `market_id` inside its group.
- `side` must be `YES` or `NO`.
- `max_notional` must be positive.
- `correlation` must be between `-1` and `1`.
- `max_correlation` must be between `0` and `1`.
- A leg's absolute correlation may not exceed its group `max_correlation`.
- Active exposure is treated as absolute notional risk when checking leg and group caps.
- Individual leg caps may sum above `max_joint_notional`; this supports flexible allocation, while the active joint exposure must remain below the group cap.

## Validate A Spec

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.portfolio_schema \
  --spec docs/examples/portfolio_hedge_example.json \
  --out-json data/paper/portfolio_risk_report.json
```

The same command is available after package installation:

```bash
pmlab-portfolio-validate \
  --spec docs/examples/portfolio_hedge_example.json \
  --out-json data/paper/portfolio_risk_report.json
```

## Validate Active Exposure

The optional exposure file can be either a direct market-to-notional object or a wrapper containing `market_exposures`.

```json
{
  "market_exposures": {
    "market-candidate-a-wins": 8,
    "market-candidate-b-wins": 7
  }
}
```

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.portfolio_schema \
  --spec docs/examples/portfolio_hedge_example.json \
  --exposures-json data/paper/example_market_exposures.json \
  --out-json data/paper/portfolio_risk_report.json
```

## Readiness Gate Integration

Pass the portfolio risk report into the conservative readiness gate:

```bash
PYTHONPATH=src .venv/bin/python -m polymarket_backtest.strategy_readiness \
  --portfolio-risk-manifest data/paper/portfolio_risk_report.json
```

If the report contains any portfolio-level violation, the readiness gate fails `portfolio_joint_exposure` and keeps `decision=NO_LIVE_TRADING`.

If the portfolio report is omitted, the readiness gate also fails `portfolio_joint_exposure`. This keeps missing portfolio-risk evidence from looking equivalent to a clean pass.

## Current Limit

This is the schema and safety-gate foundation for multi-leg work. It does not yet simulate concurrent grouped execution, compute hedge offsets, or optimize hedge sizing. Those features should remain separate paper-only follow-up work so the risk contract stays reviewable.
