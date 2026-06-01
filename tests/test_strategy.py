import unittest
from datetime import UTC, datetime

from polymarket_backtest.models import MarketSnapshot, Side
from polymarket_backtest.strategy import build_signal, kelly_fraction


class StrategyTest(unittest.TestCase):
    def test_kelly_fraction_caps_at_six_percent(self) -> None:
        self.assertEqual(kelly_fraction(0.70, 0.50), 0.06)

    def test_builds_yes_signal_for_positive_edge(self) -> None:
        snapshot = MarketSnapshot(
            timestamp=datetime.now(UTC),
            market_id="m1",
            question="Will it happen?",
            yes_price=0.50,
            no_price=0.50,
            fair_yes=0.61,
        )
        signal = build_signal(snapshot)
        self.assertIsNotNone(signal)
        self.assertIs(signal.side, Side.YES)

    def test_builds_no_signal_for_negative_yes_edge(self) -> None:
        snapshot = MarketSnapshot(
            timestamp=datetime.now(UTC),
            market_id="m2",
            question="Will it happen?",
            yes_price=0.72,
            no_price=0.28,
            fair_yes=0.58,
        )
        signal = build_signal(snapshot)
        self.assertIsNotNone(signal)
        self.assertIs(signal.side, Side.NO)


if __name__ == "__main__":
    unittest.main()
