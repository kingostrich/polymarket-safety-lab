from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import unittest

from polymarket_backtest.paper_resolution_status import parse_market_status, write_outputs


class PaperResolutionStatusTest(unittest.TestCase):
    def test_parse_market_status_requires_closed_market(self) -> None:
        status = parse_market_status(
            "m1",
            {
                "question": "Q",
                "active": True,
                "closed": False,
                "archived": False,
                "acceptingOrders": True,
                "outcomePrices": '["0.0005","0.9995"]',
                "updatedAt": "2026-01-01T00:00:00Z",
            },
        )

        self.assertEqual(status.conservative_outcome, "NO")
        self.assertFalse(status.resolution_eligible)
        self.assertEqual(status.reason, "market_not_closed")

    def test_parse_market_status_accepts_closed_binary_outcome(self) -> None:
        status = parse_market_status(
            "m1",
            {
                "question": "Q",
                "active": False,
                "closed": True,
                "archived": False,
                "acceptingOrders": False,
                "outcomePrices": '["1","0"]',
                "closedTime": "2026-01-01T00:00:00Z",
            },
        )

        self.assertEqual(status.conservative_outcome, "YES")
        self.assertTrue(status.resolution_eligible)
        self.assertEqual(status.reason, "")

    def test_write_outputs_writes_only_eligible_resolutions(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            eligible = parse_market_status(
                "m1",
                {
                    "question": "Q",
                    "active": False,
                    "closed": True,
                    "archived": False,
                    "acceptingOrders": False,
                    "outcomePrices": '["0","1"]',
                    "closedTime": "2026-01-01T00:00:00Z",
                },
            )
            open_status = parse_market_status(
                "m2",
                {
                    "question": "Q2",
                    "active": True,
                    "closed": False,
                    "archived": False,
                    "acceptingOrders": True,
                    "outcomePrices": '["1","0"]',
                    "updatedAt": "2026-01-01T00:00:00Z",
                },
            )

            manifest = write_outputs([eligible, open_status], root)

            self.assertEqual(manifest["markets"], 2)
            self.assertEqual(manifest["resolution_eligible"], 1)
            self.assertEqual(manifest["near_binary_but_open"], 1)
            self.assertIn("YES>=0.999", manifest["outcome_threshold_note"])
            with (root / "resolutions.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows, [{"market_id": "m1", "resolved_at": "2026-01-01T00:00:00Z", "resolved_outcome": "NO"}])


if __name__ == "__main__":
    unittest.main()
