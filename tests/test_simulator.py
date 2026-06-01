import unittest
from datetime import UTC, datetime

from polymarket_backtest.models import MarketSnapshot, Side
from polymarket_backtest.simulator import run_backtest


class SimulatorTest(unittest.TestCase):
    def test_forced_signal_opens_and_settles_yes_position(self) -> None:
        snapshots = [
            MarketSnapshot(
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                market_id="m1",
                question="Will it happen?",
                yes_price=0.50,
                no_price=0.50,
                fair_yes=0.62,
            ),
            MarketSnapshot(
                timestamp=datetime(2026, 1, 2, tzinfo=UTC),
                market_id="m1",
                question="Will it happen?",
                yes_price=1.00,
                no_price=0.00,
                fair_yes=1.00,
                resolved_outcome=Side.YES,
            ),
        ]

        result = run_backtest(snapshots, initial_bankroll=100.0)

        self.assertEqual(len(result.closed_trades), 1)
        self.assertGreater(result.closed_trades[0].pnl, 0)
        self.assertGreater(result.final_equity, 100.0)


if __name__ == "__main__":
    unittest.main()
