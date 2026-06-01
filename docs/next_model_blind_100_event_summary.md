# Survival Event Summary

This summarizes replay events for exposure debugging only. It is not investment advice.

- Events: 54
- Event counts: {'OPEN_POSITION': 9, 'SKIP_EXISTING_POSITION': 45}
- Positions opened: 9
- Position-close/settlement events: 0
- Existing-position skips: 45
- Unique opened markets: 9
- Markets reopened after exit: 0
- Repeated open events after prior opens: 0
- Gross opened notional: 21.3503
- Gross opened notional / min event equity: 47.15%
- Mean open edge: 0.2809
- Mean entry price: 0.3457
- Min event equity: 45.2858
- Final event equity: 46.0714

## Open Positions

| timestamp | market_id | side | edge | cost | entry price | equity after |
|---|---|---|---:|---:|---:|---:|
| 2026-05-27T12:55:08.977387+00:00 | 1809560 | YES | 0.1850 | 3.0000 | 0.0150 | 49.8000 |
| 2026-05-27T12:55:08.977387+00:00 | 1831356 | NO | 0.2330 | 2.8200 | 0.4670 | 49.4618 |
| 2026-05-27T12:55:08.977387+00:00 | 1919425 | NO | 0.2190 | 2.6508 | 0.7800 | 49.4279 |
| 2026-05-27T12:55:08.977387+00:00 | 1962237 | NO | 0.5050 | 2.4918 | 0.4900 | 49.3770 |
| 2026-05-27T12:55:08.977387+00:00 | 2308197 | NO | 0.1420 | 2.3422 | 0.0080 | 49.0842 |
| 2026-05-27T12:55:08.977387+00:00 | 2334107 | NO | 0.3380 | 2.2017 | 0.6600 | 49.0175 |
| 2026-05-27T12:55:08.977387+00:00 | 2354001 | YES | 0.0900 | 2.0696 | 0.1100 | 48.6412 |
| 2026-05-27T13:11:59.683311+00:00 | 2270330 | NO | 0.4170 | 1.9454 | 0.5800 | 48.6893 |
| 2026-05-27T13:21:58.502738+00:00 | 2335278 | YES | 0.3990 | 1.8287 | 0.0010 | 46.2836 |

## Interpretation

If `positions_closed_events` is zero while `skip_existing_position_events` is high, the replay is primarily measuring mark-to-market exposure inside a short observation window rather than settled trade performance.
