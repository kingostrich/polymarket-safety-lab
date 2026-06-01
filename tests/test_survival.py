import csv
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from polymarket_backtest.forecast_providers import RecordedForecastProvider, SyntheticEdgeForecastProvider
from polymarket_backtest.models import Side
from polymarket_backtest.survival import (
    Resolution,
    drawdown_curve_for_policy,
    load_paper_rows,
    max_drawdown,
    simulate_survival,
)

FIELDNAMES = [
    "logged_at",
    "market_id",
    "question",
    "yes_ask",
    "no_ask",
    "yes_bid",
    "no_bid",
    "fair_yes",
    "yes_depth_top3",
    "no_depth_top3",
    "yes_bid_depth_top3",
    "yes_ask_depth_top3",
    "no_bid_depth_top3",
    "no_ask_depth_top3",
    "liquidity",
    "volume_24h",
]


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


class SurvivalTest(unittest.TestCase):
    def test_timestamp_close_drawdown_uses_last_mark_per_timestamp(self) -> None:
        timestamp = datetime(2026, 1, 1, tzinfo=UTC)
        event_curve = [100.0, 80.0, 95.0]
        timestamp_marks = [(timestamp, 80.0), (timestamp, 95.0)]

        event_drawdown = max_drawdown(
            drawdown_curve_for_policy(100.0, 95.0, event_curve, timestamp_marks, "event")
        )
        timestamp_close_drawdown = max_drawdown(
            drawdown_curve_for_policy(100.0, 95.0, event_curve, timestamp_marks, "timestamp_close")
        )

        self.assertAlmostEqual(event_drawdown, 0.20)
        self.assertAlmostEqual(timestamp_close_drawdown, 0.05)

    def test_timestamp_close_drawdown_sorts_marks_by_timestamp(self) -> None:
        earlier = datetime(2026, 1, 1, tzinfo=UTC)
        later = datetime(2026, 1, 2, tzinfo=UTC)
        event_curve = [100.0, 70.0, 90.0, 95.0]
        timestamp_marks = [(later, 70.0), (earlier, 90.0), (later, 95.0)]

        curve = drawdown_curve_for_policy(100.0, 95.0, event_curve, timestamp_marks, "timestamp_close")

        self.assertEqual(curve, [100.0, 90.0, 95.0])

    def test_timestamp_close_run_still_reports_event_drawdown(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]

        result, _ = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            drawdown_policy="timestamp_close",
        )

        self.assertEqual(result.drawdown_policy, "timestamp_close")
        self.assertAlmostEqual(result.max_drawdown, result.timestamp_close_max_drawdown)
        self.assertGreaterEqual(result.event_max_drawdown, 0.0)

    def test_invalid_drawdown_policy_raises(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.51",
                "no_ask": "0.50",
                "yes_bid": "0.50",
                "no_bid": "0.49",
                "fair_yes": "0.51",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]

        with self.assertRaisesRegex(ValueError, "unknown drawdown policy"):
            simulate_survival(rows, RecordedForecastProvider(), drawdown_policy="bad")

    def test_recorded_neutral_rows_do_not_open_positions(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.51",
                "no_ask": "0.50",
                "yes_bid": "0.50",
                "no_bid": "0.49",
                "fair_yes": "0.51",
                "yes_depth_top3": "100",
                "no_depth_top3": "100",
                "yes_bid_depth_top3": "100",
                "yes_ask_depth_top3": "100",
                "no_bid_depth_top3": "100",
                "no_ask_depth_top3": "100",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]
        result, events = simulate_survival(rows, RecordedForecastProvider(), initial_bankroll=50)
        self.assertEqual(result.state, "ALIVE")
        self.assertEqual(result.positions_opened, 0)
        self.assertEqual(events, [])

    def test_synthetic_edge_opens_position(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "yes_depth_top3": "100",
                "no_depth_top3": "100",
                "yes_bid_depth_top3": "100",
                "yes_ask_depth_top3": "100",
                "no_bid_depth_top3": "100",
                "no_ask_depth_top3": "100",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]
        result, events = simulate_survival(rows, SyntheticEdgeForecastProvider(edge=0.12), initial_bankroll=50)
        self.assertEqual(result.positions_opened, 1)
        self.assertEqual(events[0].event_type, "OPEN_POSITION")

    def test_top3_liquidity_model_skips_oversized_entry(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "yes_depth_top3": "1",
                "no_depth_top3": "1",
                "yes_bid_depth_top3": "1",
                "yes_ask_depth_top3": "1",
                "no_bid_depth_top3": "1",
                "no_ask_depth_top3": "1",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]
        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            liquidity_model="top3_ask",
            max_depth_fraction=0.25,
        )
        self.assertEqual(result.positions_opened, 0)
        self.assertEqual(result.liquidity_skips, 1)
        self.assertEqual(result.partial_entries, 0)
        self.assertEqual(result.unfilled_entry_notional, 3.0)
        self.assertEqual(events[0].event_type, "SKIP_LIQUIDITY_DEPTH")

    def test_partial_entry_policy_counts_full_skip_unfilled_notional(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "yes_ask_depth_top3": "0",
                "no_ask_depth_top3": "0",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]
        result, _ = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            liquidity_model="top3_ask",
            max_depth_fraction=0.25,
            entry_fill_policy="partial",
        )
        self.assertEqual(result.positions_opened, 0)
        self.assertEqual(result.liquidity_skips, 1)
        self.assertAlmostEqual(result.unfilled_entry_notional, 3.0)

    def test_top3_liquidity_model_partially_enters_when_enabled(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "yes_ask_depth_top3": "4",
                "no_ask_depth_top3": "4",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]
        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            liquidity_model="top3_ask",
            max_depth_fraction=0.25,
            entry_fill_policy="partial",
        )

        self.assertEqual(result.positions_opened, 1)
        self.assertEqual(result.liquidity_skips, 0)
        self.assertEqual(result.partial_entries, 1)
        self.assertAlmostEqual(result.unfilled_entry_notional, 2.5)
        self.assertEqual(events[0].event_type, "OPEN_POSITION")

    def test_top3_liquidity_model_allows_sized_entry(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "yes_depth_top3": "100",
                "no_depth_top3": "100",
                "yes_bid_depth_top3": "100",
                "yes_ask_depth_top3": "100",
                "no_bid_depth_top3": "100",
                "no_ask_depth_top3": "100",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]
        result, _ = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            liquidity_model="top3_ask",
            max_depth_fraction=0.25,
        )
        self.assertEqual(result.positions_opened, 1)
        self.assertEqual(result.liquidity_skips, 0)
        self.assertEqual(result.partial_entries, 0)

    def test_depth_utilization_slippage_worsens_entry_price(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "yes_ask_depth_top3": "24",
                "no_ask_depth_top3": "24",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            liquidity_model="top3_ask",
            max_depth_fraction=0.25,
            slippage_model="depth_utilization",
            max_slippage_bps=100,
        )

        self.assertEqual(result.positions_opened, 1)
        self.assertGreater(result.slippage_cost_total, 0)
        self.assertIn("entry_price=0.505000", events[0].detail)
        self.assertIn("depth_utilization=1.000000", events[0].detail)

    def test_depth_utilization_slippage_requires_depth_model(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]

        with self.assertRaisesRegex(ValueError, "requires top3_ask or top3_bid"):
            simulate_survival(
                rows,
                SyntheticEdgeForecastProvider(edge=0.12),
                initial_bankroll=50,
                slippage_model="depth_utilization",
            )

    def test_resolution_settles_open_position(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-02T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "1.00",
                "no_ask": "0.00",
                "yes_bid": "1.00",
                "no_bid": "0.00",
                "fair_yes": "1.00",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]
        resolutions = {
            "m1": Resolution(
                market_id="m1",
                resolved_at=datetime(2026, 1, 2, tzinfo=UTC),
                outcome=Side.YES,
            )
        }

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            resolutions=resolutions,
            initial_bankroll=50,
        )

        self.assertEqual(result.positions_opened, 1)
        self.assertEqual(result.positions_closed, 1)
        self.assertGreater(result.final_cash, 50)
        self.assertEqual([event.event_type for event in events], ["OPEN_POSITION", "SETTLE_POSITION"])

    def test_resolution_settles_even_without_new_market_row(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.60",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-02T00:00:00+00:00",
                "market_id": "m2",
                "question": "Will something else happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]
        resolutions = {
            "m1": Resolution(
                market_id="m1",
                resolved_at=datetime(2026, 1, 2, tzinfo=UTC),
                outcome=Side.YES,
            )
        }

        result, events = simulate_survival(rows, RecordedForecastProvider(), resolutions=resolutions, initial_bankroll=50)

        self.assertEqual(result.open_positions, 0)
        self.assertEqual(result.positions_closed, 1)
        self.assertIn("SETTLE_POSITION", [event.event_type for event in events])

    def test_edge_below_exit_policy_closes_position(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
        )

        self.assertEqual(result.positions_opened, 1)
        self.assertEqual(result.positions_closed, 1)
        self.assertEqual(result.open_positions, 0)
        self.assertEqual(events[-1].event_type, "EXIT_POSITION")

    def test_top3_bid_exit_model_skips_when_bid_depth_missing(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            exit_liquidity_model="top3_bid",
            max_exit_depth_fraction=0.25,
        )

        self.assertEqual(result.positions_opened, 1)
        self.assertEqual(result.positions_closed, 0)
        self.assertEqual(result.exit_liquidity_skips, 1)
        self.assertEqual(result.open_positions, 1)
        self.assertEqual(events[-1].event_type, "SKIP_EXIT_LIQUIDITY_DEPTH")

    def test_repeated_exit_liquidity_skips_track_current_unfilled_notional_once(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "yes_bid_depth_top3": "0",
                "no_bid_depth_top3": "0",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "yes_bid_depth_top3": "0",
                "no_bid_depth_top3": "0",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:20:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "yes_bid_depth_top3": "0",
                "no_bid_depth_top3": "0",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            exit_liquidity_model="top3_bid",
            max_exit_depth_fraction=0.25,
        )

        self.assertEqual([event.event_type for event in events].count("SKIP_EXIT_LIQUIDITY_DEPTH"), 2)
        self.assertEqual(result.exit_liquidity_skips, 1)
        self.assertAlmostEqual(result.unfilled_exit_notional, 2.94)

    def test_exit_liquidity_skip_counts_again_after_exit_signal_clears(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "yes_bid_depth_top3": "100",
                "no_bid_depth_top3": "100",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "yes_bid_depth_top3": "0",
                "no_bid_depth_top3": "100",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:20:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.80",
                "yes_bid_depth_top3": "0",
                "no_bid_depth_top3": "100",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:30:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "yes_bid_depth_top3": "0",
                "no_bid_depth_top3": "100",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, events = simulate_survival(
            rows,
            RecordedForecastProvider(),
            initial_bankroll=50,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            exit_liquidity_model="top3_bid",
            max_exit_depth_fraction=0.25,
        )

        self.assertEqual(result.exit_liquidity_skips, 2)
        self.assertEqual([event.event_type for event in events].count("SKIP_EXIT_LIQUIDITY_DEPTH"), 2)

    def test_settlement_clears_prior_unfilled_exit_notional(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "yes_bid_depth_top3": "0",
                "no_bid_depth_top3": "0",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "yes_bid_depth_top3": "0",
                "no_bid_depth_top3": "0",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-02T00:00:00+00:00",
                "market_id": "m2",
                "question": "Will something else happen?",
                "yes_ask": "0.95",
                "no_ask": "0.95",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]
        resolutions = {
            "m1": Resolution(
                market_id="m1",
                resolved_at=datetime(2026, 1, 2, tzinfo=UTC),
                outcome=Side.YES,
            )
        }

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            resolutions=resolutions,
            initial_bankroll=50,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            exit_liquidity_model="top3_bid",
            max_exit_depth_fraction=0.25,
        )

        self.assertIn("SKIP_EXIT_LIQUIDITY_DEPTH", [event.event_type for event in events])
        self.assertIn("SETTLE_POSITION", [event.event_type for event in events])
        self.assertEqual(result.open_positions, 0)
        self.assertEqual(result.unfilled_exit_notional, 0.0)

    def test_exit_notional_clears_when_exit_signal_disappears(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "yes_bid_depth_top3": "0",
                "no_bid_depth_top3": "0",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "yes_bid_depth_top3": "0",
                "no_bid_depth_top3": "0",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:20:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.70",
                "yes_bid_depth_top3": "0",
                "no_bid_depth_top3": "0",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]
        result, events = simulate_survival(
            rows,
            RecordedForecastProvider(),
            initial_bankroll=50,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            exit_liquidity_model="top3_bid",
            max_exit_depth_fraction=0.25,
        )
        self.assertIn("SKIP_EXIT_LIQUIDITY_DEPTH", [event.event_type for event in events])
        self.assertEqual(result.open_positions, 1)
        self.assertEqual(result.unfilled_exit_notional, 0.0)

    def test_top3_bid_exit_model_partially_exits_when_depth_limited(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "yes_bid_depth_top3": "100",
                "no_bid_depth_top3": "100",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "yes_bid_depth_top3": "8",
                "no_bid_depth_top3": "100",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            exit_liquidity_model="top3_bid",
            max_exit_depth_fraction=0.25,
        )

        self.assertEqual(result.positions_opened, 1)
        self.assertEqual(result.positions_closed, 0)
        self.assertEqual(result.partial_exits, 1)
        self.assertEqual(result.open_positions, 1)
        self.assertAlmostEqual(result.realized_pnl, -0.02)
        self.assertEqual(events[-1].event_type, "PARTIAL_EXIT_POSITION")

    def test_top3_bid_exit_model_fully_exits_when_depth_sufficient(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "yes_bid_depth_top3": "100",
                "no_bid_depth_top3": "100",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "yes_bid_depth_top3": "100",
                "no_bid_depth_top3": "100",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            exit_liquidity_model="top3_bid",
            max_exit_depth_fraction=0.25,
        )

        self.assertEqual(result.positions_opened, 1)
        self.assertEqual(result.positions_closed, 1)
        self.assertEqual(result.partial_exits, 0)
        self.assertEqual(result.open_positions, 0)
        self.assertEqual(events[-1].event_type, "EXIT_POSITION")

    def test_exit_immediately_checks_death_threshold(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.50",
                "no_bid": "0.50",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.40",
                "no_bid": "0.50",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            death_threshold=49.5,
        )

        self.assertEqual(result.state, "DEAD")
        self.assertEqual(result.death_reason, "equity_below_death_threshold")
        self.assertEqual(events[-1].event_type, "DEAD")

    def test_depth_utilization_slippage_worsens_exit_bid(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.50",
                "no_bid": "0.50",
                "fair_yes": "0.50",
                "yes_bid_depth_top3": "100",
                "no_bid_depth_top3": "100",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.50",
                "no_bid": "0.50",
                "fair_yes": "0.50",
                "yes_bid_depth_top3": "6",
                "no_bid_depth_top3": "100",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            exit_liquidity_model="top3_bid",
            max_exit_depth_fraction=1.0,
            slippage_model="depth_utilization",
            max_slippage_bps=100,
        )

        self.assertEqual(result.positions_closed, 1)
        self.assertAlmostEqual(result.realized_pnl, -0.03)
        self.assertAlmostEqual(result.slippage_cost_total, 0.03)
        self.assertIn("exec_bid=0.495000", events[-1].detail)

    def test_zero_spread_exit_does_not_create_spread_loss(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.50",
                "no_bid": "0.50",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.50",
                "no_bid": "0.50",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, _ = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
        )

        self.assertEqual(result.positions_opened, 1)
        self.assertEqual(result.positions_closed, 1)
        self.assertAlmostEqual(result.realized_pnl, 0.0)
        self.assertAlmostEqual(result.final_equity, 50.0)

    def test_agent_dies_when_forecast_cost_exhausts_bankroll(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]
        result, events = simulate_survival(rows, RecordedForecastProvider(cost_per_forecast=51), initial_bankroll=50)
        self.assertEqual(result.state, "DEAD")
        self.assertEqual(result.final_cash, 0)
        self.assertEqual(result.forecast_cost_total, 50)
        self.assertEqual(result.death_reason, "cash_depleted_by_forecast_cost")
        self.assertEqual(result.max_drawdown, 1.0)
        self.assertEqual(events[0].event_type, "DEAD")

    def test_equal_forecast_cost_is_paid_then_threshold_death_applies(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]
        result, _ = simulate_survival(rows, RecordedForecastProvider(cost_per_forecast=50), initial_bankroll=50)
        self.assertEqual(result.state, "DEAD")
        self.assertEqual(result.final_cash, 0)
        self.assertEqual(result.forecast_cost_total, 50)
        self.assertEqual(result.death_reason, "equity_below_death_threshold")

    def test_actionable_forecast_policy_skips_cost_when_max_positions_full(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m2",
                "question": "Will another thing happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12, cost_per_forecast=5),
            initial_bankroll=50,
            max_positions=1,
            forecast_call_policy="actionable",
        )

        self.assertEqual(result.forecast_calls, 1)
        self.assertEqual(result.forecast_cost_total, 5)
        self.assertEqual(result.positions_opened, 1)
        self.assertEqual(events[-1].event_type, "SKIP_FORECAST_MAX_POSITIONS")

    def test_actionable_forecast_policy_skips_cost_for_held_market_without_exit_policy(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12, cost_per_forecast=5),
            initial_bankroll=50,
            forecast_call_policy="actionable",
        )

        self.assertEqual(result.forecast_calls, 1)
        self.assertEqual(result.forecast_cost_total, 5)
        self.assertEqual(result.positions_opened, 1)
        self.assertEqual(events[-1].event_type, "SKIP_FORECAST_HELD_NO_EXIT")

    def test_actionable_forecast_policy_checks_death_when_skipping_max_positions(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.00",
                "no_bid": "0.00",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m2",
                "question": "Will another thing happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            max_positions=1,
            death_threshold=47.5,
            forecast_call_policy="actionable",
        )

        self.assertEqual(result.state, "DEAD")
        self.assertEqual(result.death_reason, "equity_below_death_threshold")
        self.assertEqual(events[-1].event_type, "DEAD")

    def test_default_forecast_policy_keeps_existing_cost_behavior(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m2",
                "question": "Will another thing happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, _ = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12, cost_per_forecast=5),
            initial_bankroll=50,
            max_positions=1,
        )

        self.assertEqual(result.forecast_calls, 2)
        self.assertEqual(result.forecast_cost_total, 10)

    def test_history_first_timestamp_order_processes_existing_market_before_new_entry(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m2",
                "question": "Will held market happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will new market happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m2",
                "question": "Will held market happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        sequential_result, sequential_events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            max_positions=1,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
        )
        history_first_result, history_first_events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            max_positions=1,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            timestamp_order_policy="history_first",
        )

        self.assertEqual(sequential_result.positions_opened, 1)
        self.assertIn("SKIP_MAX_POSITIONS", [event.event_type for event in sequential_events])
        self.assertEqual(history_first_result.positions_opened, 2)
        self.assertEqual(history_first_result.positions_closed, 1)
        self.assertEqual(history_first_events[-1].event_type, "OPEN_POSITION")

    def test_position_first_timestamp_order_handles_seen_market_exit_before_seen_entry(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will seen unheld market happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m2",
                "question": "Will held market happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will seen unheld market happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m2",
                "question": "Will held market happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        history_first_result, history_first_events = simulate_survival(
            rows,
            RecordedForecastProvider(),
            initial_bankroll=50,
            max_positions=1,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            timestamp_order_policy="history_first",
        )
        position_first_result, position_first_events = simulate_survival(
            rows,
            RecordedForecastProvider(),
            initial_bankroll=50,
            max_positions=1,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            timestamp_order_policy="position_first",
        )

        self.assertEqual(history_first_result.positions_opened, 1)
        self.assertIn("SKIP_MAX_POSITIONS", [event.event_type for event in history_first_events])
        self.assertEqual(position_first_result.positions_opened, 2)
        self.assertEqual(position_first_result.positions_closed, 1)
        self.assertEqual(position_first_events[-1].event_type, "OPEN_POSITION")

    def test_position_first_premark_updates_batch_quotes_before_exit_death_check(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will first held market happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.50",
                "no_bid": "0.50",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m2",
                "question": "Will second held market happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.50",
                "no_bid": "0.50",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will first held market happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.50",
                "no_bid": "0.50",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m2",
                "question": "Will second held market happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.50",
                "no_bid": "0.50",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            max_positions=2,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            death_threshold=47.5,
            timestamp_order_policy="position_first",
        )

        self.assertEqual(result.state, "ALIVE")
        self.assertGreaterEqual(result.positions_closed, 1)
        self.assertNotEqual(events[-1].event_type, "DEAD")

    def test_equity_threshold_death_uses_drawdown_reason(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]
        result, _ = simulate_survival(rows, RecordedForecastProvider(), initial_bankroll=50, death_threshold=50)
        self.assertEqual(result.state, "DEAD")
        self.assertEqual(result.death_reason, "equity_below_death_threshold")

    def test_empty_quote_fields_do_not_crash(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "",
                "no_ask": "",
                "yes_bid": "",
                "no_bid": "",
                "fair_yes": "0.50",
                "liquidity": "",
                "volume_24h": "",
            }
        ]
        result, events = simulate_survival(rows, RecordedForecastProvider(), initial_bankroll=50)
        self.assertEqual(result.state, "ALIVE")
        self.assertEqual(events, [])

    def test_missing_bid_policy_zero_can_trigger_threshold_death(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "",
                "no_bid": "",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, _ = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            death_threshold=47.1,
        )

        self.assertEqual(result.state, "DEAD")
        self.assertEqual(result.death_reason, "equity_below_death_threshold")

    def test_missing_bid_policy_last_valid_bid_avoids_false_threshold_death(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "",
                "no_bid": "",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, _ = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            death_threshold=47.1,
            missing_quote_policy="last_valid_bid",
        )

        self.assertEqual(result.state, "ALIVE")
        self.assertGreater(result.final_equity, 47.1)

    def test_missing_bid_policy_last_valid_bid_applies_to_exit_execution(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "yes_bid_depth_top3": "100",
                "no_bid_depth_top3": "100",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-01T00:10:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "",
                "no_bid": "",
                "yes_bid_depth_top3": "100",
                "no_bid_depth_top3": "100",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            initial_bankroll=50,
            exit_policy="edge_below",
            exit_edge_threshold=0.20,
            exit_liquidity_model="top3_bid",
            max_exit_depth_fraction=1.0,
            missing_quote_policy="last_valid_bid",
        )

        self.assertEqual(result.positions_closed, 1)
        self.assertAlmostEqual(result.realized_pnl, -0.06)
        self.assertIn("bid=0.490000", events[-1].detail)

    def test_missing_bid_policy_last_valid_bid_rejects_exit_without_depth_model(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            }
        ]

        with self.assertRaisesRegex(ValueError, "last_valid_bid exits require top3_bid"):
            simulate_survival(
                rows,
                SyntheticEdgeForecastProvider(edge=0.12),
                initial_bankroll=50,
                exit_policy="edge_below",
                missing_quote_policy="last_valid_bid",
            )

    def test_unknown_resolution_outcome_refunds_cost(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.60",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-02T00:00:00+00:00",
                "market_id": "m2",
                "question": "Will something else happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.49",
                "no_bid": "0.49",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]
        resolutions = {"m1": Resolution(market_id="m1", resolved_at=datetime(2026, 1, 2), outcome=None)}

        result, _ = simulate_survival(rows, RecordedForecastProvider(), resolutions=resolutions, initial_bankroll=50)

        self.assertEqual(result.positions_closed, 1)
        self.assertAlmostEqual(result.realized_pnl, 0.0)

    def test_settlement_immediately_checks_death_threshold(self) -> None:
        rows = [
            {
                "logged_at": "2026-01-01T00:00:00+00:00",
                "market_id": "m1",
                "question": "Will it happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.50",
                "no_bid": "0.50",
                "fair_yes": "0.62",
                "liquidity": "1000",
                "volume_24h": "100",
            },
            {
                "logged_at": "2026-01-02T00:00:00+00:00",
                "market_id": "m2",
                "question": "Will something else happen?",
                "yes_ask": "0.50",
                "no_ask": "0.50",
                "yes_bid": "0.50",
                "no_bid": "0.50",
                "fair_yes": "0.50",
                "liquidity": "1000",
                "volume_24h": "100",
            },
        ]
        resolutions = {
            "m1": Resolution(
                market_id="m1",
                resolved_at=datetime(2026, 1, 2, tzinfo=UTC),
                outcome=Side.NO,
            )
        }

        result, events = simulate_survival(
            rows,
            SyntheticEdgeForecastProvider(edge=0.12),
            resolutions=resolutions,
            initial_bankroll=50,
            death_threshold=47.5,
        )

        self.assertEqual(result.state, "DEAD")
        self.assertEqual(result.death_reason, "equity_below_death_threshold")
        self.assertEqual(events[-1].event_type, "DEAD")

    def test_loads_only_timestamped_signal_files(self) -> None:
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            write_rows(
                directory / "paper_signals_20260101T000000Z.csv",
                [
                    {
                        "logged_at": "2026-01-01T00:00:00+00:00",
                        "market_id": "m1",
                        "question": "Will it happen?",
                        "yes_ask": "0.50",
                        "no_ask": "0.50",
                        "yes_bid": "0.49",
                        "no_bid": "0.49",
                        "fair_yes": "0.50",
                        "liquidity": "1000",
                        "volume_24h": "100",
                    }
                ],
            )
            write_rows(directory / "latest_paper_signals.csv", [])
            self.assertEqual(len(load_paper_rows(directory)), 1)

    def test_load_paper_rows_sorts_by_actual_timestamp_not_string(self) -> None:
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            write_rows(
                directory / "paper_signals_20260101T000000Z.csv",
                [
                    {
                        "logged_at": "2026-01-01T09:00:00+09:00",
                        "market_id": "late",
                        "question": "Late string first?",
                        "yes_ask": "0.50",
                        "no_ask": "0.50",
                        "yes_bid": "0.49",
                        "no_bid": "0.49",
                        "fair_yes": "0.50",
                        "liquidity": "1000",
                        "volume_24h": "100",
                    },
                    {
                        "logged_at": "2026-01-01T00:30:00Z",
                        "market_id": "later",
                        "question": "Actually later",
                        "yes_ask": "0.50",
                        "no_ask": "0.50",
                        "yes_bid": "0.49",
                        "no_bid": "0.49",
                        "fair_yes": "0.50",
                        "liquidity": "1000",
                        "volume_24h": "100",
                    },
                ],
            )

            rows = load_paper_rows(directory)
            self.assertEqual([row["market_id"] for row in rows], ["late", "later"])


if __name__ == "__main__":
    unittest.main()
