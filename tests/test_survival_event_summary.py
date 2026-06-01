import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from polymarket_backtest.survival_event_summary import summarize_events, write_outputs


class SurvivalEventSummaryTest(unittest.TestCase):
    def test_summarize_events_counts_open_and_skip_events(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["timestamp", "event_type", "market_id", "side", "cash", "equity", "detail"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "event_type": "OPEN_POSITION",
                        "market_id": "m1",
                        "side": "YES",
                        "cash": "47",
                        "equity": "49.5",
                        "detail": "edge=0.120000;fraction=0.060000;cost=3.000000;quoted_price=0.400000;entry_price=0.400000;slippage_cost=0.000000;",
                    }
                )
                writer.writerow(
                    {
                        "timestamp": "2026-01-01T00:01:00+00:00",
                        "event_type": "SKIP_EXISTING_POSITION",
                        "market_id": "m1",
                        "side": "YES",
                        "cash": "47",
                        "equity": "49.0",
                        "detail": "",
                    }
                )

            summary, open_events = summarize_events(path)

        self.assertEqual(summary.total_events, 2)
        self.assertEqual(summary.positions_opened, 1)
        self.assertEqual(summary.positions_closed_events, 0)
        self.assertEqual(summary.skip_existing_position_events, 1)
        self.assertEqual(summary.unique_open_markets, 1)
        self.assertEqual(summary.reopened_markets, 0)
        self.assertEqual(summary.repeated_open_events, 0)
        self.assertEqual(summary.open_notional, 3.0)
        self.assertEqual(summary.min_equity, 49.0)
        self.assertAlmostEqual(summary.open_notional_to_min_equity, 3.0 / 49.0)
        self.assertEqual(open_events[0].edge, 0.12)

    def test_write_outputs_creates_markdown_csv_and_json(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.csv"
            events.write_text(
                "timestamp,event_type,market_id,side,cash,equity,detail\n"
                "2026-01-01T00:00:00+00:00,OPEN_POSITION,m1,NO,47,49,edge=0.2;cost=3;entry_price=0.5;\n"
            )
            summary, open_events = summarize_events(events)

            write_outputs(summary, open_events, root / "summary.json", root / "opens.csv", root / "summary.md")

            self.assertTrue((root / "summary.json").exists())
            self.assertTrue((root / "opens.csv").exists())
            content = (root / "summary.md").read_text()
            self.assertIn("Survival Event Summary", content)
            self.assertIn("m1", content)

    def test_exit_position_counts_as_closed_event(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.csv"
            events.write_text(
                "timestamp,event_type,market_id,side,cash,equity,detail\n"
                "2026-01-01T00:00:00+00:00,OPEN_POSITION,m1,YES,47,49,edge=0.2;cost=3;entry_price=0.5;\n"
                "2026-01-01T00:01:00+00:00,EXIT_POSITION,m1,YES,49,49,bid=0.4;pnl=-1;\n"
            )

            summary, _ = summarize_events(events)

            self.assertEqual(summary.positions_closed_events, 1)

    def test_repeated_open_events_count_reentries(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.csv"
            events.write_text(
                "timestamp,event_type,market_id,side,cash,equity,detail\n"
                "2026-01-01T00:00:00+00:00,OPEN_POSITION,m1,YES,47,49,edge=0.2;cost=3;entry_price=0.5;\n"
                "2026-01-01T00:01:00+00:00,EXIT_POSITION,m1,YES,49,49,bid=0.4;pnl=-1;\n"
                "2026-01-01T00:02:00+00:00,OPEN_POSITION,m1,YES,46,48,edge=0.2;cost=3;entry_price=0.5;\n"
            )

            summary, _ = summarize_events(events)

            self.assertEqual(summary.unique_open_markets, 1)
            self.assertEqual(summary.reopened_markets, 1)
            self.assertEqual(summary.repeated_open_events, 1)


if __name__ == "__main__":
    unittest.main()
